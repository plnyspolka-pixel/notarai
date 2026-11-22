"""SEC-06: operator-side NEGATIVE KMS decrypt probe on SYNTHETIC random bytes.

Default makes ZERO AWS calls. This is not a Nitro or independent root proof.
With BOTH explicit opt-in switches, the tool obtains only the public RSA
key, locally RSA-OAEP-encrypts a fresh synthetic string, and requests KMS
Decrypt WITHOUT a Recipient/attestation document from one operator identity.

If KMS grants Decrypt, the code discards the result and FAILS CLOSED.
It NEVER prints, hashes, logs, writes, or returns any decrypted plaintext.
Only an explicit AccessDeniedException counts as one denied operator path.
Unexpected KMS errors are INCONCLUSIVE, not proof of denial.
NO customer ciphertext or private document is used at any point.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confidential.custody_ops import validate_state
from confidential.operator_boundary import BoundaryDenied

_REGION = "eu-central-1"
_DENIED_CODES = frozenset({"AccessDeniedException", "AccessDenied"})


def probe_operator_denial(*, state: dict, operator_profile: str,
                          execute: bool = False,
                          synthetic_only_ack: bool = False,
                          session_factory=None) -> dict:
    s = validate_state(state)
    if not isinstance(operator_profile, str) or not operator_profile:
        raise BoundaryDenied("named operator-only AWS profile required")
    if not execute:
        return {
            "status": "BLOCKED_DRY_RUN", "aws_calls": 0,
            "single_operator_identity_denied": False,
            "effective_revocation_verified": False,
            "independent_custody_verified": False,
            "customer_data_used": False,
        }
    if synthetic_only_ack is not True:
        raise BoundaryDenied("explicit synthetic-only authorization required")
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    try:
        session = session_factory(
            profile_name=operator_profile, region_name=_REGION)
        operator = session.client("sts").get_caller_identity()
        if not isinstance(operator, dict) or operator.get(
            "Account") != s["workload_account"]:
            raise BoundaryDenied("negative probe must use exact workload account")
        kms = session.client("kms")
        public_result = kms.get_public_key(KeyId=s["decrypt_key_arn"])
        if (not isinstance(public_result, dict) or
                public_result.get("KeyId") != s["decrypt_key_arn"] or
                public_result.get("KeySpec") != "RSA_3072" or
                public_result.get("KeyUsage") != "ENCRYPT_DECRYPT" or
                "RSAES_OAEP_SHA_256" not in public_result.get(
                    "EncryptionAlgorithms", ())):
            raise BoundaryDenied("synthetic probe public KMS key mismatch")
        public_key = serialization.load_der_public_key(
            public_result["PublicKey"])
        if (not isinstance(public_key, rsa.RSAPublicKey) or
                public_key.key_size != 3072):
            raise BoundaryDenied("synthetic probe requires approved RSA-3072")
        plaintext = b"NOTARAI_SEC06_SYNTHETIC_DENIAL_PROBE_V1:" + os.urandom(32)
        blob = public_key.encrypt(
            plaintext, padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(), label=None))
        # Only synthetic string; never use a caller-supplied ciphertext.
        # Deliberately DO NOT pass Recipient: no Nitro attestation is presented.
        try:
            kms.decrypt(
                KeyId=s["decrypt_key_arn"], CiphertextBlob=blob,
                EncryptionAlgorithm="RSAES_OAEP_SHA_256")
        except Exception as error:
            # boto3 ClientError response is the only accepted denial proof.
            from botocore.exceptions import ClientError
            if (isinstance(error, ClientError) and
                    isinstance(error.response, dict) and
                    isinstance(error.response.get("Error"), dict) and
                    error.response["Error"].get("Code") in _DENIED_CODES):
                return {
                    "status": "OPERATOR_DECRYPT_DENIED_FOR_ONE_IDENTITY",
                    "aws_calls": 3,
                    "single_operator_identity_denied": True,
                    "effective_revocation_verified": False,
                    "independent_custody_verified": False,
                    "customer_data_used": False,
                    "synthetic_ciphertext_persisted": False,
                    "plaintext_logged_or_returned": False,
                    "nitro_attestation_presented": False,
                }
            raise BoundaryDenied(
                "operator negative probe inconclusive: not an explicit access denial") from None
    except BoundaryDenied:
        raise
    except Exception:
        raise BoundaryDenied("synthetic KMS negative probe setup unavailable") from None

    # An accidental KMS success is a security incident even though its
    # plaintext is only locally generated test bytes. Do not log the result.
    raise BoundaryDenied("FAIL_OPEN: operator without attestation could decrypt")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--operator-profile", required=True)
    parser.add_argument("--execute-negative-probe", action="store_true")
    parser.add_argument("--acknowledge-synthetic-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.state_file, encoding="utf-8") as input_file:
            state = json.load(input_file)
        result = probe_operator_denial(
            state=state, operator_profile=args.operator_profile,
            execute=args.execute_negative_probe,
            synthetic_only_ack=args.acknowledge_synthetic_only)
    except (OSError, ValueError, BoundaryDenied) as error:
        reason = (str(error) if isinstance(error, BoundaryDenied)
                  else "synthetic state unavailable")
        print(json.dumps({"status": "BLOCKED", "reason": reason,
                          "independent_custody_verified": False}))
        return 4 if reason.startswith("FAIL_OPEN") else 2
    print(json.dumps(result, sort_keys=True))
    # Even a denied operator profile does not prove all possible IAM,
    # SSO, Organizations, key admin or future grant paths are denied.
    return 3 if args.execute_negative_probe else 0


if __name__ == "__main__":
    raise SystemExit(main())
