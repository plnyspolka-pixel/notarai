"""SEC-07 Nitro/KMS read-only evidence audit: no deploy, decrypt or AWS writes.

--check is OFFLINE and can only return BLOCKED.
--verify-live performs a read-only recheck of independently observed ECS, KMS
and CloudTrail evidence from two accounts. Signing remains OUTSIDE NotarAI.
This tool verifies already executed synthetic trials; it never launches them.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.nitro_hardware_proof import (
    ProofRejected, assemble_audit_payload, blocked_result,
    canonical_bytes, evidence_sha256, validate_manifest,
)
from confidential.cloudtrail_readonly import PacedCloudTrail
from confidential.release_approval import public_key_fingerprint
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

_REGION = "eu-central-1"
_MAX_INPUT = 128 * 1024


def _file(path: str) -> bytes:
    value = Path(path).read_bytes()
    if not value or len(value) > _MAX_INPUT:
        raise ProofRejected("evidence input size invalid")
    return value


def _json(path: str) -> dict:
    document = json.loads(_file(path))
    if not isinstance(document, dict):
        raise ProofRejected("evidence JSON must be an object")
    return document


def _event(trail, event_id: str, start: datetime, end: datetime) -> dict:
    response = trail.lookup_events(
        LookupAttributes=[{"AttributeKey": "EventId", "AttributeValue": event_id}],
        StartTime=start, EndTime=end, MaxResults=50,
    )
    events = response.get("Events", [])
    if response.get("NextToken") or len(events) != 1:
        raise ProofRejected("CloudTrail event unavailable or ambiguous")
    return json.loads(events[0]["CloudTrailEvent"])


def _verify_external_signature(payload: dict, signature_file: str,
                               public_key_file: str, fingerprint: str) -> None:
    key = _file(public_key_file)
    if public_key_fingerprint(key) != fingerprint:
        raise ProofRejected("audit signing key is not independently pinned")
    try:
        signature = base64.b64decode(_file(signature_file).strip(), validate=True)
        pub = serialization.load_pem_public_key(key)
        if not isinstance(pub, ec.EllipticCurvePublicKey) or not isinstance(
            pub.curve, ec.SECP256R1,
        ):
            raise ProofRejected("auditor key is not ECDSA P-256")
        pub.verify(signature, canonical_bytes(payload), ec.ECDSA(hashes.SHA256()))
    except (ValueError, TypeError, InvalidSignature, binascii.Error):
        raise ProofRejected("independent audit signature invalid") from None


def verify_live(*, manifest: dict, operator_profile: str, custody_profile: str,
                release_envelope: dict, custodian_public_key: bytes,
                custodian_public_key_sha256: str,
                auditor_signature_file: str | None = None,
                auditor_public_key_file: str | None = None,
                auditor_public_key_sha256: str | None = None,
                session_factory=None) -> dict:
    """Fail closed: only signed, re-fetched AWS evidence can yield HARDWARE PASS."""
    validate_manifest(manifest)
    if (not operator_profile or not custody_profile or
            operator_profile == custody_profile):
        raise ProofRejected("distinct AWS read-only profiles required")

    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    operator = session_factory(profile_name=operator_profile, region_name=_REGION)
    custody = session_factory(profile_name=custody_profile, region_name=_REGION)
    operator_id = operator.client("sts").get_caller_identity()
    custody_id = custody.client("sts").get_caller_identity()
    if (operator_id.get("Account") != manifest["workload_account"] or
            custody_id.get("Account") != manifest["custody_account"]):
        raise ProofRejected("AWS caller identities do not match manifest")

    # Re-verify the signed release AND current KMS policy/grants/task definition
    # by fetching both accounts read-only. Do not trust operator-authored JSON.
    from scripts.verify_confidential_release import check_release
    release = check_release(
        operator_profile=operator_profile, custody_profile=custody_profile,
        tenant=manifest["tenant"],
        task_definition_arn=manifest["task_definition_arn"],
        kms_key_arn=manifest["kms_key_arn"],
        pcr17=manifest["expected_pcr17"],
        image_sha256=manifest["image_sha256"],
        receipt=release_envelope,
        trusted_public_key_pem=custodian_public_key,
        trusted_public_key_sha256=custodian_public_key_sha256,
        check=True, session_factory=session_factory,
    )
    ecs = operator.client("ecs")
    # The actual task result is read from ECS; the task may not be inferred
    # from an independently submitted success flag.
    arn = manifest["task_arn"]
    cluster = arn.rsplit("/", 2)[1]
    tasks = ecs.describe_tasks(cluster=cluster, tasks=[arn]).get("tasks", [])
    if len(tasks) != 1:
        raise ProofRejected("ECS task not found")

    from scripts.confidential_pilot_run import outputs
    # Read-only CloudFormation stack lookup uses the trusted operator profile.
    stage = outputs(operator_profile,
                    "notarai-confidential-staging-" + manifest["tenant"])
    bucket = stage.get("BucketName")
    if not isinstance(bucket, str) or not bucket:
        raise ProofRejected("synthetic staging bucket unavailable")
    marker = f"kancelarie/{manifest['tenant']}/confidential-results/{manifest['job_id']}.json"
    # Read the tiny synthetic result marker and reject a success without
    # an explicit no-submit flag. No document, ciphertext or PII is read.
    obj = operator.client("s3").get_object(Bucket=bucket, Key=marker)
    if obj.get("ContentLength", 0) > 2048:
        raise ProofRejected("guest marker size invalid")
    with obj["Body"] as stream:
        try:
            marker_document = json.loads(stream.read(2049))
        except (ValueError, UnicodeDecodeError):
            raise ProofRejected("guest marker invalid") from None
    marker_exists = marker_document == {
        "version": 1, "job_id": manifest["job_id"],
        "status": "preview_completed", "fields_filled": 2,
        "submitted": False,
    }
    if not marker_exists:
        raise ProofRejected("guest result was not verified as no-submit")

    start = datetime.strptime(manifest["started_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc,
    ) - timedelta(minutes=2)
    end = datetime.strptime(manifest["ended_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc,
    ) + timedelta(minutes=2)
    workload_trail = PacedCloudTrail(operator.client("cloudtrail"))
    custody_trail = PacedCloudTrail(custody.client("cloudtrail"))
    ids = [manifest["positive_event_id"], *manifest["denied_event_ids"].values()]
    events = {event_id: _event(workload_trail, event_id, start, end)
              for event_id in ids}
    positive_shared = events[manifest["positive_event_id"]].get("sharedEventID")
    if not positive_shared:
        raise ProofRejected("cross-account correlation ID missing")
    # Caller and key owner have DIFFERENT event IDs: use exact sharedEventID
    # to locate the owner-side record, not a fabricated duplicate ID.
    response = custody_trail.lookup_events(
        LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "Decrypt"}],
        StartTime=start, EndTime=end, MaxResults=50,
    )
    counterpart = []
    for item in response.get("Events", []):
        candidate = json.loads(item["CloudTrailEvent"])
        if candidate.get("sharedEventID") == positive_shared:
            counterpart.append(candidate)
    next_token = response.get("NextToken")
    pages = 1
    while next_token and pages < 100:
        response = custody_trail.lookup_events(
            LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "Decrypt"}],
            StartTime=start, EndTime=end, MaxResults=50, NextToken=next_token,
        )
        for item in response.get("Events", []):
            candidate = json.loads(item["CloudTrailEvent"])
            if candidate.get("sharedEventID") == positive_shared:
                counterpart.append(candidate)
        next_token = response.get("NextToken")
        pages += 1
    if next_token or len(counterpart) != 1:
        raise ProofRejected("custody CloudTrail counterpart unavailable")

    payload = assemble_audit_payload(
        manifest=manifest, workload_events=events, custody_event=counterpart[0],
        task=tasks[0], release=release, result_marker_exists=marker_exists,
    )
    summary = {
        **blocked_result("independent_audit_signature_required"),
        "live_evidence_consistent": True,
        "evidence_sha256": evidence_sha256(payload),
        "audit_payload": payload,
        "audit_signature_protocol": "ECDSA-P256-SHA256-over-domain-separated-canonical-JSON",
    }
    if auditor_signature_file:
        if not auditor_public_key_file or not auditor_public_key_sha256:
            raise ProofRejected("auditor public key and out-of-band pin required")
        _verify_external_signature(payload, auditor_signature_file,
                                   auditor_public_key_file,
                                   auditor_public_key_sha256)
        # A signature over event IDs does not prove the attack preconditions.
        # In particular CloudTrail cannot independently show that a task was
        # launched *without* signed release, nor that an image was maliciously
        # changed. SEC-05/06 and a separately witnessed signed per-case runbook
        # are still necessary. Never turn this partial proof into hardware PASS.
        summary.update({
            "status": "BLOCKED",
            "reason": "six_live_attack_preconditions_not_independently_verified",
            "audit_signature_verified": True,
            "hardware_attestation_verified": False,
            "zero_operator_access_proven": False,
            "production_enabled": False,
        })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Offline manifest check; NEVER yields hardware PASS")
    parser.add_argument("--verify-live", action="store_true",
                        help="Read-only AWS audit; no resources created or modified")
    parser.add_argument("--manifest")
    parser.add_argument("--operator-profile")
    parser.add_argument("--custody-profile")
    parser.add_argument("--release-file")
    parser.add_argument("--custodian-public-key-file")
    parser.add_argument("--custodian-public-key-sha256")
    parser.add_argument("--auditor-signature-file")
    parser.add_argument("--auditor-public-key-file")
    parser.add_argument("--auditor-public-key-sha256")
    args = parser.parse_args()
    try:
        if args.verify_live == args.check:
            raise ProofRejected("specify exactly one of --check and --verify-live")
        if args.manifest:
            manifest = validate_manifest(_json(args.manifest))
        else:
            manifest = None
        if args.check:
            print(json.dumps(blocked_result("live_aws_trials_not_executed"),
                             sort_keys=True))
            return 2
        if not manifest or not all((
            args.operator_profile, args.custody_profile, args.release_file,
            args.custodian_public_key_file, args.custodian_public_key_sha256,
        )):
            raise ProofRejected("AWS audit inputs incomplete")
        result = verify_live(
            manifest=manifest,
            operator_profile=args.operator_profile,
            custody_profile=args.custody_profile,
            release_envelope=_json(args.release_file),
            custodian_public_key=_file(args.custodian_public_key_file),
            custodian_public_key_sha256=args.custodian_public_key_sha256,
            auditor_signature_file=args.auditor_signature_file,
            auditor_public_key_file=args.auditor_public_key_file,
            auditor_public_key_sha256=args.auditor_public_key_sha256,
        )
        # JSON contains only scoped synthetic IDs and sha digests, never raw
        # CloudTrail responses, credentials, plaintext or ciphertext.
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["hardware_attestation_verified"] else 2
    except Exception:
        print(json.dumps(blocked_result("proof_unavailable_or_rejected"),
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
