"""Offline cross-language canonicalization assertions, no AWS credentials."""
import hashlib
import hmac
import unittest

from scripts.virtual_employee_fixture import canonical, make_diagnostic_job

KEY = bytes(range(32))
FIXTURE = {
    "schema": 1,
    "tenantId": "pilot01",
    "jobId": "0123456789abcdef0123456789abcdef",
    "operation": "probe.session",
    "issuedAtUnix": 1799999990,
    "expiresAtUnix": 1800000050,
    "nonce": "abcdef0123456789abcdef0123456789",
}


class VirtualEmployeeProtocolTests(unittest.TestCase):
    def test_reference_signature(self):
        expected = "3001f34ea8457f39c5da9142fc6c2e2680956f5484a32082c030736c819ba7f0"
        self.assertEqual(hmac.new(KEY, canonical(FIXTURE), hashlib.sha256).hexdigest(), expected)

    def test_fixture_uses_signed_read_only_command(self):
        job = make_diagnostic_job("pilot01", "probe.session", KEY, now=1800000000)
        self.assertEqual(job["expiresAtUnix"] - job["issuedAtUnix"], 120)
        self.assertEqual(job["signature"], hmac.new(KEY, canonical(job), hashlib.sha256).hexdigest())
        self.assertNotIn("payload", job)

    def test_denies_arbitrary_commands(self):
        with self.assertRaises(ValueError):
            make_diagnostic_job("pilot01", "shell.execute", KEY)

    def test_tenant_validation(self):
        with self.assertRaises(ValueError):
            make_diagnostic_job("tenant\n2", "probe.session", KEY)


if __name__ == "__main__":
    unittest.main()
