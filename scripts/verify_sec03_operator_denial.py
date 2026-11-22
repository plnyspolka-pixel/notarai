"""Read-only-by-default K6 synthetic decrypt-denial probe in EU.

No client documents, no deploy, no state change. Explicit --check is required
for live AWS; the operator account is tested ONLY as the supplied principal.
A denial for one principal alone is NOT proof that root/Organizations admins
cannot alter external custody or modify the release.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import secrets

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

_REGION = "eu-central-1"
_KMS = re.compile(r"^arn:aws:kms:eu-central-1:([0-9]{12}):key/[A-Za-z0-9-]+$")
_ACCOUNT = re.compile(r"^[0-9]{12}$")
_PIN = re.compile(r"^[A-Za-z0-9+/]{43}=$")


class OperatorProbeRejected(ValueError):
    pass


def run_probe(*, operator_sts, operator_kms, custody_sts, custody_kms,
              expected_operator: str, expected_custody: str,
              key_arn: str, trusted_public_key_pin: str) -> dict:
    if not all(isinstance(a, str) and _ACCOUNT.fullmatch(a)
               for a in (expected_operator, expected_custody)):
        raise OperatorProbeRejected("invalid AWS account identifiers")
    m = _KMS.fullmatch(key_arn) if isinstance(key_arn, str) else None
    if (not m or expected_operator == expected_custody
            or m.group(1) != expected_custody
            or not isinstance(trusted_public_key_pin, str)
            or not _PIN.fullmatch(trusted_public_key_pin)):
        raise OperatorProbeRejected("independent custodian scope not established")
    try:
        current_operator = operator_sts.get_caller_identity()["Account"]
        current_custody = custody_sts.get_caller_identity()["Account"]
    except Exception:
        raise OperatorProbeRejected("AWS identity evidence unavailable") from None
    if (current_operator != expected_operator or
            current_custody != expected_custody):
        raise OperatorProbeRejected("AWS account identity mismatch")
    try:
        info = custody_kms.get_public_key(KeyId=key_arn)
    except Exception:
        raise OperatorProbeRejected("custodian public key unavailable") from None
    if (info.get("KeyId") != key_arn or
            info.get("KeyUsage") != "ENCRYPT_DECRYPT" or
            info.get("KeySpec") not in ("RSA_3072", "RSA_4096")):
        raise OperatorProbeRejected("wrong independently controlled KMS key")
    der = info.get("PublicKey")
    if not isinstance(der, bytes):
        raise OperatorProbeRejected("invalid KMS public key format")
    if (base64.b64encode(hashlib.sha256(der).digest()).decode("ascii")
            != trusted_public_key_pin):
        raise OperatorProbeRejected("custodian public key pin mismatch")
    key = serialization.load_der_public_key(der)
    if not isinstance(key, rsa.RSAPublicKey):
        raise OperatorProbeRejected("KMS public key is not RSA")
    # Disposable synthetic key data. It is never sent to the backend or PR.
    synthetic = bytearray(secrets.token_bytes(32))
    try:
        wrapped = key.encrypt(
            bytes(synthetic), padding.OAEP(
                mgf=padding.MGF1(hashes.SHA256()),
                algorithm=hashes.SHA256(), label=None,
            ),
        )
    finally:
        synthetic[:] = b"\x00" * len(synthetic)
    result = {
        "schema": "notarai.sec03.operator-decrypt-denial.v1",
        "region": _REGION,
        "operator_account_separate": True,
        "independent_public_key_pin_match": True,
        "unenclaved_decrypt_denied_for_test_principal": False,
        "global_operator_denial_proven": False,
        "nitro_attestation_verified": False,
        "status": "BLOCKED",
    }
    try:
        response = operator_kms.decrypt(
            KeyId=key_arn, CiphertextBlob=wrapped,
            EncryptionAlgorithm="RSAES_OAEP_SHA_256",
        )
    except Exception as exc:
        code = (getattr(exc, "response", {}) or {}).get("Error", {}).get("Code")
        if code in ("AccessDenied", "AccessDeniedException"):
            result["unenclaved_decrypt_denied_for_test_principal"] = True
            return result
        raise OperatorProbeRejected("non-authoritative KMS decrypt outcome") from None
    # Do not log or serialize the returned contents even on a policy failure.
    if response.get("Plaintext") is not None:
        result["status"] = "FAIL"
        return result
    raise OperatorProbeRejected("ambiguous KMS decrypt response")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-profile", required=True)
    parser.add_argument("--custody-profile", required=True)
    parser.add_argument("--operator-account", required=True)
    parser.add_argument("--custody-account", required=True)
    parser.add_argument("--key-arn", required=True)
    parser.add_argument("--independent-pin", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        print(json.dumps({"status": "BLOCKED", "aws_calls": 0,
                          "reason": "explicit --check required"}))
        return 0
    import boto3
    operator = boto3.Session(profile_name=args.operator_profile, region_name=_REGION)
    custody = boto3.Session(profile_name=args.custody_profile, region_name=_REGION)
    try:
        result = run_probe(
            operator_sts=operator.client("sts"),
            operator_kms=operator.client("kms"),
            custody_sts=custody.client("sts"),
            custody_kms=custody.client("kms"),
            expected_operator=args.operator_account,
            expected_custody=args.custody_account,
            key_arn=args.key_arn,
            trusted_public_key_pin=args.independent_pin,
        )
    except OperatorProbeRejected:
        print(json.dumps({"status": "BLOCKED",
                          "reason": "independent AWS evidence incomplete"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 2 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
