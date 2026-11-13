"""NotarAI Sealed v2 — office-held X25519 keys, per-document random AES key.

Runs OFFLINE on the notary's own computer. The server receives only the
ciphertext envelope, recipient PUBLIC keys and ephemeral PUBLIC keys.

This is a standalone reference implementation, NOT an audited QTSP,
hardware-backed key store, qualified seal or signed Windows distribution.
"""
from __future__ import annotations
import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SCHEMA = "notarai.sealed.v2"
KEY_SCHEMA = "notarai.office-key.v1"
MAX_BYTES = 4 * 1024 * 1024
MAX_RECIPIENTS = 16
RE_B64 = re.compile(r"^[A-Za-z0-9_-]+$")
PUB_FMT = serialization.PublicFormat.Raw


def enc(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def dec(value: str, length: int | None = None) -> bytes:
    if not isinstance(value, str) or not RE_B64.fullmatch(value):
        raise ValueError("Invalid base64url")
    data = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if enc(data) != value or (length is not None and len(data) != length):
        raise ValueError("Invalid or noncanonical base64url")
    return data


def check_tenant(tenant: str) -> str:
    if not isinstance(tenant, str) or not 1 <= len(tenant) <= 120 or any(ord(c) < 32 or ord(c) == 127 for c in tenant):
        raise ValueError("Invalid tenant")
    return tenant


def check_doc(doc: str) -> str:
    ident = uuid.UUID(doc)
    if str(ident) != doc or ident.version != 4:
        raise ValueError("Document reference must be canonical UUIDv4")
    return doc


def aad(tenant: str, doc: str) -> bytes:
    return (SCHEMA + "\x00" + check_tenant(tenant) + "\x00" + check_doc(doc)).encode("utf-8")


def key_id(public: bytes) -> str:
    if len(public) != 32:
        raise ValueError("X25519 public key must have 32 bytes")
    return hashlib.sha256(b"NOTARAI-SEAL-RECIPIENT-V1" + public).hexdigest()[:40]


def make_office_key(tenant: str, passphrase: str) -> tuple[dict, dict]:
    check_tenant(tenant)
    if not isinstance(passphrase, str) or not 20 <= len(passphrase) <= 1024:
        raise ValueError("Use a long recovery passphrase (20+ characters)")
    private = x25519.X25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, PUB_FMT)
    kid = key_id(public)
    pub = {"schema": KEY_SCHEMA, "tenantRef": tenant, "keyId": kid, "algorithm": "X25519", "publicKey": enc(public)}
    encrypted_pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(passphrase.encode("utf-8"))
    ).decode("ascii")
    keyfile = {"schema": KEY_SCHEMA, "tenantRef": tenant, "keyId": kid,
               "publicKey": enc(public), "privateKeyPem": encrypted_pem}
    return pub, keyfile


def load_office_private(keyfile: dict, passphrase: str) -> x25519.X25519PrivateKey:
    if keyfile.get("schema") != KEY_SCHEMA or keyfile.get("algorithm") is not None:
        raise ValueError("Incorrect office key format")
    check_tenant(keyfile["tenantRef"])
    expected_public = dec(keyfile["publicKey"], 32)
    if key_id(expected_public) != keyfile.get("keyId"):
        raise ValueError("Invalid office key identifier")
    private = serialization.load_pem_private_key(keyfile["privateKeyPem"].encode("ascii"),
                                                  password=passphrase.encode("utf-8"))
    if not isinstance(private, x25519.X25519PrivateKey):
        raise ValueError("Wrong private key algorithm")
    actual = private.public_key().public_bytes(serialization.Encoding.Raw, PUB_FMT)
    if actual != expected_public:
        raise ValueError("Private and public keys do not match")
    return private


def check_public(pub: dict, tenant: str) -> tuple[str, x25519.X25519PublicKey]:
    if pub.get("schema") != KEY_SCHEMA or pub.get("algorithm") != "X25519" or pub.get("tenantRef") != tenant:
        raise ValueError("Recipient belongs to another office or protocol")
    data = dec(pub["publicKey"], 32)
    kid = key_id(data)
    if pub.get("keyId") != kid:
        raise ValueError("Recipient key identifier mismatch")
    return kid, x25519.X25519PublicKey.from_public_bytes(data)


