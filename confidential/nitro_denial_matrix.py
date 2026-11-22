"""SEC-07: check *which* security boundary denied each Nitro test.

Four cases must produce real KMS Decrypt denials. An altered OCI image can be
rejected by ECS confidential container admission before it calls KMS, while
an unsigned release must be refused before ECS RunTask. Fabricating an
AccessDenied event for these two cases is not valid evidence.

This module checks structure and independently retrieved CloudTrail metadata.
Even a valid offline matrix remains BLOCKED until independently witnessed,
signed live evidence exists for all six attempts.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone

SCHEMA = "notarai.confidential.nitro-denial-matrix.v2"
CASES = (
    "ordinary_host",
    "wrong_pcr17",
    "altered_image",
    "cross_tenant_or_role",
    "unsigned_release",
    "wrong_key",
)
KMS_CASES = frozenset({
    "ordinary_host", "wrong_pcr17", "cross_tenant_or_role", "wrong_key",
})
EARLY_CASES = {
    "altered_image": "ecs_admission",
    "unsigned_release": "custodian_release_gate",
}
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_PCR = re.compile(r"[a-f0-9]{96}\Z")
_ACCOUNT = re.compile(r"[0-9]{12}\Z")
_UUID = re.compile(
    r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\Z"
)
_HEX32 = re.compile(r"[a-f0-9]{32}\Z")
_KMS = re.compile(
    r"arn:aws:kms:eu-central-1:(?P<account>[0-9]{12}):key/[a-zA-Z0-9-]+\Z"
)
_REGION = "eu-central-1"


class DenialEvidenceRejected(ValueError):
    """Deliberately generic; never disclose raw untrusted CloudTrail fields."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise DenialEvidenceRejected(reason)


def utc(value: object) -> datetime:
    require(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value,
    ) is not None, "UTC timestamp required")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc,
        )
    except ValueError:
        raise DenialEvidenceRejected("invalid UTC timestamp") from None


def validate_matrix(matrix: Mapping, *, now: datetime | None = None) -> dict:
    require(isinstance(matrix, dict) and set(matrix) == {
        "schema", "region", "tenant", "workload_account",
        "custody_account", "approved_kms_key_arn", "expected_pcr17",
        "image_sha256", "job_id", "started_at", "ended_at", "trials",
    }, "denial matrix shape invalid")
    require(matrix["schema"] == SCHEMA and matrix["region"] == _REGION,
            "denial matrix schema/region invalid")
    tenant, op, custody = (
        matrix["tenant"], matrix["workload_account"], matrix["custody_account"]
    )
    require(tenant in ("pilot01", "pilot02") and
            all(isinstance(a, str) and _ACCOUNT.fullmatch(a) for a in (op, custody))
            and op != custody,
            "synthetic tenant or account boundary invalid")
    key = matrix["approved_kms_key_arn"]
    match = _KMS.fullmatch(key) if isinstance(key, str) else None
    require(match is not None and match.group("account") == custody,
            "approved custody key ARN invalid")
    require(isinstance(matrix["expected_pcr17"], str) and
            _PCR.fullmatch(matrix["expected_pcr17"]) is not None and
            matrix["expected_pcr17"] != "0" * 96 and
            isinstance(matrix["image_sha256"], str) and
            _SHA.fullmatch(matrix["image_sha256"]) is not None and
            isinstance(matrix["job_id"], str) and
            _HEX32.fullmatch(matrix["job_id"]) is not None,
            "immutable measurement/job binding missing")
    start, end = utc(matrix["started_at"]), utc(matrix["ended_at"])
    current = now or datetime.now(timezone.utc)
    require(current.tzinfo is not None and start <= end <= current and
            (end - start).total_seconds() <= 7200 and
            (current - end).total_seconds() <= 89 * 86400,
            "denial experiment window invalid")
    trials = matrix["trials"]
    require(isinstance(trials, dict) and set(trials) == set(CASES),
            "exactly six negative trial cases required")
    events = []
    for name in CASES:
        trial = trials[name]
        require(isinstance(trial, dict) and
                set(trial) == {"boundary", "event_id", "receipt_sha256", "observed_at"},
                "negative trial metadata shape invalid")
        require(isinstance(trial["receipt_sha256"], str) and
                _SHA.fullmatch(trial["receipt_sha256"]) is not None and
                start <= utc(trial["observed_at"]) <= end,
                "negative trial independent receipt digest/time invalid")
        expected = "kms" if name in KMS_CASES else EARLY_CASES[name]
        require(trial["boundary"] == expected, "denial at wrong trust boundary")
        event_id = trial["event_id"]
        if name in KMS_CASES:
            require(isinstance(event_id, str) and _UUID.fullmatch(event_id) is not None,
                    "KMS denial EventId required")
            events.append(event_id)
        else:
            require(event_id is None, "prelaunch/admission denial cannot forge KMS EventId")
    require(len(set(events)) == 4, "KMS denial EventIds must be distinct")
    return dict(matrix)


