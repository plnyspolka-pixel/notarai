import hashlib
import unittest

from private_ai.synthetic import png_fixture, fixture_sha256


class SyntheticFixtureTests(unittest.TestCase):
    def test_deterministic_valid_png_header(self):
        data = png_fixture()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(fixture_sha256(), hashlib.sha256(data).hexdigest())
        self.assertLess(len(data), 1024 * 1024)

    def test_dimensions(self):
        self.assertEqual(png_fixture()[16:24], bytes.fromhex("0000020000000180"))
