"""Build a signed, standalone, network-disabled browser encryption client.

Run on an independently controlled custodian signing workstation.
No NotarAI application deployment, AWS call, or notary-PC installation.
The publisher must serve this artifact from a custodian-controlled origin,
or provide a verifiably signed copy out of band. This builder cannot
independently establish who owns that origin or the signing key.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
import re
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from confidential.client_release import canonical_release_bytes, verify_client_release

_ID = re.compile(r"^[a-z0-9]{1,12}$")
_KMS = re.compile(r"^arn:aws:kms:eu-central-1:[0-9]{12}:key/[A-Za-z0-9-]+$")
_SHA_B64 = re.compile(r"^[A-Za-z0-9+/]{43}=$")
_RELEASE = re.compile(r"^[a-f0-9]{32}$")


def _write_new(path: Path, value: bytes) -> None:
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(value)
        output.flush()
        os.fsync(output.fileno())


def build_custodian_client(
    *, repository_root: Path, output_dir: Path,
    tenant: str, kms_arn: str, kms_public_pem: str, key_pin: str,
    release_id: str, expires_at: int,
    custodian_private_key_pem: bytes, password: bytes | None = None,
) -> dict:
    if (not _ID.fullmatch(tenant) or not _KMS.fullmatch(kms_arn)
            or not _SHA_B64.fullmatch(key_pin) or not _RELEASE.fullmatch(release_id)
            or type(expires_at) is not int or not 0 < expires_at < 4102444800):
        raise ValueError("invalid pinned client release settings")
    key = serialization.load_pem_public_key(kms_public_pem.encode("ascii"))
    if (not isinstance(key, rsa.RSAPublicKey) or key.key_size not in (3072, 4096)):
        raise ValueError("only approved RSA-OAEP KMS public keys are supported")
    der = key.public_bytes(serialization.Encoding.DER,
                           serialization.PublicFormat.SubjectPublicKeyInfo)
    actual_pin = base64.b64encode(hashlib.sha256(der).digest()).decode("ascii")
    if actual_pin != key_pin:
        raise ValueError("independent public key pin mismatch")
    signer = serialization.load_pem_private_key(custodian_private_key_pem, password)
    if not isinstance(signer, ed25519.Ed25519PrivateKey):
        raise ValueError("custodian release signer must use Ed25519")

    source = (repository_root / "static/confidential-crypto.js").read_text(
        encoding="utf-8"
    )
    if "</script" in source.lower():
        raise ValueError("embedded JS script delimiter forbidden")
    config = json.dumps({
        "tenant": tenant, "kmsArn": kms_arn, "publicKeyPem": kms_public_pem,
        "keyPin": key_pin,
    }, separators=(",", ":"), ensure_ascii=True)
    app = r"""
const settings = Object.freeze(__CONFIG__);
const form = document.getElementById("local-encrypt");
const output = document.getElementById("status");
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const action = document.getElementById("encrypt");
  action.disabled = true;
  output.textContent = "Szyfrowanie lokalne w przeglądarce…";
  let bytes = null;
  try {
    const selected = document.getElementById("document").files;
    if (selected.length !== 1) throw new Error("Wybierz jeden dokument");
    const caseId = document.getElementById("caseId").value.trim();
    const objectId = document.getElementById("objectId").value.trim();
    if (!/^[A-Za-z0-9_-]{1,80}$/.test(caseId) ||
        !/^[A-Za-z0-9_-]{1,80}$/.test(objectId)) {
      throw new Error("Nieprawidłowy identyfikator sprawy lub dokumentu");
    }
    bytes = new Uint8Array(await selected[0].arrayBuffer());
    const encrypted = await encryptForConfidentialTask({
      bytes, tenantId: settings.tenant, caseId, objectId,
      kmsKeyArn: settings.kmsArn, publicKeyPem: settings.publicKeyPem,
      pinnedKeySha256: settings.keyPin
    });
    const url = URL.createObjectURL(new Blob(
      [JSON.stringify(encrypted)], {type:"application/json"}
    ));
    try {
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "notarai-" + objectId + ".encrypted.json";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      output.textContent = "Zaszyfrowany plik zapisany. Wyślij wyłącznie plik .encrypted.json.";
    } finally {
      URL.revokeObjectURL(url);
    }
  } catch (_) {
    output.textContent = "Szyfrowanie odmówione. Sprawdź plik i przypięty klucz.";
  } finally {
    if (bytes) bytes.fill(0);
    document.getElementById("document").value = "";
    action.disabled = false;
  }
});
document.getElementById("objectId").value = "obj_" +
  Array.from(crypto.getRandomValues(new Uint8Array(16)),
             x => x.toString(16).padStart(2, "0")).join("");
