"""Regresyjne kontrole podlaczenia nowej szaty graficznej.

Testy sa statyczne: nie uruchamiaja aplikacji ani nie pobieraja zewnetrznych zasobow.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
THEME = ROOT / "static" / "financeyou-theme.css"
LANDING = ROOT / "strona" / "style.css"


def test_theme_is_linked_after_inline_styles():
    for name in ("index.html", "admin.html", "rejestracja.html"):
        page = (ROOT / "static" / name).read_text(encoding="utf-8")
        link = '<link rel="stylesheet" href="/static/financeyou-theme.css">'
        assert page.count(link) == 1, name
        assert page.index("</style>") < page.index(link) < page.index("</head>"), name


def test_landing_subpages_use_shared_brand_stylesheet():
    pages = [
        ROOT / "strona" / "index.html",
        ROOT / "strona" / "instrukcja-ai" / "index.html",
        ROOT / "strona" / "prywatnosc" / "index.html",
        ROOT / "strona" / "regulamin" / "index.html",
        ROOT / "strona" / "umowa-powierzenia" / "index.html",
    ]
    for path in pages:
        page = path.read_text(encoding="utf-8")
        assert 'rel="stylesheet"' in page, str(path)
        assert 'style.css' in page, str(path)
    assert "Finance You visual refresh" in LANDING.read_text(encoding="utf-8")


def test_theme_has_brand_tokens_mobile_and_reduced_motion():
    styles = THEME.read_text(encoding="utf-8")
    for value in ("#0d193c", "#050a30", "#1c1cc0", "#2197d3"):
        assert value in styles
    assert "@media (max-width: 820px)" in styles
    assert "@media (prefers-color-scheme: dark)" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


def test_theme_does_not_inject_scripts_or_external_font_cdn():
    styles = THEME.read_text(encoding="utf-8")
    assert "<script" not in styles.lower()
    assert "fonts.googleapis.com" not in styles
    assert "url(http" not in styles
