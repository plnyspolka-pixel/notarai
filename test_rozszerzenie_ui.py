"""Panel rozszerzenia na prawdziwej stronie (Chromium z Playwrighta).

Kod panelu, silnika i "rak" na stronie jest tu dokladnie ten z rozszerzenia.
Podstawiamy tylko interfejs chrome.* (pamiec, karty, wstrzykiwanie skryptu),
bo Chromium uruchamiane z testu nie laduje rozszerzen w sposob powtarzalny.
Samo zaladowanie rozszerzenia do Chrome/Edge sprawdza sie recznie - patrz
rozszerzenie/README.md i pozycja NA w docs/czeka-na-dostep.md.

Udawany serwer notarai podaje kroki "modelu", a strona probna ma to, co
portale urzedowe: pole w ramce (iframe), pole PIN i przycisk "Podpisz i wyslij".
Sprawdzamy od poczatku do konca:
  - laczenie z kancelaria kodem (bez przepisywania tokenu),
  - wpisywanie i klikanie na stronie, takze w ramce,
  - ze do pola PIN nic nie trafia, a "Podpisz i wyslij" nie zostaje klikniete -
    podpis elektroniczny sklada wylacznie notariusz.

Bez Chromium test jest pomijany. Dane zmyslone.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

KATALOG = Path(__file__).parent / "rozszerzenie"
TYPY = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
        ".png": "image/png", ".json": "application/json"}

# Stanowisko: panel i strona urzedu obok siebie, jak w przegladarce notariusza.
STANOWISKO = """<!doctype html><meta charset="utf-8"><title>stanowisko</title>
<iframe id="panel" name="panel" src="/ext/panel.html" width="420" height="700"></iframe>
<iframe id="cel" name="cel" src="/formularz" width="700" height="700"></iframe>"""

FORMULARZ = """<!doctype html><meta charset="utf-8"><title>Rejestr probny</title>
<h1>Rejestr probny</h1>
<label for="dz">Numer działki</label> <input id="dz" type="text">
<label for="pin">PIN karty</label> <input id="pin" type="password">
<button id="szukaj" onclick="document.getElementById('wynik').textContent='SZUKANO ' + document.getElementById('dz').value">Szukaj</button>
<button id="podpisz" onclick="document.getElementById('wynik').textContent='WYSLANO'">Podpisz i wyślij</button>
<p id="wynik"></p>
<iframe src="/ramka" title="obreb"></iframe>"""

RAMKA = """<!doctype html><meta charset="utf-8">
<label for="ob">Obręb</label> <input id="ob" type="text">"""

# Probny KRZ: zgoda na ciasteczka na stronie, formularz w ramce - jak w prawdziwym.
# Strona glowna nie moze zawierac napisu z formularza ("Wyszukaj").
KRZ = """<!doctype html><meta charset="utf-8"><title>Rejestr zadluzonych - proba</title>
<h1>Krajowy Rejestr - proba</h1>
<button onclick="this.remove(); window.zgoda = true">Akceptuj</button>
<iframe src="/krz-ramka" title="formularz" width="640" height="420"></iframe>"""

KRZ_RAMKA = """<!doctype html><meta charset="utf-8">
<button onclick="top.zakladki = (top.zakladki || 0) + 1">Osoba fizyczna prowadząca działalność gospodarczą</button>
<button onclick="top.zakladki = (top.zakladki || 0) + 1">Osoba fizyczna nieprowadząca działalności gospodarczej</button>
<input id="ident" type="text" aria-label="Identyfikator (PESEL)">
<button onclick="document.getElementById('wynik').textContent =
  document.getElementById('ident').value === '44051401359'
    ? 'Nie zostały znalezione żadne pozycje dla podanych kryteriów wyszukiwania.'
    : 'Postępowanie upadłościowe, numer sprawy WA1M/GUp/1/2026'">Wyszukaj</button>
