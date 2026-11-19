"""Simulated independent checkpoint verifier; no production keys are created."""
import copy
import hashlib
import hmac
import unittest

from private_ai.evidence import (
    LabLedger, IntegrityError, make_checkpoint, verify_checkpoint, verify_chain,
)


def fixture_event():
    return {
        "tenant_id": "tenant_one", "request_id": "request_00001",
        "purpose": "document_analysis", "classification": "internal",
        "region": "eu-central-1",
        "model": "eu.anthropic.claude-opus-4-6-v1",
        "event": "authorized",
    }


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.ledger = LabLedger()
        self.ledger.record(fixture_event())
        # HMAC models a separate signing/verifying dependency in unit tests.
        # It is explicitly NOT the production Ed25519/HSM implementation.
        self.secret = b"synthetic-verifier-fixture"
        self.sign = lambda msg: hmac.new(self.secret, msg, hashlib.sha384).digest()
        self.verify = lambda key, msg, sig: (
            key == "test-independent-signer" and hmac.compare_digest(self.sign(msg), sig)
        )

    def checkpoint(self):
        return make_checkpoint(self.ledger.rows, "test-independent-signer", self.sign)

    def test_receipt_matches_independent_verifier(self):
        receipt = self.checkpoint()
        self.assertIsNone(verify_checkpoint(self.ledger.rows, receipt, self.verify))
        self.assertEqual(verify_chain(self.ledger.rows)["count"], 1)

    def test_event_payload_cannot_enter_audit(self):
        bad = {**fixture_event(), "prompt": "confidential content"}
        with self.assertRaises(IntegrityError):
            self.ledger.record(bad)
        self.assertEqual(len(self.ledger.rows), 1)

    def test_tampered_metadata_rejected(self):
        rows = copy.deepcopy(self.ledger.rows)
        rows[0]["event"]["tenant_id"] = "tenant_two"
        with self.assertRaises(IntegrityError):
            verify_chain(rows)

    def test_truncation_detected_against_previous_checkpoint(self):
        receipt = self.checkpoint()
        with self.assertRaisesRegex(IntegrityError, "Rollback"):
            verify_checkpoint([], receipt, self.verify)

    def test_reordered_entry_detected(self):
        self.ledger.record({**fixture_event(), "event": "completed"})
        rows = copy.deepcopy(self.ledger.rows)
        rows.reverse()
        with self.assertRaises(IntegrityError):
            verify_chain(rows)

    def test_forged_signature_rejected(self):
        receipt = self.checkpoint()
        receipt["signature_hex"] = (b"x" * 48).hex()
        with self.assertRaisesRegex(IntegrityError, "signature rejected"):
            verify_checkpoint(self.ledger.rows, receipt, self.verify)

    def test_wrong_signer_rejected(self):
        receipt = self.checkpoint()
        receipt["statement"]["key_id"] = "attacker"
        with self.assertRaisesRegex(IntegrityError, "signature rejected"):
            verify_checkpoint(self.ledger.rows, receipt, self.verify)

    def test_broken_chain_detected(self):
        self.ledger.record({**fixture_event(), "event": "completed"})
        rows = copy.deepcopy(self.ledger.rows)
        rows[1]["prev_hash"] = "0" * 96
        with self.assertRaises(IntegrityError):
            verify_chain(rows)

    def test_invalid_token_type_rejected(self):
        with self.assertRaises(IntegrityError):
            self.ledger.record({**fixture_event(), "input_tokens": -1})

    def test_malformed_statement_rejected(self):
        receipt = self.checkpoint()
        receipt["statement"]["extra"] = "untrusted"
        with self.assertRaises(IntegrityError):
            verify_checkpoint(self.ledger.rows, receipt, self.verify)
