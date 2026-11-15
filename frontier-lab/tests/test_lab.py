"""Dependency-free tests for safe offline lab foundations."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
import catalog
import hashchain
import uplift_demo


class CatalogTests(unittest.TestCase):
    def test_real_catalogs(self):
        rows = catalog.load_catalogs()
        self.assertEqual(len(rows), 90)
        self.assertEqual({x["track"] for x in rows}, set(catalog.TRACKS))
        self.assertTrue(all(x["locally_tested"] is False for x in rows))

    def test_reject_untrusted_or_duplicate_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "catalog").mkdir()
            for track in catalog.TRACKS:
                rows = [x for x in catalog.load_catalogs() if x["track"] == track]
                original = json.loads((LAB / "catalog" / f"{track}.json").read_text())
                (root / "catalog" / f"{track}.json").write_text(json.dumps(original))
            path = root / "catalog" / "sales.json"
            data = json.loads(path.read_text())
            data["items"][0]["url"] = "http://insecure.invalid"
            path.write_text(json.dumps(data))
            with self.assertRaises(catalog.CatalogError):
                catalog.load_catalogs(root)


class UpliftTests(unittest.TestCase):
    def test_reproducible_and_bounded(self):
        x = uplift_demo.simulate()
        self.assertEqual(x, uplift_demo.simulate())
        self.assertEqual(x["provenance"], "synthetic_demo_only")
        self.assertGreaterEqual(x["control"]["wilson_95"][0], 0)
        self.assertLessEqual(x["treatment"]["wilson_95"][1], 1)
        self.assertAlmostEqual(x["risk_difference"], x["treatment"]["rate"] - x["control"]["rate"])

    def test_bad_probability_or_n(self):
        for kwargs in ({"n_per_arm": 0}, {"n_per_arm": True}, {"p_control": float("nan")}, {"p_treatment": 1.2}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                uplift_demo.simulate(**kwargs)


class HashchainTests(unittest.TestCase):
    def test_tampering_detected(self):
        chain = []
        hashchain.add_entry(chain, {"kind": "policy_check", "synthetic_task_id": "demo-42", "status": "allowed"})
        hashchain.add_entry(chain, {"kind": "job_stopped", "synthetic_task_id": "demo-42", "status": "ok"})
        self.assertTrue(hashchain.verify(chain))
        changed = copy.deepcopy(chain)
        changed[0]["event"]["status"] = "denied"
        self.assertFalse(hashchain.verify(changed))
        changed = copy.deepcopy(chain)
        changed.pop(0)
        self.assertFalse(hashchain.verify(changed))
        with self.assertRaises(ValueError):
            hashchain.add_entry(changed, {"kind": "job_stopped", "synthetic_task_id": "demo-42", "status": "ok"})

    def test_bad_event_rejected(self):
        with self.assertRaises(ValueError):
            hashchain.add_entry([], {"kind": "policy_check", "synthetic_task_id": "person@example.com", "status": "ok"})
        self.assertTrue(hashchain.demo()["valid_original"])
        self.assertFalse(hashchain.demo()["valid_tampered"])


if __name__ == "__main__":
    unittest.main()