"""
    script = source + "\n" + app.replace("__CONFIG__", config)
    script_digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    html = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-__SCRIPT_HASH__'; style-src 'unsafe-inline'; connect-src 'none'; object-src 'none'; form-action 'none'; base-uri 'none'">
<title>NotarAI — niezależne szyfrowanie</title>
<style>body{font:16px system-ui,sans-serif;max-width:640px;margin:2rem auto;padding:0 1rem;color:#142534}form{display:grid;gap:1rem}label{display:grid;gap:.4rem}input{font:inherit;padding:.6rem}button{padding:.8rem;background:#184e77;color:white;border:0;border-radius:5px}button:disabled{opacity:.6}.note{background:#f1f4f7;padding:.8rem;border-radius:5px}</style></head>
<body><h1>NotarAI — bezpieczne szyfrowanie lokalne</h1>
<p class="note">Ta strona nie ma dostępu do sieci ani skryptów zewnętrznych.
Dane pozostają w przeglądarce przed zaszyfrowaniem. Oprogramowanie i klucze
wydania powinny być zweryfikowane u niezależnego kustosza.</p>
<form id="local-encrypt" autocomplete="off">
<label>Identyfikator sprawy <input id="caseId" required maxlength="80" pattern="[A-Za-z0-9_-]{1,80}" autocomplete="off"></label>
<label>Identyfikator dokumentu <input id="objectId" required maxlength="80" pattern="[A-Za-z0-9_-]{1,80}" autocomplete="off"></label>
<label>Plik do zaszyfrowania <input id="document" type="file" required></label>
<button id="encrypt" type="submit">Zaszyfruj i zapisz</button></form>
<p id="status" role="status" aria-live="polite"></p>
<script type="module">__SCRIPT__</script></body></html>""".replace(
        "__SCRIPT_HASH__", script_digest
    ).replace("__SCRIPT__", script)
    raw_html = html.encode("utf-8")
    manifest = {
        "schema": "notarai.client-release.v1",
        "release_id": release_id, "tenant_id": tenant,
        "kms_key_arn": kms_arn, "public_key_sha256": key_pin,
        # legacy manifest field identifies the HASH OF THE ENTIRE HTML FILE,
        # not merely a remote script (no remote scripts are permitted).
        "javascript_sha256": hashlib.sha256(raw_html).hexdigest(),
        "expires_at": expires_at,
    }
    sig = signer.sign(canonical_release_bytes(manifest))
    public = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    verify_client_release(
        javascript=raw_html, manifest=manifest, signature=sig,
        trusted_public_key=public, tenant_id=tenant,
        expected_kms_arn=kms_arn, expected_key_pin=key_pin,
        now=expires_at - 1,
    )
    output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    _write_new(output_dir / "client.html", raw_html)
    _write_new(output_dir / "manifest.json", json.dumps(
        manifest, sort_keys=True, indent=2
    ).encode("ascii") + b"\n")
    _write_new(output_dir / "manifest.sig", base64.b64encode(sig) + b"\n")
    # This file must be distributed independently, not trusted merely because
    # it appears in the same folder as the signed client or manifest.
    _write_new(output_dir / "CUSTODIAN_PUBLIC_KEY_UNTRUSTED.bin", public)
    return {"release_id": release_id, "artifact_sha256": manifest["javascript_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--kms-key-arn", required=True)
    parser.add_argument("--kms-public-pem", type=Path, required=True)
    parser.add_argument("--independent-pin", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--expires-at", type=int, required=True)
    parser.add_argument("--custodian-signing-key", type=Path, required=True)
    parser.add_argument("--encrypted-key", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    password = getpass.getpass("Custodian key passphrase: ").encode() if args.encrypted_key else None
    build_custodian_client(
        repository_root=Path(__file__).resolve().parents[1],
        output_dir=args.output_dir, tenant=args.tenant,
        kms_arn=args.kms_key_arn,
        kms_public_pem=args.kms_public_pem.read_text(encoding="ascii"),
        key_pin=args.independent_pin, release_id=args.release_id,
        expires_at=args.expires_at,
        custodian_private_key_pem=args.custodian_signing_key.read_bytes(),
        password=password,
    )
    print("Signed standalone browser client generated (not deployed or independently verified).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
