"""Regresja brandingu: brak ikon i palety Pieczapy na widokach produkcyjnych.

Bez zależności zewnętrznych, sieci i danych kancelarii.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD_COLORS = ("#c96442", "#b5532f", "#faf9f5", "#d9785a", "#e58a6d")
PRODUCTION_VIEWS = (
    "static/index.html",
    "static/admin.html",
    "static/rejestracja.html",
    "static/stenogramy.html",
    "static/poswiadczenia.html",
    "static/notariusze.html",
    "strona/kalkulator/index.html",
    "strona/style.css",
    "rozszerzenie/panel.css",
)


def test_public_views_do_not_reintroduce_legacy_palette():
    for rel in PRODUCTION_VIEWS:
        source = (ROOT / rel).read_text("utf-8")
        # Inline scripts may include user-generated strings; inspect display CSS.
        css = source.split("</style>", 1)[0] if rel.endswith(".html") else source
        for color in OLD_COLORS:
            assert color not in css.lower(), f"{rel}: legacy color {color}"


def test_brand_symbols_are_canonical_everywhere():
    symbol = (ROOT / "static/notarai-symbol.svg").read_bytes()
    assert symbol == (ROOT / "static/osiol.svg").read_bytes(), "old donkey SVG is publicly served"
    assert symbol == (ROOT / "rozszerzenie/ikony/notarai.svg").read_bytes()
    for rel in ("static/admin.html", "static/rejestracja.html",
                "static/stenogramy.html", "static/poswiadczenia.html"):
        source = (ROOT / rel).read_text("utf-8")
        assert '/static/notarai-symbol.svg' in source
        assert '/static/logo.png' not in source
        assert '/static/favicon.png' not in source


# Fixed hashes of brand-approved rasterizations of static/notarai-symbol.svg.
# This also makes a future accidental revert to the old donkey fail CI.
APPROVED_ICON_SHA256 = {
    "rozszerzenie/ikony/16.png": "d215baee4ea5053131e440a5720f794e2eb7ab3ea428d7410b68a0f804664233",
    "rozszerzenie/ikony/48.png": "bb8e55a03f0f4522a7b4e127141bfcbd78db2423fa532760954ba4d0e0990c43",
    "rozszerzenie/ikony/128.png": "e852d723d283b5da2ddecfff86ec22d1d909973629254aa0ba9cd00e33ff2d28",
    "static/notarai.ico": "8843aea261273a8c27e05318b4a7735247b56815a16a81033977fa09fc5024be",
    "static/pieczapp.ico": "8843aea261273a8c27e05318b4a7735247b56815a16a81033977fa09fc5024be",
    "static/logo.png": "e852d723d283b5da2ddecfff86ec22d1d909973629254aa0ba9cd00e33ff2d28",
    "static/favicon.png": "bb8e55a03f0f4522a7b4e127141bfcbd78db2423fa532760954ba4d0e0990c43",
}


def test_brand_raster_assets_are_current():
    for rel, expected in APPROVED_ICON_SHA256.items():
        digest = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert digest == expected, f"{rel}: outdated or unapproved branding"


def test_extension_manifest_and_panel_use_notarai_brand():
    folder = ROOT / "rozszerzenie"
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    assert manifest["icons"] == {
        "16": "ikony/16.png", "48": "ikony/48.png", "128": "ikony/128.png"}
    panel = (folder / "panel.html").read_text("utf-8")
    css = (folder / "panel.css").read_text("utf-8")
    assert 'src="ikony/notarai.svg"' in panel
    assert "<h1>notar<strong>ai</strong></h1>" in panel
    assert "#2b52d9" in css
    assert 'url("fonts/montserrat-latin-wght-normal.woff2")' in css
    assert (folder / "fonts/montserrat-latin-wght-normal.woff2").is_file()
    assert "https://" not in css and "http://" not in css
