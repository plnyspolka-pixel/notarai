"""SEC-07: tie the positive hardware run to its six negative experiments.

V1 SEC-07 manifest conflates all six denial cases with KMS event IDs.
V2 correctly recognizes four KMS denials, ECS admission and custody gate.
A v1 negative matrix alone therefore CANNOT close K2/K6. This module binds
the positive v1 identifiers to v2 without trusting v1 negative assertions.

No AWS calls. Consistency is metadata only and always remains BLOCKED.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime

from confidential.nitro_hardware_proof import validate_manifest
from confidential.nitro_denial_matrix import (
    KMS_CASES, validate_matrix,
)


class ScopeBindingRejected(ValueError):
    """Do not print untrusted AWS/account/tenant data."""


_FIELDS = (
    "region", "tenant", "workload_account", "custody_account",
    "job_id", "image_sha256", "expected_pcr17",
    "started_at", "ended_at",
)


def bind_positive_negative_scope(*, positive: Mapping, negative: Mapping,
                                 now: datetime | None = None) -> dict:
    """Reject accidental deliberate cherry-picking across separate trials."""
    try:
        p = validate_manifest(positive, now=now)
        n = validate_matrix(negative, now=now)
    except (ValueError, TypeError, KeyError):
        raise ScopeBindingRejected("SEC-07 source evidence invalid") from None
    if (any(p[field] != n[field] for field in _FIELDS) or
            p["kms_key_arn"] != n["approved_kms_key_arn"]):
        raise ScopeBindingRejected("positive/negative experiments differ")
    event_ids = {
        n["trials"][case]["event_id"] for case in KMS_CASES
    }
    if p["positive_event_id"] in event_ids:
        raise ScopeBindingRejected("positive KMS event reused as negative")
    if (p["positive_event_id"] in p["denied_event_ids"].values() or
            len(event_ids) != len(KMS_CASES)):
        raise ScopeBindingRejected("non-distinct SEC-07 KMS event IDs")
    # Deliberately no use of the legacy v1 six-denial event IDs. In v2,
    # altered_image/unsigned_release MUST NOT masquerade as KMS events.
    scope = {
        "schema": "notarai.confidential.nitro-scope-binding.v1",
        "region": p["region"],
        "tenant": p["tenant"],
        "job_id": p["job_id"],
        "image_sha256": p["image_sha256"],
        "expected_pcr17": p["expected_pcr17"],
        "workload_account": p["workload_account"],
        "custody_account": p["custody_account"],
        "approved_kms_key_arn_sha256": hashlib.sha256(
            p["kms_key_arn"].encode("ascii")
        ).hexdigest(),
        "started_at": p["started_at"],
        "ended_at": p["ended_at"],
        "positive_event_id": p["positive_event_id"],
        "negative_kms_event_ids": {
            case: n["trials"][case]["event_id"]
            for case in sorted(KMS_CASES)
        },
        "early_boundaries": {
            "altered_image": "ecs_admission",
            "unsigned_release": "custodian_release_gate",
        },
    }
    encoded = json.dumps(
        scope, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    return {
        "status": "BLOCKED",
        "scope_consistent": True,
        "scope_sha256": hashlib.sha256(
            b"NotarAI:SEC-07:scope-binding:v1\x00" + encoded,
        ).hexdigest(),
        "hardware_attestation_verified": False,
        "negative_cases_independently_verified": False,
        "zero_operator_access_proven": False,
        "production_enabled": False,
        "reason": "matching_metadata_cannot_substitute_for_live_hardware",
    }
