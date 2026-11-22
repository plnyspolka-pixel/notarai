"""SEC-07: fail-closed, metadata-only verifier for an AWS Nitro hardware test.

Offline fixtures can test the verifier but NEVER establish hardware proof.
Actual events must be fetched by an independent auditor from AWS, not submitted
as trusted operator JSON. No decrypt operation is made by this module.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from collections.abc import Mapping

SCHEMA = "notarai.confidential.nitro-hardware-evidence.v1"
DENIAL_CASES = (
    "ordinary_host",
    "wrong_pcr17",
    "altered_image",
    "cross_tenant_or_role",
    "unsigned_release",
    "wrong_key",
)
_ACCOUNT = re.compile(r"[0-9]{12}\Z")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_PCR = re.compile(r"[a-f0-9]{96}\Z")
_UUID = re.compile(r"[a-f0-9-]{36}\Z")
_HEX32 = re.compile(r"[a-f0-9]{32}\Z")
_REGION = "eu-central-1"
_DOMAIN = b"NotarAI:SEC-07:hardware-audit:v1\x00"


class ProofRejected(ValueError):
    """An evidence predicate was not satisfied; no untrusted data in messages."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ProofRejected(reason)


def canonical_bytes(document: Mapping) -> bytes:
    return _DOMAIN + json.dumps(
        document, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")


def evidence_sha256(document: Mapping) -> str:
    return hashlib.sha256(canonical_bytes(document)).hexdigest()


def _timestamp(value: object) -> datetime:
    require(isinstance(value, str) and
            re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is not None,
            "invalid UTC timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc,
        )
    except ValueError:
        raise ProofRejected("invalid UTC timestamp") from None


def validate_manifest(manifest: Mapping, *, now: datetime | None = None) -> dict:
    required = {
        "schema", "region", "tenant", "workload_account", "custody_account",
        "task_definition_arn", "task_arn", "kms_key_arn", "image_sha256",
        "expected_pcr17", "job_id", "positive_event_id", "denied_event_ids",
        "started_at", "ended_at",
    }
    require(isinstance(manifest, dict) and set(manifest) == required,
            "evidence manifest must have exact fields")
    require(manifest["schema"] == SCHEMA and manifest["region"] == _REGION,
            "unapproved schema or region")
    tenant = manifest["tenant"]
    workload = manifest["workload_account"]
    custody = manifest["custody_account"]
    require(isinstance(tenant, str) and
            re.fullmatch(r"pilot0[12]", tenant) is not None,
            "only synthetic pilot01 and pilot02 are allowed")
    require(all(isinstance(a, str) and _ACCOUNT.fullmatch(a)
                for a in (workload, custody)) and workload != custody,
            "custody and workload accounts must be distinct")
    require(isinstance(manifest["image_sha256"], str) and
            _SHA256.fullmatch(manifest["image_sha256"]) is not None,
            "image digest must be pinned")
    require(isinstance(manifest["expected_pcr17"], str) and
            _PCR.fullmatch(manifest["expected_pcr17"]) is not None and
            manifest["expected_pcr17"] != "0" * 96,
            "PCR17 must be pinned and nonzero")
    require(isinstance(manifest["job_id"], str) and
            _HEX32.fullmatch(manifest["job_id"]) is not None,
            "synthetic job ID invalid")
    prefix = f"notarai-confidential-{tenant}"
    require(manifest["task_definition_arn"].startswith(
        f"arn:aws:ecs:{_REGION}:{workload}:task-definition/{prefix}:"
    ) and manifest["task_definition_arn"].rsplit(":", 1)[-1].isdigit(),
            "task definition is not pinned")
    require(isinstance(manifest["task_arn"], str) and
            re.fullmatch(
                rf"arn:aws:ecs:{_REGION}:{workload}:task/"
                r"[A-Za-z0-9_-]+/[a-f0-9]{32}",
                manifest["task_arn"],
            ) is not None, "ECS task ARN invalid")
    require(isinstance(manifest["kms_key_arn"], str) and
            re.fullmatch(
                rf"arn:aws:kms:{_REGION}:{custody}:key/[a-zA-Z0-9-]+",
                manifest["kms_key_arn"],
            ) is not None, "external KMS ARN invalid")
    denials = manifest["denied_event_ids"]
    require(isinstance(denials, dict) and set(denials) == set(DENIAL_CASES),
            "exactly six required denial cases")
    ids = [manifest["positive_event_id"], *denials.values()]
    require(all(isinstance(v, str) and _UUID.fullmatch(v) for v in ids)
            and len(ids) == len(set(ids)),
            "CloudTrail IDs missing or reused")
    start = _timestamp(manifest["started_at"])
    end = _timestamp(manifest["ended_at"])
    instant = now or datetime.now(timezone.utc)
    require(instant.tzinfo is not None and start <= end <= instant and
            (end - start).total_seconds() <= 7200 and
            (instant - end).total_seconds() <= 86400 * 89,
            "hardware test time window invalid or stale")
    return dict(manifest)


def check_cloudtrail_event(event: Mapping, *, manifest: Mapping,
                           event_id: str, accepted: bool,
                           case: str | None = None) -> dict:
    """Accept only AWS KMS events fetched independently, never event claims."""
    require(isinstance(event, dict) and
            event.get("eventID") == event_id and
            event.get("eventSource") == "kms.amazonaws.com" and
            event.get("eventName") == "Decrypt" and
            event.get("awsRegion") == _REGION,
            "KMS event identity mismatch")
    key_id = (event.get("requestParameters") or {}).get("keyId")
    if case == "wrong_key":
        # This negative test MUST use a different key, not a denial
        # on the approved key mislabeled as a wrong-key attack.
        require(isinstance(key_id, str) and key_id != manifest["kms_key_arn"]
                and key_id.startswith(
                    f"arn:aws:kms:{_REGION}:{manifest['custody_account']}:key/"),
                "wrong-key trial did not use a different custody key")
    else:
        require(key_id == manifest["kms_key_arn"], "KMS key mismatch")
    require(event.get("responseElements") is None,
            "unexpected KMS response data in CloudTrail")
    event_time = _timestamp(event.get("eventTime"))
    start = _timestamp(manifest["started_at"])
    end = _timestamp(manifest["ended_at"])
    require(start <= event_time <= end, "KMS event outside signed run window")
    account = (event.get("userIdentity") or {}).get("accountId")
    require(account == manifest["workload_account"],
            "KMS caller must be from workload account")
    if accepted:
        require(not event.get("errorCode"), "positive KMS operation denied")
        recipient = ((event.get("additionalEventData") or {}).get("recipient") or {})
        require(isinstance(recipient, dict) and
                bool(recipient.get("attestationDocumentModuleId")) and
                recipient.get("attestationDocumentEnclavePCR17", "").lower() ==
                manifest["expected_pcr17"],
                "NSM PCR17 not attested in KMS event")
        return {"event_id": event_id, "kms_result": "ALLOW",
                "pcr17": manifest["expected_pcr17"]}
    error = event.get("errorCode")
    require(isinstance(error, str) and
            (error.lower().startswith("accessdenied") or
             error.lower() in ("notfoundexception", "kmsinvalidstateexception")),
            "negative attempt did not produce a KMS denial")
    return {"event_id": event_id, "kms_result": "DENY"}


def check_cross_account_pair(workload_event: Mapping,
                             custody_event: Mapping, manifest: Mapping) -> None:
    """A successful cross-account KMS call is logged in BOTH accounts."""
    require(isinstance(custody_event, dict) and
            workload_event.get("sharedEventID") and
            workload_event.get("sharedEventID") == custody_event.get("sharedEventID") and
            workload_event.get("eventID") != custody_event.get("eventID") and
            custody_event.get("recipientAccountId") == manifest["custody_account"] and
            custody_event.get("eventSource") == "kms.amazonaws.com" and
            custody_event.get("eventName") == "Decrypt" and
            custody_event.get("requestParameters", {}).get("keyId") ==
            manifest["kms_key_arn"] and not custody_event.get("errorCode"),
            "independent custody-account CloudTrail counterpart missing")


def check_ecs_task(task: Mapping, manifest: Mapping) -> None:
    require(isinstance(task, dict) and
            task.get("taskArn") == manifest["task_arn"] and
            task.get("taskDefinitionArn") == manifest["task_definition_arn"] and
            task.get("lastStatus") == "STOPPED" and
            (task.get("trustedExecutionSummary") or {}).get("isolationMode") ==
            "CONFIDENTIAL_SANDBOX" and
            (task.get("trustedExecutionSummary") or {}).get(
                "attestationPolicyStatus") == "CONFIGURED",
            "ECS task was not a verified confidential task")
    containers = task.get("containers")
    require(isinstance(containers, list) and len(containers) == 1 and
            containers[0].get("name") == "confidential-browser" and
            containers[0].get("exitCode") == 0,
            "guest workload did not finish successfully")


def assemble_audit_payload(*, manifest: Mapping, workload_events: Mapping,
                           custody_event: Mapping, task: Mapping,
                           release: Mapping, result_marker_exists: bool) -> dict:
    """Pure verifier. Returned data is NOT independently authenticated."""
    validate_manifest(manifest)
    require(isinstance(release, dict) and
            release.get("independent_release_signature_verified") is True and
            release.get("static_configuration_verified") is True and
            release.get("tenant") == manifest["tenant"] and
            release.get("kms_key_arn") == manifest["kms_key_arn"] and
            release.get("task_definition_arn") == manifest["task_definition_arn"] and
            release.get("expected_pcr17") == manifest["expected_pcr17"] and
            release.get("image_sha256") == manifest["image_sha256"],
            "independent release verification missing")
    require(result_marker_exists is True, "synthetic guest result not recorded")
    check_ecs_task(task, manifest)
    require(isinstance(workload_events, Mapping) and
            set(workload_events) == {
                manifest["positive_event_id"], *manifest["denied_event_ids"].values()
            }, "AWS CloudTrail evidence incomplete")
    positive = workload_events[manifest["positive_event_id"]]
    accepted = check_cloudtrail_event(
        positive, manifest=manifest, event_id=manifest["positive_event_id"],
        accepted=True,
    )
    check_cross_account_pair(positive, custody_event, manifest)
    denials = {}
    for case in DENIAL_CASES:
        event_id = manifest["denied_event_ids"][case]
        denials[case] = check_cloudtrail_event(
            workload_events[event_id], manifest=manifest,
            event_id=event_id, accepted=False, case=case,
        )
    return {
        "schema": SCHEMA,
        "region": _REGION,
        "tenant": manifest["tenant"],
        "workload_account": manifest["workload_account"],
        "custody_account": manifest["custody_account"],
        "job_id": manifest["job_id"],
        "task_definition_arn": manifest["task_definition_arn"],
        "task_arn": manifest["task_arn"],
        "image_sha256": manifest["image_sha256"],
        "expected_pcr17": manifest["expected_pcr17"],
        "kms_key_arn_sha256": hashlib.sha256(
            manifest["kms_key_arn"].encode("ascii")
        ).hexdigest(),
        "key_policy_sha256": release["key_policy_sha256"],
        "task_definition_sha256": release["task_definition_sha256"],
        "custodian_public_key_sha256": release["custody_public_key_sha256"],
        "started_at": manifest["started_at"],
        "ended_at": manifest["ended_at"],
        "positive": accepted,
        "denials": denials,
        "custody_cloudtrail_event_id": custody_event["eventID"],
        "guest_result_marker": True,
        "auto_submit": False,
        "auto_sign": False,
    }


def blocked_result(reason: str = "live_aws_and_independent_signature_required") -> dict:
    """No fixture, mock, static CI or dry-run may assert a hardware PASS."""
    return {
        "status": "BLOCKED", "reason": reason,
        "hardware_attestation_verified": False,
        "zero_operator_access_proven": False,
        "production_enabled": False,
    }
