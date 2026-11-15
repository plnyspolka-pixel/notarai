import json
import tempfile
import unittest
from pathlib import Path
from auditlab.audit import append, verify, new_key, make_checkpoint, verify_checkpoint

class AuditLabTests(unittest.TestCase):
    def test_chain_and_signed_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            log = root / "events.jsonl"
            priv, pub, receipt = (root / n for n in ("signer.pem", "signer.pub", "checkpoint.json"))
            new_key(priv, pub)
            append(log, {"type": "case.created", "subject_id": "case:1", "actor": "user:1"})
            append(log, {"type": "document.accessed", "subject_id": "doc:1", "actor": "user:1"})
            self.assertEqual(verify(log)["count"], 2)
            make_checkpoint(log, priv, receipt)
            self.assertTrue(verify_checkpoint(log, pub, receipt))
            rows = log.read_text().splitlines()
            first = json.loads(rows[0])
            first["event"]["subject_id"] = "doc:999"
            rows[0] = json.dumps(first)
            log.write_text("\n".join(rows) + "\n")
            with self.assertRaises(ValueError):
                verify(log)

    def test_truncation_detected_if_checkpoint_is_independent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            log = root / "events.jsonl"
            priv, pub, receipt = (root / n for n in ("signer.pem", "signer.pub", "checkpoint.json"))
            new_key(priv, pub)
            append(log, {"type": "case.created", "subject_id": "case:1"})
            make_checkpoint(log, priv, receipt)
            log.write_text("")
            self.assertEqual(verify(log)["count"], 0)
            with self.assertRaises(ValueError):
                verify_checkpoint(log, pub, receipt)

if __name__ == "__main__":
    unittest.main()
