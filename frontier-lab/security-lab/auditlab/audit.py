"""Educational audit-chain demo. NOT a production append-only or qualified service."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def canonical(item: dict) -> bytes:
    return json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(item: dict) -> str:
    return hashlib.sha384(canonical(item)).hexdigest()


def verify(path: Path) -> dict:
    prev = "0" * 96
    count = 0
    if not path.exists():
        return {"count": 0, "head": prev}
    with path.open("rb") as f:
        for line in f:
            count += 1
            try:
                raw = json.loads(line)
            except Exception as exc:
                raise ValueError(f"Invalid JSON at entry {count}") from exc
            if not isinstance(raw, dict):
                raise ValueError(f"Not a JSON object at entry {count}")
            claimed = raw.get("hash")
            if raw.get("seq") != count or raw.get("prev_hash") != prev:
                raise ValueError(f"Broken sequence/link at entry {count}")
            actual = digest({k: v for k, v in raw.items() if k != "hash"})
            if claimed != actual:
                raise ValueError(f"Hash mismatch at entry {count}")
            prev = actual
    return {"count": count, "head": prev}


def append(path: Path, event: dict) -> dict:
    # Single-writer demo: no concurrency control; do not use this on production traffic.
    if not isinstance(event, dict) or not event.get("type") or not event.get("subject_id"):
        raise ValueError("event requires type and subject_id")
    if any(k in event for k in ("hash", "prev_hash", "seq", "at")):
        raise ValueError("event contains reserved fields")
    previous = verify(path)
    row = {
        "seq": previous["count"] + 1,
        "prev_hash": previous["head"],
        "at": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    row["hash"] = digest(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as f:
        f.write(canonical(row) + b"\n")
        f.flush()
        os.fsync(f.fileno())
    return row


def new_key(key_path: Path, pub_path: Path):
    if key_path.exists() or pub_path.exists():
        raise FileExistsError("Refusing to overwrite signing keys")
    private = Ed25519PrivateKey.generate()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    with key_path.open("xb") as f:
        os.chmod(key_path, 0o600)
        f.write(private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
    pub_path.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))


def make_checkpoint(log_path: Path, key_path: Path, output: Path) -> dict:
    private = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("Expected an Ed25519 private key")
    state = verify(log_path)
    statement = {"schema": "auditlab-checkpoint-v1", "count": state["count"], "head": state["head"]}
    receipt = {"statement": statement, "signature_hex": private.sign(canonical(statement)).hex()}
    output.write_bytes(canonical(receipt) + b"\n")
    return receipt


def verify_checkpoint(log_path: Path, pub_path: Path, receipt_path: Path) -> bool:
    public = serialization.load_pem_public_key(pub_path.read_bytes())
    if not isinstance(public, Ed25519PublicKey):
        raise ValueError("Expected an Ed25519 public key")
    receipt = json.loads(receipt_path.read_bytes())
    public.verify(bytes.fromhex(receipt["signature_hex"]), canonical(receipt["statement"]))
    state = verify(log_path)
    statement = receipt["statement"]
    if statement != {"schema": "auditlab-checkpoint-v1", **state}:
        raise ValueError("Valid signature, but checkpoint differs from ledger head")
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("append")
    a.add_argument("log"); a.add_argument("type"); a.add_argument("subject_id")
    a.add_argument("--actor", default="demo-user")
    v = sub.add_parser("verify"); v.add_argument("log")
    k = sub.add_parser("keygen"); k.add_argument("private"); k.add_argument("public")
    c = sub.add_parser("checkpoint"); c.add_argument("log"); c.add_argument("private"); c.add_argument("output")
    r = sub.add_parser("verify-checkpoint"); r.add_argument("log"); r.add_argument("public"); r.add_argument("receipt")
    args = p.parse_args()
    if args.command == "append":
        out = append(Path(args.log), {"type": args.type, "subject_id": args.subject_id, "actor": args.actor})
    elif args.command == "verify":
        out = verify(Path(args.log))
    elif args.command == "keygen":
        new_key(Path(args.private), Path(args.public)); out = {"created": True}
    elif args.command == "checkpoint":
        out = make_checkpoint(Path(args.log), Path(args.private), Path(args.output))
    else:
        out = {"valid": verify_checkpoint(Path(args.log), Path(args.public), Path(args.receipt))}
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
