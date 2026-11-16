"""Offline security contract for the synthetic-only control-room preview."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "private_ai_dashboard"


class HtmlScanner(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []
        self.csp = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for attr in ("src", "href"):
            if a.get(attr):
                self.resources.append(a[attr])
        if tag == "meta" and a.get("http-equiv") == "Content-Security-Policy":
            self.csp.append(a.get("content", ""))


class DashboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
        cls.js = (DASHBOARD / "dashboard.js").read_text(encoding="utf-8")
        cls.css = (DASHBOARD / "dashboard.css").read_text(encoding="utf-8")
        cls.tags = HtmlScanner()
        cls.tags.feed(cls.html)

    def test_not_a_public_notarai_page(self):
        self.assertFalse((ROOT / "static" / "private-ai.html").exists())

    def test_synthetic_and_noindex(self):
        self.assertIn("DEMO · dane syntetyczne", self.html)
        self.assertIn("bez danych klientów", self.html)
        self.assertIn('name="robots" content="noindex,nofollow,noarchive"', self.html)

    def test_no_external_resources(self):
        self.assertEqual(self.tags.resources, ["./dashboard.css", "./dashboard.js"])
        self.assertEqual(len(self.tags.csp), 1)
        csp = self.tags.csp[0]
        for x in ("default-src 'none'", "script-src 'self'", "connect-src 'none'",
                  "form-action 'none'", "frame-src 'none'", "object-src 'none'"):
            self.assertIn(x, csp)

    def test_no_network_or_browser_storage(self):
        for bad in ("fetch(", "new WebSocket(", "XMLHttpRequest",
                    "localStorage.", "sessionStorage.", "eval(", "innerHTML ="):
            self.assertNotIn(bad, self.js)
        self.assertIn("synthetic:true", self.js)
        self.assertIn("URL.createObjectURL", self.js)

    def test_only_pseudonyms(self):
        self.assertIn('asset:"doc_a01"', self.js)
        self.assertIn('actor:"user_104"', self.js)
        self.assertNotIn("@", self.js)

    def test_auth_not_claimed(self):
        self.assertIn("Real server MUST authorize", self.js)
        self.assertIn('e.actor==="user_104"', self.js)

    def test_accessibility_and_mobile(self):
        self.assertIn('aria-label="Menu panelu"', self.html)
        self.assertIn('aria-label="Przepływ dokumentu"', self.html)
        self.assertIn('addEventListener("keydown"', self.js)
        self.assertIn("@media(max-width:740px)", self.css)


if __name__ == "__main__":
    unittest.main()