<button onclick="document.getElementById('ident').value = ''; document.getElementById('wynik').textContent = ''">Wyczyść</button>
<p id="wynik"></p>"""

# Probny formularz rejestru: pole, lista, pole wyboru i przycisk wysylki.
REJESTR = """<!doctype html><meta charset="utf-8"><title>Formularz probny</title>
<label for="pesel">PESEL</label> <input id="pesel" type="text">
<label for="rodzaj">Rodzaj</label> <select id="rodzaj"><option>Darowizna</option><option>Sprzedaż</option></select>
<label for="zgoda">Zgoda</label> <input id="zgoda" type="checkbox">
<button id="wyslij" onclick="document.getElementById('stan').textContent='WYSLANO'">Wyślij</button>
<p id="stan"></p>"""

# chrome.* dla panelu: karta = ramka "cel", ramki strony = jej ramki.
CHROME = """
if (location.pathname.endsWith("/panel.html")) {
  const cel = () => parent.frames.cel;
  const okna = () => [cel(), ...Array.from({length: cel().frames.length}, (_, i) => cel().frames[i])];
  const karta = () => ({ id: 1, url: cel().location.href, status: "complete" });
  const pamiec = { adres: location.origin };
  const nic = { addListener() {} };
  window.chrome = {
    storage: { local: {
      get: async (klucze) => Object.fromEntries(klucze.filter(k => k in pamiec).map(k => [k, pamiec[k]])),
      set: async (dane) => { Object.assign(pamiec, dane); },
    } },
    tabs: { query: async () => [karta()], get: async () => karta(),
            create: async (nowa) => { cel().location.href = nowa.url; return { id: 1 }; },
            update: async (id, zmiana) => { cel().location.href = zmiana.url; },
            onActivated: nic, onUpdated: nic },
    permissions: {
      _zgody: new Set(),
      contains: async ({ origins }) => origins.every(o => chrome.permissions._zgody.has(o)),
      request: async ({ origins }) => { origins.forEach(o => chrome.permissions._zgody.add(o)); return true; },
    },
    scripting: { executeScript: async ({ target, func, args }) => {
      const wszystkie = okna();
      const numery = target.frameIds || wszystkie.map((_, i) => i);
      return numery.map(i => ({ frameId: i,
        result: wszystkie[i].eval("(" + func.toString() + ")")(args[0]) }));
    } },
  };
}
"""

# Scenariusze "modelu": opis elementu -> czynnosc. Numer bierzemy z listy,
# ktora przyslal panel - tak samo jak prawdziwy model.
SCENARIUSZE = {
    "wypelnij": [("wpisz", "Numer działki", "123/4"), ("wpisz", "Obręb", "Słoneczna"),
                 ("kliknij", "Szukaj", ""), ("wpisz", "PIN karty", "1234")],
    "podpisz": [("kliknij", "Podpisz i wyślij", "")],
}


class Notarai(BaseHTTPRequestHandler):
    zadania: list = []
    kolejka: list = []      # zlecenia czekajace na rozszerzenie
    wyniki: dict = {}       # raporty odeslane przez rozszerzenie

    def log_message(self, *_):
        pass

    def _odpowiedz(self, kod, tresc, typ="application/json"):
        if isinstance(tresc, str):
            dane = tresc.encode("utf-8")
        elif isinstance(tresc, bytes):
            dane = tresc
        else:
            dane = json.dumps(tresc).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", typ + ("" if typ.startswith("image/") else "; charset=utf-8"))
        self.send_header("Content-Length", str(len(dane)))
        self.end_headers()
        self.wfile.write(dane)

    def do_GET(self):
        if self.path == "/":
            return self._odpowiedz(200, STANOWISKO, "text/html")
        if self.path == "/formularz":
            return self._odpowiedz(200, FORMULARZ, "text/html")
        if self.path == "/ramka":
            return self._odpowiedz(200, RAMKA, "text/html")
        strony = {"/krz": KRZ, "/krz-ramka": KRZ_RAMKA, "/rejestr": REJESTR}
        if self.path in strony:
            return self._odpowiedz(200, strony[self.path], "text/html")
        if self.path.startswith("/api/pomocnik/zlecenia"):
            return self._odpowiedz(200, list(self.kolejka))
        if self.path.startswith("/ext/"):
            plik = (KATALOG / self.path[5:].split("?")[0]).resolve()
            if plik.is_file() and KATALOG.resolve() in plik.parents:
                return self._odpowiedz(200, plik.read_bytes(), TYPY.get(plik.suffix, "text/plain"))
        self._odpowiedz(404, {})

    def do_POST(self):
        tresc = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        self.zadania.append((self.path, tresc, self.headers.get("Authorization", "")))
        if self.path == "/api/pomocnik/parowanie":
            return self._odpowiedz(201, {"kod": "ABCD-EFGH", "sekret": "s", "wazny_s": 600})
        if self.path == "/api/pomocnik/parowanie/ABCD-EFGH":
            return self._odpowiedz(200, {"token": "pm_test", "id": "u1"})
        if self.path == "/api/pomocnik/klikamy":
            return self._odpowiedz(201, {"zlecenie": "z1"})
        if self.path == "/api/pomocnik/klikamy/z1/krok":
            plan = SCENARIUSZE[tresc["cel"]]
            numer = len(tresc["kroki"])
            if numer >= len(plan):
                return self._odpowiedz(200, {"akcja": "koniec", "podsumowanie": "Zrobione."})
            akcja, opis, tekst = plan[numer]
            nr = next(e["nr"] for e in tresc["stan"]["elementy"] if e["opis"] == opis)
            return self._odpowiedz(200, {"akcja": akcja, "nr": nr, "tekst": tekst,
                                         "mysl": "krok testowy"})
        if self.path == "/api/pomocnik/klikamy/z1/koniec":
            return self._odpowiedz(200, {"stan": "wykonane"})
        if self.path.startswith("/api/pomocnik/zlecenia/") and self.path.endswith("/wynik"):
            identyfikator = self.path.split("/")[4]
            Notarai.kolejka[:] = [z for z in Notarai.kolejka if z["id"] != identyfikator]
            Notarai.wyniki[identyfikator] = tresc
            return self._odpowiedz(200, {"stan": "wykonane"})
        self._odpowiedz(404, {})


@pytest.fixture
def notarai():
    Notarai.zadania, Notarai.kolejka, Notarai.wyniki = [], [], {}
    serwer =ThreadingHTTPServer(("127.0.0.1", 0), Notarai)
    threading.Thread(target=serwer.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{serwer.server_port}"
    serwer.shutdown()
    serwer.server_close()


def _chromium():
    """Skad wziac Chromium: wskazane zmienna, wlasne Playwrighta, Chrome albo
    dowolna wersja zainstalowana wczesniej przez Playwrighta."""
    if os.environ.get("PIECZAPP_CHROMIUM"):
        yield {"executable_path": os.environ["PIECZAPP_CHROMIUM"]}
    yield {}
    yield {"channel": "chrome"}
    baza = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    for exe in sorted(baza.glob("chromium-*/chrome-win*/chrome.exe"), reverse=True):
        yield {"executable_path": str(exe)}


@pytest.fixture
def stanowisko(notarai):
    with playwright.sync_playwright() as p:
        przegladarka = None
        for opcje in _chromium():
            try:
                przegladarka = p.chromium.launch(headless=True, timeout=60000, **opcje)
                break
            except Exception:  # noqa: BLE001 - probujemy nastepnej przegladarki
                continue
        if przegladarka is None:
            pytest.skip("Brak Chromium dla Playwrighta")
        try:
            kontekst = przegladarka.new_context()
            kontekst.add_init_script(CHROME)
            strona = kontekst.new_page()
            bledy = []
            strona.on("pageerror", lambda blad: bledy.append(str(blad)))
            strona.goto(notarai + "/")
            yield strona, bledy
        finally:
            przegladarka.close()


def _uruchom(panel, cel):
    panel.locator("#cel").fill(cel)
    panel.locator("#btn-wykonaj").click()
    panel.locator("#wynik:not([hidden])").wait_for(timeout=30000)   # klik chowa poprzedni
    panel.locator("#btn-wykonaj:not([disabled])").wait_for(timeout=30000)
    return panel.locator("#wynik").inner_text()


def test_panel_prowadzi_strone_ale_nie_podpisuje_i_nie_wpisuje_pinu(stanowisko):
    strona, bledy = stanowisko
    panel = strona.frame_locator("#panel")
    cel = strona.frame_locator("#cel")

    # Laczenie: panel sam prosi o kod i odbiera token - nic nie przepisujemy.
    panel.locator("#widok-praca:not([hidden])").wait_for(timeout=20000)
    assert panel.locator("#host").inner_text() == "127.0.0.1"

    wynik = _uruchom(panel, "wypelnij")
    assert "wyłącznie Ty" in wynik                              # pole PIN: stery do czlowieka
    assert cel.locator("#dz").input_value() == "123/4"
    assert cel.frame_locator("iframe").locator("#ob").input_value() == "Słoneczna"
    assert cel.locator("#wynik").inner_text() == "SZUKANO 123/4"   # zwykly przycisk klikniety
    assert cel.locator("#pin").input_value() == ""
    assert panel.locator("#kroki li").count() == 4

    wynik = _uruchom(panel, "podpisz")
    assert "Nie kliknę" in wynik and "Podpisz i wyślij" in wynik
    assert cel.locator("#wynik").inner_text() == "SZUKANO 123/4"   # nic nie wyslano

    sciezki = [s for s, _, _ in Notarai.zadania]
    assert sciezki.count("/api/pomocnik/klikamy/z1/koniec") == 2
    # Token idzie w naglowku; model nie dostaje selektorow ani wpisanych wartosci.
    kroki = [(t, a) for s, t, a in Notarai.zadania if s.endswith("/krok")]
    assert kroki and all(a == "Bearer pm_test" for _, a in kroki)
    wyslane = json.dumps([t for t, _ in kroki], ensure_ascii=False)
    assert "selektor" not in wyslane and "1234" not in wyslane
    assert bledy == []


def _poczekaj_na_wynik(strona, identyfikator, sekund=90):
    for _ in range(sekund * 4):
        if identyfikator in Notarai.wyniki:
            return Notarai.wyniki[identyfikator]
        strona.wait_for_timeout(250)
    raise AssertionError(f"rozszerzenie nie odeslalo wyniku zlecenia {identyfikator}")


def test_zlecenia_z_kolejki_krz_i_formularz(stanowisko, notarai):
    """Sprawdzenie w KRZ i wypelnienie formularza zlecone ze sprawy w notarai."""
    import krz_portal

    strona, bledy = stanowisko
    panel = strona.frame_locator("#panel")
    cel = strona.frame_locator("#cel")
    panel.locator("#widok-praca:not([hidden])").wait_for(timeout=20000)

    # --- KRZ: pierwsze zlecenie dla serwisu czeka na zgode notariusza ---
    portal = {**krz_portal.opis_portalu(), "adres": notarai + "/krz", "odstep_s": 0}
    Notarai.kolejka.append({"id": "k1", "rodzaj": "krz", "sprawa": "abc123", "tresc": {
        "portal": portal,
        "osoby": [{"pesel": "44051401359", "etykieta": "zbywca"},
                  {"pesel": "85031512331", "etykieta": "nabywca"}]}})
    panel.locator("#zgoda:not([hidden])").wait_for(timeout=20000)
    assert "KRZ" in panel.locator("#zgoda-tytul").inner_text()
    assert "k1" not in Notarai.wyniki                 # bez zgody nic sie nie dzieje
    panel.locator("#btn-zgoda").click()

    raport = _poczekaj_na_wynik(strona, "k1")
    assert [(s["etykieta"], s["status"]) for s in raport["sprawdzenia"]] == \
        [("zbywca", "brak_wpisu"), ("nabywca", "wpis")]
    assert raport["bledy"] == []
    assert all(s["rejestr"] == "KRZ" and s["zrodlo"] == notarai + "/krz"
               for s in raport["sprawdzenia"])
    assert strona.evaluate("window.zakladki") == 4              # dwie zakladki na osobe
    assert strona.evaluate("frames.cel.zgoda") is True          # zgoda na ciasteczka kliknieta
    panel.locator("#btn-wykonaj:not([disabled])").wait_for(timeout=10000)
    # W panelu widac etykiety stron czynnosci, nigdy numery.
    assert "44051401359" not in panel.locator("body").inner_text()

    # --- formularz: zgoda juz jest, wiec zlecenie rusza samo ---
    strona.evaluate("frames.cel.location.href = '/rejestr'")
    cel.locator("#pesel").wait_for(timeout=10000)
    Notarai.kolejka.append({"id": "f1", "rodzaj": "formularz", "sprawa": "abc123", "tresc": {
        "system": "probny", "adres": notarai + "/rejestr", "gotowosc": "#pesel",
        "przycisk_wysylki": "#wyslij", "status_mapowania": "gotowe", "tryb": "faktyczny",
        "kroki": [{"pole": "PESEL", "selektor": "#pesel", "typ": "tekst", "wartosc": "44051401359"},
                  {"pole": "Rodzaj", "selektor": "#rodzaj", "typ": "lista", "wartosc": "Sprzedaż"},
                  {"pole": "Zgoda", "selektor": "#zgoda", "typ": "pole_wyboru", "wartosc": "tak"},
                  {"pole": "Uwagi", "selektor": "#uwagi", "typ": "tekst", "wartosc": None}]}})
    raport = _poczekaj_na_wynik(strona, "f1")
    assert [k["wykonano"] for k in raport["kroki"]] == [True, True, True, False]
    assert raport["bledy"] == []
    assert "44051401359" not in json.dumps(raport)              # raport bez wartosci pol
    assert cel.locator("#pesel").input_value() == "44051401359"
    assert cel.locator("#rodzaj").input_value() == "Sprzedaż"
    assert cel.locator("#zgoda").is_checked()
    assert cel.locator("#stan").inner_text() == ""              # nic nie wyslano

    # --- zlecenie celujace w przycisk wysylki: odmowa calosci ---
    Notarai.kolejka.append({"id": "f2", "rodzaj": "formularz", "sprawa": "abc123", "tresc": {
        "system": "probny", "adres": notarai + "/rejestr", "gotowosc": "#pesel",
        "przycisk_wysylki": "#wyslij", "status_mapowania": "gotowe", "tryb": "faktyczny",
        "kroki": [{"pole": "Wyślij", "selektor": "#wyslij", "typ": "pole_wyboru", "wartosc": "tak"}]}})
    raport = _poczekaj_na_wynik(strona, "f2")
    assert "przycisku wysyłki" in raport["bledy"][0]
    assert cel.locator("#stan").inner_text() == ""
    assert bledy == []
