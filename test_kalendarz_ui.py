"""Smoke test okna dnia w kalendarzu - prawdziwa strona w Chrome (Playwright).

Odtwarza nagranie z 1.11.2026: w trakcie edycji terminu klik w wolna godzine
przenosil go po cichu, a jego godzina wygladala na wolna. Teraz:
- klik w wolna godzine z dala od terminu zaczyna nowa rezerwacje,
- przeniesienie idzie przyciskiem "Przenies" i wymaga potwierdzenia,
- przedluzenie o sasiednia godzine dziala bez pytan,
- niezapisane zmiany nie gina po cichu przy kliknieciu innego terminu,
- termin ma kilka telefonow z imionami,
- dzien ma domyslnie godziny 8:30-15:00; pozniejsze doklada przycisk i nie
  licza sie one do kropki zajetosci dnia (prosba z 28.11.2026).

Wymaga Chrome; bez niego test jest pomijany. Dane zmyslone (Sobczak/Pawlak).
"""
import socket
import threading
import time
from datetime import date, timedelta

import pytest

playwright = pytest.importorskip("playwright.sync_api")

DZIEN = date.today().isoformat()


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
        try:
            przegladarka = p.chromium.launch(channel="chrome", headless=True)
        except Exception as blad:  # noqa: BLE001
            pytest.skip(f"Brak Chrome dla Playwright: {blad}")
        strona = przegladarka.new_page()
        strona.okna = []        # tresci okien confirm(), w kolejnosci
        strona.zgoda = True     # odpowiedz na nastepne confirm()

        def okno(dialog):
            strona.okna.append(dialog.message)
            dialog.accept() if strona.zgoda else dialog.dismiss()
        strona.on("dialog", okno)
        # Abonament w trybie lokalnym konczy sie bledem serwera (brak kancelarii
        # w zadaniu) - kalendarza nie dotyczy, a zasmieca test ostrzezeniami.
        strona.route("**/api/abonament*", lambda trasa: trasa.fulfill(status=404, json={"detail": "tryb lokalny"}))
        strona.adres = serwer
        yield strona
        przegladarka.close()


def zarezerwuj(strona, godzina, koniec, uczestnicy, rodzaj, dzien=DZIEN):
    odp = strona.request.post(strona.adres + "/api/kalendarz", data={
        "data": dzien, "godzina": godzina, "koniec": koniec, "uczestnicy": uczestnicy, "rodzaj": rodzaj})
    assert odp.ok, odp.text()


def dzien_roboczy():
    """Najblizszy wtorek albo sroda bez stalego swieta (ruchome wypadaja w inne dni)."""
    stale = {"01-01", "01-06", "05-01", "05-03", "08-15", "11-01", "11-11", "12-24", "12-25", "12-26"}
    d = date.today() + timedelta(days=1)
    while d.weekday() not in (1, 2) or d.strftime("%m-%d") in stale:
        d += timedelta(days=1)
    return d.isoformat()


def na_serwerze(strona):
    wpisy = strona.request.get(strona.adres + "/api/kalendarz").json()
    return {w["uczestnicy"]: (w["godzina"], w["koniec"]) for w in wpisy}


def okienko(strona, od):
    return strona.locator(".kal-slot", has_text=od + "–")


def wejdz_do_kalendarza(strona):
    strona.goto(strona.adres + "/")
    # Po wczytaniu ustawien aplikacja sama przechodzi na Pulpit AI - klik
    # w Kalendarz przed tym momentem bywal cofany i test losowo padal.
    strona.locator("#pulpit-ai").wait_for(state="visible")
    strona.locator('.krok[data-etap="6"]').click()


def otworz_termin(strona, kto):
    wejdz_do_kalendarza(strona)
    strona.locator(".kal-wpis", has_text=kto).click()
    strona.locator("#kal-okno").wait_for(state="visible")


