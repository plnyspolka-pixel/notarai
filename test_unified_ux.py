"""Spójnosc wszystkich modułów UX NotarAI. Kontrole statyczne bez AWS."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_client_journey_routes():
    app = read("app.py")
    auth = read("autoryzacja.py")
    for router in ("kalkulator.router", "wizyty.router", "wizyty.router_zapytan",
                   "notariusze.router", "notariusze.router_kancelarii"):
        assert "app.include_router(" + router + ")" in app
    assert '@app.get("/notariusze"' in app
    assert '"/api/notariusze"' in auth
    assert '"/api/mapa"' not in auth.split("_OTWARTE =", 1)[1].split("_BEZ_ABONAMENTU =", 1)[0]
    assert '"/api/zapytania"' in auth.split("_POZA_SERWISEM =", 1)[1].split("_SERWIS_MAKS_GODZIN", 1)[0]

def test_no_public_map_without_explicit_optin():
    assert 'wpis.get("na_mapie", False)' in read("notariusze.py")
    assert 'notariusze.ustal_polozenie(wpis)' in read("rejestracja.py")

def test_customer_site_navigation():
    main = read("strona/index.html")
    for link in ('href="kalkulator/"', 'href="notariusz/"',
                 'href="blog/"', 'href="https://app.notarai.pl/notariusze"'):
        assert link in main
    assert 'id="dla-klientow"' in main
    assert (ROOT / "strona/kalkulator/index.html").exists()
    assert (ROOT / "seo/kancelarie.json").exists()

def test_notary_dashboard_integrations():
    html = read("static/index.html")
    for element in ("kokpit-open-leads", "kokpit-open-calendar",
                    "okno-zapytania", "mapa-na-mapie", "ekw-karta",
                    "kokpit", "btn-kokpit"):
        assert 'id="' + element + '"' in html
    assert 'src="/static/klienci-panel.js"' in html
    assert 'src="/static/kokpit.js"' in html
    assert 'ekwDostepne = !!ustawienia.ekw' in html
    assert 'window.odswiezKokpit?.(lista)' in html

def test_notary_ekw_providers_are_optional():
    yaml = read("infra/notarai-aplikacja.yaml")
    for token in ("PIECZAPP_EMAIL_NADAWCA", "MamyApify", "MamyFinyou",
                  "PIECZAPP_APIFY_TOKEN", "PIECZAPP_FINYOU_TOKEN"):
        assert token in yaml
    assert '@app.post("/api/sprawy/{identyfikator}/ekw")' in read("app.py")
