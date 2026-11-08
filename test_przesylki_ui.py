"""Smoke test widoku "Przesylki i korespondencja" w prawdziwej przegladarce.

Dodanie wypisu do dziennika przesylanych dokumentow, numer nadania wpisany
"czytnikiem" (tekst + Enter), poprawka pozycji, osobna numeracja dziennika
korespondencyjnego. Dane zmyslone (Sobczak/Pawlak).
"""
import socket
import threading
import time

import pytest

playwright = pytest.importorskip("playwright.sync_api")


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
    with playwright.sync_playwright() as p:
        przegladarka = None
        for opcje in ({"channel": "chrome"}, {}):
            try:
                przegladarka = p.chromium.launch(headless=True, **opcje)
                break
            except Exception:  # noqa: BLE001
                continue
        if przegladarka is None:
            pytest.skip("Brak przegladarki dla Playwright")
        strona = przegladarka.new_page()
        strona.on("dialog", lambda d: d.accept("pomyłka"))
        strona.route("**/api/abonament*", lambda trasa: trasa.fulfill(status=404, json={"detail": "tryb lokalny"}))
        strona.adres = serwer
        yield strona
        przegladarka.close()


def wpisy(strona, ksiega="przeslane"):
    return strona.request.get(f"{strona.adres}/api/przesylki/{ksiega}").json()


def test_wypis_numer_z_czytnika_i_poprawka(strona):
    strona.goto(strona.adres + "/")
    # Start aplikacji sam przelacza widok (kokpit, etap 1) - klikamy po nim.
    strona.wait_for_load_state("networkidle")
    strona.locator('.krok[data-etap="8"]').click()
    strona.locator("#prz-repertorium").wait_for()
    strona.locator("#prz-repertorium").fill("A 1234/2026")
    strona.locator("#prz-adresat").fill("Sąd Rejonowy w Zalesiu, Wydział Ksiąg Wieczystych")
    strona.locator("#prz-ulica").fill("ul. Sądowa 1")
    strona.locator("#prz-kod").fill("05-500")
    strona.locator("#prz-miejscowosc").fill("Zalesie")
    strona.locator("#prz-zapisz").click()
    strona.locator("#stan8", has_text="Dodano pozycję 1").wait_for()

    # Drugi wpis do tego samego sadu: adres podpowiada sie z poprzedniego.
    strona.locator("#prz-repertorium").fill("A 1235/2026")
    strona.locator("#prz-adresat").fill("Sąd Rejonowy w Zalesiu, Wydział Ksiąg Wieczystych")
    strona.locator("#prz-adresat").dispatch_event("change")
    assert strona.locator("#prz-kod").input_value() == "05-500"
    strona.locator("#prz-zapisz").click()
    strona.locator("#stan8", has_text="Dodano pozycję 2").wait_for()

    # Czytnik kodow: numer + Enter zapisuje i przechodzi do nastepnej pozycji.
    pola = strona.locator("input.prz-nr")
    pola.nth(0).click()
    strona.keyboard.type("00659007734210012346")
    strona.keyboard.press("Enter")
    strona.locator("#stan8b", has_text="Numer nadania zapisany").wait_for()
    assert strona.evaluate("document.activeElement.classList.contains('prz-nr')")
    assert {w["lp"]: w["numer_nadania"] for w in wpisy(strona)}[2] == "00659007734210012346"

    # Poprawka pozycji 1 zostawia slad.
    strona.locator("#prz-lista tr", has_text="A 1234/2026").locator('[data-akcja="popraw"]').click()
    strona.locator("#prz-repertorium").fill("A 1243/2026")
    strona.locator("#prz-zapisz").click()
    strona.locator("#stan8", has_text="Poprawiono pozycję 1").wait_for()
    pierwsza = wpisy(strona)[0]
    assert pierwsza["repertorium"] == "A 1243/2026" and pierwsza["poprawki"]

    # Anulowanie: pozycja zostaje, przekreslona.
    strona.locator("#prz-lista tr", has_text="A 1243/2026").locator('[data-akcja="anuluj"]').click()
    strona.locator("#prz-lista tr.anul").wait_for()
    assert wpisy(strona)[0]["status"] == "anulowany"

    # Dziennik korespondencyjny ma wlasna numeracje.
    strona.locator('#prz-ksiegi .chip[data-k="korespondencja"]').click()
    strona.locator("#prz-kierunek").select_option("przychodzące")
    assert strona.locator("#prz-et-adresat").inner_text() == "Nadawca"
    strona.locator("#prz-tresc").fill("wezwanie do uzupełnienia wniosku")
    strona.locator("#prz-adresat").fill("Urząd Gminy Zalesie")
    strona.locator("#prz-sposob").select_option("list zwykły")
    strona.locator("#prz-zapisz").click()
    strona.locator("#stan8", has_text="Dodano pozycję 1").wait_for()
    assert len(wpisy(strona, "korespondencja")) == 1

    # Podglad ksiegi otwiera PDF w nowej karcie.
    with strona.context.expect_page() as nowa:
        strona.locator("#prz-podglad").click()
    nowa.value.wait_for_url("blob:**")