def wrap_dek(dek: bytes, recipient: dict, tenant: str, doc: str) -> dict:
    kid, public = check_public(recipient, tenant)
    eph = x25519.X25519PrivateKey.generate()
    eph_public = eph.public_key().public_bytes(serialization.Encoding.Raw, PUB_FMT)
    salt = os.urandom(32)
    nonce = os.urandom(12)
    associated = aad(tenant, doc) + b"\x00" + kid.encode("ascii")
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt,
               info=b"NotarAI-Sealed-v2-DEK-Wrap\x00" + associated).derive(eph.exchange(public))
    wrapped = AESGCM(key).encrypt(nonce, dek, associated)
    return {"keyId": kid, "ephemeralPublic": enc(eph_public),
            "salt": enc(salt), "nonce": enc(nonce), "wrappedKey": enc(wrapped)}


def unwrap_dek(envelope: dict, keyfile: dict, passphrase: str) -> bytes:
    tenant = envelope["tenantRef"]
    if keyfile.get("tenantRef") != tenant:
        raise ValueError("Office key does not belong to this office")
    private = load_office_private(keyfile, passphrase)
    kid = keyfile["keyId"]
    wraps = [r for r in envelope["recipients"] if r.get("keyId") == kid]
    if len(wraps) != 1:
        raise ValueError("Missing or ambiguous recipient key")
    wrap = wraps[0]
    eph = x25519.X25519PublicKey.from_public_bytes(dec(wrap["ephemeralPublic"],32))
    associated = aad(tenant, envelope["documentId"]) + b"\x00" + kid.encode("ascii")
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=dec(wrap["salt"],32),
               info=b"NotarAI-Sealed-v2-DEK-Wrap\x00" + associated).derive(private.exchange(eph))
    return AESGCM(key).decrypt(dec(wrap["nonce"],12), dec(wrap["wrappedKey"],48), associated)


def seal_bytes(plaintext: bytes, tenant: str, recipients: list[dict],
               doc: str | None = None) -> dict:
    if not isinstance(plaintext, bytes) or not 1 <= len(plaintext) <= MAX_BYTES:
        raise ValueError("Document outside prototype limit")
    if not 1 <= len(recipients) <= MAX_RECIPIENTS:
        raise ValueError("Provide 1-16 authorized office recipient public keys")
    doc = doc or str(uuid.uuid4())
    associated = aad(tenant, doc)
    ids = [check_public(p, tenant)[0] for p in recipients]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate recipient keys")
    dek = os.urandom(32)
    nonce = os.urandom(12)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, associated)
    return {
        "schema": SCHEMA, "documentId": doc, "tenantRef": tenant,
        "algorithm": "AES-256-GCM", "keyWrap": "X25519-HKDF-SHA256-AES256GCM",
        "nonce": enc(nonce), "ciphertext": enc(ciphertext),
        "recipients": [wrap_dek(dek, p, tenant, doc) for p in recipients]
    }


def open_envelope(envelope: dict, keyfile: dict, passphrase: str) -> bytes:
    if envelope.get("schema") != SCHEMA or envelope.get("algorithm") != "AES-256-GCM" or \
       envelope.get("keyWrap") != "X25519-HKDF-SHA256-AES256GCM":
        raise ValueError("Unsupported Sealed v2 format")
    if not 1 <= len(envelope["recipients"]) <= MAX_RECIPIENTS:
        raise ValueError("Invalid recipients")
    associated = aad(envelope["tenantRef"], envelope["documentId"])
    nonce=dec(envelope["nonce"],12)
    cipher=dec(envelope["ciphertext"])
    if not 17 <= len(cipher) <= MAX_BYTES+16:
        raise ValueError("Invalid ciphertext")
    dek = unwrap_dek(envelope,keyfile,passphrase)
    if len(dek) != 32: raise ValueError("Invalid content key")
    return AESGCM(dek).decrypt(nonce,cipher,associated)


def grant_recipient(envelope: dict, owner_key: dict, password: str, new_public: dict) -> dict:
    """Add authorized recipient without re-uploading or re-encrypting the content.
    NOTE: recipients cannot be cryptographically revoked without re-encrypting
    the content with a NEW DEK and redistributing it to retained recipients.
    """
    import copy
    doc, tenant = envelope["documentId"],envelope["tenantRef"]
    check_doc(doc)
    if envelope.get("schema") != SCHEMA: raise ValueError("Unsupported envelope")
    new_kid, _ = check_public(new_public,tenant)
    if any(r.get("keyId")==new_kid for r in envelope["recipients"]):
        raise ValueError("Recipient already authorized")
    if len(envelope["recipients"]) >= MAX_RECIPIENTS: raise ValueError("Recipient quota")
    # Authenticate original ciphertext with owner before changing recipient metadata.
    open_envelope(envelope,owner_key,password)
    dek=unwrap_dek(envelope,owner_key,password)
    new_envelope=copy.deepcopy(envelope)
    new_envelope["recipients"].append(wrap_dek(dek,new_public,tenant,doc))
    return new_envelope


