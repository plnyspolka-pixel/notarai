"""Odcinek 01 „Poniedziałek, 8:57” - caly scenariusz na prawdziwym interfejsie.

Serwer demo (scripts/demo_odcinek01.py) w osobnym procesie: tryb wielu
kancelarii z logowaniem, cztery konta (Helena, Marta - notariusze, Kuba -
aplikant, Basia - sekretariat), fikcyjna sprawa Nowak. Model zastapiony
atrapa (projekt oznaczony „PRÓBA NAGRANIA”), wiec test nie wola Bedrock.

Sceny: 03 kalendarz -> sprawa (Basia), 04 ta sama sprawa na telefonie (Kuba),
05 zdjecie aparatem -> widoczne na komputerze Marty bez odswiezania, 06 filtr
„Wymagają uwagi”, 08-10 „Sporządź projekt” w tle, praca w kalendarzu,
powiadomienie, podglad ze znacznikami, „Pobierz jako Word” ze znacznikami.
Plus stanowiska: sekretariat nie sporzadza projektu (UI i serwer).

Zrzuty ekranu tylko na zyczenie:  NOTARAI_ZRZUTY=docs/odcinek-01-zrzuty pytest test_odcinek01_ui.py
"""
import io
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

HASLO = "Demo-Odc01!"
SPRAWA = "e01demo00001"
SYGNATURA = "KPS 47/2026"
ATRAPA_S = 3.0
TELEFON = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True,
           "device_scale_factor": 2}
BIURKO = {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 2}
ZRZUTY = os.getenv("NOTARAI_ZRZUTY", "")


