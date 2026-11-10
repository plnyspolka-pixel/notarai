"""Smoke test ekranu "Styl i zasady kancelarii" w prawdziwej przegladarce.

Zasada wpisana zdaniem -> podglad "Tak to rozumiem" -> Enter -> na liscie.
Akty wrzucone do nauki -> nawyki i podpowiedzi -> "Pilnuj tego".
Raport zasad nad projektem z podswietleniem naruszenia. Dane zmyslone.
"""
import io
import os
import socket
import threading
import time

import pytest
from docx import Document

playwright = pytest.importorskip("playwright.sync_api")

AKT = """AKT NOTARIALNY
Dnia 03.12.2025r. przed notariuszem w Kancelarii Notarialnej w Zalesiu stawił się:
1. Jan KOWALSKI, PESEL 80010112345, zamieszkały w Zalesiu.
UMOWA SPRZEDAŻY
§ 1. Stawający oświadcza, że jest właścicielem lokalu za cenę 250.000,00 zł (dwieście pięćdziesiąt tysięcy złotych).
§ 2. Notariusz pouczył o treści art. 158 kodeksu cywilnego, o którym mowa w § 1.
§ 3. Taksę notarialną pobrano zgodnie z § 3 rozporządzenia.
Akt ten został odczytany, przyjęty i podpisany."""


@pytest.fixture
def serwer(tmp_path, monkeypatch):
    import uvicorn
    import config
    import magazyn
    monkeypatch.setattr(config, "DANE", tmp_path)
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    assert magazyn.TRYB == "lokalny"
    import app as aplikacja

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    uv = uvicorn.Server(uvicorn.Config(aplikacja.app, host="127.0.0.1", port=port, log_config=None))
    watek = threading.Thread(target=uv.run, daemon=True)
    watek.start()
    for _ in range(100):
        if uv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    uv.should_exit = True
    watek.join(5)


@pytest.fixture
def strona(serwer):
    opcje_startu = [{"channel": "chrome"}, {}]
    if os.getenv("PIECZAPP_CHROMIUM"):
        opcje_startu.append({"executable_path": os.environ["PIECZAPP_CHROMIUM"]})
    with playwright.sync_playwright() as p:
        przegladarka = None
        for opcje in opcje_startu:
            try:
                przegladarka = p.chromium.launch(headless=True, **opcje)
                break
            except Exception:  # noqa: BLE001
                continue
        if przegladarka is None:
            pytest.skip("Brak przegladarki dla Playwright")
        strona = przegladarka.new_page()
        bledy = []
        strona.on("pageerror", lambda e: bledy.append(str(e)))
        strona.route("**/api/abonament*", lambda trasa: trasa.fulfill(status=404, json={"detail": "tryb lokalny"}))
        strona.adres = serwer
        yield strona
        assert not bledy, bledy
        przegladarka.close()


def docx(tekst, sciezka):
    d = Document()
    for linia in tekst.split("\n"):
        d.add_paragraph(linia)
    d.save(sciezka)
    return str(sciezka)


def test_zasady_styl_i_raport(strona, tmp_path):
    strona.goto(strona.adres + "/")
    strona.wait_for_load_state("networkidle")
    strona.locator('.krok[data-etap="9"]').click()
    strona.locator("#pz-liczby .pz-liczba").first.wait_for()

    # Zdanie -> "Tak to rozumiem" -> Enter
    strona.locator("#pz-tekst").fill("Zamiast „w/w” pisz „wyżej wymieniony”")
    strona.locator("#pz-podglad .pz-opis-glowny", has_text="wyżej wymieniony").wait_for()
    strona.keyboard.press("Enter")
    strona.locator("#pz-stan", has_text="Dodane").wait_for()
    strona.locator(".pz-zasada", has_text="Zamiast „w/w”").wait_for()
    assert strona.locator(".pz-grupa", has_text="Słownictwo").count() == 1

    # Nauka stylu z aktow
    pliki = [docx(AKT.replace("Jan KOWALSKI", f"Osoba NUMER{'ABCDE'[i]}"), tmp_path / f"a{i}.docx") for i in range(5)]
    strona.locator("#pz-pliki").set_input_files(pliki)
    strona.locator("#pz-wynik-nauki", has_text="Nauczyłem się z 5 aktów").wait_for()
    assert strona.locator(".pz-nawyk").count() >= 3
    if strona.locator("#pz-wiecej-sugestii").count():
        strona.locator("#pz-wiecej-sugestii").click()
    strona.locator(".pz-sugestia", has_text="Po § zawsze spacja").locator("button", has_text="Pilnuj tego").click()
    strona.locator(".pz-zasada", has_text="Po § zawsze spacja").wait_for()
    assert strona.locator("#pz-sformulowania .pz-sformulowanie").count() >= 1
    assert "KOWALSKI" not in strona.locator("#pz-karta-sformulowan").inner_text()

    # Sprawdzenie dowolnego tekstu z wersja poprawiona
    strona.locator("#pz-test").fill("§1. Sprzedaje w/w lokal.")
    strona.locator("#pz-sprawdz").click()
    strona.locator("#pz-wstaw").click()
    assert strona.locator("#pz-test").input_value() == "§ 1. Sprzedaje wyżej wymieniony lokal."

    # Raport nad projektem z podswietlonym naruszeniem
    strona.evaluate("""() => { pokaz(3); pokazProjekt({projekt: '§ 1. Sprzedaje lokal.', brakujace: 0, do_wyboru: 0,
        zgodnosc: {zgodny: false, sprawdzonych: 7, blokujacych: 1, ostrzezen: 0, poprawki: [],
          naruszenia: [{poziom: 'blokuje', komunikat: 'Użyto „lokal”.', tekst_zasady: 'Nigdy nie używaj „lokal”',
                        fragment: 'Sprzedaje lokal.', trafienie: 'lokal'}]}}); }""")
    assert "narusza 1" in strona.locator("#zgodnosc3").inner_text()
    assert strona.locator("#projekt mark.naruszenie").inner_text() == "lokal"


