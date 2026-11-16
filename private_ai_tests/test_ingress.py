"""Synthetic IAM, tenant and audit regressions. No network and no secrets."""
import base64
import json
import unittest
from unittest.mock import Mock

from private_ai import DocumentGateway, Deployment, PolicyDenied
from private_ai.ingress import process_event
from private_ai.lambda_entry import S3AuditSink

ROLE = "arn:aws:iam::123456789012:role/private-ai-pilot-caller"
STS = "arn:aws:sts::123456789012:assumed-role/private-ai-pilot-caller/session-1"


class Audit:
    def __init__(self, fail=False):
        self.events, self.fail = [], fail

    def record(self, event):
        if self.fail:
            raise RuntimeError("audit sink unavailable")
        self.events.append(event)


class IngressTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.converse.return_value = {
            "output": {"message": {"content": [{"text": "SYNTHETIC OUTPUT"}]}},
            "usage": {"inputTokens": 4, "outputTokens": 2},
        }
        self.audit = Audit()
        self.gateway = DocumentGateway(
            deployment=Deployment("eu-central-1", "eu.anthropic.claude-opus-4-6-v1"),
            client=self.client, audit=self.audit,
        )
        self.payload = {
            "request_id": "request_00002",
            "purpose": "document_analysis",
            "prompt": "synthetic fake document",
            "media_type": "application/pdf",
            "document_base64": base64.b64encode(b"%PDF-1.7 synthetic").decode(),
        }
        self.event = {
            "version": "2.0",
            "routeKey": "POST /v1/documents",
            "isBase64Encoded": False,
            "requestContext": {
                "apiId": "example123",
                "http": {"method": "POST"},
                "authorizer": {"iam": {"userArn": STS}},
            },
            "body": json.dumps(self.payload),
        }

    def call(self, **overrides):
        kwargs = {"allowed_role": ROLE, "api_id": "example123",
                  "tenant_id": "tenant_one", "gateway": self.gateway}
        kwargs.update(overrides)
        return process_event(self.event, **kwargs)

    def deny(self):
        with self.assertRaises(PolicyDenied):
            self.call()
        self.client.converse.assert_not_called()

    def test_authorized_and_redacted(self):
        out = self.call()
        self.assertEqual(out["result"], "SYNTHETIC OUTPUT")
        self.assertEqual(self.audit.events[0]["event"], "authorized")
        self.assertNotIn("fake document", str(self.audit.events))
        self.assertNotIn("SYNTHETIC OUTPUT", str(self.audit.events))

    def test_missing_iam(self):
        self.event["requestContext"]["authorizer"] = {}
        self.deny()

    def test_wrong_account(self):
        self.event["requestContext"]["authorizer"]["iam"]["userArn"] = (
            "arn:aws:sts::999999999999:assumed-role/private-ai-pilot-caller/session")
        self.deny()

    def test_wrong_role(self):
        self.event["requestContext"]["authorizer"]["iam"]["userArn"] = (
            "arn:aws:sts::123456789012:assumed-role/other/session")
        self.deny()

    def test_wrong_api(self):
        self.event["requestContext"]["apiId"] = "other"
        self.deny()

    def test_unsupported_route(self):
        self.event["routeKey"] = "POST /v1/admin"
        self.deny()

    def test_client_tenant_claim_denied(self):
        self.payload["tenant_id"] = "tenant_two"
        self.event["body"] = json.dumps(self.payload)
        self.deny()

    def test_client_confidential_claim_denied(self):
        self.payload["classification"] = "confidential"
        self.event["body"] = json.dumps(self.payload)
        self.deny()

    def test_signed_url_not_an_attachment(self):
        self.payload["document_base64"] = "https://example.test/secret.pdf"
        self.event["body"] = json.dumps(self.payload)
        self.deny()

    def test_missing_file_denied(self):
        del self.payload["document_base64"]
        self.event["body"] = json.dumps(self.payload)
        self.deny()

    def test_audit_outage_before_inference(self):
        self.gateway.audit = Audit(fail=True)
        with self.assertRaisesRegex(RuntimeError, "audit sink"):
            self.call()
        self.client.converse.assert_not_called()

    def test_s3_audit_redacts_and_rejects_unsafe_fields(self):
        s3 = Mock()
        sink = S3AuditSink(s3, "synthetic-audit-bucket")
        ev = {
            "tenant_id": "tenant_one", "request_id": "request_00002",
            "purpose": "document_analysis", "classification": "internal",
            "region": "eu-central-1", "model": "eu.anthropic.claude-opus-4-6-v1",
            "event": "authorized",
        }
        sink.record(ev)
        self.assertNotIn("synthetic fake document", str(s3.put_object.call_args))
        with self.assertRaises(ValueError):
            sink.record({**ev, "prompt": "secret"})
        self.assertEqual(s3.put_object.call_count, 1)


if __name__ == "__main__":
    unittest.main()
