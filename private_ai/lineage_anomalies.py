"""Conservative gaps detector: reports missing evidence, never invents a leak.

No raw content, no URLs, no personal names. Only an already authorized
tenant-scoped projection may be analyzed. A gap means INSUFFICIENT EVIDENCE,
not proof of a security incident or proof that the action did not happen.
"""
from __future__ import annotations
from collections import defaultdict
from .lineage import LineageRecord, view_lineage
from .policy import Principal

CAP = 200


def find_gaps(*, principal: Principal, rows: list[LineageRecord], tenant_id: str) -> dict:
    authorized = view_lineage(principal=principal, rows=rows, tenant_id=tenant_id, limit=500)
    # Operate only on already authorized and allowlisted records.
    events = authorized["events"]
    by_request = defaultdict(list)
    for row in events:
        by_request[row["request_id"]].append(row)
    findings = []
    for request_id, steps in sorted(by_request.items()):
        actions = {e["action"] for e in steps}
        for event in steps:
            if event["action"] == "egress_blocked":
                findings.append({
                    "request_id": request_id, "asset_key": event["asset_key"],
                    "code": "EGRESS_POLICY_BLOCKED", "severity": "blocked",
                    "evidence_state": event["evidence_state"],
                })
            if event["evidence_state"] == "unknown":
                findings.append({
                    "request_id": request_id, "asset_key": event["asset_key"],
                    "code": "EVIDENCE_MISSING", "severity": "needs_review",
                    "evidence_state": "unknown",
                })
        if "inference" in actions and "access_granted" not in actions:
            findings.append({
                "request_id": request_id, "asset_key": steps[0]["asset_key"],
                "code": "AUTH_EVENT_NOT_OBSERVED", "severity": "needs_review",
                "evidence_state": "unknown",
            })
        if "deletion_requested" in actions and "deletion_confirmed" not in actions:
            findings.append({
                "request_id": request_id, "asset_key": steps[0]["asset_key"],
                "code": "DELETION_CONFIRMATION_NOT_OBSERVED", "severity": "needs_review",
                "evidence_state": "unknown",
            })
    return {
        "schema": "private-ai-lineage-gaps-v1",
        "tenant_id": tenant_id,
        "scope": authorized["read_scope"],
        "findings": findings[:CAP],
        "truncated": len(findings) > CAP or authorized["total_matching"] > authorized["returned"],
        "warning": "Gaps signal missing recorded evidence; they are not confirmed exfiltration.",
    }