@pytest.fixture
def serwer_u_siebie(tmp_path, monkeypatch):
    """Ta sama aplikacja, ale kazde zadanie jak od kancelarii "u siebie"."""
    import uvicorn
    import config
    import magazyn
    monkeypatch.setattr(config, "DANE", tmp_path)
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    import app as aplikacja

    async def u_siebie(scope, receive, send):
        znacznik = magazyn.przechowywanie_var.set("u-klienta")
        try:
            await aplikacja.app(scope, receive, send)
        finally:
            magazyn.przechowywanie_var.reset(znacznik)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    uv = uvicorn.Server(uvicorn.Config(u_siebie, host="127.0.0.1", port=port, log_config=None))
    watek = threading.Thread(target=uv.run, daemon=True)
    watek.start()
    for _ in range(100):
        if uv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    uv.should_exit = True
    watek.join(5)


def test_u_siebie_zasady_w_folderze_kancelarii(serwer_u_siebie, tmp_path):
    opcje_startu = [{"channel": "chrome"}, {}]
    if os.getenv("PIECZAPP_CHROMIUM"):
        opcje_startu.append({"executable_path": os.environ["PIECZAPP_CHROMIUM"]})
    with playwright.sync_playwright() as p:
        przegladarka = None
        for opcje in opcje_startu:
            try:
                przegladarka = p.chromium.launch(headless=True, **opcje)
                break
            except Exception:  # noqa: BLE001
                continue
        if przegladarka is None:
            pytest.skip("Brak przegladarki dla Playwright")
        strona = przegladarka.new_page()
        bledy = []
        strona.on("pageerror", lambda e: bledy.append(str(e)))
        strona.route("**/api/abonament*", lambda trasa: trasa.fulfill(status=404, json={"detail": "tryb lokalny"}))
        strona.goto(serwer_u_siebie + "/")
        strona.wait_for_load_state("networkidle")
        # Folder kancelarii: prywatny folder przegladarki zamiast wskazanego na dysku.
        strona.evaluate("async () => { dysk.aktywny = true; dysk.folder = await navigator.storage.getDirectory(); }")
        strona.locator('.krok[data-etap="9"]').click()
        strona.locator("#pz-gdzie", has_text="Twoim folderze").wait_for()

        strona.locator("#pz-tekst").fill("Kwoty zawsze cyframi i słownie")
        strona.locator("#pz-podglad .pz-opis-glowny").wait_for()
        strona.keyboard.press("Enter")
        strona.locator(".pz-zasada", has_text="Kwoty zawsze").wait_for()

        pliki = [docx(AKT, tmp_path / f"a{i}.docx") for i in range(3)]
        strona.locator("#pz-pliki").set_input_files(pliki)
        strona.locator("#pz-wynik-nauki", has_text="Nauczyłem się z 3 aktów").wait_for()

        zapisane = strona.evaluate("""async () => {
            const f = await navigator.storage.getDirectory();
            const czytaj = async n => JSON.parse(await (await (await f.getFileHandle(n)).getFile()).text());
            return {zasady: await czytaj("notarai-zasady.json"), styl: await czytaj("notarai-styl.json")}; }""")
        assert [z["typ"] for z in zapisane["zasady"]["zasady"]] == ["kwoty_slownie"]
        assert len(zapisane["styl"]["akty"]) == 3 and "KOWALSKI" not in str(zapisane["styl"])
        # serwer: zadnych plikow zasad, stylu ani aktow
        assert not [p for p in tmp_path.rglob("*") if p.suffix == ".json"]

        # po odswiezeniu strony zasady wracaja z folderu
        strona.reload()
        strona.wait_for_load_state("networkidle")
        strona.evaluate("async () => { dysk.aktywny = true; dysk.folder = await navigator.storage.getDirectory(); }")
        strona.locator('.krok[data-etap="9"]').click()
        strona.locator(".pz-zasada", has_text="Kwoty zawsze").wait_for()
        assert not bledy, bledy
        przegladarka.close()