def test_kreator_poczty_od_wniosku_do_zbioru(strona, monkeypatch):
    import httpx
    import poczta_polska
    from test_poczta_polska import HASLO, LOGIN, Sejf, UdawanyNadawca
    nadawca, sejf = UdawanyNadawca(), Sejf()
    monkeypatch.setattr(poczta_polska, "TRANSPORT", httpx.MockTransport(nadawca))
    monkeypatch.setattr(poczta_polska, "sejf", sejf)

    strona.goto(strona.adres + "/")
    strona.wait_for_load_state("networkidle")
    strona.locator('.krok[data-etap="8"]').click()
    strona.locator("#pp-krok1").wait_for()

    # Krok 1: wniosek.
    for pole, wartosc in {"firma": "Kancelaria Notarialna Ewa Sobczak", "nip": "5260001246", "ulica": "Rynek",
                          "numer": "5", "kod": "05-500", "miejscowosc": "Zalesie", "imie": "Ewa", "nazwisko": "Sobczak",
                          "email": "kancelaria@example.com", "telefon": "600100200"}.items():
        strona.locator("#pp-" + pole).fill(wartosc)
    strona.locator("#pp-zapisz-wniosek").click()
    strona.locator("#pp-wyslij").wait_for()
    with strona.context.expect_page() as pdf:
        strona.locator("#pp-pdf").click()
    pdf.value.wait_for_url("blob:**")
    strona.locator("#pp-wyslalem").click()

    # Krok 2 -> 3: czekanie na umowe, potem login.
    strona.locator("#pp-krok2").wait_for()
    strona.locator("#pp-mam-login").click()
    strona.locator("#pp-krok3").wait_for()
    strona.locator("#pp-login").fill(LOGIN)
    strona.locator("#pp-haslo").fill(HASLO)
    strona.locator("#pp-polacz").click()
    strona.locator("#pp-polaczona").wait_for()
    assert "Połączono" in strona.locator("#pp-opis-polaczenia").inner_text()
    assert strona.locator("#pp-urzad").input_value() == "263867"
    assert sejf.dane["lokalna"]["haslo"] == HASLO and strona.locator("#pp-haslo").input_value() == ""

    # Wpis, nadanie, etykiety, zbior.
    strona.locator("#prz-repertorium").fill("A 1234/2026")
    strona.locator("#prz-adresat").fill("Sąd Rejonowy w Zalesiu, Wydział Ksiąg Wieczystych")
    strona.locator("#prz-ulica").fill("ul. Sądowa 1")
    strona.locator("#prz-kod").fill("05-500")
    strona.locator("#prz-miejscowosc").fill("Zalesie")
    strona.locator("#prz-zapisz").click()
    strona.locator("#stan8", has_text="Dodano pozycję 1").wait_for()
    strona.locator("#pp-akcje").wait_for()
    strona.locator(".prz-wybor").first.check()
    strona.locator("#pp-nadaj").click()
    strona.locator("#stan-pp-akcje", has_text="Nadano: 1").wait_for()
    assert strona.locator("input.prz-nr").first.input_value() == "00659007734000000001"
    with strona.context.expect_page() as etykiety:
        strona.locator(".prz-wybor").first.check()
        strona.locator("#pp-etykiety").click()
    etykiety.value.wait_for_url("blob:**")
    with strona.context.expect_page() as ksiazka:
        strona.locator("#pp-zbior").click()
    ksiazka.value.wait_for_url("blob:**")
    strona.locator("#pp-zbiory", has_text="zbiór 900").wait_for()
    assert nadawca.wywolania.count("sendEnvelope") == 1