def test_klik_w_wolna_godzine_nie_przenosi_terminu(strona):
    zarezerwuj(strona, "10:00", "10:30", "Pawlak Ewa", "testament")
    zarezerwuj(strona, "10:30", "11:00", "Sobczak Tomasz", "poświadczenie podpisów")
    zarezerwuj(strona, "11:00", "12:00", "Pawlak Grzegorz", "darowizna")
    przed = na_serwerze(strona)

    otworz_termin(strona, "Sobczak Tomasz")
    assert strona.locator("#kal-zapisz").inner_text() == "Zapisz zmiany"
    okienko(strona, "12:30").click()

    # Nowa rezerwacja, a termin Sobczaka dalej zajmuje 10:30.
    assert strona.locator("#kal-zapisz").inner_text() == "Rezerwuj"
    assert "zajety" in okienko(strona, "10:30").get_attribute("class")
    assert "Sobczak Tomasz" in okienko(strona, "10:30").inner_text()
    assert "wybrany" in okienko(strona, "12:30").get_attribute("class")
    assert strona.locator("#kal-uczestnicy").input_value() == ""
    assert strona.okna == []
    assert na_serwerze(strona) == przed


def test_przeniesienie_przyciskiem(strona):
    zarezerwuj(strona, "10:00", "10:30", "Pawlak Ewa", "testament")
    zarezerwuj(strona, "10:30", "11:00", "Sobczak Tomasz", "poświadczenie podpisów")

    otworz_termin(strona, "Sobczak Tomasz")
    strona.locator("#kal-przenies").click()
    okienko(strona, "13:00").click()
    assert "wybrany" in okienko(strona, "13:00").get_attribute("class")
    # Dawna godzina nie udaje wolnej, dopoki zmiana nie jest zapisana.
    assert "zwolni się po zapisie" in okienko(strona, "10:30").inner_text()

    strona.zgoda = False
    strona.locator("#kal-zapisz").click()
    assert strona.okna and "Przenieść termin z 10:30–11:00 na 13:00–13:30" in strona.okna[-1]
    assert na_serwerze(strona)["Sobczak Tomasz"] == ("10:30", "11:00")

    strona.zgoda = True
    strona.locator("#kal-zapisz").click()
    strona.locator("#stan6", has_text="Zapisano").wait_for(state="attached")
    assert na_serwerze(strona) == {"Pawlak Ewa": ("10:00", "10:30"), "Sobczak Tomasz": ("13:00", "13:30")}


def test_przedluzenie_i_niezapisane_zmiany(strona):
    zarezerwuj(strona, "10:00", "10:30", "Pawlak Ewa", "testament")
    zarezerwuj(strona, "11:00", "12:00", "Pawlak Grzegorz", "darowizna")

    otworz_termin(strona, "Pawlak Grzegorz")
    okienko(strona, "12:00").click()          # sasiednia - przedluzenie
    assert strona.locator("#kal-wybrane").inner_text().startswith("Termin 11:00–12:30")

    # Klik w inny termin z niezapisanymi zmianami - pytamy; "Anuluj" zostawia edycje.
    strona.zgoda = False
    okienko(strona, "10:00").click()
    assert "nie są zapisane" in strona.okna[-1]
    assert strona.locator("#kal-uczestnicy").input_value() == "Pawlak Grzegorz"

    ile_okien = len(strona.okna)
    strona.locator("#kal-zapisz").click()     # przedluzenie bez pytania
    strona.locator("#stan6", has_text="Zapisano").wait_for(state="attached")
    assert len(strona.okna) == ile_okien
    assert na_serwerze(strona)["Pawlak Grzegorz"] == ("11:00", "12:30")
    assert na_serwerze(strona)["Pawlak Ewa"] == ("10:00", "10:30")


