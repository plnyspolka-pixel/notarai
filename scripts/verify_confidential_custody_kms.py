"""SEC-06: read-only KMS control snapshot under an EXTERNAL custody identity.

Default makes zero AWS calls. --check reads one KMS key with STS,
DescribeKey, GetKeyPolicy, ListKeyPolicies and paginated ListGrants.
No policy writes, no Decrypt, no grant mutation. A snapshot NEVER proves
effective revocation, hardware identity or independent institutional custody.
Do not use this tool as a production release/marketing gate.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidential.custody_ops import (
    render_kms_policy_target, validate_state, verify_kms_policy_snapshot,
)
from confidential.operator_boundary import BoundaryDenied, canonical_digest

_REGION = "eu-central-1"
_MAX_PAGES = 200


def _unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BoundaryDenied("duplicate JSON field in KMS policy")
        result[key] = value
    return result


def _read_policy(kms, arn: str) -> dict:
    try:
        response = kms.get_key_policy(KeyId=arn, PolicyName="default")
    except Exception:
        raise BoundaryDenied("KMS default policy unavailable") from None
    if not isinstance(response, dict):
        raise BoundaryDenied("KMS policy response incomplete")
    policy = response.get("Policy")
    if not isinstance(policy, str):
        raise BoundaryDenied("KMS policy is not JSON text")
    try:
        decoded = json.loads(
            policy, object_pairs_hook=_unique_json_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                BoundaryDenied("invalid JSON constant in KMS policy")),
        )
    except (json.JSONDecodeError, UnicodeError):
        raise BoundaryDenied("KMS policy JSON invalid") from None
    if not isinstance(decoded, dict):
        raise BoundaryDenied("KMS policy must be an object")
    return decoded


def _list_all(kms, arn: str, operation: str, data_field: str) -> list:
    """Pagination is complete only after an explicit Truncated=False."""
    marker = None
    markers = set()
    results = []
    for _ in range(_MAX_PAGES):
        args = {"KeyId": arn, "Limit": 100}
        if marker is not None:
            args["Marker"] = marker
        try:
            response = getattr(kms, operation)(**args)
        except Exception:
            raise BoundaryDenied("KMS inventory inaccessible") from None
        if not isinstance(response, dict):
            raise BoundaryDenied("KMS inventory response invalid")
        items = response.get(data_field)
        if not isinstance(items, list):
            raise BoundaryDenied("KMS inventory entries missing")
        results.extend(items)
        is_truncated = response.get("Truncated")
        if type(is_truncated) is not bool:
            raise BoundaryDenied("KMS inventory completion unavailable")
        if not is_truncated:
            return results
        marker = response.get("NextMarker")
        if not isinstance(marker, str) or not marker or marker in markers:
            raise BoundaryDenied("KMS inventory pagination invalid")
        markers.add(marker)
    raise BoundaryDenied("KMS inventory pagination limit exceeded")


def inspect(*, state: dict, custody_profile: str, check: bool = False,
            session_factory=None) -> dict:
    current = validate_state(state)
    if not custody_profile:
        raise BoundaryDenied("independent custody identity required")
    if not check:
        return {
            "status": "BLOCKED", "mode": "dry-run", "aws_calls": 0,
            "kms_policy_snapshot_checked": False,
            "kms_grants_fully_enumerated": False,
            "independent_custody_verified": False,
            "effective_revocation_verified": False,
        }
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    try:
        session = session_factory(
            profile_name=custody_profile, region_name=_REGION)
        caller = session.client("sts").get_caller_identity()
        if not isinstance(caller, dict) or caller.get(
            "Account") != current["custody_account"]:
            raise BoundaryDenied("KMS audit must use custody account")
        kms = session.client("kms")
        metadata = kms.describe_key(
            KeyId=current["decrypt_key_arn"])["KeyMetadata"]
        if not isinstance(metadata, dict) or any([
            metadata.get("Arn") != current["decrypt_key_arn"],
            metadata.get("AWSAccountId") != current["custody_account"],
            metadata.get("KeyManager") != "CUSTOMER",
            metadata.get("Origin") != "AWS_KMS",
            metadata.get("KeySpec") != "RSA_3072",
            metadata.get("KeyUsage") != "ENCRYPT_DECRYPT",
            metadata.get("MultiRegion") is not False,
            metadata.get("KeyState") not in
            ({"Enabled"} if current["state"] == "ACTIVE"
             else {"Enabled", "Disabled"}),
            metadata.get("Enabled") is not (
                current["state"] == "ACTIVE" or
                metadata.get("KeyState") == "Enabled"),
        ]):
            raise BoundaryDenied("KMS custody key metadata differs from binding")
        policy_names = _list_all(
            kms, current["decrypt_key_arn"], "list_key_policies", "PolicyNames")
        if policy_names != ["default"]:
            raise BoundaryDenied("unreviewed additional KMS key policy")
        observed_policy = _read_policy(kms, current["decrypt_key_arn"])
        grants = _list_all(
            kms, current["decrypt_key_arn"], "list_grants", "Grants")
        verify_kms_policy_snapshot(current, observed_policy, grants)
    except BoundaryDenied:
        raise
    except Exception:
        raise BoundaryDenied("read-only KMS custody evidence unavailable") from None
    return {
        "status": "BLOCKED",
        "region": _REGION,
        "state": current["state"],
        "custody_state_revision": current["revision"],
        "custody_state_sha256": canonical_digest(current),
        "kms_policy_sha256": canonical_digest(observed_policy),
        "kms_policy_snapshot_checked": True,
        "kms_policy_names_checked": 1,
        "kms_grants_fully_enumerated": True,
        "kms_grant_count": 0,
        "kms_decrypt_performed": False,
        "kms_policy_write_performed": False,
        "aws_calls": "read-only (at least 5)",
        "independent_custody_verified": False,
        "effective_revocation_verified": False,
        "negative_decrypt_test": "BLOCKED",
        "evidence_limitations": (
            "KMS list APIs are eventually consistent; a single point-in-time "
            "snapshot is not a historical grant proof or effective deny test"
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--custody-profile", required=True)
    parser.add_argument("--check", action="store_true",
                        help="Explicit read-only live KMS inspection")
    parser.add_argument("--output",
                        help="New report, mode 0600; refuses overwrite")
    args = parser.parse_args(argv)
    try:
        state = json.loads(Path(args.state_file).read_text(encoding="utf-8"))
        report = inspect(
            state=state, custody_profile=args.custody_profile,
            check=args.check)
        if args.output:
            fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                         0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(report, f, sort_keys=True, indent=2)
                f.write("\n")
    except (OSError, json.JSONDecodeError, BoundaryDenied) as exc:
        print(json.dumps({
            "status": "BLOCKED", "reason": str(exc) if isinstance(
                exc, BoundaryDenied) else "KMS evidence file unavailable",
            "independent_custody_verified": False,
        }))
        return 2
    print(json.dumps(report, sort_keys=True))
    # A structural success must NEVER become an independent custody PASS.
    return 3 if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
