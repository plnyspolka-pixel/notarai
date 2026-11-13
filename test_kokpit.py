"""Regression checks for the operational NotarAI dashboard.

Run with: python -m pytest test_kokpit.py
No live clients, AWS credentials, or external network access are required.
"""
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / "static/index.html").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "static/kokpit.js").read_text(encoding="utf-8")
CSS = (ROOT / "static/kokpit.css").read_text(encoding="utf-8")
API = (ROOT / "app.py").read_text(encoding="utf-8")


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.scripts = []
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if "id" in data:
            self.ids.append(data["id"])
        if tag == "script":
            self.scripts.append(data.get("src"))
        if tag == "link" and data.get("rel") == "stylesheet":
            self.stylesheets.append(data.get("href"))


def _tags():
    parser = _Tags()
    parser.feed(HTML)
    return parser


def test_dashboard_assets_and_unique_html_ids():
    page = _tags()
    assert len(page.ids) == len(set(page.ids))
    assert "/static/kokpit.js" in page.scripts
    assert "/static/kokpit.css" in page.stylesheets
    assert (ROOT / "static/notarai-symbol.svg").is_file()
    for element in (
        "kokpit", "btn-kokpit", "btn-kokpit-menu", "kokpit-new",
        "kokpit-assistant", "kokpit-sprawy", "kokpit-search", "kokpit-refresh",
        "kokpit-showall", "kokpit-filters", "kokpit-upload", "kokpit-ai",
        "kokpit-review", "kokpit-word",
    ):
        assert element in page.ids, element


def test_dashboard_routes_into_existing_real_workflow():
    assert "window.odswiezKokpit?.(lista)" in HTML
    assert 'const nowyKokpit = numer === 0;' in HTML
    assert "pokaz(0); // Domyślnie" in HTML
    assert 'node("btn-nowa").click()' in DASHBOARD
    assert 'node("pliki").click()' in DASHBOARD
    assert 'wczytajSprawe(s.id)' in DASHBOARD
    assert 'pokaz(2)' in DASHBOARD
    assert 'pokaz(3)' in DASHBOARD
    assert 'node("btn-pobierz")?.click()' in DASHBOARD
    assert '@app.get("/api/sprawy")' in API
    assert '@app.get("/api/sprawy/{identyfikator}")' in API
    assert '@app.post("/api/sprawy/{identyfikator}/projekt")' in API


def test_dashboard_is_never_seeded_with_fake_clients():
    assert 'Przykładowe dane' not in HTML[HTML.index('id="kokpit"'):HTML.index('<!-- ===== 1 ===== -->')]
    assert "state.cases = Array.isArray(cases)" in DASHBOARD
    assert 'document.createElement("button")' in DASHBOARD
    assert "titleNode.textContent = title" in DASHBOARD
    assert 'window.odswiezKokpit?.([], "Zaloguj' in HTML


def test_local_mode_and_error_states():
    assert 'await uchwyt.getFileHandle("projekt.txt")' in HTML
    assert 'await uchwyt.getFileHandle("projekt.docx")' in HTML
    assert "Wskaż folder na sprawy w bocznym menu." in HTML
    assert "Brak dostępu do folderu" in HTML
    assert 'state.issue' in DASHBOARD


def test_accessibility_and_responsive_styles():
    assert 'aria-labelledby="kokpit-title"' in HTML
    assert 'aria-live="polite"' in HTML
    assert 'aria-pressed="true"' in HTML
    assert 'type="button"' in HTML
    assert "@media(max-width:620px)" in CSS
    assert "@media(prefers-reduced-motion:reduce)" in CSS
    assert "kokpit-widoczny" in CSS
    assert "focus-visible" in CSS


def test_dashboard_menu_can_be_collapsed_again():
    # Przycisk musi być widoczny również po rozwinięciu sidebara.
    assert "body.kokpit-widoczny > aside .kokpit-menu-toggle { display:flex; }" in CSS
    assert "body.kokpit-widoczny:not(.kokpit-aside-expanded) > aside .kokpit-menu-toggle { display:flex; }" not in CSS


def test_previous_session_data_cannot_repopulate_dashboard():
    assert "function wyczyscDanePoWylogowaniu()" in HTML
    assert "sprawyLista = [];" in HTML
    assert "const pobranePokolenie = pokolenieSesji;" in HTML
    assert "const czyNieaktualne = () => pobranePokolenie !== pokolenieSesji" in HTML
    assert HTML.count("if (czyNieaktualne()) return;") == 3
    assert "pobranePokolenieOtwierania !== pokolenieOtwierania" in HTML
    assert "function otworzBrame(komunikat){\n  wyczyscDanePoWylogowaniu();" in HTML


def test_project_word_action_downloads_generated_project():
    # Wygenerowanie projektu ustawia najdalej=3, lecz nie ustawia sprawa.projekt.
    assert "if (najdalej >= 3)" in DASHBOARD
    assert 'node("btn-pobierz")?.click()' in DASHBOARD
    assert "sprawa.projekt && najdalej >= 3" not in DASHBOARD


def test_session_switch_resets_private_content_and_filters():
    for item in ("sprawyLista = [];", "sprawa = null;", "wybraneSkany = [];",
                 '"projekt", "pola", "czat2", "czat3", "ostrzezenia"',
                 "window.resetujKokpit?.();"):
        assert item in HTML
    assert "window.resetujKokpit = function ()" in DASHBOARD
    assert 'state.filter = "all";' in DASHBOARD


def test_latest_selected_case_wins():
    assert "const pobranePokolenieOtwierania = ++pokolenieOtwierania;" in HTML
    assert "pobranePokolenieOtwierania !== pokolenieOtwierania" in HTML
    assert "const pobranePokolenieListy = ++pokolenieListy;" in HTML
    assert "pobranePokolenieListy !== pokolenieListy" in HTML


def test_ai_result_not_rendered_after_logout_or_switch():
    assert "sesjaZadania !== pokolenieSesji" in HTML
    assert "numerSprawy !== pokolenieOtwierania" in HTML
    assert "edytowanaSprawa !== sprawa" in HTML
    assert "sprawa.projekt = wynik.tekst;" in HTML


def test_modules_use_existing_authorized_navigation():
    for label in ("Rejestry i weryfikacja", "Formularze urzędowe",
                  "Kalendarz", "Osoby i telefony", "Przesyłki i korespondencja", "Dokumenty i RODO",
                  "Zespół kancelarii", "Abonament", "Pomocnik lokalny",
                  "Księgi i repertoria", "Zgłoszenia GIIF", "Ustawienia kancelarii"):
        assert label in HTML
    assert HTML.count("data-kokpit-nav=") == 12
    assert "element.click(); // Wykorzystuje dotychczasowe kontrole" in DASHBOARD
    assert "button.hidden = !element || element.hidden" in DASHBOARD
    assert ".kokpit-module[hidden] { display:none!important; }" in CSS


def test_same_user_token_refresh_does_not_clear_ongoing_work():
    assert 'function tozsamoscTokena(t){' in HTML
    assert 'ladunek["custom:kancelaria"]' in HTML
    assert "nowaTozsamosc === staraTozsamosc) return;" in HTML
