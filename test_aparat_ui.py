"""Smoke test zdjec do sprawy na telefonie - prawdziwa strona w Chrome
(Playwright) w rozmiarze telefonu.

Notariusz robi kilka zdjec, moze jedno usunac, i dopiero "Wyslij" dodaje je
do plikow sprawy. Dwie drogi:
- podglad aparatu w przegladarce (tu: udawany aparat Chrome),
- bez podgladu (brak zgody albo aparatu) - migawka otwiera aparat telefonu
  przez <input capture>, po jednym zdjeciu.

Wymaga Chrome; bez niego test jest pomijany. Dane zmyslone (Sobczak/Pawlak).
"""
import json

import pytest

from test_kalendarz_ui import serwer  # noqa: F401

playwright = pytest.importorskip("playwright.sync_api")

SPRAWA = "aaa111aaa111"
TELEFON = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}


@pytest.fixture
def sprawa_na_serwerze(serwer):  # noqa: F811
    import config
    katalog = config.SPRAWY / SPRAWA
    (katalog / "skany").mkdir(parents=True)
    (katalog / "sprawa.json").write_text(json.dumps({"id": SPRAWA, "nazwa": "Sobczak - Pawlak",
                                                     "utworzono": "2026-10-28T10:00:00"}), "utf-8")
    (katalog / "odczyt.json").write_text(json.dumps({"pola": []}), "utf-8")
    return serwer


def otworz(p, adres, aparat: bool):
    argumenty = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] if aparat else []
    try:
        przegladarka = p.chromium.launch(channel="chrome", headless=True, args=argumenty)
    except Exception as blad:  # noqa: BLE001
        pytest.skip(f"Brak Chrome dla Playwright: {blad}")
    kontekst = przegladarka.new_context(**TELEFON, permissions=["camera"] if aparat else [])
    if not aparat:
        # Telefon bez podgladu w przegladarce: getUserMedia odmawia.
        kontekst.add_init_script("navigator.mediaDevices.getUserMedia = () =>"
                                 " Promise.reject(new DOMException('brak', 'NotAllowedError'))")
    strona = kontekst.new_page()
    strona.okna = []
    strona.on("dialog", lambda d: (strona.okna.append(d.message), d.accept()))
    strona.route("**/api/abonament*", lambda t: t.fulfill(status=404, json={"detail": "tryb lokalny"}))
    strona.goto(adres + "/")
    strona.locator("#btn-menu").click()
    strona.locator(".sprawa-el", has_text="Sobczak - Pawlak").click()
    strona.locator("#btn-aparat-gora").click()   # aparat w gornym pasku, bez przewijania
    strona.locator("#okno-aparat").wait_for(state="visible")
    return przegladarka, strona


def pliki_sprawy(strona, adres):
    return [p["nazwa"] for p in strona.request.get(f"{adres}/api/sprawy/{SPRAWA}/pliki").json()]


def test_kilka_zdjec_podgladem_i_jedno_wyslij(sprawa_na_serwerze):
    adres = sprawa_na_serwerze
    with playwright.sync_playwright() as p:
        przegladarka, strona = otworz(p, adres, aparat=True)
        strona.wait_for_function("document.getElementById('aparat-wideo').videoWidth > 0")
        for _ in range(3):
            strona.locator("#aparat-migawka").click()
        strona.locator("#aparat-wyslij", has_text="Wyślij (3)").wait_for()
        assert pliki_sprawy(strona, adres) == []        # nic nie idzie przed "Wyslij"

        strona.locator(".miniatura button").nth(1).click()   # jedno nieudane - usuwamy
        assert strona.locator("#aparat-wyslij").inner_text() == "Wyślij (2)"

        strona.locator("#aparat-wyslij").click()
        strona.locator("#okno-aparat").wait_for(state="hidden")
        nazwy = pliki_sprawy(strona, adres)
        assert len(nazwy) == 2 and all(n.startswith("zdjecie-") and n.endswith(".jpg") for n in nazwy)
        assert strona.locator("#pliki-lista .zal-el").count() == 2
        jpg = strona.request.get(f"{adres}/api/sprawy/{SPRAWA}/pliki/{nazwy[0]}").body()
        assert jpg[:2] == b"\xff\xd8"
        przegladarka.close()


def test_bez_podgladu_aparat_telefonu_po_jednym(sprawa_na_serwerze, tmp_path):
    adres = sprawa_na_serwerze
    zdjecie = tmp_path / "IMG_0001.jpg"
    zdjecie.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 2000)
    with playwright.sync_playwright() as p:
        przegladarka, strona = otworz(p, adres, aparat=False)
        assert "nie dostała zgody" in strona.locator("#aparat-brak").inner_text()
        for _ in range(2):
            with strona.expect_file_chooser() as wybor:
                strona.locator("#aparat-migawka").click()
            wybor.value.set_files(str(zdjecie))
        assert strona.locator("#aparat-wyslij").inner_text() == "Wyślij (2)"

        # Zamkniecie z niewyslanymi zdjeciami pyta (tu: zgoda) i niczego nie wysyla.
        strona.locator("#aparat-zamknij").click()
        assert "przepadną" in strona.okna[-1]
        assert pliki_sprawy(strona, adres) == []

        strona.locator("#btn-aparat-gora").click()
        with strona.expect_file_chooser() as wybor:
            strona.locator("#aparat-migawka").click()
        wybor.value.set_files(str(zdjecie))
        strona.locator("#aparat-wyslij").click()
        strona.locator("#okno-aparat").wait_for(state="hidden")
        assert len(pliki_sprawy(strona, adres)) == 1
        przegladarka.close()