def _caller_role(event: Mapping) -> str:
    identity = event.get("userIdentity") or {}
    if not isinstance(identity, Mapping):
        return ""
    issuer = (identity.get("sessionContext") or {}).get("sessionIssuer") or {}
    return issuer.get("arn", "") if isinstance(issuer, Mapping) else ""


def kms_receipt_sha256(case: str, event: Mapping) -> str:
    """Canonical digest of a whitelisted KMS log projection, with no PII/raw log.

    This is what the independent witness signs. A human-entered hash or a
    different CloudTrail event cannot be swapped in after the audit.
    """
    req = event.get("requestParameters") or {}
    recipient = (event.get("additionalEventData") or {}).get("recipient") or {}
    if not isinstance(req, Mapping) or not isinstance(recipient, Mapping):
        raise DenialEvidenceRejected("KMS receipt fields invalid")
    key = req.get("keyId")
    if not isinstance(key, str) or not _KMS.fullmatch(key):
        raise DenialEvidenceRejected("KMS key identity for receipt invalid")
    projection = {
        "schema": "notarai.confidential.kms-denial-receipt.v1",
        "case": case,
        "event_id": event.get("eventID"),
        "request_id": event.get("requestID"),
        "event_time": event.get("eventTime"),
        "caller_account": (event.get("userIdentity") or {}).get("accountId"),
        "caller_role": _caller_role(event),
        "key_arn_sha256": hashlib.sha256(key.encode("ascii")).hexdigest(),
        "error_code": event.get("errorCode"),
        "recipient_module_present": bool(recipient.get("attestationDocumentModuleId")),
        "recipient_pcr17": recipient.get("attestationDocumentEnclavePCR17"),
    }
    return hashlib.sha256(json.dumps(
        projection, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def inspect_kms_denial(case: str, event: Mapping, matrix: Mapping) -> dict:
    """Validate observed KMS request semantics, not just a case label."""
    validate_matrix(matrix)
    require(case in KMS_CASES and isinstance(event, dict),
            "KMS test case or event invalid")
    trial = matrix["trials"][case]
    require(event.get("eventID") == trial["event_id"] and
            event.get("eventName") == "Decrypt" and
            event.get("eventSource") == "kms.amazonaws.com" and
            event.get("awsRegion") == _REGION and
            event.get("responseElements") is None and
            (event.get("userIdentity") or {}).get("accountId") ==
            matrix["workload_account"] and
            utc(matrix["started_at"]) <= utc(event.get("eventTime")) <=
            utc(matrix["ended_at"]),
            "KMS denial does not match independently recorded AWS event")
    require(isinstance(event.get("requestID"), str) and
            _UUID.fullmatch(event["requestID"]) is not None,
            "KMS requestID missing or invalid")
    code = event.get("errorCode")
    errors = {"accessdeniedexception", "accessdenied", "accessdeniedexceptionv2"}
    if case == "wrong_key":
        errors |= {"incorrectkeyexception", "invalidciphertextexception"}
    require(isinstance(code, str) and code.lower() in errors,
            "negative KMS call was not denied with an expected error")

    key_id = (event.get("requestParameters") or {}).get("keyId")
    allowed = matrix["approved_kms_key_arn"]
    key_match = _KMS.fullmatch(key_id) if isinstance(key_id, str) else None
    require(key_match is not None, "negative test key ARN missing")
    if case == "wrong_key":
        require(key_id != allowed and
                key_match.group("account") == matrix["custody_account"],
                "wrong-key test did not target an independent custody key")
    else:
        require(key_id == allowed, "unapproved KMS request key for negative test")

    recipient = ((event.get("additionalEventData") or {}).get("recipient"))
    role = _caller_role(event)
    current_role = (
        f"arn:aws:iam::{matrix['workload_account']}:role/"
        f"notarai-confidential-{matrix['tenant']}"
    )
    if case == "ordinary_host":
        require(not recipient and role == current_role,
                "ordinary-host test must have no signed NSM Recipient")
    elif case == "wrong_pcr17":
        require(isinstance(recipient, dict) and
                bool(recipient.get("attestationDocumentModuleId")) and
                isinstance(recipient.get("attestationDocumentEnclavePCR17"), str) and
                _PCR.fullmatch(recipient["attestationDocumentEnclavePCR17"]) is not None and
                recipient["attestationDocumentEnclavePCR17"].lower() !=
                matrix["expected_pcr17"],
                "wrong-PCR test did not present a distinct signed measurement")
        require(role == current_role, "wrong-PCR test used an unapproved role")
    elif case == "cross_tenant_or_role":
        other = "pilot02" if matrix["tenant"] == "pilot01" else "pilot01"
        alternative = (
            f"arn:aws:iam::{matrix['workload_account']}:role/"
            f"notarai-confidential-{other}"
        )
        require(role == alternative, "cross-tenant test did not use the other tenant role")
    elif case == "wrong_key":
        require(role == current_role, "wrong-key test role must be task role")
    receipt_digest = kms_receipt_sha256(case, event)
    require(receipt_digest == trial["receipt_sha256"],
            "KMS CloudTrail metadata differs from independently pinned receipt")
    return {
        "case": case,
        "boundary": "kms",
        "event_id": event["eventID"],
        "error_code": code,
        "precondition_observed": True,
        "receipt_sha256": receipt_digest,
    }


def inspect_early_denial_receipt(case: str, receipt: Mapping,
                                 matrix: Mapping) -> dict:
    """Witness metadata check; cannot independently establish absence of calls."""
    validate_matrix(matrix)
    require(case in EARLY_CASES and isinstance(receipt, dict) and set(receipt) == {
        "schema", "case", "tenant", "job_id", "observed_at",
        "boundary", "result", "image_sha256",
        "run_task_count", "kms_decrypt_count", "observation_sha256",
        "ecs_task_arn",
    }, "early denial receipt shape invalid")
    trial = matrix["trials"][case]
    require(receipt["schema"] == "notarai.confidential.nitro-denial-receipt.v1"
            and receipt["case"] == case and receipt["tenant"] == matrix["tenant"]
            and receipt["job_id"] == matrix["job_id"]
            and receipt["observed_at"] == trial["observed_at"]
            and receipt["boundary"] == trial["boundary"]
            and receipt["result"] == "DENIED"
            and isinstance(receipt["observation_sha256"], str) and
            _SHA.fullmatch(receipt["observation_sha256"]) is not None
            and receipt["kms_decrypt_count"] == 0
            and type(receipt["kms_decrypt_count"]) is int,
            "early refusal proof has wrong binding/outcome")
    if case == "unsigned_release":
        require(receipt["run_task_count"] == 0 and
                type(receipt["run_task_count"]) is int and
                receipt["ecs_task_arn"] is None and
                receipt["image_sha256"] == matrix["image_sha256"],
                "unsigned release must stop before ECS RunTask")
    else:
        arn = receipt["ecs_task_arn"]
        require(type(receipt["run_task_count"]) is int and
                receipt["run_task_count"] == 1 and
                isinstance(arn, str) and
                re.fullmatch(
                    rf"arn:aws:ecs:{_REGION}:{matrix['workload_account']}:task/"
                    r"notarai-confidential-shared/[a-f0-9]{32}", arn,
                ) is not None and
                isinstance(receipt["image_sha256"], str) and
                _SHA.fullmatch(receipt["image_sha256"]) is not None and
                receipt["image_sha256"] != matrix["image_sha256"],
                "altered image must start one different task for ECS admission test")
    # This SHA is what an independent witness must sign/store outside NotarAI.
    # Operator-authored JSON alone must never turn this into hardware PASS.
    digest = hashlib.sha256(json.dumps(receipt, sort_keys=True,
                separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    require(digest == trial["receipt_sha256"],
            "independent denial receipt hash does not match")
    return {
        "case": case, "boundary": trial["boundary"], "result": "DENIED",
        "receipt_sha256": digest, "evidence_status": "STRUCTURALLY_VALID_ONLY",
    }


def inspect_altered_image_ecs(*, task: Mapping, task_definition: Mapping,
                              receipt: Mapping, matrix: Mapping) -> dict:
    """Re-fetch a stopped ECS task and candidate image from AWS read-only.

    An arbitrary failed app process is not an admission-policy rejection.
    We require the sandbox to report policy/authorization rejection; an
    ambiguous ECS stop reason is BLOCKED for later independent inspection.
    """
    inspect_early_denial_receipt("altered_image", receipt, matrix)
    require(isinstance(task, dict) and isinstance(task_definition, dict) and
            task.get("taskArn") == receipt["ecs_task_arn"] and
            task.get("lastStatus") == "STOPPED" and
            task.get("taskDefinitionArn") ==
            task_definition.get("taskDefinitionArn") and
            (task.get("trustedExecutionSummary") or {}).get("isolationMode") ==
            "CONFIDENTIAL_SANDBOX",
            "altered-image ECS confidential task was not stopped as expected")
    containers = task.get("containers") or []
    require(isinstance(containers, list) and not any(
        isinstance(c, dict) and c.get("exitCode") == 0 for c in containers
    ), "altered-image task completed successfully rather than being denied")
    reason = task.get("stoppedReason")
    require(isinstance(reason, str) and any(
        word in reason.lower() for word in (
            "policy", "denied", "not authorized", "unauthorized",
        )
    ), "ECS stop did not confirm admission policy or authorization rejection")
    definitions = task_definition.get("containerDefinitions") or []
    require(isinstance(definitions, list) and len(definitions) == 1 and
            definitions[0].get("name") == "confidential-browser" and
            isinstance(definitions[0].get("image"), str) and
            definitions[0]["image"].endswith(
                "@sha256:" + receipt["image_sha256"]
            ),
            "ECS candidate image is not the witnessed altered digest")
    require(task_definition.get("taskRoleArn") ==
            (f"arn:aws:iam::{matrix['workload_account']}:role/"
             f"notarai-confidential-{matrix['tenant']}"),
            "altered-image test did not use approved task role")
    return {
        "case": "altered_image",
        "boundary": "ecs_admission",
        "ecs_metadata_observed": True,
        "receipt_sha256": matrix["trials"]["altered_image"]["receipt_sha256"],
        "hardware_attestation_verified": False,
    }


def incomplete_audit_result() -> dict:
    return {
        "status": "BLOCKED",
        "hardware_attestation_verified": False,
        "negative_cases_independently_verified": False,
        "production_enabled": False,
        "reason": "independent_witness_and_live_aws_evidence_required",
    }
