"""Klucz kancelarii (minimalne 3 x ZERO): sprawy w S3 tylko jako szyfrogram,
bez kodu kancelarii ani odczytu, ani zapisu. Atrapy S3 i Cognito, dane fikcyjne."""
import importlib

import pytest
from fastapi import Request

import szyfrowanie_kancelarii as szyfr
from test_magazyn import AtrapaS3, magazyn_s3  # noqa: F401
from test_zespol import ADMIN, _kancelaria, jako, srodowisko  # noqa: F401
from test_logowanie import _przywroc_moduly, logowanie_atrapa  # noqa: F401

CANARY = "PESEL 02070803628 Jan Testowy ul. Fikcyjna 1"


@pytest.fixture
def z_kluczem():
    kod = szyfr.nowy_kod()
    znacznik = szyfr.ustaw_dla_zadania(szyfr.kcv(kod), kod)
    yield kod
    szyfr.stan_var.reset(znacznik)


# --- kod i kryptografia ------------------------------------------------------


def test_kod_toleruje_myslniki_male_litery_i_pomylki_0_1_8():
    kod = szyfr.nowy_kod()
    assert len(kod.replace("-", "")) == 26
    wpisany = kod.lower().replace("-", " ").replace("O", "0").replace("o", "0")
    assert szyfr.z_kodu(wpisany) == szyfr.z_kodu(kod)


@pytest.mark.parametrize("zly", ["", "ABCD", "A" * 25 + "!", "A" * 30])
def test_zly_format_kodu(zly):
    with pytest.raises(szyfr.ZlyKlucz):
        szyfr.z_kodu(zly)


def test_kcv_nie_ujawnia_klucza_plikow(z_kluczem):
    klucz_plikow = szyfr.stan_var.get()
    assert szyfr.kcv(z_kluczem) not in klucz_plikow.hex()
    assert szyfr.z_kodu(z_kluczem).hex() not in szyfr.kcv(z_kluczem)


def test_szyfrogram_powiazany_z_adresem(z_kluczem):
    plik = szyfr.szyfruj(CANARY.encode(), "kancelarie/a/sprawy/1/sprawa.json")
    assert CANARY.encode() not in plik
    assert szyfr.odszyfruj(plik, "kancelarie/a/sprawy/1/sprawa.json") == CANARY.encode()
    # Ten sam plik podlozony pod inna sprawe albo kancelarie: odmowa.
    for obcy in ("kancelarie/a/sprawy/2/sprawa.json", "kancelarie/b/sprawy/1/sprawa.json"):
        with pytest.raises(szyfr.ZlyKlucz):
            szyfr.odszyfruj(plik, obcy)


def test_zmieniony_bajt_albo_jawny_plik_odrzucone(z_kluczem):
    adres = "kancelarie/a/sprawy/1/x"
    plik = bytearray(szyfr.szyfruj(b"tresc", adres))
    plik[-1] ^= 1
    with pytest.raises(szyfr.ZlyKlucz):
        szyfr.odszyfruj(bytes(plik), adres)
    with pytest.raises(szyfr.ZlyKlucz):
        szyfr.odszyfruj(b'{"jawny": true}', adres)


def test_inny_kod_tej_samej_kancelarii_odrzucony():
    with pytest.raises(szyfr.ZlyKlucz):
        szyfr.ustaw_dla_zadania(szyfr.kcv(szyfr.nowy_kod()), szyfr.nowy_kod())


def test_bez_kodu_brak_klucza():
    znacznik = szyfr.ustaw_dla_zadania(szyfr.kcv(szyfr.nowy_kod()), None)
    try:
        assert szyfr.aktywne()
        with pytest.raises(szyfr.BrakKlucza):
            szyfr.szyfruj(b"x", "k")
    finally:
        szyfr.stan_var.reset(znacznik)


def test_kancelaria_bez_klucza_jak_dotad():
    znacznik = szyfr.ustaw_dla_zadania(None, "cokolwiek")
    try:
        assert not szyfr.aktywne()
    finally:
        szyfr.stan_var.reset(znacznik)


# --- magazyn: S3 widzi tylko szyfrogram ---------------------------------------


