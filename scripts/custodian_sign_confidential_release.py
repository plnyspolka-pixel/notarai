"""Custodian-only action: independently sign a verified Nitro/KMS release.

The trusted approval happens in the *external* custody AWS account, not in
the NotarAI repo/CI/operator account. No private signing key leaves AWS KMS.
A checked read-only boundary proof from TWO separate AWS accounts is required.

Default behavior: dry-run, no AWS calls. To approve a release, an authorized
custodian runs --approve-release with a separate signing IAM identity.
This command NEVER modifies KMS policies, decrypts, or launches tasks.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.operator_boundary import BoundaryDenied
from confidential.release_approval import (
    canonical_bytes, make_release_payload, public_key_fingerprint,
)
from scripts.verify_confidential_operator_boundary import inspect


def approve(*, operator_audit_profile: str, custody_audit_profile: str,
            custody_signer_profile: str, tenant: str,
            task_definition_arn: str, kms_key_arn: str,
            pcr17: str, image_sha256: str,
            signing_key_arn: str, approve_release: bool = False,
            session_factory=None, clock: datetime | None = None) -> dict:
    if len({operator_audit_profile, custody_audit_profile,
            custody_signer_profile}) != 3 or not all((
                operator_audit_profile, custody_audit_profile, custody_signer_profile
            )):
        raise BoundaryDenied("distinct audit and external signing identities required")
    if not approve_release:
        return {"state": "dry-run", "aws_calls": 0,
                "zero_operator_access_proven": False}
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    # Re-fetch from real AWS immediately before signing. Never sign a
    # snapshot supplied by the operator as a static JSON input.
    report = inspect(
        operator_profile=operator_audit_profile,
        custody_profile=custody_audit_profile,
        tenant=tenant, task_definition_arn=task_definition_arn,
        kms_key_arn=kms_key_arn, pcr17=pcr17,
        image_sha256=image_sha256, check=True,
        session_factory=session_factory,
    )
    custodian = session_factory(profile_name=custody_signer_profile,
                                region_name="eu-central-1")
    if custodian.client("sts").get_caller_identity().get(
        "Account"
    ) != report["custody_account"]:
        raise BoundaryDenied("release signer is not in independently held custody account")
    if not isinstance(signing_key_arn, str) or not signing_key_arn.startswith(
        f"arn:aws:kms:eu-central-1:{report['custody_account']}:key/"
    ):
        raise BoundaryDenied("release key belongs to wrong AWS account")
    kms = custodian.client("kms")
    meta = kms.describe_key(KeyId=signing_key_arn)["KeyMetadata"]
    if (meta.get("Arn") != signing_key_arn or
            meta.get("AWSAccountId") != report["custody_account"] or
            meta.get("KeyManager") != "CUSTOMER" or
            meta.get("KeyUsage") != "SIGN_VERIFY" or
            meta.get("KeySpec") != "ECC_NIST_P256" or
            meta.get("KeyState") != "Enabled"):
        raise BoundaryDenied("release key is not a live independent ECDSA signing key")
    public = kms.get_public_key(KeyId=signing_key_arn)
    if "ECDSA_SHA_256" not in public.get("SigningAlgorithms", []):
        raise BoundaryDenied("release key cannot sign ECDSA SHA-256")
    try:
        public_key = serialization.load_der_public_key(public["PublicKey"])
        pem = public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    except (KeyError, ValueError, TypeError):
        raise BoundaryDenied("custodian public signing key unavailable") from None
    fingerprint = public_key_fingerprint(pem)
    payload = make_release_payload(
        report, clock=clock or datetime.now(timezone.utc),
    )
    request = canonical_bytes(payload)
    signed = kms.sign(
        KeyId=signing_key_arn, Message=request,
        MessageType="RAW", SigningAlgorithm="ECDSA_SHA_256",
    )
    signature = signed.get("Signature")
    if (signed.get("KeyId") != signing_key_arn or
            signed.get("SigningAlgorithm") != "ECDSA_SHA_256" or
            not isinstance(signature, bytes)):
        raise BoundaryDenied("independent custody KMS signing failed")
    try:
        public_key.verify(signature, request, ec.ECDSA(hashes.SHA256()))
    except Exception:
        raise BoundaryDenied("custodian signature failed local verification") from None
    return {
        "payload": payload,
        "signature_b64": base64.b64encode(signature).decode("ascii"),
        # The fingerprint is NOT a trusted root by itself; a verifier must
        # obtain and pin it independently from the custodian.
        "_independent_fingerprint_for_delivery": fingerprint,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for key in (
        "operator-audit-profile", "custody-audit-profile",
        "custody-signer-profile", "tenant",
        "task-definition-arn", "kms-key-arn", "pcr17",
        "image-sha256", "signing-key-arn",
    ):
        p.add_argument("--" + key, required=True)
    p.add_argument("--approve-release", action="store_true",
                   help="EXPLICIT independent custodian approval; invokes chargeable KMS Sign")
    p.add_argument("--output", type=Path,
                   help="Write signed release receipt as new file, never overwrite")
    args = p.parse_args()
    if args.approve_release and args.output is None:
        raise SystemExit("DENIED: custodian release requires --output")
    try:
        result = approve(
            operator_audit_profile=args.operator_audit_profile,
            custody_audit_profile=args.custody_audit_profile,
            custody_signer_profile=args.custody_signer_profile,
            tenant=args.tenant,
            task_definition_arn=args.task_definition_arn,
            kms_key_arn=args.kms_key_arn,
            pcr17=args.pcr17,
            image_sha256=args.image_sha256,
            signing_key_arn=args.signing_key_arn,
            approve_release=args.approve_release,
        )
        if args.output:
            fingerprint = result.pop("_independent_fingerprint_for_delivery", None)
            fd = os.open(str(args.output),
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
            if fingerprint:
                print("Signed release created. Custodian must deliver pinned SHA256 "
                      "public-key fingerprint to auditor OUT OF BAND.")
        else:
            print(json.dumps(result, sort_keys=True))
    except Exception:
        raise SystemExit("DENIED: independent custody release not authorized") from None


if __name__ == "__main__":
    main()
