"""Privacy-minimized evidence-aware data lineage projection for Private AI.

This is NOT a running API or a production data store. Only server-minted,
strictly allowlisted metadata passes the projection boundary. The
evidence_state is a descriptive OBSERVATION, not a cryptographic attestation.
No stored content, filenames, PESEL, free text, user emails or source URLs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Iterable

from .policy import PolicyDenied, Principal

KEY = re.compile(r"^[a-zA-Z0-9_-]{3,64}$")
UTC_ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$")


class Origin(str, Enum):
    CLIENT_PORTAL = "client_portal"
    PRIVATE_API = "private_api"
    TENANT_VAULT = "tenant_vault"
    SCHEDULED_JOB = "scheduled_job"
    CONNECTOR = "connector"


class Action(str, Enum):
    RECEIVED = "received"
    CLASSIFIED = "classified"
    ACCESS_GRANTED = "access_granted"
    INFERENCE = "inference"
    STORED = "stored"
    EGRESS_BLOCKED = "egress_blocked"
    DELETION_REQUESTED = "deletion_requested"
    DELETION_CONFIRMED = "deletion_confirmed"


class Destination(str, Enum):
    POLICY_GATE = "policy_gate"
    TENANT_VAULT = "tenant_vault"
    EU_BEDROCK = "eu_bedrock"
    AUDIT_STORE = "audit_store"
    DENIED = "denied"
    NONE = "none"


class EvidenceState(str, Enum):
    OBSERVED = "observed"
    DECLARED = "declared"
    UNKNOWN = "unknown"


class Result(str, Enum):
    ACCEPTED = "accepted"
    SUCCESS = "success"
    BLOCKED = "blocked"
    ERROR = "error"
    PENDING = "pending"


@dataclass(frozen=True)
class LineageRecord:
    tenant_id: str
    event_id: str
    asset_key: str
    actor_key: str
    agent_key: str
    request_id: str
    timestamp_utc: str
    origin: Origin
    action: Action
    destination: Destination
    result: Result
    evidence_state: EvidenceState
    eu_region: str | None = None
    # Opaque trace/certificate identifier, NOT a signature verification status.
    trace_key: str | None = None


def _check(record: LineageRecord) -> None:
    if not isinstance(record, LineageRecord):
        raise PolicyDenied("Invalid lineage data type")
    for field in ("tenant_id", "event_id", "asset_key", "actor_key", "agent_key", "request_id"):
        value = getattr(record, field)
        if not isinstance(value, str) or not KEY.fullmatch(value):
            raise PolicyDenied("Nonopaque identifier or unapproved metadata")
    if not isinstance(record.timestamp_utc, str) or not UTC_ISO.fullmatch(record.timestamp_utc):
        raise PolicyDenied("Invalid UTC timestamp")
    try:
        d = datetime.fromisoformat(record.timestamp_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PolicyDenied("Invalid timestamp") from exc
    if d.tzinfo != timezone.utc:
        raise PolicyDenied("Timezone must be UTC")
    for field, typ in (("origin", Origin), ("action", Action), ("destination", Destination),
                       ("result", Result), ("evidence_state", EvidenceState)):
        if not isinstance(getattr(record, field), typ):
            raise PolicyDenied("Unexpected lineage state or free text")
    if record.eu_region is not None and record.eu_region not in {
        "eu-central-1", "eu-west-1", "eu-west-3", "eu-north-1", "eu-south-1", "eu-south-2"
    }:
        raise PolicyDenied("Unreviewed region")
    if record.trace_key is not None and (
        not isinstance(record.trace_key, str) or not KEY.fullmatch(record.trace_key)
    ):
        raise PolicyDenied("Trace contains unapproved data")
    if record.action is Action.EGRESS_BLOCKED and (
        record.result is not Result.BLOCKED or record.destination is not Destination.DENIED
    ):
        raise PolicyDenied("Contradictory blocked event")
    if record.action is Action.INFERENCE and record.destination is Destination.EU_BEDROCK:
        if record.eu_region is None:
            raise PolicyDenied("Model routing cannot omit region")


def serialize_record(record: LineageRecord) -> dict:
    _check(record)
    data = asdict(record)
    for k in ("origin", "action", "destination", "result", "evidence_state"):
        data[k] = getattr(record, k).value
    return data


def view_lineage(
    *, principal: Principal, rows: Iterable[LineageRecord], tenant_id: str,
    asset_key: str | None = None, limit: int = 200,
) -> dict:
    """Called ONLY from server-verified context, never an untrusted LLM request.

    Tenant isolation and view scope are decided by trusted Principal. A "read"
    principal may view the whole tenant; an "own" principal only its own actor
    pseudonym. Agent identity with neither capability cannot inspect this.
    """
    if (not isinstance(principal, Principal) or not principal.active or
        principal.tenant_id != tenant_id or not principal.subject):
        raise PolicyDenied("No tenant authorization")
    all_access = "private_ai:lineage:read" in principal.scopes
    own_access = "private_ai:lineage:own" in principal.scopes
    if not (all_access or own_access):
        raise PolicyDenied("No lineage viewing capability")
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise PolicyDenied("Invalid viewing limit")
    if asset_key is not None and (not isinstance(asset_key, str) or not KEY.fullmatch(asset_key)):
        raise PolicyDenied("Unapproved asset filter")
    events = []
    for record in rows:
        # Strict validation BEFORE any projection; do not silently accept raw data.
        _check(record)
        if record.tenant_id != tenant_id:
            continue
        if not all_access and record.actor_key != principal.subject:
            continue
        if asset_key is not None and record.asset_key != asset_key:
            continue
        events.append(serialize_record(record))
    events.sort(key=lambda x: (x["timestamp_utc"], x["event_id"]), reverse=True)
    selected = events[:limit]
    return {
        "schema": "private-ai-lineage-view-v1",
        "tenant_id": tenant_id,
        "read_scope": "tenant" if all_access else "actor",
        "total_matching": len(events),
        "returned": len(selected),
        "events": selected,
        "metrics": {
            "blocked": sum(e["result"] == "blocked" for e in events),
            "errors": sum(e["result"] == "error" for e in events),
            "unknown_evidence": sum(e["evidence_state"] == "unknown" for e in events),
        },
        "note": "evidence_state is descriptive, not an independent security attestation",
    }