def _sprawa(tmp, magazyn):
    magazyn.kancelaria_var.set("kancelaria-a")
    katalog = magazyn.sprawy_dir(tmp) / "abc123"
    katalog.mkdir(parents=True)
    (katalog / "sprawa.json").write_text('{"strony": "' + CANARY + '"}', encoding="utf-8")
    (katalog / "skan.pdf").write_bytes(b"%PDF-1.7 " + CANARY.encode())
    return katalog


def test_s3_dostaje_tylko_szyfrogram_i_odczyt_wraca(magazyn_s3, z_kluczem):
    magazyn, s3, tmp = magazyn_s3
    katalog = _sprawa(tmp, magazyn)
    magazyn.utrwal_sprawe(katalog)
    assert len(s3.obiekty) == 2
    for tresc in s3.obiekty.values():
        assert tresc.startswith(b"NAI1") and CANARY.encode() not in tresc

    # Inna kopia aplikacji (pusty dysk) z tym samym kodem odtwarza sprawe.
    import shutil
    shutil.rmtree(katalog)
    assert magazyn.pobierz_sprawe(katalog) is True
    assert CANARY in (katalog / "sprawa.json").read_text("utf-8")


def test_bez_kodu_nic_nie_idzie_do_s3_ani_z_s3(magazyn_s3, z_kluczem):
    magazyn, s3, tmp = magazyn_s3
    katalog = _sprawa(tmp, magazyn)
    magazyn.utrwal_sprawe(katalog)
    kcv = szyfr.kcv(z_kluczem)
    znacznik = szyfr.ustaw_dla_zadania(kcv, None)   # np. operator albo dostep serwisowy
    try:
        przed = dict(s3.obiekty)
        (katalog / "nowy.txt").write_text("x")
        with pytest.raises(szyfr.BrakKlucza):
            magazyn.utrwal_sprawe(katalog)
        assert s3.obiekty == przed
        with pytest.raises(szyfr.BrakKlucza):
            magazyn.pobierz_sprawe(katalog)
    finally:
        szyfr.stan_var.reset(znacznik)


def test_jawny_plik_podlozony_w_s3_odrzucony(magazyn_s3, z_kluczem):
    magazyn, s3, tmp = magazyn_s3
    katalog = _sprawa(tmp, magazyn)
    magazyn.utrwal_sprawe(katalog)
    s3.obiekty["kancelarie/kancelaria-a/sprawy/abc123/sprawa.json"] = b'{"strony": "podmiana"}'
    import shutil
    shutil.rmtree(katalog)
    with pytest.raises(szyfr.ZlyKlucz):
        magazyn.pobierz_sprawe(katalog)


def test_cache_plaintext_znika_po_bezczynnosci(magazyn_s3, z_kluczem):
    magazyn, _, tmp = magazyn_s3
    katalog = _sprawa(tmp, magazyn)
    magazyn.utrwal_sprawe(katalog)
    import time
    assert magazyn._sprzataj_cache(time.monotonic()) == 0 and katalog.exists()
    assert magazyn._sprzataj_cache(time.monotonic() + magazyn.CACHE_MINUT * 60 + 1) == 1
    assert not katalog.exists()
    assert magazyn.pobierz_sprawe(katalog) is True   # wraca z S3 z kodem


def test_kancelaria_bez_klucza_dalej_jawnie(magazyn_s3):
    """Zgodnosc wstecz: bez wlaczonego klucza nic sie nie zmienia."""
    magazyn, s3, tmp = magazyn_s3
    katalog = _sprawa(tmp, magazyn)
    magazyn.utrwal_sprawe(katalog)
    assert any(CANARY.encode() in t for t in s3.obiekty.values())


# --- API: wlaczenie przez wlasciciela, odmowy ----------------------------------


def _z_trasa_testowa(klient):
    """Trasa w obszarze /api/zespol (bez wymogu umowy) pokazujaca stan klucza."""
    @klient.app.get("/api/zespol-test/stan")
    def _stan(request: Request):
        return {"aktywne": szyfr.aktywne(),
                "mam_klucz": isinstance(szyfr.stan_var.get(), bytes)}
    return klient