@pytest.fixture(scope="module")
def serwer_demo(tmp_path_factory):
    dane = tmp_path_factory.mktemp("demo-odcinek01")
    skrypt = Path(__file__).parent / "scripts" / "demo_odcinek01.py"
    srodowisko = {**os.environ, "PIECZAPP_MAGAZYN": "lokalny", "PIECZAPP_AML_LISTY": "0"}
    srodowisko.pop("PIECZAPP_COGNITO_POOL", None)
    subprocess.run([sys.executable, str(skrypt), "przygotuj", "--dane", str(dane)],
                   check=True, env=srodowisko, capture_output=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proces = subprocess.Popen([sys.executable, str(skrypt), "serwer", "--dane", str(dane), "--haslo", HASLO,
                               "--port", str(port), "--atrapa-modelu", str(ATRAPA_S)],
                              env=srodowisko, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    adres = f"http://127.0.0.1:{port}"
    import urllib.request
    for _ in range(100):
        try:
            urllib.request.urlopen(adres + "/zdrowie", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    else:
        proces.kill()
        proces.wait(10)
        pytest.fail("serwer demo nie wstal: " + proces.stdout.read().decode(errors="replace")[-2000:])
    yield adres
    proces.terminate()
    proces.wait(10)
    proces.stdout.close()


def zrzut(strona, nazwa):
    if ZRZUTY:
        Path(ZRZUTY).mkdir(parents=True, exist_ok=True)
        strona.screenshot(path=str(Path(ZRZUTY) / nazwa))


def zaloguj(kontekst, adres, email, hasz=""):
    strona = kontekst.new_page()
    strona.bledy = []
    strona.on("pageerror", lambda e: strona.bledy.append(str(e)))
    strona.on("dialog", lambda d: d.accept())
    strona.goto(adres + "/" + hasz)
    strona.fill("#pole-email", email)
    strona.fill("#pole-haslo", HASLO)
    strona.click("#btn-zaloguj")
    strona.wait_for_selector("#brama", state="hidden")
    return strona


def test_scenariusz_odcinka_01(serwer_demo):
    adres = serwer_demo
    with playwright.sync_playwright() as p:
        try:
            przegladarka = p.chromium.launch(args=["--use-fake-ui-for-media-stream",
                                                   "--use-fake-device-for-media-stream"])
        except Exception as blad:  # noqa: BLE001
            pytest.skip(f"Brak Chromium dla Playwright: {blad}")

        # --- sc. 03: Basia (sekretariat) - kalendarz, termin jutro 11:30, przejscie do sprawy
        basia = zaloguj(przegladarka.new_context(**BIURKO), adres, "basia@kancelaria-demo.test")
        basia.wait_for_function("document.body.classList.contains('bez-projekt')")
        assert not basia.locator('.krok[data-etap="10"]').is_visible()      # ksiegi - tylko notariusz
        assert not basia.locator("#btn-nowa").is_visible()                   # odczyt modelem - nie
        basia.click('.krok[data-etap="6"]')
        termin = basia.locator("#kal-najblizsze .termin", has_text="11:30")
        termin.wait_for()
        assert "sprzedaż nieruchomości" in termin.inner_text() and SYGNATURA in termin.inner_text()
        assert "brak telefonu" not in termin.inner_text()
        termin.scroll_into_view_if_needed()
        zrzut(basia, "01-kalendarz-termin-jutro.png")
        termin.get_by_role("button", name="Otwórz sprawę").click()
        basia.wait_for_selector("#etap2:not([hidden])")
        assert basia.inner_text("#oznaczenie2") == SYGNATURA
        assert basia.evaluate("location.hash") == "#sprawa=" + SPRAWA
        assert not basia.locator("#btn-generuj").is_visible()               # sekretariat nie sporzadza
        assert basia.locator("#pola input").first.evaluate("w => w.readOnly")
        zrzut(basia, "02-sprawa-z-kalendarza-sekretariat.png")
        odmowa = basia.request.post(f"{adres}/api/sprawy/{SPRAWA}/projekt", data={"pola": [], "polecenie": ""},
                                    headers={"Authorization": "Bearer " + basia.evaluate("token")})
        assert odmowa.status == 403 and "sekretariat" in odmowa.json()["detail"]

        # Marta (notariusz) ma sprawe otwarta na komputerze, zanim Kuba zrobi zdjecie.
        marta = zaloguj(przegladarka.new_context(**BIURKO), adres, "marta@kancelaria-demo.test", "#sprawa=" + SPRAWA)
        marta.wait_for_selector("#etap2:not([hidden])")
        assert marta.locator("#pliki-lista .zal-el").count() == 0

        # --- sc. 04: Kuba na telefonie - ta sama sprawa, to samo oznaczenie
        kuba = zaloguj(przegladarka.new_context(**TELEFON, permissions=["camera"]), adres,
                       "kuba@kancelaria-demo.test", "#sprawa=" + SPRAWA)
        kuba.wait_for_selector("#etap2:not([hidden])")
        assert kuba.inner_text("#oznaczenie2") == SYGNATURA
        assert kuba.evaluate("document.documentElement.scrollWidth") <= 390   # bez przewijania w bok
        zrzut(kuba, "03-telefon-ta-sama-sprawa.png")

        # --- sc. 05: „Aparatem” -> zdjecie -> „Wyślij”
        kuba.click("#btn-aparat-gora")
        kuba.wait_for_function("document.getElementById('aparat-wideo').videoWidth > 0")
        kuba.click("#aparat-migawka")
        kuba.locator("#aparat-wyslij", has_text="Wyślij (1)").wait_for()
        zrzut(kuba, "04-telefon-aparat.png")
        kuba.click("#aparat-wyslij")
        kuba.wait_for_selector("#okno-aparat", state="hidden")
        kuba.locator("#pliki-lista .zal-el").first.wait_for()
        kuba.locator("#pliki-sprawy").scroll_into_view_if_needed()
        zrzut(kuba, "05-telefon-zdjecie-w-sprawie.png")
        # Zdjecie nie uruchamia odczytu: pola sprawy bez zmian.
        sprawa = kuba.request.get(f"{adres}/api/sprawy/{SPRAWA}",
                                  headers={"Authorization": "Bearer " + kuba.evaluate("token")}).json()
        assert sum(1 for p in sprawa["pola"] if p["wymaga_uwagi"]) == 3 and sprawa["projekt"] is None

        # Na komputerze Marty zdjecie pojawia sie samo (lista plikow odswieza sie co 15 s).
        start = time.monotonic()
        marta.locator("#pliki-lista .zal-el", has_text=".jpg").wait_for(timeout=25000)
        assert time.monotonic() - start < 25
        marta.locator("#pliki-sprawy").scroll_into_view_if_needed()
        zrzut(marta, "06-komputer-marty-zdjecie-widoczne.png")

        # --- sc. 06: weryfikacja odczytu, filtr „Wymagają uwagi”
        marta.click('#etap2 .chip[data-f="uwaga"]')
        widoczne = marta.locator("#pola .wiersz:visible")
        assert widoczne.count() == 3
        assert marta.locator('#etap2 .chip[data-f="uwaga"]').inner_text() == "Wymagają uwagi (3)"
        marta.locator("#pola").scroll_into_view_if_needed()
        zrzut(marta, "07-weryfikacja-wymagaja-uwagi.png")

        # --- sc. 08-10: „Sporządź projekt”, w tym czasie kalendarz, powiadomienie, podglad
        start = time.monotonic()
        marta.click("#btn-generuj")
        marta.locator("#stan2", has_text="Sporządzam projekt…").wait_for()
        assert marta.locator("#btn-generuj").is_disabled()
        marta.locator("#btn-generuj").scroll_into_view_if_needed()
        zrzut(marta, "08-sporzadzam-projekt.png")
        # Drugie urzadzenie widzi, ze projekt sie pisze, i nie zleci go drugi raz.
        stan = kuba.request.get(f"{adres}/api/sprawy/{SPRAWA}/projekt/stan",
                                headers={"Authorization": "Bearer " + kuba.evaluate("token")}).json()
        assert stan["stan"] == "w_toku"
        marta.click('.krok[data-etap="6"]')                                  # praca w innym widoku
        marta.wait_for_selector("#powiadomienie:not([hidden])", timeout=60000)
        czas = time.monotonic() - start
        assert marta.locator("#etap6").is_visible()                         # nikt nie przerzuca widoku
        zrzut(marta, "09-projekt-gotowy-powiadomienie.png")
        marta.click("#powiadomienie [data-akcja]")
        marta.wait_for_selector("#etap3:not([hidden])")
        assert marta.locator("#projekt mark.brak").count() >= 2
        assert marta.locator("#projekt mark.wybor").count() == 2
        assert "PRÓBA NAGRANIA" in marta.inner_text("#projekt")             # atrapa nie udaje modelu
        zrzut(marta, "10-projekt-dokumentu.png")
        print(f"\nczas projektu (atrapa {ATRAPA_S:g} s): {czas:.1f} s, narzut aplikacji {czas - ATRAPA_S:.1f} s")

        # --- sc. 10: „Pobierz jako Word”
        with marta.expect_download() as pobranie:
            marta.click("#btn-pobierz")
        from docx import Document
        from docx.enum.text import WD_COLOR_INDEX
        plik = Document(io.BytesIO(Path(pobranie.value.path()).read_bytes()))
        zakreslone = [(r.text, r.font.highlight_color) for a in plik.paragraphs for r in a.runs
                      if r.font.highlight_color]
        assert ("<<BRAK: dowód osobisty kupującego>>", WD_COLOR_INDEX.YELLOW) in zakreslone
        assert sum(1 for _, k in zakreslone if k == WD_COLOR_INDEX.TURQUOISE) == 2
        if ZRZUTY:
            Path(ZRZUTY, "projekt-demo-atrapa.docx").write_bytes(Path(pobranie.value.path()).read_bytes())

        # Helena (wlascicielka) widzi stanowiska zespolu.
        helena = zaloguj(przegladarka.new_context(**BIURKO), adres, "helena@kancelaria-demo.test")
        helena.click('.krok[data-etap="6"]')        # w panelu glownym stopka paska jest zwinieta
        helena.locator("#btn-zespol").wait_for(state="visible")
        helena.click("#btn-zespol")
        helena.locator("#zespol-lista select[data-stanowisko]").first.wait_for()
        wybrane = helena.eval_on_selector_all("#zespol-lista select[data-stanowisko]", "l => l.map(s => s.value)")
        assert sorted(wybrane) == ["aplikant", "notariusz", "notariusz", "sekretariat"]
        zrzut(helena, "11-zespol-stanowiska.png")

        for strona in (basia, marta, kuba, helena):
            assert strona.bledy == [], strona.bledy
        przegladarka.close()
