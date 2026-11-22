"""SEC-07 read-only audit of the four KMS-negative trials.

An unsigned release should never reach RunTask, and a changed OCI image can
be denied at ECS admission. Neither should be misrepresented by a fabricated
KMS AccessDenied ID. Both need separate independent evidence and witnessing.

The script never launches a task, calls KMS Decrypt or alters AWS.
Exit 2 (BLOCKED) is intentional until the full independent hardware audit.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.nitro_witness import verify_independent_witnesses
from confidential.nitro_denial_matrix import (
    KMS_CASES, EARLY_CASES, DenialEvidenceRejected, incomplete_audit_result,
    inspect_early_denial_receipt, inspect_altered_image_ecs,
    inspect_kms_denial, validate_matrix,
)

_MAX_BYTES = 32 * 1024


def _read_json(path: str) -> dict:
    payload = Path(path).read_bytes()
    if not payload or len(payload) > _MAX_BYTES:
        raise DenialEvidenceRejected("audit input invalid")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise DenialEvidenceRejected("audit input not an object")
    return value


def _lookup(trail, event_id: str, start: datetime, end: datetime) -> dict:
    result = trail.lookup_events(
        LookupAttributes=[{"AttributeKey": "EventId", "AttributeValue": event_id}],
        StartTime=start, EndTime=end, MaxResults=50,
    )
    entries = result.get("Events", [])
    if len(entries) != 1 or result.get("NextToken"):
        raise DenialEvidenceRejected("CloudTrail negative event missing/ambiguous")
    raw = entries[0].get("CloudTrailEvent", "")
    if not isinstance(raw, str) or len(raw) > 128 * 1024:
        raise DenialEvidenceRejected("CloudTrail negative record invalid")
    return json.loads(raw)


def audit_live(*, matrix: dict, operator_profile: str, custody_profile: str,
               receipts: dict, session_factory=None) -> dict:
    """Re-fetch four real KMS events and check two early receipt structures.

    This does not establish independent witness provenance of early denials;
    consequently, the return value can never be hardware PASS.
    """
    validate_matrix(matrix)
    if (not operator_profile or not custody_profile or
            operator_profile == custody_profile):
        raise DenialEvidenceRejected("two distinct audit profiles required")
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    operator = session_factory(
        profile_name=operator_profile, region_name="eu-central-1",
    )
    custody = session_factory(
        profile_name=custody_profile, region_name="eu-central-1",
    )
    caller = operator.client("sts").get_caller_identity()
    owner = custody.client("sts").get_caller_identity()
    if (caller.get("Account") != matrix["workload_account"] or
            owner.get("Account") != matrix["custody_account"]):
        raise DenialEvidenceRejected("live AWS account mismatch")

    start = datetime.strptime(matrix["started_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc,
    ) - timedelta(minutes=2)
    end = datetime.strptime(matrix["ended_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc,
    ) + timedelta(minutes=2)
    trail = operator.client("cloudtrail")
    observed = {}
    for case in sorted(KMS_CASES):
        record = _lookup(trail, matrix["trials"][case]["event_id"], start, end)
        observed[case] = inspect_kms_denial(case, record, matrix)
    if not isinstance(receipts, dict) or set(receipts) != set(EARLY_CASES):
        raise DenialEvidenceRejected("early-denial receipts unavailable")
    early = {}
    for case in sorted(EARLY_CASES):
        early[case] = inspect_early_denial_receipt(
            case, receipts[case], matrix,
        )
    # ECS stopped tasks are queryable for a limited time after execution.
    # Re-fetch candidate image from ECS instead of trusting a receipt label.
    ecs = operator.client("ecs")
    altered_arn = receipts["altered_image"]["ecs_task_arn"]
    cluster = altered_arn.split("/")[1]
    task_result = ecs.describe_tasks(cluster=cluster, tasks=[altered_arn])
    task_list = task_result.get("tasks", [])
    if task_result.get("failures") or len(task_list) != 1:
        raise DenialEvidenceRejected("altered-image ECS task unavailable")
    candidate = task_list[0]
    definition_result = ecs.describe_task_definition(
        taskDefinition=candidate["taskDefinitionArn"],
    )
    ecs_observed = inspect_altered_image_ecs(
        task=candidate, task_definition=definition_result.get("taskDefinition"),
        receipt=receipts["altered_image"], matrix=matrix,
    )
    return {
        **incomplete_audit_result(),
        "kms_cases_live_observed": len(observed),
        "early_case_metadata_validated": len(early),
        "altered_image_ecs_metadata_observed": ecs_observed["ecs_metadata_observed"],
        "kms_observations": observed,
        "early_observations": early,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="Offline check; never contacts AWS")
    group.add_argument("--verify-live", action="store_true",
                       help="Read-only AWS CloudTrail/STS; never triggers trials")
    parser.add_argument("--matrix")
    parser.add_argument("--operator-profile")
    parser.add_argument("--custody-profile")
    parser.add_argument("--altered-image-receipt")
    parser.add_argument("--unsigned-release-receipt")
    parser.add_argument("--witness-payload")
    parser.add_argument("--custodian-witness-signature")
    parser.add_argument("--custodian-witness-public-key")
    parser.add_argument("--custodian-witness-public-key-sha256")
    parser.add_argument("--auditor-witness-signature")
    parser.add_argument("--auditor-witness-public-key")
    parser.add_argument("--auditor-witness-public-key-sha256")
    args = parser.parse_args()
    try:
        matrix = validate_matrix(_read_json(args.matrix)) if args.matrix else None
        if args.check:
            print(json.dumps(incomplete_audit_result(), sort_keys=True))
            return 2
        if (matrix is None or not args.operator_profile or
                not args.custody_profile or not args.altered_image_receipt or
                not args.unsigned_release_receipt):
            raise DenialEvidenceRejected("live audit requires two profiles and receipts")
        result = audit_live(
            matrix=matrix,
            operator_profile=args.operator_profile,
            custody_profile=args.custody_profile,
            receipts={
                "altered_image": _read_json(args.altered_image_receipt),
                "unsigned_release": _read_json(args.unsigned_release_receipt),
            },
        )
        witness_inputs = (
            args.witness_payload,
            args.custodian_witness_signature,
            args.custodian_witness_public_key,
            args.custodian_witness_public_key_sha256,
            args.auditor_witness_signature,
            args.auditor_witness_public_key,
            args.auditor_witness_public_key_sha256,
        )
        if any(witness_inputs):
            if not all(witness_inputs):
                raise DenialEvidenceRejected("both independently pinned witness signatures required")
            witness = verify_independent_witnesses(
                payload=_read_json(args.witness_payload), matrix=matrix,
                custodian_signature_b64=Path(args.custodian_witness_signature)
                    .read_text(encoding="ascii").strip(),
                custodian_public_key_pem=Path(args.custodian_witness_public_key)
                    .read_bytes(),
                custodian_public_key_sha256=args.custodian_witness_public_key_sha256,
                auditor_signature_b64=Path(args.auditor_witness_signature)
                    .read_text(encoding="ascii").strip(),
                auditor_public_key_pem=Path(args.auditor_witness_public_key)
                    .read_bytes(),
                auditor_public_key_sha256=args.auditor_witness_public_key_sha256,
            )
            result["witness_signatures_verified"] = witness["witness_signatures_verified"]
            result["witness_sha256"] = witness["witness_sha256"]
            result["custodian_public_key_sha256"] = witness["custodian_public_key_sha256"]
            result["auditor_public_key_sha256"] = witness["auditor_public_key_sha256"]
        else:
            result["witness_signatures_verified"] = False
        # A signed matrix remains BLOCKED: negative cloud evidence cannot
        # independently prove all attempted attack preconditions or operator
        # non-administration of the custody/signing account.
        result["hardware_attestation_verified"] = False
        result["negative_cases_independently_verified"] = False
        result["production_enabled"] = False
        result["status"] = "BLOCKED"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps(incomplete_audit_result(), sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
