"""Synthetic offline adversarial checks. No real client data or API credentials."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from private_ai import Principal, Deployment, Classification, Backend, PolicyDenied
from private_ai import DocumentGateway, DocumentRequest


class Audit:
    def __init__(self, broken=False):
        self.events = []
        self.broken = broken

    def record(self, event):
        if self.broken:
            raise RuntimeError("audit offline")
        self.events.append(event)


class SecurityTests(TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.converse.return_value = {
            "output": {"message": {"content": [{"text": "synthetic output"}]}},
            "usage": {"inputTokens": 10, "outputTokens": 3}}
        self.audit = Audit()
        self.principal = Principal("user_a", "tenant_one", frozenset({"private_ai:invoke"}))
        self.req = DocumentRequest("tenant_one", "request_00001", "document_analysis",
                                   Classification.INTERNAL, "synthetic prompt",
                                   "application/pdf", b"%PDF-1.7 synthetic data")
        self.dep = Deployment("eu-central-1", "eu.anthropic.claude-opus-4-6-v1")

    def run_ai(self, principal=None, req=None, dep=None, audit=None):
        return DocumentGateway(deployment=dep or self.dep, client=self.client,
                               audit=audit or self.audit).process(
            principal or self.principal, req or self.req)

    def deny(self, **kwargs):
        with self.assertRaises(PolicyDenied):
            self.run_ai(**kwargs)
        self.client.converse.assert_not_called()

    def test_synthetic_and_audit_minimization(self):
        result = self.run_ai()
        self.assertEqual(result.text, "synthetic output")
        self.assertEqual(self.client.converse.call_count, 1)
        for secret in ("synthetic prompt", "%PDF-", "synthetic output"):
            self.assertNotIn(secret, str(self.audit.events))

    def test_cross_tenant(self):
        self.deny(principal=replace(self.principal, tenant_id="tenant_two"))

    def test_missing_scope(self):
        self.deny(principal=replace(self.principal, scopes=frozenset()))

    def test_inactive_identity(self):
        self.deny(principal=replace(self.principal, active=False))

    def test_non_eu_region(self):
        self.deny(dep=replace(self.dep, region="us-east-1"))

    def test_non_eu_model(self):
        self.deny(dep=replace(self.dep, model_id="anthropic.claude"))

    def test_unknown_backend(self):
        self.deny(dep=replace(self.dep, backend="external-api"))

    def test_unattested_gpu(self):
        self.deny(dep=replace(self.dep, backend=Backend.DEDICATED_VLLM))

    def test_confidential_closed_by_default(self):
        self.deny(req=replace(self.req, classification=Classification.CONFIDENTIAL))

    def test_restricted_denied_even_with_release(self):
        self.deny(req=replace(self.req, classification=Classification.RESTRICTED),
                  dep=replace(self.dep, confidential_release_approved=True))

    def test_approved_managed_confidential_in_synthetic_fixture(self):
        self.assertEqual("synthetic output", self.run_ai(
            req=replace(self.req, classification=Classification.CONFIDENTIAL),
            dep=replace(self.dep, confidential_release_approved=True)).text)

    def test_unknown_classification(self):
        self.deny(req=replace(self.req, classification="confidential"))

    def test_hostile_content_not_accepted_as_url(self):
        self.deny(req=replace(self.req, content=b"https://external.example/secret"))

    def test_oversize_file_denied(self):
        self.deny(req=replace(self.req, content=b"%PDF-" + b"x" * (8 * 1024 * 1024)))

    def test_unapproved_purpose_denied(self):
        self.deny(req=replace(self.req, purpose="publish_secret"))

    def test_no_tools_or_external_calls(self):
        self.run_ai()
        self.assertNotIn("toolConfig", self.client.converse.call_args.kwargs)

    def test_audit_down_denies_before_network(self):
        with self.assertRaisesRegex(RuntimeError, "audit offline"):
            self.run_ai(audit=Audit(broken=True))
        self.client.converse.assert_not_called()

    def test_no_fallback_on_model_error(self):
        self.client.converse.side_effect = RuntimeError("model unavailable")
        with self.assertRaisesRegex(RuntimeError, "model unavailable"):
            self.run_ai()
        self.assertEqual(self.client.converse.call_count, 1)
        self.assertEqual(self.audit.events[-1]["event"], "failed")
