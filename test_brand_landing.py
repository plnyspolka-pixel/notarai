"""Static regression checks for the NotarAI public brand landing.

Tests the actual repository HTML, CSS, and scalable symbol; no network or AWS.
"""
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "strona"
HTML = (SITE / "index.html").read_text(encoding="utf-8")
CSS = (SITE / "brand-site.css").read_text(encoding="utf-8")
LOGO = (SITE / "logo-mark.svg").read_text(encoding="utf-8")


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []
        self.images = []
        self.controls = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a":
            self.links.append(a.get("href", ""))
        if tag == "img":
            self.images.append(a.get("src", ""))
        if tag == "button" and a.get("id"):
            self.controls[a["id"]] = a


def _parse():
    parser = _PageParser()
    parser.feed(HTML)
    return parser


def test_site_assets_and_semantic_navigation():
    p = _parse()
    for path in ("style.css", "brand-site.css", "logo-mark.svg"):
        assert path in HTML
        assert (SITE / path).is_file()
    assert HTML.count('class="brand-hero"') == 1
    assert 'id="brand-hero-heading"' in HTML
    for href in p.links:
        if href.startswith("#") and len(href) > 1:
            assert href[1:] in p.ids, f"Broken on-page anchor: {href}"
    assert "brand-primary-nav" in p.ids
    assert "brand-menu-toggle" in p.controls
    assert p.controls["brand-menu-toggle"].get("aria-controls") == "brand-primary-nav"
    assert p.controls["brand-menu-toggle"].get("aria-expanded") == "false"


def test_real_conversion_links_and_existing_legal_sections():
    for href in (
        "https://app.notarai.pl/rejestracja",
        "https://app.notarai.pl",
        "regulamin/",
        "umowa-powierzenia/",
        "instrukcja-ai/",
        "prywatnosc/",
    ):
        assert href in _parse().links
    for anchor in ("klikamy", "latwo", "dane", "zgodnosc", "cennik", "kontakt"):
        assert anchor in _parse().ids
    assert "150 kredytów" in HTML and "abonament" not in HTML.lower().replace("bez abonamentu", "")
    assert "KRS 0001140846" in HTML


def test_brand_art_direction_responsive_and_accessibility():
    for token in ("#071d49", "#2b52d9", "#00cfff"):
        assert token in CSS.lower()
    assert "@media (max-width: 900px)" in CSS
    assert "@media (max-width: 620px)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert ".brand-nav.is-open" in CSS
    assert "aria-label" in HTML
    assert "<svg" in LOGO
    assert "<script" not in LOGO
    assert "http://" not in CSS and "https://" not in CSS


def test_mockup_does_not_make_unverified_savings_claim():
    # The approval mockup pictured a -70% number without performance evidence.
    # This landing intentionally showcases workflows, not an unverified metric.
    assert "–70%" not in HTML
    assert "-70%" not in HTML
    assert "WIZUALIZACJA POGLĄDOWA" in HTML
