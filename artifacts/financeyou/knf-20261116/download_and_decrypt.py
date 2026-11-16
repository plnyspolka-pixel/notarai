#!/usr/bin/env python3
"""Pobierz publicznie zaszyfrowany zbiór Finance You KNF i odszyfruj lokalnie.

Zależność: pip install cryptography
Klucz 64 cyfr hex tylko przez FINYOU_KNF_KEY_HEX lub interaktywnie przez getpass.
Bez zgody na mailing; żadne e-maile nie są nigdzie wysyłane.
"""
from __future__ import annotations
import argparse
import getpass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import sys
import urllib.request
import zipfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DEFAULT_MANIFEST = "https://raw.githubusercontent.com/plnyspolka-pixel/notarai/assets/financeyou-knf-encrypted-20261116/artifacts/financeyou/knf-20261116/manifest.json"
MAX_PART = 4_000_000
MAX_PAYLOAD = 20_000_000

def read_url(url: str, limit: int) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS supported")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "finyou-knf-asset/1.0"}), timeout=40) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Exceeded download size limit")
    return data

def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default=DEFAULT_MANIFEST, help="Public manifest URL or local JSON path")
    p.add_argument("--out", default="data-import/financial-intermediaries", help="Private output directory, gitignored")
    args = p.parse_args()
    if args.manifest.startswith("https://"):
        m = json.loads(read_url(args.manifest, 100_000))
    else:
        m = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if m["schema_version"] != 1 or m["encryption"] != "AES-256-GCM":
        raise ValueError("Unsupported encrypted manifest")
    assembled = bytearray()
    for entry in sorted(m["parts"], key=lambda a: a["index"]):
        part = read_url(entry["url"], MAX_PART)
        if len(part) != entry["size"] or sha256(part) != entry["sha256"]:
            raise ValueError("Part integrity check failed: " + entry["file"])
        assembled.extend(part)
        if len(assembled) > MAX_PAYLOAD:
            raise ValueError("Encrypted payload too large")
    blob = bytes(assembled)
    if len(blob) != m["ciphertext_bytes"] or sha256(blob) != m["ciphertext_sha256"]:
        raise ValueError("Encrypted archive integrity check failed")
    key_hex = os.environ.get("FINYOU_KNF_KEY_HEX") or getpass.getpass("Klucz AES-256 (64 znaki HEX): ")
    try:
        key = bytes.fromhex(key_hex.strip())
    except ValueError as e:
        raise ValueError("Klucz nie jest poprawnym HEX") from e
    if len(key) != 32:
        raise ValueError("AES-256 requires 32-byte key")
    if blob[:7] != b"FYKNF01":
        raise ValueError("Unknown ciphertext format")
    raw = AESGCM(key).decrypt(blob[7:19], blob[19:], blob[:7])
    if sha256(raw) != m["decoded_zip_sha256"]:
        raise ValueError("Decrypted ZIP checksum mismatch")
    dest = Path(args.out).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(dest, 0o700)
    except OSError:
        pass
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for member in zf.infolist():
            parts = PurePosixPath(member.filename).parts
            if not parts or any(part in ("..", "") for part in parts) or member.filename.startswith("/"):
                raise ValueError("Unsafe member path")
            if member.is_dir():
                (dest / member.filename).mkdir(parents=True, exist_ok=True)
                continue
            output_path = (dest / member.filename).resolve()
            if not output_path.is_relative_to(dest):
                raise ValueError("ZIP path outside output directory")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as inp, output_path.open("wb") as out:
                import shutil
                shutil.copyfileobj(inp, out)
            try:
                os.chmod(output_path, 0o600)
            except OSError:
                pass
    print(f"OK: archiwum zweryfikowane, pliki dostępne lokalnie w {dest}")
    print("Uwaga: dane zawierają hipotezy adresów; nie wysyłaj mailingu bez weryfikacji.")

if __name__ == "__main__":
    main()
