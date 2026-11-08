"""Smoke test ekranow "Ksiegi i repertoria" oraz "Zgloszenia GIIF" w Chrome.

Wpis do rep. A z formularza, wniosek KW, zlozenie z numerem REP.C (wpis
w repertorium C) i szkic zgloszenia GIIF. Bez Chrome / Chromium test jest
pomijany. Dane zmyslone (Sobczak/Pawlak).
"""
import pytest

from test_kalendarz_ui import serwer  # noqa: F401 - fixture serwera

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def strona(serwer):  # noqa: F811
    with playwright.sync_playwright() as p:
        try:
            przegladarka = p.chromium.launch(channel="chrome", headless=True)
        except Exception:  # noqa: BLE001
            try:
                przegladarka = p.chromium.launch(headless=True)
            except Exception as blad:  # noqa: BLE001
                pytest.skip(f"Brak przegladarki dla Playwright: {blad}")
        strona = przegladarka.new_page()
        strona.odpowiedzi = []

        def okno(dialog):
            dialog.accept(strona.odpowiedzi.pop(0) if strona.odpowiedzi else None)
        strona.on("dialog", okno)
        strona.route("**/api/abonament*", lambda trasa: trasa.fulfill(status=404, json={"detail": "tryb lokalny"}))
        strona.adres = serwer
        yield strona
        przegladarka.close()


def test_repertorium_wniosek_kw_i_giif(strona):
    strona.goto(strona.adres + "/")
    # Start aplikacji konczy sie pokazaniem kokpitu - dopiero potem przechodzimy dalej.
    strona.locator("#kokpit").wait_for(state="visible")
    strona.wait_for_load_state("networkidle")
    strona.locator('.krok[data-etap="8"]').click()
    strona.locator("#ks-zakladki button", has_text="Repertorium A").wait_for()
    strona.fill('#ks-rok', "2026")
    pola = {"data_czynnosci": "2026-11-03", "strony": "Jan Sobczak; Anna Pawlak",
            "tresc": "Umowa sprzedazy lokalu", "wartosc_przedmiotu": "650000", "podatek_pcc": "13000"}
    for pole, wartosc in pola.items():
        strona.fill(f'#ks-nowy [data-p="{pole}"]', wartosc)
    strona.click("#ks-dodaj")
    strona.locator("#ks-lista td", has_text="Rep. A nr 1/2026").wait_for()

    strona.locator('#ks-lista [data-a="kw"]').click()
    strona.fill("#kw-numer", "WA4M/00160286/2")
    strona.fill("#kw-sad", "SR dla Warszawy-Mokotowa")
    strona.fill("#kw-notariusz", "Maria Notariuszowa")
    strona.fill("#kw-siedziba", "Warszawa")
    strona.select_option("#kw-na-rzecz", "Anna Pawlak")
    strona.check('.kw-zad[value="wpis_wlasnosci"]')
    strona.click("#kw-zapisz")
    # strony z formularza nie maja PESEL - wniosek pokazuje braki
    strona.locator("#ks-wniosek .stan.blad", has_text="PESEL").wait_for()
    strona.locator("[data-pakiet]").first.click()
    strona.locator("#kw-pakiet b", has_text="STOP").wait_for()

    # strona z PESEL przez API, potem zlozenie w UI
    rep = strona.request.get(strona.adres + "/api/ksiegi-kancelarii/repertorium_a").json()[0]
    from conftest import z_suma_kontrolna
    strona.request.post(f"{strona.adres}/api/ksiegi-kancelarii/repertorium_a/{rep['id']}/poprawka", data={
        "zmiany": {"strony": [{"nazwa": "Jan Sobczak"},
                              {"nazwa": "Anna Pawlak", "pesel": z_suma_kontrolna("9002021234")}]},
        "powod": "PESEL nabywcy"})
    strona.click('#ks-zakladki button:has-text("Repertorium P")')
    strona.click('#ks-zakladki button:has-text("Repertorium A")')
    strona.locator('#ks-lista [data-a="kw"]').click()
    strona.fill("#kw-numer", "WA4M/00160286/2")
    strona.fill("#kw-sad", "SR dla Warszawy-Mokotowa")
    strona.fill("#kw-notariusz", "Maria Notariuszowa")
    strona.fill("#kw-siedziba", "Warszawa")
    strona.select_option("#kw-na-rzecz", "Anna Pawlak")
    strona.fill("#kw-rodzice", "Adam, Ewa")
    strona.check('.kw-zad[value="wpis_wlasnosci"]')
    strona.click("#kw-zapisz")
    strona.locator("[data-zloz]").nth(1).wait_for()
    strona.odpowiedzi = ["REP.C/NOTA/1234/26", "2026-11-03"]
    strona.locator("[data-zloz]").nth(1).click()
    strona.locator("#ks-wniosek", has_text="REP.C/NOTA/1234/26").wait_for()

    strona.click('#ks-zakladki button:has-text("Repertorium C")')
    strona.locator("#ks-lista td", has_text="REP.C/NOTA/1234/26").first.wait_for()

    strona.click('#ks-zakladki button:has-text("Repertorium A")')
    strona.odpowiedzi = ["4.25"]
    strona.locator('#ks-lista [data-a="giif"]').click()
    strona.locator("#stan8", has_text="szkic zgłoszenia").wait_for()
    strona.locator('.krok[data-etap="9"]').click()
    strona.locator("#giif-lista", has_text="Rep. A nr 1/2026").wait_for()
    assert "Braki" in strona.locator("#giif-lista").inner_text()
