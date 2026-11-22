"""Chromium E2E for a signed, standalone, network-disabled fictitious client.

Mandatory GitHub Actions Chromium smoke only; no real documents or AWS.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from playwright.sync_api import sync_playwright

from confidential.envelope import Envelope
from scripts.build_custodian_browser_client import build_custodian_client


def main():
    root = Path(__file__).resolve().parents[1]
    kms = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    der = kms.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pem = kms.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")
    pin = base64.b64encode(hashlib.sha256(der).digest()).decode("ascii")
    signer = ed25519.Ed25519PrivateKey.generate()
    private_pem = signer.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    with tempfile.TemporaryDirectory() as td:
        directory = Path(td) / "custodian"
        build_custodian_client(
            repository_root=root, output_dir=directory,
            tenant="pilot01", kms_arn="arn:aws:kms:eu-central-1:111122223333:key/fixture",
            kms_public_pem=pem, key_pin=pin,
            release_id="a" * 32, expires_at=2000000000,
            custodian_private_key_pem=private_pem,
        )
        forbidden = []
        sample = b"FICTIONAL LOCAL ENCRYPTION / NO NOTARIAL DATA"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            # Network access must remain unnecessary for the client to work.
            def network_block(route):
                forbidden.append(route.request.url)
                route.abort()
            context.route("http://**/*", network_block)
            context.route("https://**/*", network_block)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto((directory / "client.html").as_uri())
            page.locator("#caseId").fill("case01")
            page.locator("#objectId").fill("scan01")
            page.locator("#document").set_input_files({
                "name": "synthetic.txt", "mimeType": "text/plain", "buffer": sample,
            })
            with page.expect_download(timeout=20000) as info:
                page.locator("#encrypt").click()
            downloaded = info.value
            assert downloaded.suggested_filename == "notarai-scan01.encrypted.json"
            content = Path(downloaded.path()).read_bytes()
            assert not forbidden, "standalone client attempted external network access"
            assert not errors, "standalone client JavaScript failed"
            browser.close()
        assert sample not in content
        envelope = Envelope.parse(json.loads(content))
        dek = kms.decrypt(envelope.wrapped_dek, padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(),
            label=None,
        ))
        decrypted = AESGCM(dek).decrypt(
            envelope.nonce, envelope.ciphertext, envelope.associated_data(),
        )
        assert decrypted == sample
    print("SEC-03 offline custodian Chromium E2E: PASS (no network, fictional data)")


if __name__ == "__main__":
    main()