def rotate_recipients(envelope: dict, owner_key: dict, password: str,
                      remaining_public_keys: list[dict]) -> dict:
    """Client-side revocation: NEW file UUID, NEW random DEK and fresh ciphertext.

    The removed recipient cannot open the NEW encrypted version. Previously
    downloaded copies or cached old DEKs cannot be revoked retroactively.
    """
    plaintext = open_envelope(envelope, owner_key, password)
    return seal_bytes(plaintext, envelope["tenantRef"], remaining_public_keys)


def write_new(path: str, content: bytes, private: bool = False):
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    fd=os.open(path,flags,0o600 if private else 0o644)
    try:
        with os.fdopen(fd,"wb") as f: f.write(content)
    except BaseException:
        try: os.unlink(path)
        except OSError: pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Offline NotarAI Sealed v2, office-held keys")
    sub=parser.add_subparsers(dest="command",required=True)
    keygen=sub.add_parser("keygen")
    keygen.add_argument("--office",required=True)
    keygen.add_argument("--public-out",required=True)
    keygen.add_argument("--private-out",required=True)
    seal=sub.add_parser("encrypt")
    seal.add_argument("--office",required=True)
    seal.add_argument("--input",required=True)
    seal.add_argument("--output",required=True)
    seal.add_argument("--recipient",required=True,action="append")
    op=sub.add_parser("decrypt")
    op.add_argument("--office",required=True)
    op.add_argument("--input",required=True)
    op.add_argument("--output",required=True)
    op.add_argument("--private-key",required=True)
    grant=sub.add_parser("grant")
    grant.add_argument("--input",required=True)
    grant.add_argument("--output",required=True)
    grant.add_argument("--private-key",required=True)
    grant.add_argument("--new-recipient",required=True)
    grant.add_argument("--office",required=True)
    rotate=sub.add_parser("rotate")
    rotate.add_argument("--office",required=True)
    rotate.add_argument("--input",required=True)
    rotate.add_argument("--output",required=True)
    rotate.add_argument("--private-key",required=True)
    rotate.add_argument("--recipient",required=True,action="append",
                        help="Remaining, still-authorized recipient public key JSON")
    args=parser.parse_args(argv)
    try:
        if args.command=="keygen":
            if Path(args.public_out).exists() or Path(args.private_out).exists():
                raise ValueError("Refusing to overwrite office keys")
            password=getpass.getpass("New office recovery passphrase (20+ characters): ")
            pub, priv=make_office_key(args.office,password)
            write_new(args.private_out,json.dumps(priv,ensure_ascii=False).encode(),private=True)
            write_new(args.public_out,json.dumps(pub,ensure_ascii=False).encode())
        elif args.command=="encrypt":
            recipient_keys=[json.loads(Path(p).read_text("utf-8")) for p in args.recipient]
            result=seal_bytes(Path(args.input).read_bytes(),args.office,recipient_keys)
            write_new(args.output,json.dumps(result,separators=(",",":"),ensure_ascii=False).encode())
        elif args.command in ("decrypt","grant","rotate"):
            envelope=json.loads(Path(args.input).read_text("utf-8"))
            if envelope.get("tenantRef")!=args.office: raise ValueError("Wrong office")
            private=json.loads(Path(args.private_key).read_text("utf-8"))
            password=getpass.getpass("Office recovery passphrase: ")
            if args.command=="decrypt":
                result=open_envelope(envelope,private,password)
                write_new(args.output,result,private=True)
            elif args.command=="grant":
                pub=json.loads(Path(args.new_recipient).read_text("utf-8"))
                result=grant_recipient(envelope,private,password,pub)
                write_new(args.output,json.dumps(result,separators=(",",":"),ensure_ascii=False).encode())
            else:
                publics=[json.loads(Path(p).read_text("utf-8")) for p in args.recipient]
                result=rotate_recipients(envelope,private,password,publics)
                write_new(args.output,json.dumps(result,separators=(",",":"),ensure_ascii=False).encode())
        print("Success (offline). No network calls.")
        return 0
    except (ValueError,KeyError,InvalidTag,OSError,TypeError) as error:
        print("Operation failed: invalid key, document, authorization or destination",file=sys.stderr)
        return 1

if __name__=="__main__":
    sys.exit(main())
