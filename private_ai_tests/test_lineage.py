"""Adversarial test suite for metadata-only lineage and tenant-scoped projection."""
import json
import unittest
from dataclasses import replace

from private_ai.lineage import (
    Action, Destination, EvidenceState, LineageRecord, Origin, Result,
    serialize_record, view_lineage,
)
from private_ai.policy import PolicyDenied, Principal


def record(**overrides):
    fields = dict(
        tenant_id="tenant_alpha", event_id="event_001", asset_key="asset_001",
        actor_key="user_001", agent_key="agent_ocr", request_id="req_00001",
        timestamp_utc="2026-11-16T12:00:00Z", origin=Origin.CLIENT_PORTAL,
        action=Action.INFERENCE, destination=Destination.EU_BEDROCK,
        result=Result.SUCCESS, evidence_state=EvidenceState.OBSERVED,
        eu_region="eu-central-1", trace_key="trace_001",
    )
    fields.update(overrides)
    return LineageRecord(**fields)


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.auditor = Principal("auditor_001", "tenant_alpha", frozenset({"private_ai:lineage:read"}))
        self.user = Principal("user_001", "tenant_alpha", frozenset({"private_ai:lineage:own"}))
        self.rows = [
            record(),
            record(event_id="event_002", actor_key="user_002", action=Action.EGRESS_BLOCKED,
                   destination=Destination.DENIED, result=Result.BLOCKED),
            record(tenant_id="tenant_beta", event_id="event_003",
                   actor_key="user_001", asset_key="asset_002"),
        ]

    def test_tenant_auditor(self):
        view = view_lineage(principal=self.auditor, rows=self.rows, tenant_id="tenant_alpha")
        self.assertEqual(view["total_matching"], 2)
        self.assertEqual(view["metrics"]["blocked"], 1)
        self.assertNotIn("tenant_beta", json.dumps(view))

    def test_user_sees_only_own_event(self):
        view = view_lineage(principal=self.user, rows=self.rows, tenant_id="tenant_alpha")
        self.assertEqual(view["returned"], 1)
        self.assertEqual(view["events"][0]["actor_key"], "user_001")

    def test_cross_tenant_is_denied(self):
        with self.assertRaises(PolicyDenied):
            view_lineage(principal=self.auditor, rows=self.rows, tenant_id="tenant_beta")

    def test_agent_has_no_view_permission(self):
        p = Principal("agent_ocr", "tenant_alpha", frozenset({"private_ai:invoke"}))
        with self.assertRaises(PolicyDenied):
            view_lineage(principal=p, rows=self.rows, tenant_id="tenant_alpha")

    def test_inactive_viewer_denied(self):
        with self.assertRaises(PolicyDenied):
            view_lineage(principal=replace(self.auditor, active=False),
                         rows=self.rows, tenant_id="tenant_alpha")

    def test_raw_filename_or_email_denied(self):
        for name in ("Jan Kowalski.pdf", "someone@example.org", "PESEL 12345678901"):
            with self.subTest(name=name), self.assertRaises(PolicyDenied):
                serialize_record(record(asset_key=name))

    def test_free_text_destination_denied(self):
        with self.assertRaises(PolicyDenied):
            serialize_record(record(destination="https://external-host.test/secret"))

    def test_unknown_provenance_visible_as_unknown_not_verified(self):
        event = record(evidence_state=EvidenceState.UNKNOWN)
        view = view_lineage(principal=self.auditor, rows=[event], tenant_id="tenant_alpha")
        self.assertEqual(view["metrics"]["unknown_evidence"], 1)

    def test_no_model_inference_without_region(self):
        with self.assertRaises(PolicyDenied):
            serialize_record(record(eu_region=None))

    def test_blocked_requires_denied_destination(self):
        with self.assertRaises(PolicyDenied):
            serialize_record(record(action=Action.EGRESS_BLOCKED, destination=Destination.EU_BEDROCK))

    def test_asset_filter(self):
        view = view_lineage(principal=self.auditor, rows=self.rows,
                            tenant_id="tenant_alpha", asset_key="asset_001")
        self.assertEqual(view["returned"], 2)

    def test_no_content_fields_in_view(self):
        fields = json.dumps(view_lineage(
            principal=self.auditor, rows=self.rows, tenant_id="tenant_alpha"))
        for forbidden in ("filename", "email", "prompt", "document_content",
                          "pesel", "document_url", "signed_url"):
            self.assertNotIn(forbidden, fields)

    def test_invalid_timestamp(self):
        with self.assertRaises(PolicyDenied):
            serialize_record(record(timestamp_utc="2026-11-16T99:99:99Z"))

    def test_filter_injection_denied(self):
        with self.assertRaises(PolicyDenied):
            view_lineage(principal=self.auditor, rows=self.rows, tenant_id="tenant_alpha",
                         asset_key="../../../etc/passwd")

    def test_deterministic_pagination_limit(self):
        view = view_lineage(principal=self.auditor, rows=self.rows, tenant_id="tenant_alpha", limit=1)
        self.assertEqual(view["returned"], 1)
        self.assertEqual(view["total_matching"], 2)
