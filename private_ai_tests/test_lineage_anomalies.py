"""No cross-tenant leaks, conservative alerting and no fabricated incident claims."""
import json
import unittest
from dataclasses import replace

from private_ai.lineage import Action, Destination, EvidenceState, Result
from private_ai.lineage_anomalies import find_gaps
from private_ai.policy import Principal, PolicyDenied
from test_lineage import record


class AnomalyTests(unittest.TestCase):
    def setUp(self):
        self.auditor = Principal("auditor_001", "tenant_alpha", frozenset({"private_ai:lineage:read"}))

    def test_missing_auth_event_is_gap_not_proven_exfiltration(self):
        result = find_gaps(principal=self.auditor, tenant_id="tenant_alpha", rows=[record()])
        self.assertIn("AUTH_EVENT_NOT_OBSERVED", [x["code"] for x in result["findings"]])
        self.assertIn("not confirmed exfiltration", result["warning"])

    def test_authorized_flow_does_not_generate_false_auth_gap(self):
        granted = record(event_id="event_002", action=Action.ACCESS_GRANTED,
                         destination=Destination.POLICY_GATE)
        result = find_gaps(principal=self.auditor, tenant_id="tenant_alpha",
                           rows=[granted, record()])
        self.assertNotIn("AUTH_EVENT_NOT_OBSERVED", [x["code"] for x in result["findings"]])

    def test_blocked_egress_explicit(self):
        row = record(action=Action.EGRESS_BLOCKED, destination=Destination.DENIED,
                     result=Result.BLOCKED)
        result = find_gaps(principal=self.auditor, tenant_id="tenant_alpha", rows=[row])
        self.assertIn("EGRESS_POLICY_BLOCKED", [x["code"] for x in result["findings"]])

    def test_pending_deletion_confirmation(self):
        row = record(action=Action.DELETION_REQUESTED, destination=Destination.TENANT_VAULT)
        result = find_gaps(principal=self.auditor, tenant_id="tenant_alpha", rows=[row])
        self.assertIn("DELETION_CONFIRMATION_NOT_OBSERVED",
                      [x["code"] for x in result["findings"]])

    def test_unknown_evidence_explicit(self):
        row = record(evidence_state=EvidenceState.UNKNOWN)
        result = find_gaps(principal=self.auditor, tenant_id="tenant_alpha", rows=[row])
        self.assertIn("EVIDENCE_MISSING", [x["code"] for x in result["findings"]])

    def test_other_tenant_is_not_visible_even_in_count(self):
        row = record(tenant_id="tenant_beta", event_id="event_991")
        result = find_gaps(principal=self.auditor, tenant_id="tenant_alpha", rows=[row])
        self.assertEqual(result["findings"], [])
        self.assertNotIn("tenant_beta", json.dumps(result))

    def test_wrong_tenant_principal_denied(self):
        with self.assertRaises(PolicyDenied):
            find_gaps(principal=self.auditor, tenant_id="tenant_beta", rows=[])

    def test_operator_own_scope_does_not_inherit_other_actors(self):
        owner = Principal("user_001", "tenant_alpha", frozenset({"private_ai:lineage:own"}))
        rows = [record(actor_key="user_002", action=Action.EGRESS_BLOCKED,
                       result=Result.BLOCKED, destination=Destination.DENIED)]
        result = find_gaps(principal=owner, tenant_id="tenant_alpha", rows=rows)
        self.assertEqual(result["findings"], [])
