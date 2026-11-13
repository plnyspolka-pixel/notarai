"""Odcinek 01 „Poniedziałek, 8:57” - caly scenariusz na prawdziwym interfejsie.

Serwer demo (scripts/demo_odcinek01.py) w osobnym procesie: tryb wielu
kancelarii z logowaniem, cztery konta (Helena, Marta - notariusze, Kuba -
aplikant, Basia - sekretariat), fikcyjna sprawa NOWAK — KACZMAREK (S-041-2026). Model zastapiony
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
SYGNATURA = "S-041-2026"
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
                               "--port", str(port), "--atrapa-modelu", str(ATRAPA_S),
                               "--skrzynka-demo", str(Path(__file__).parent / "scripts" / "demo_odcinek01_skrzynka")],
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
        assert marta.locator("#projekt mark.wybor").count() == 1             # kanon: tylko § 2 (hipoteka)
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
        assert ("<<BRAK: termin wydania lokalu>>", WD_COLOR_INDEX.YELLOW) in zakreslone
        assert sum(1 for _, k in zakreslone if k == WD_COLOR_INDEX.TURQUOISE) == 1
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


def test_poczta_do_przypisania_i_ustalenia_ze_zrodlem(serwer_demo):
    """Skrzynka testowa (3 maile .eml): Basia przypisuje maile do sprawy jednym
    kliknieciem, Marta wyciaga ustalenia (atrapa modelu). Przy polu „termin
    wydania” widac zrodla i brak potwierdzenia sprzedajacej; pole zostaje puste."""
    adres = serwer_demo
    with playwright.sync_playwright() as p:
        try:
            przegladarka = p.chromium.launch()
        except Exception as blad:  # noqa: BLE001
            pytest.skip(f"Brak Chromium dla Playwright: {blad}")
        basia = zaloguj(przegladarka.new_context(**BIURKO), adres, "basia@kancelaria-demo.test")
        basia.click('.krok[data-etap="12"]')
        basia.wait_for_selector("#etap12:not([hidden])")
        # Skrzynka sprawdza sie sama po otwarciu okna - bez klikania.
        maile = basia.locator("#skrzynka-lista .kor-el")
        maile.nth(2).wait_for()
        assert maile.count() == 3 and basia.inner_text("#licznik-poczty") == "3"
        assert basia.locator("#skrzynka-polaczona").is_visible()          # demo: skrzynka testowa podlaczona
        assert "tryb demo" in basia.inner_text("#skrzynka-polaczona")
        basia.click("#btn-skrzynka-sprawdz")
        basia.locator("#stan12", has_text="Brak nowych wiadomości").wait_for()
        d09 = maile.filter(has_text="najem")
        assert SYGNATURA in d09.locator(".propozycja").first.inner_text()
        assert "pewność: wysoka" in d09.locator(".propozycja").first.inner_text()
        zrzut(basia, "12-poczta-do-przypisania.png")
        # Nic nie jest przypisane, dopoki Basia nie kliknie.
        naglowki = {"Authorization": "Bearer " + basia.evaluate("token")}
        assert basia.request.get(f"{adres}/api/sprawy/{SPRAWA}/korespondencja", headers=naglowki).json()["wiadomosci"] == []
        import re
        for temat in ("Warunki transakcji", "Re: Warunki transakcji", SYGNATURA):
            el = maile.filter(has=basia.locator(".kor-temat", has_text=re.compile("^" + re.escape(temat)))).first
            if temat == "Re: Warunki transakcji":
                assert "odpowiedź w wątku" in el.locator(".propozycja").first.inner_text()
            przed = maile.count()
            el.locator(".propozycja button").first.click()
            basia.wait_for_function(f"document.querySelectorAll('#skrzynka-lista .kor-el').length === {przed - 1}")
        assert basia.locator("#licznik-poczty").is_hidden()

        marta = zaloguj(przegladarka.new_context(**BIURKO), adres, "marta@kancelaria-demo.test", "#sprawa=" + SPRAWA)
        marta.wait_for_selector("#etap2:not([hidden]), #etap3:not([hidden])")
        if marta.locator("#etap3").is_visible():          # po scenariuszu projekt juz jest
            marta.click('.krok[data-etap="2"]')
            marta.wait_for_selector("#etap2:not([hidden])")
        karta = marta.locator("#korespondencja-sprawy")
        karta.locator(".kor-el").nth(2).wait_for()
        assert "osoba kontaktowa" in karta.locator(".kor-el", has_text="Paweł Nowak").inner_text()
        for i in range(3):
            karta.locator(".kor-el").nth(i).get_by_role("button", name="Wyciągnij ustalenia").click()
            marta.locator("#stan-kor", has_text="Pola sprawy bez zmian").wait_for()
            stan = marta.locator("#stan-kor")
            stan.evaluate("e => e.textContent = ''")
        wiersz = marta.locator("#pola .wiersz", has_text="www: termin wydania lokalu")
        komunikat = wiersz.locator(".komunikat.korespondencja")
        komunikat.wait_for()
        tekst = komunikat.inner_text()
        assert "W korespondencji: 1.12" in tekst
        assert "Paweł Nowak — osoba kontaktowa, 9.11" in tekst and "Robert Kaczmarek — kupujący, 6.11" in tekst
        assert "Brak potwierdzenia: Irena Nowak (sprzedająca)" in tekst
        assert "relacjonuje" in tekst and "[atrapa modelu]" in tekst
        assert wiersz.locator("input").input_value() == ""                 # pole nie zostalo wypelnione
        assert marta.locator("#pliki-lista .zal-el", has_text="e-mail: Robert Kaczmarek (kupujący)").count() == 2
        wiersz.scroll_into_view_if_needed()
        zrzut(marta, "13-weryfikacja-ustalenie-z-korespondencji.png")
        karta.scroll_into_view_if_needed()
        zrzut(marta, "14-korespondencja-sprawy.png")
        sprawa = marta.request.get(f"{adres}/api/sprawy/{SPRAWA}",
                                   headers={"Authorization": "Bearer " + marta.evaluate("token")}).json()
        assert next(p for p in sprawa["pola"] if p["nazwa"].startswith("www:"))["wartosc"] is None
        for strona in (basia, marta):
            assert strona.bledy == [], strona.bledy
        przegladarka.close()


def test_kreator_podlaczenia_skrzynki(serwer_demo):
    """Helena (wlascicielka) wpisuje tylko adres - aplikacja rozpoznaje dostawce
    i podpowiada, jak sie zalogowac (bez prawdziwego logowania do poczty)."""
    adres = serwer_demo
    with playwright.sync_playwright() as p:
        try:
            przegladarka = p.chromium.launch()
        except Exception as blad:  # noqa: BLE001
            pytest.skip(f"Brak Chromium dla Playwright: {blad}")
        helena = zaloguj(przegladarka.new_context(**BIURKO), adres, "helena@kancelaria-demo.test")
        helena.click('.krok[data-etap="12"]')
        helena.wait_for_selector("#etap12:not([hidden])")
        # W demo skrzynka testowa jest podlaczona - kreator pokazujemy po wylaczeniu trybu demo w przegladarce.
        helena.evaluate("pokazUstawieniaSkrzynki({podlaczona: false, dni_wstecz: 30})")
        helena.fill("#skrz-email", "biuro@gmail.com")
        helena.click("#skrz-dalej")
        helena.locator("#skrz-nazwa", has_text="Gmail").wait_for()
        assert "hasło aplikacji" in helena.inner_text("#skrz-pomoc")
        assert helena.locator("#skrz-haslo").is_visible()
        zrzut(helena, "15-kreator-skrzynki-gmail.png")
        helena.fill("#skrz-email", "biuro@outlook.com")
        helena.click("#skrz-dalej")
        helena.locator("#skrz-nazwa", has_text="Microsoft").wait_for()
        assert "logowania przez Microsoft" in helena.inner_text("#stan-skrz")
        assert helena.bledy == [], helena.bledy
        przegladarka.close()