def test_kilka_telefonow(strona):
    zarezerwuj(strona, "09:00", "09:30", "Pawlak Ewa", "testament")
    otworz_termin(strona, "Pawlak Ewa")
    strona.locator("#kal-anuluj").click()
    strona.locator("#kal-pozniej").click()    # 15:00 to juz pozniejsza godzina
    okienko(strona, "15:00").click()
    strona.locator("#kal-uczestnicy").fill("Sobczak, Pawlak")
    strona.locator("#kal-telefony .imie").nth(0).fill("Tomasz")
    strona.locator("#kal-telefony .numer").nth(0).fill("600 100 200")
    strona.locator("#kal-dodaj-tel").click()
    strona.locator("#kal-telefony .imie").nth(1).fill("Ewa")
    strona.locator("#kal-telefony .numer").nth(1).fill("601 200 300")
    strona.locator(".kal-rodzaj").get_by_text("Sprzedaż", exact=True).click()
    strona.locator("#kal-zapisz").click()
    strona.locator("#stan6", has_text="Zapisano").wait_for(state="attached")

    wpis = next(w for w in strona.request.get(strona.adres + "/api/kalendarz").json()
                if w["uczestnicy"] == "Sobczak, Pawlak")
    assert wpis["telefony"] == [{"imie": "Tomasz", "numer": "600 100 200"}, {"imie": "Ewa", "numer": "601 200 300"}]
    # Po ponownym otwarciu oba wiersze wracaja do formularza (dzien z terminem
    # po 15:00 sam pokazuje pozniejsze godziny).
    okienko(strona, "15:00").click()
    assert strona.locator("#kal-telefony .numer").evaluate_all("l => l.map(x => x.value)") == ["600 100 200", "601 200 300"]
    assert "Tomasz:" in strona.locator("#kal-najblizsze").inner_text()


def otworz_dzien(strona, dzien):
    wejdz_do_kalendarza(strona)
    strona.locator("#kal-najblizsze .termin").first.wait_for()
    strona.evaluate("d => otworzDzien(d)", dzien)
    strona.locator("#kal-okno").wait_for(state="visible")


def kropka_dnia(strona):
    return (strona.locator("#kal-kropka-dnia").get_attribute("class").split()[-1],
            strona.locator("#kal-stan-dnia").inner_text())


def test_domyslne_godziny_i_pozniejsze_bez_wplywu_na_kropke(strona):
    dzien = dzien_roboczy()
    zarezerwuj(strona, "09:00", "09:30", "Pawlak Ewa", "testament", dzien)
    otworz_dzien(strona, dzien)

    # Domyslnie 8:30-15:00: 13 okienek, ostatnie 14:30-15:00.
    godziny = strona.locator("#kal-godziny .kal-slot .g").all_inner_texts()
    assert godziny[0] == "08:30–09:00" and godziny[-1] == "14:30–15:00" and len(godziny) == 13
    assert strona.locator("#kal-pozniej").inner_text() == "+ Dodaj późniejszą godzinę (15:00–16:00)"
    assert kropka_dnia(strona) == ("k-ziel", "Wolne 6 z 6,5 godz. (8:30–15:00)")

    # Przycisk doklada godzine; kolejne klikniecie nastepna.
    strona.locator("#kal-pozniej").click()
    assert "po" in okienko(strona, "15:30").get_attribute("class").split()
    assert strona.locator("#kal-pozniej").inner_text() == "+ Dodaj późniejszą godzinę (16:00–17:00)"
    strona.locator("#kal-pozniej").click()
    assert okienko(strona, "16:30").count() == 1

    # Rezerwacja po 15:00 nie zmienia koloru ani opisu dnia.
    okienko(strona, "15:00").click()
    okienko(strona, "16:30").click()
    strona.locator("#kal-uczestnicy").fill("Sobczak Tomasz")
    strona.locator("#kal-zapisz").click()
    strona.locator("#stan6", has_text="Zapisano 15:00–17:00").wait_for(state="attached")
    assert kropka_dnia(strona) == ("k-ziel", "Wolne 6 z 6,5 godz. (8:30–15:00)")

    # Po odswiezeniu dzien z terminem po 15:00 sam pokazuje te godziny.
    otworz_dzien(strona, dzien)
    assert "Sobczak Tomasz" in okienko(strona, "16:30").inner_text()
    assert strona.locator("#kal-pozniej").inner_text() == "+ Dodaj późniejszą godzinę (17:00–18:00)"

    # Kolor zmienia dopiero zajetosc 8:30-15:00: 4,5 godz. zajete, 2 wolne ->
    # czerwona. Razem z 2 godz. po 15:00 byloby "pelne" - tych nie liczymy.
    zarezerwuj(strona, "10:00", "12:00", "Pawlak Grzegorz", "darowizna", dzien)
    zarezerwuj(strona, "12:00", "14:00", "Sobczak Ewa", "darowizna", dzien)
    otworz_dzien(strona, dzien)
    assert kropka_dnia(strona) == ("k-czerw", "Wolne 2 z 6,5 godz. (8:30–15:00)")
