"""Testy kolejki zlecen dla pomocnika. Atrapa S3, bez sieci."""
import importlib
import json

import pytest

from test_magazyn import AtrapaS3  # ta sama atrapa co przy sprawach


@pytest.fixture
def kolejka(monkeypatch):
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "s3")
    monkeypatch.setenv("PIECZAPP_S3_BUCKET", "testowy-bucket")
    import magazyn
    importlib.reload(magazyn)
    atrapa = AtrapaS3()
    monkeypatch.setattr(magazyn, "_s3", atrapa)
    import zlecenia
    importlib.reload(zlecenia)
    znacznik = magazyn.kancelaria_var.set("kowalski")
    yield zlecenia, magazyn, atrapa
    magazyn.kancelaria_var.reset(znacznik)
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    importlib.reload(magazyn)
    importlib.reload(zlecenia)


TRESC = {"osoby": [{"pesel": "44051401359", "etykieta": "zbywca"}]}


def test_zlozone_zlecenie_czeka_na_pomocnika(kolejka):
    zlecenia, _, _ = kolejka
    zlozone = zlecenia.zloz("krz", "abc123", TRESC)
    czekajace = zlecenia.czekajace()
    assert [z["id"] for z in czekajace] == [zlozone["id"]]
    assert czekajace[0]["tresc"] == TRESC


def test_nieznany_rodzaj_odrzucony(kolejka):
    zlecenia, _, _ = kolejka
    with pytest.raises(ValueError):
        zlecenia.zloz("cokolwiek", "abc123", TRESC)


def test_pomocnik_innej_kancelarii_nie_widzi_zlecenia(kolejka):
    """Izolacja kancelarii jest tu wazniejsza niz przy sprawach: zlecenie
    niesie numery PESEL i konczy sie wpisaniem ich w cudzy formularz."""
    zlecenia, magazyn, _ = kolejka
    zlecenia.zloz("krz", "abc123", TRESC)
    znacznik = magazyn.kancelaria_var.set("inna-kancelaria")
    try:
        assert zlecenia.czekajace() == []
    finally:
        magazyn.kancelaria_var.reset(znacznik)


def test_wykonane_zlecenie_znika_z_kolejki(kolejka):
    zlecenia, _, _ = kolejka
    zlozone = zlecenia.zloz("krz", "abc123", TRESC)
    zlecenia.zapisz_wynik(zlozone["id"], {"wpisy": 2, "bledy": []})
    assert zlecenia.czekajace() == []
    assert zlecenia.wynik(zlozone["id"])["stan"] == "wykonane"


def test_po_wykonaniu_nie_przechowujemy_numerow(kolejka):
    """Tresc zlecenia byla potrzebna do wykonania, nie do archiwum."""
    zlecenia, _, atrapa = kolejka
    zlozone = zlecenia.zloz("krz", "abc123", TRESC)
    zlecenia.zapisz_wynik(zlozone["id"], {"wpisy": 2, "bledy": []})
    wszystko = b"".join(atrapa.obiekty.values())
    assert b"44051401359" not in wszystko


def test_wynik_nieznanego_zlecenia_to_none(kolejka):
    zlecenia, _, _ = kolejka
    assert zlecenia.wynik("niemaTakiego") is None


def test_zapis_wyniku_nieznanego_zlecenia_to_blad(kolejka):
    zlecenia, _, _ = kolejka
    with pytest.raises(KeyError):
        zlecenia.zapisz_wynik("niemaTakiego", {})


class TestObecnosciPomocnika:
    """Przycisk KRZ ma byc czynny tylko wtedy, gdy jest komu zlecenie wykonac."""

    def test_bez_pomocnika_nie_jest_aktywny(self, kolejka):
        zlecenia, _, _ = kolejka
        assert zlecenia.pomocnik_aktywny() is False

    def test_po_odbiciu_sie_jest_aktywny(self, kolejka):
        zlecenia, _, _ = kolejka
        zlecenia.odnotuj_pomocnika("1.0")
        assert zlecenia.pomocnik_aktywny() is True

    def test_milczacy_pomocnik_przestaje_sie_liczyc(self, kolejka):
        from datetime import timedelta
        zlecenia, magazyn, atrapa = kolejka
        zlecenia.odnotuj_pomocnika()
        klucz = zlecenia._klucz_pomocnika(magazyn.kancelaria())
        stare = zlecenia._teraz() - timedelta(minutes=zlecenia.ODDECH_MINUT + 1)
        atrapa.obiekty[klucz] = json.dumps(
            {"widziany": stare.isoformat(timespec="seconds"), "wersja": ""}).encode("utf-8")
        assert zlecenia.pomocnik_aktywny() is False

    def test_pomocnik_jednej_kancelarii_nie_wlacza_przycisku_drugiej(self, kolejka):
        zlecenia, magazyn, _ = kolejka
        zlecenia.odnotuj_pomocnika()
        znacznik = magazyn.kancelaria_var.set("inna-kancelaria")
        try:
            assert zlecenia.pomocnik_aktywny() is False
        finally:
            magazyn.kancelaria_var.reset(znacznik)


class TestPrzeterminowania:
    """Zlecenie ma krotkie zycie. Nieodebrane nie moze wrocic po tygodniu i
    wpisac czegos w formularz otwarty przy zupelnie innej sprawie."""

    @staticmethod
    def _postarz(zlecenia, magazyn, identyfikator, minut):
        from datetime import timedelta
        klucz = zlecenia._klucz(magazyn.kancelaria(), identyfikator)
        zlecenie = json.loads(magazyn._klient_s3().obiekty[klucz].decode("utf-8"))
        stare = zlecenia._teraz() - timedelta(minutes=minut)
        zlecenie["zlozono"] = stare.isoformat(timespec="seconds")
        magazyn._klient_s3().obiekty[klucz] = json.dumps(zlecenie).encode("utf-8")

    def test_stare_zlecenie_nie_trafia_do_pomocnika(self, kolejka):
        zlecenia, magazyn, _ = kolejka
        zlozone = zlecenia.zloz("krz", "abc123", TRESC)
        self._postarz(zlecenia, magazyn, zlozone["id"], zlecenia.WAZNOSC_MINUT + 1)
        assert zlecenia.czekajace() == []

    def test_stare_zlecenie_jest_kasowane_a_nie_tylko_ukrywane(self, kolejka):
        zlecenia, magazyn, atrapa = kolejka
        zlozone = zlecenia.zloz("krz", "abc123", TRESC)
        self._postarz(zlecenia, magazyn, zlozone["id"], zlecenia.WAZNOSC_MINUT + 1)
        zlecenia.czekajace()
        assert not any(zlozone["id"] in k for k in atrapa.obiekty), \
            "przeterminowane zlecenie niesie numery PESEL i ma zniknac"

    def test_swieze_zlecenie_zostaje(self, kolejka):
        zlecenia, magazyn, _ = kolejka
        zlozone = zlecenia.zloz("krz", "abc123", TRESC)
        self._postarz(zlecenia, magazyn, zlozone["id"], 1)
        assert len(zlecenia.czekajace()) == 1
