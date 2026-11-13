"""NotarAI release signature tool — OFFLINE Ed25519 manifest signing.

No signing key is stored in GitHub. Offices must independently pin and
authenticate the release PUBLIC key, not download trust roots from the same
untrusted app hosting the executable. Authenticode is a separate requirement.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

SCHEMA="notarai.release.v1"

def stable_json(value) -> bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("utf-8")

def sha256(path:Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        while chunk:=stream.read(1024*1024):
            digest.update(chunk)
    return digest.hexdigest()

def manifest(files:list[Path]) -> dict:
    if not files or len(files)>50: raise ValueError("Expected 1-50 release files")
    seen=set()
    entries=[]
    for path in files:
        if not path.is_file() or path.name in (".","..") or "/" in path.name or "\\" in path.name:
            raise ValueError("Invalid release file path")
        if path.name in seen: raise ValueError("Duplicate release filename")
        seen.add(path.name)
        entries.append({"file":path.name,"sha256":sha256(path),"size":path.stat().st_size})
    return {"schema":SCHEMA,"files":sorted(entries,key=lambda entry:entry["file"])}

def keygen(password:str) -> tuple[bytes,bytes]:
    if len(password)<20:raise ValueError("Need 20+ character offline signing password")
    private=ed25519.Ed25519PrivateKey.generate()
    secret=private.private_bytes(
        serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(password.encode("utf-8")))
    public=private.public_key().public_bytes(
        serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    return secret,public

def sign(doc:dict,private_pem:bytes,password:str) -> bytes:
    if doc.get("schema")!=SCHEMA: raise ValueError("Manifest schema mismatch")
    private=serialization.load_pem_private_key(private_pem,password=password.encode("utf-8"))
    if not isinstance(private,ed25519.Ed25519PrivateKey):
        raise ValueError("Not an Ed25519 signing key")
    return private.sign(stable_json(doc))

def verify(doc:dict,signature:bytes,public_pem:bytes,base:Path) -> bool:
    """Verify signature AND every actual release file from independently pinned pubkey."""
    try:
        if doc.get("schema")!=SCHEMA: return False
        pub=serialization.load_pem_public_key(public_pem)
        if not isinstance(pub,ed25519.Ed25519PublicKey):return False
        pub.verify(signature,stable_json(doc))
        items=doc.get("files")
        if not isinstance(items,list) or not 1<=len(items)<=50:return False
        names=set()
        for entry in items:
            name=entry.get("file")
            if not isinstance(name,str) or name in (".","..") or name!=Path(name).name or "\\" in name:
                return False
            if name in names:return False
            names.add(name)
            path=base/name
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(base.resolve()):
                return False
            if path.stat().st_size!=entry.get("size") or sha256(path)!=entry.get("sha256"):
                return False
        return True
    except (InvalidSignature,ValueError,TypeError,KeyError,AttributeError,OSError):
        return False

def write_new(path:Path, data:bytes,private:bool=False):
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600 if private else 0o644)
    with os.fdopen(fd,"wb") as stream:stream.write(data)

def main(argv:list[str]|None=None):
    import getpass
    p=argparse.ArgumentParser(description="Verify or sign NotarAI Sealed release offline")
    sub=p.add_subparsers(dest="command",required=True)
    g=sub.add_parser("keygen")
    g.add_argument("--private-out",required=True)
    g.add_argument("--public-out",required=True)
    s=sub.add_parser("sign")
    s.add_argument("--private",required=True)
    s.add_argument("--manifest",required=True)
    s.add_argument("--signature-out",required=True)
    v=sub.add_parser("verify")
    v.add_argument("--trusted-public",required=True)
    v.add_argument("--manifest",required=True)
    v.add_argument("--signature",required=True)
    v.add_argument("--files-dir",required=True)
    args=p.parse_args(argv)
    try:
        if args.command=="keygen":
            password=getpass.getpass("Offline release-key passphrase: ")
            prv,pub=keygen(password)
            write_new(Path(args.private_out),prv,True)
            write_new(Path(args.public_out),pub)
            print("Offline signing key created; secure backup required.")
        elif args.command=="sign":
            doc=json.loads(Path(args.manifest).read_text("utf-8"))
            password=getpass.getpass("Release-key passphrase: ")
            signed=sign(doc,Path(args.private).read_bytes(),password)
            write_new(Path(args.signature_out),signed)
            print("Manifest signed offline.")
        else:
            doc=json.loads(Path(args.manifest).read_text("utf-8"))
            if not verify(doc,Path(args.signature).read_bytes(),
                          Path(args.trusted_public).read_bytes(),Path(args.files_dir)):
                raise ValueError("RELEASE_SIGNATURE_INVALID")
            print("RELEASE_SIGNATURE_VERIFIED: trusted key, manifest and file digests")
        return 0
    except (OSError,ValueError,InvalidSignature,TypeError,KeyError):
        print("Release verification or signing failed")
        return 1

if __name__=="__main__":
    raise SystemExit(main())
