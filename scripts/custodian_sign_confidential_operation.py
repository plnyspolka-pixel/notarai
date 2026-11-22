"""SEC-06 custodian-side signer for synthetic custody lifecycle actions.

Default is NO AWS calls. --approve-action must be exercised by an external
custodian holding its own profile and out-of-band pinned signing key.
This only signs approval events: it NEVER changes KMS key policy or decrypts.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.operator_boundary import BoundaryDenied, canonical_digest
from confidential.custody_ops import (
    _EVENT_SCHEMA, _IDENTITY_FIELDS, _ROTATION_FIELDS, _signed_event_bytes,
    _utc, validate_state,
)

_REGION = "eu-central-1"
_SIGNING_ARN = re.compile(
    r"arn:aws:kms:eu-central-1:([0-9]{12}):key/[0-9a-fA-F-]{36}\Z")
_HEX = re.compile(r"[a-f0-9]{64}\Z")


def _validate_intent(payload: dict, state: dict | None, now: datetime) -> str:
    _signed_event_bytes(payload)
    issued, expiry = _utc(payload["issued_at"]), _utc(payload["expires_at"])
    if (not isinstance(now, datetime) or now.tzinfo is None or
            not issued <= now.astimezone(timezone.utc) < expiry
            or not timedelta(0) < expiry - issued <= timedelta(hours=24)):
        raise BoundaryDenied("custodian action outside approved time window")
    action = payload["action"]
    if state is None:
        if (action != "ENROLL" or payload["revision"] != 1 or
                payload["previous_sha256"] != "0" * 64 or
                not isinstance(payload["changes"], dict) or
                set(payload["changes"]) != _IDENTITY_FIELDS):
            raise BoundaryDenied("new enrollment requires full custody binding")
        proposed = validate_state({
            **payload["changes"], "schema": "notarai.confidential.custody-state.v1",
            "generation": 1, "revision": 1, "state": "ACTIVE"})
        if payload["tenant"] != proposed["tenant"]:
            raise BoundaryDenied("custodian enrollment tenant mismatch")
        return proposed["signing_key_arn"]
    current = validate_state(state)
    if (payload["tenant"] != current["tenant"] or
            type(payload["revision"]) is not int or
            payload["revision"] != current["revision"] + 1 or
            payload["previous_sha256"] != canonical_digest(current)):
        raise BoundaryDenied("custodian action has stale state or wrong tenant")
    if current["state"] in ("REVOKED", "LOST"):
        raise BoundaryDenied("terminal custody state cannot be recovered")
    changes = payload["changes"]
    if not isinstance(changes, dict):
        raise BoundaryDenied("invalid custodian changes")
    if action == "FREEZE":
        ok = current["state"] == "ACTIVE" and changes == {}
    elif action == "REVOKE" or action == "MARK_LOST":
        ok = changes == {}
    elif action == "UNFREEZE":
        ok = current["state"] == "FROZEN" and changes == {}
    elif action == "ROTATE":
        ok = (current["state"] == "FROZEN" and
              set(changes) == _ROTATION_FIELDS and
              changes["decrypt_key_arn"] != current["decrypt_key_arn"] and
              changes["signing_key_arn"] != current["signing_key_arn"] and
              changes["release_sha256"] != current["release_sha256"])
        if ok:
            validate_state({**current, **changes, "revision":
                            current["revision"] + 1,
                            "generation": current["generation"] + 1})
    else:
        ok = False
    if not ok:
        raise BoundaryDenied("custodian lifecycle transition is invalid")
    # Rotation is approved with the previously trusted signer. The new
    # trust-root must then be explicitly pinned out-of-band by the client.
    return current["signing_key_arn"]


def sign_operation(*, payload: dict, state: dict | None,
                   custody_profile: str, signing_key_arn: str,
                   pinned_public_key_sha256: str,
                   pinned_current_state_sha256: str | None = None,
                   approve_action: bool = False,
                   session_factory=None, clock: datetime | None = None) -> dict:
    if not custody_profile:
        raise BoundaryDenied("independent custody profile required")
    if not isinstance(pinned_public_key_sha256, str) or not _HEX.fullmatch(
        pinned_public_key_sha256
    ):
        raise BoundaryDenied("independent public signing pin required")
    now = clock if clock is not None else datetime.now(timezone.utc)
    expected_key = _validate_intent(payload, state, now)
    match = _SIGNING_ARN.fullmatch(signing_key_arn)
    if not match or signing_key_arn != expected_key:
        raise BoundaryDenied("custodian signing key is not tenant bound")
    custody_account = (state or payload["changes"])["custody_account"]
    workload_account = (state or payload["changes"])["workload_account"]
    if match.group(1) != custody_account or custody_account == workload_account:
        raise BoundaryDenied("custody account not independent of workload")
    if not approve_action:
        return {"status": "dry-run", "aws_calls": 0,
                "independent_custody_verified": False}
    # The authoritative expected state hash must come independently from the
    # custodian ledger, not from the operator-supplied JSON at signing time.
    current_hash = canonical_digest(state) if state is not None else "0" * 64
    if (not isinstance(pinned_current_state_sha256, str) or
            not _HEX.fullmatch(pinned_current_state_sha256) or
            pinned_current_state_sha256 != current_hash):
        raise BoundaryDenied("independent custody ledger state pin missing or stale")
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    try:
        session = session_factory(
            profile_name=custody_profile, region_name=_REGION)
        caller = session.client("sts").get_caller_identity()
        if caller.get("Account") != custody_account:
            raise BoundaryDenied("approval attempted from non-custody account")
        kms = session.client("kms")
        metadata = kms.describe_key(KeyId=signing_key_arn)["KeyMetadata"]
        if (metadata.get("Arn") != signing_key_arn or
                metadata.get("KeySpec") != "ECC_NIST_P256" or
                metadata.get("KeyUsage") != "SIGN_VERIFY" or
                metadata.get("KeyState") != "Enabled"):
            raise BoundaryDenied("custodian signer metadata not approved")
        key_der = kms.get_public_key(KeyId=signing_key_arn)["PublicKey"]
        public = serialization.load_der_public_key(key_der)
        if not isinstance(public, ec.EllipticCurvePublicKey) or not isinstance(
            public.curve, ec.SECP256R1
        ):
            raise BoundaryDenied("custodian signer must be P-256")
        if hashlib.sha256(key_der).hexdigest() != pinned_public_key_sha256:
            raise BoundaryDenied("custodian trust-root fingerprint mismatch")
        signature = kms.sign(
            KeyId=signing_key_arn, Message=_signed_event_bytes(payload),
            MessageType="RAW", SigningAlgorithm="ECDSA_SHA_256")["Signature"]
        public.verify(
            signature, _signed_event_bytes(payload), ec.ECDSA(hashes.SHA256()))
    except BoundaryDenied:
        raise
    except Exception:
        raise BoundaryDenied("external KMS signing failed") from None
    return {
        "status": "signed", "aws_calls": 4,
        "independent_custody_verified": False,
        "envelope": {
            "payload": payload,
            "signature_b64": base64.b64encode(signature).decode("ascii"),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-file", required=True)
    parser.add_argument("--current-state-file")
    parser.add_argument("--custody-profile", required=True)
    parser.add_argument("--signing-key-arn", required=True)
    parser.add_argument("--pinned-public-key-sha256", required=True,
                        help="Fingerprint independently pinned by custodian")
    parser.add_argument("--pinned-current-state-sha256",
                        help="Expected state digest obtained OUT-OF-BAND from independent custodian ledger")
    parser.add_argument("--approve-action", action="store_true",
                        help="Explicitly execute KMS Sign in external account")
    parser.add_argument("--output",
                        help="Required for approval; O_EXCL file with mode 0600")
    args = parser.parse_args(argv)
    if args.approve_action and not args.output:
        parser.error("--output is required for --approve-action")
    try:
        payload = json.loads(Path(args.payload_file).read_text("utf-8"))
        state = (json.loads(Path(args.current_state_file).read_text("utf-8"))
                 if args.current_state_file else None)
        result = sign_operation(
            payload=payload, state=state, custody_profile=args.custody_profile,
            signing_key_arn=args.signing_key_arn,
            pinned_public_key_sha256=args.pinned_public_key_sha256,
            pinned_current_state_sha256=args.pinned_current_state_sha256,
            approve_action=args.approve_action)
        if args.approve_action:
            fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as target:
                json.dump(result["envelope"], target, sort_keys=True, indent=2)
                target.write("\n")
        # Never print AWS signing material or entire receipt to stdout.
        print(json.dumps({
            "status": result["status"], "aws_calls": result["aws_calls"],
            "independent_custody_verified": False}))
        return 0
    except (OSError, json.JSONDecodeError, BoundaryDenied) as exc:
        # AWS exceptions and secrets are intentionally not echoed.
        if isinstance(exc, BoundaryDenied):
            reason = str(exc)
        else:
            reason = "signed action input/output unavailable"
        print(json.dumps({"status": "BLOCKED", "reason": reason,
                          "independent_custody_verified": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
