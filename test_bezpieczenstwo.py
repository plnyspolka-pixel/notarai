"""Zabezpieczenia danych: izolacja kancelarii, SSRF, naglowki, sciezki otwarte."""
import pytest
from fastapi.testclient import TestClient

import autoryzacja
import skrzynki
import tokenomia
import wizyty

BAZA = {"miejscowosci": [{"slug": "lublin", "nazwa": "Lublin", "izba": "Lublinie", "liczba": 1}],
        "kancelarie": [{"id": 1, "slug": "lublin", "miejscowosc": "Lublin", "nazwa": "Kancelaria X",
                        "email": "biuro@kancelaria-x.test", "telefony": [], "adres": ""}]}


def _rejestr(osoba: dict) -> dict:
    return {"a": {"id": "kancelaria-a", "nazwa": "A", "aktywna": True, "zespol": [
        {"email": "wlasciciel@a.test", "rola": "wlasciciel", "dolaczyl": "2026-10-01T09:00:00"}, osoba]}}


@pytest.mark.parametrize("osoba", [
    # zaproszony adres cudzej kancelarii - nikt sie z niego nie zalogowal
    {"email": "biuro@kancelaria-x.test", "rola": "czlonek", "zaproszono": "2026-11-01T09:00:00", "dolaczyl": None},
    # czlonek zespolu, nawet zalogowany, nie reprezentuje kancelarii z bazy
    {"email": "biuro@kancelaria-x.test", "rola": "czlonek", "dolaczyl": "2026-11-01T09:00:00"},
    # wlasciciel zaproszony przez administratora, ale jeszcze bez logowania
    {"email": "biuro@kancelaria-x.test", "rola": "wlasciciel", "dolaczyl": None},
])
def test_zaproszenie_adresu_cudzej_kancelarii_nie_przejmuje_jej_zapytan(monkeypatch, tmp_path, osoba):
    import config
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja, "_wczytaj_rejestr", lambda: _rejestr(osoba))
    wizyty._ustaw_baze(BAZA)
    try:
        assert wizyty.kancelarie_notarai() == {}
    finally:
        wizyty._ustaw_baze(None)


def test_osoba_spoza_zespolu_nie_ma_dostepu(monkeypatch):
    monkeypatch.setattr(autoryzacja, "_wczytaj_rejestr",
                        lambda: _rejestr({"email": "ewa@a.test", "rola": "czlonek"}))
    assert autoryzacja._w_zespole("kancelaria-a", "ewa@a.test")
    assert not autoryzacja._w_zespole("kancelaria-a", "usunieta@a.test")
    assert not autoryzacja._w_zespole("inna-kancelaria", "ewa@a.test")


def test_kancelaria_bez_spisu_zespolu_przepuszcza(monkeypatch):
    monkeypatch.setattr(autoryzacja, "_wczytaj_rejestr",
                        lambda: {"a": {"id": "stara", "aktywna": True}})
    assert autoryzacja._w_zespole("stara", "ktokolwiek@a.test")


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "10.0.0.5", "192.168.1.1",
                                  "169.254.169.254", "169.254.170.2", "::1"])
def test_serwer_poczty_nie_moze_byc_adresem_wewnetrznym(host):
    assert not skrzynki.host_publiczny(host)
    with pytest.raises(skrzynki.BladPolaczenia):
        skrzynki.sprawdz_serwer(host, 993)
    with pytest.raises(skrzynki.BladPolaczenia):
        skrzynki.polacz_imap(host, 993, "ssl")


@pytest.mark.parametrize("port", [22, 80, 443, 5432, 6379, 8000])
def test_serwer_poczty_tylko_porty_imap(port):
    with pytest.raises(skrzynki.BladPolaczenia):
        skrzynki.sprawdz_serwer("imap.example.com", port)


@pytest.mark.parametrize("zamowienie", ["../../sekret:1", "a/b:1", "a.b:1", ":1", "x" * 70 + ":1"])
def test_sygnal_platnosci_odrzuca_identyfikator_ze_sciezka(monkeypatch, zamowienie):
    def nie_wolno(*a, **k):
        raise AssertionError("nie powinno dojsc do odczytu")
    monkeypatch.setattr(tokenomia, "uzgodnij_zamowienie", nie_wolno)
    assert tokenomia.ping_platnosci(tokenomia.PingPlatnosci(zamowienie=zamowienie)) == {"odebrano": False}


def test_odpowiedzi_niosa_naglowki_ochronne():
    import app as aplikacja
    odp = TestClient(aplikacja.app).get("/zdrowie")
    assert odp.headers["x-content-type-options"] == "nosniff"
    assert odp.headers["x-frame-options"] == "DENY"
    assert "max-age=" in odp.headers["strict-transport-security"]
    assert "frame-ancestors 'none'" in odp.headers["content-security-policy"]
    assert odp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
