"""Czas przechowywania kopii spraw na serwerze - wybiera notariusz.

Dane zmyslone, bez AWS (S3 zastapione atrapa listy obiektow).
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app as aplikacja
import config
import magazyn
import retencja_spraw
import ustawienia_kancelarii as ustawienia


@pytest.fixture
def baza(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(config, "SPRAWY", tmp_path / "sprawy", raising=False)
    (tmp_path / "sprawy").mkdir(exist_ok=True)
    retencja_spraw._ostatnie_sprzatanie.clear()
    return tmp_path / "sprawy"


def _sprawa(baza, id_sprawy: str, dni_temu: float):
    katalog = baza / id_sprawy
    (katalog / "skany").mkdir(parents=True)
    (katalog / "sprawa.json").write_text(json.dumps({"id": id_sprawy, "utworzono": "2024-01-01T10:00:00"}))
    (katalog / "skany" / "akt.pdf").write_bytes(b"%PDF-atrapa")
    chwila = time.time() - dni_temu * 86400
    for plik in katalog.rglob("*"):
        os.utime(plik, (chwila, chwila))
    return katalog


class TestUstawienia:
    def test_domyslnie_nic_nie_znika(self, baza):
        u = ustawienia.wczytaj()
        assert (u["przechowywanie_spraw"], u["usuwanie_spraw"]) == ("bez_limitu", "przypominaj")
        assert (u["wylogowanie"], u["bezczynnosc"]) == ("30_dni", "wylaczone")

    def test_zle_wartosci_odrzucone(self, baza):
        for klucz in ("wylogowanie", "bezczynnosc", "przechowywanie_spraw", "usuwanie_spraw"):
            with pytest.raises(ValueError):
                ustawienia.zapisz({klucz: "na-zawsze-i-jeden-dzien"})

    def test_wlaczenie_usuwania_zaczyna_karencje(self, baza):
        u = ustawienia.zapisz({"przechowywanie_spraw": "90_dni", "usuwanie_spraw": "automatycznie"})
        od = ustawienia.usuwanie_od(u)
        assert od and timedelta(days=6.9) < od - datetime.now() <= timedelta(days=7)

    def test_skrocenie_czasu_liczy_karencje_od_nowa_a_wydluzenie_nie(self, baza):
        ustawienia.zapisz({"przechowywanie_spraw": "1_rok", "usuwanie_spraw": "automatycznie"})
        magazyn.zmien_plik_kancelarii("ustawienia", lambda d: d.update(automatyczne_od="2020-01-01T00:00:00"), {})
        assert ustawienia.wczytaj()["automatyczne_od"] == "2020-01-01T00:00:00"
        ustawienia.zapisz({"przechowywanie_spraw": "2_lata"})
        assert ustawienia.wczytaj()["automatyczne_od"] == "2020-01-01T00:00:00", "dluzej = bezpieczniej"
        ustawienia.zapisz({"przechowywanie_spraw": "30_dni"})
        assert ustawienia.wczytaj()["automatyczne_od"] > "2026-01-01", "krocej = nowa karencja"

    def test_wylaczenie_usuwania_kasuje_znacznik(self, baza):
        ustawienia.zapisz({"przechowywanie_spraw": "90_dni", "usuwanie_spraw": "automatycznie"})
        u = ustawienia.zapisz({"usuwanie_spraw": "przypominaj"})
        assert "automatyczne_od" not in u and ustawienia.usuwanie_od(u) is None


class TestTerminy:
    def test_bez_limitu_brak_terminow(self, baza):
        _sprawa(baza, "stara1", 1000)
        assert retencja_spraw.terminy(baza) == {}

    def test_liczone_od_ostatniej_zmiany(self, baza):
        _sprawa(baza, "stara1", 100)
        _sprawa(baza, "swieza1", 10)
        ustawienia.zapisz({"przechowywanie_spraw": "90_dni"})
        t = retencja_spraw.terminy(baza)
        assert t["stara1"]["po_terminie"] is True and t["swieza1"]["po_terminie"] is False
        assert t["stara1"]["usunie_serwer"] is False

    def test_u_klienta_nic_nie_lezy_na_serwerze(self, baza):
        _sprawa(baza, "stara1", 100)
        ustawienia.zapisz({"przechowywanie_spraw": "30_dni"})
        zn = magazyn.przechowywanie_var.set("u-klienta")
        try:
            assert retencja_spraw.terminy(baza) == {} and retencja_spraw.sprzataj(baza) == []
        finally:
            magazyn.przechowywanie_var.reset(zn)


class TestSprzatanie:
    def test_przypominaj_niczego_nie_usuwa(self, baza):
        _sprawa(baza, "stara1", 100)
        ustawienia.zapisz({"przechowywanie_spraw": "30_dni", "usuwanie_spraw": "przypominaj"})
        assert retencja_spraw.sprzataj(baza, datetime.now() + timedelta(days=30)) == []
        assert (baza / "stara1").exists()

    def test_w_karencji_nic_nie_znika(self, baza):
        _sprawa(baza, "stara1", 100)
        ustawienia.zapisz({"przechowywanie_spraw": "30_dni", "usuwanie_spraw": "automatycznie"})
        assert retencja_spraw.sprzataj(baza) == []
        t = retencja_spraw.terminy(baza)["stara1"]
        assert t["usunie_serwer"] and datetime.fromisoformat(t["usuniecie"]) > datetime.now() + timedelta(days=6)

    def test_po_karencji_usuwa_tylko_sprawy_po_terminie(self, baza, monkeypatch):
        _sprawa(baza, "stara1", 100)
        _sprawa(baza, "swieza1", 1)
        wywolania = []
        monkeypatch.setattr(retencja_spraw.kalendarz, "usun_sprawe", wywolania.append)
        monkeypatch.setattr(retencja_spraw.przesylki, "usun_sprawe", wywolania.append)
        ustawienia.zapisz({"przechowywanie_spraw": "30_dni", "usuwanie_spraw": "automatycznie"})
        usuniete = retencja_spraw.sprzataj(baza, datetime.now() + timedelta(days=8))
        assert usuniete == ["stara1"]
        assert not (baza / "stara1").exists() and (baza / "swieza1").exists()
        assert wywolania == ["stara1", "stara1"], "jak przycisk: kalendarz i ksiegi przesylek"

    def test_lista_spraw_pokazuje_termin_i_sprzata(self, baza):
        _sprawa(baza, "stara1", 100)
        _sprawa(baza, "swieza1", 1)
        ustawienia.zapisz({"przechowywanie_spraw": "90_dni", "usuwanie_spraw": "automatycznie"})
        magazyn.zmien_plik_kancelarii("ustawienia", lambda d: d.update(automatyczne_od="2020-01-01T00:00:00"), {})
        lista = TestClient(aplikacja.app).get("/api/sprawy").json()
        assert [s["id"] for s in lista] == ["swieza1"], "sprawa po terminie usunieta przy otwarciu listy"
        assert lista[0]["przechowanie"]["usunie_serwer"] is True

    def test_bez_ustawien_lista_jak_dawniej(self, baza):
        _sprawa(baza, "stara1", 1000)
        lista = TestClient(aplikacja.app).get("/api/sprawy").json()
        assert lista[0]["id"] == "stara1" and lista[0]["przechowanie"] is None


class _Paginator:
    def __init__(self, obiekty):
        self.obiekty = obiekty

    def paginate(self, Bucket, Prefix):
        yield {"Contents": [o for o in self.obiekty if o["Key"].startswith(Prefix)]}


class _AtrapaS3:
    def __init__(self, obiekty):
        self.obiekty = obiekty

    def get_paginator(self, nazwa):
        assert nazwa == "list_objects_v2"
        return _Paginator(self.obiekty)


def test_w_chmurze_data_zmiany_z_s3_a_nie_z_dysku(monkeypatch, tmp_path):
    """Po restarcie kontenera pliki sciagniete z S3 maja dzisiejsza date -
    liczy sie LastModified w S3. Pliki synchronizacji sie nie licza."""
    stara = datetime(2025, 1, 1, tzinfo=timezone.utc)
    nowa = datetime(2026, 3, 1, tzinfo=timezone.utc)
    p = "kancelarie/k1/sprawy/"
    obiekty = [{"Key": p + "abc/sprawa.json", "LastModified": stara},
               {"Key": p + "abc/skany/akt.pdf", "LastModified": nowa},
               {"Key": p + "def/sprawa.json", "LastModified": stara},
               {"Key": p + "def/" + magazyn._SKROTY, "LastModified": nowa},
               {"Key": "kancelarie/k2/sprawy/xyz/sprawa.json", "LastModified": nowa}]
    monkeypatch.setattr(magazyn, "TRYB", "s3")
    monkeypatch.setattr(magazyn, "_s3", _AtrapaS3(obiekty))
    zn = magazyn.kancelaria_var.set("k1")
    try:
        assert magazyn.daty_zmian_spraw(tmp_path) == {"abc": nowa.timestamp(), "def": stara.timestamp()}
    finally:
        magazyn.kancelaria_var.reset(zn)