def test_wlasciciel_wlacza_i_rejestr_ma_tylko_kcv(srodowisko):
    klient, _ = srodowisko
    k = _kancelaria(klient)["id"]
    wl = jako("anna@kancelaria-sobczak.test", k)
    assert klient.get("/api/zespol/szyfrowanie", headers=wl).json() == {
        "wlaczone": False, "od": None, "moge_wlaczyc": True}

    kod = szyfr.nowy_kod()
    odp = klient.post("/api/zespol/szyfrowanie", headers={**wl, szyfr.NAGLOWEK: kod})
    assert odp.status_code == 201, odp.text
    import autoryzacja
    wpis = next(w for w in autoryzacja._wczytaj_rejestr().values() if w["id"] == k)
    assert wpis["szyfrowanie"]["kcv"] == szyfr.kcv(kod)
    assert kod not in str(wpis) and szyfr.z_kodu(kod).hex() not in str(wpis)

    # Drugi raz nie (rotacja to osobny krok); inny kod odpada juz w middleware.
    assert klient.post("/api/zespol/szyfrowanie", headers={**wl, szyfr.NAGLOWEK: kod}).status_code == 409
    assert klient.post("/api/zespol/szyfrowanie",
                       headers={**wl, szyfr.NAGLOWEK: szyfr.nowy_kod()}).status_code == 403

    _z_trasa_testowa(klient)
    assert klient.get("/api/zespol-test/stan", headers={**wl, szyfr.NAGLOWEK: kod}).json() == {
        "aktywne": True, "mam_klucz": True}
    assert klient.get("/api/zespol-test/stan", headers=wl).json() == {
        "aktywne": True, "mam_klucz": False}
    zly = klient.get("/api/zespol-test/stan", headers={**wl, szyfr.NAGLOWEK: szyfr.nowy_kod()})
    assert zly.status_code == 403 and zly.json()["klucz_kancelarii"] == "zly"


def test_czlonek_nie_wlacza(srodowisko):
    klient, _ = srodowisko
    k = _kancelaria(klient)["id"]
    wl = jako("anna@kancelaria-sobczak.test", k)
    klient.post("/api/zespol", headers=wl, json={"email": "jan@kancelaria-sobczak.test"})
    czl = jako("jan@kancelaria-sobczak.test", k)
    assert klient.get("/api/zespol/szyfrowanie", headers=czl).json()["moge_wlaczyc"] is False
    assert klient.post("/api/zespol/szyfrowanie",
                       headers={**czl, szyfr.NAGLOWEK: szyfr.nowy_kod()}).status_code == 403


def test_zly_format_kodu_przy_wlaczaniu(srodowisko):
    klient, _ = srodowisko
    k = _kancelaria(klient)["id"]
    wl = jako("anna@kancelaria-sobczak.test", k)
    assert klient.post("/api/zespol/szyfrowanie", headers={**wl, szyfr.NAGLOWEK: "1234"}).status_code == 400
    assert klient.post("/api/zespol/szyfrowanie", headers=wl).status_code == 400


def test_nie_wlacza_przy_istniejacych_sprawach(srodowisko, tmp_path):
    klient, _ = srodowisko
    k = _kancelaria(klient)["id"]
    wl = jako("anna@kancelaria-sobczak.test", k)
    import config
    (config.DANE / "kancelarie" / k / "sprawy" / "stara").mkdir(parents=True)
    assert klient.get("/api/zespol/szyfrowanie", headers=wl).json()["moge_wlaczyc"] is False
    assert klient.post("/api/zespol/szyfrowanie",
                       headers={**wl, szyfr.NAGLOWEK: szyfr.nowy_kod()}).status_code == 409


def test_kod_nie_trafia_do_logow(srodowisko, caplog):
    klient, _ = srodowisko
    k = _kancelaria(klient)["id"]
    wl = jako("anna@kancelaria-sobczak.test", k)
    kod = szyfr.nowy_kod()
    with caplog.at_level("DEBUG"):
        klient.post("/api/zespol/szyfrowanie", headers={**wl, szyfr.NAGLOWEK: kod})
        klient.get("/api/zespol/szyfrowanie", headers={**wl, szyfr.NAGLOWEK: kod})
    tekst = caplog.text
    assert kod not in tekst and kod.replace("-", "") not in tekst
