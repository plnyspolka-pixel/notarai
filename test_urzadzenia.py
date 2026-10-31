"""Laczenie pomocnika z kancelaria bez przepisywania tokenu. Atrapa S3, bez sieci."""
import importlib

import pytest
from fastapi.testclient import TestClient

from test_magazyn import AtrapaS3

ADMIN = {"Authorization": "Bearer sekret-admina"}


@pytest.fixture
def srodowisko(monkeypatch):
    monkeypatch.setenv("PIECZAPP_MULTI", "true")
    monkeypatch.setenv("PIECZAPP_ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "s3")
    monkeypatch.setenv("PIECZAPP_S3_BUCKET", "testowy-bucket")
    import magazyn
    importlib.reload(magazyn)
    atrapa = AtrapaS3()
    monkeypatch.setattr(magazyn, "_s3", atrapa)
    import zlecenia
    import urzadzenia
    import autoryzacja
    import app as aplikacja
    for modul in (zlecenia, urzadzenia, autoryzacja, aplikacja):
        importlib.reload(modul)
    klient = TestClient(aplikacja.app)
    # Do spraw wchodzi sie tylko logujac sie. Token "jwt|<email>|<kancelaria>"
    # udaje podpisany token tozsamosci.
    monkeypatch.setattr(autoryzacja.logowanie, "wlaczone", lambda: True)
    monkeypatch.setattr(autoryzacja.logowanie, "czy_jwt", lambda t: t.startswith("jwt|"))
    monkeypatch.setattr(autoryzacja.logowanie, "dane_z_tokenu",
                        lambda t: {"email": t.split("|")[1], "kancelaria": t.split("|")[2]})

    def kancelaria(nazwa):
        id_k = klient.post("/api/admin/kancelarie", json={"nazwa": nazwa}, headers=ADMIN).json()["id"]
        # Tu sprawdzamy pomocnika, nie akceptacje umowy (test_rejestracja.py).
        rejestr = autoryzacja._wczytaj_rejestr()
        autoryzacja._znajdz(rejestr, id_k)[1]["umowa"] = {"zaakceptowano": "2026-10-24T10:00:00"}
        autoryzacja._zapisz_rejestr(rejestr)
        return id_k, {"Authorization": f"Bearer jwt|notariusz@{id_k}.test|{id_k}"}

    yield klient, kancelaria, urzadzenia, atrapa

    for nazwa in ("PIECZAPP_MULTI", "PIECZAPP_ADMIN_TOKEN", "PIECZAPP_S3_BUCKET"):
        monkeypatch.delenv(nazwa, raising=False)
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    importlib.reload(magazyn)
    for modul in (zlecenia, urzadzenia, autoryzacja, aplikacja):
        importlib.reload(modul)


def _polacz(klient, notariusz, nazwa="BIURO-1"):
    """Caly przeplyw tak, jak go widzi notariusz: kod -> Polacz -> token."""
    start = klient.post("/api/pomocnik/parowanie", json={"nazwa": nazwa})
    assert start.status_code == 201
    kod, sekret = start.json()["kod"], start.json()["sekret"]
    czeka = klient.post(f"/api/pomocnik/parowanie/{kod}", json={"sekret": sekret})
    assert czeka.status_code == 202, "przed potwierdzeniem pomocnik czeka"
    assert klient.get(f"/api/urzadzenia/kod/{kod}", headers=notariusz).json()["nazwa"] == nazwa
    assert klient.post("/api/urzadzenia/polacz", json={"kod": kod},
                       headers=notariusz).status_code == 200
    odbior = klient.post(f"/api/pomocnik/parowanie/{kod}", json={"sekret": sekret})
    assert odbior.status_code == 200
    return {"Authorization": "Bearer " + odbior.json()["token"]}, odbior.json()["id"]


class TestLaczenia:
    def test_pomocnik_dostaje_wlasny_token_bez_przepisywania(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        pomocnik, _ = _polacz(klient, notariusz)
        assert klient.get("/api/pomocnik/zlecenia", headers=pomocnik).status_code == 200

    def test_pomocnik_od_razu_widoczny_jako_polaczony(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        pomocnik, _ = _polacz(klient, notariusz)
        klient.get("/api/pomocnik/zlecenia", headers=pomocnik)
        stan = klient.get("/api/urzadzenia", headers=notariusz).json()
        assert stan["polaczony"] is True
        assert [u["nazwa"] for u in stan["urzadzenia"]] == ["BIURO-1"]
        assert klient.get("/api/ustawienia", headers=notariusz).json()["pomocnik_polaczony"]

    def test_kod_mozna_przepisac_malymi_literami_i_bez_kreski(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        kod = klient.post("/api/pomocnik/parowanie", json={"nazwa": "X"}).json()["kod"]
        przepisany = kod.replace("-", " ").lower()
        assert klient.post("/api/urzadzenia/polacz", json={"kod": przepisany},
                           headers=notariusz).status_code == 200

    def test_kod_potwierdzony_z_innej_sieci_odrzucony(self, srodowisko):
        """Obrona przed wyludzeniem: "kliknij ten link i potwierdz"."""
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        kod = klient.post("/api/pomocnik/parowanie", json={"nazwa": "X"},
                          headers={"X-Forwarded-For": "203.0.113.7"}).json()["kod"]
        odp = klient.post("/api/urzadzenia/polacz", json={"kod": kod},
                          headers={**notariusz, "X-Forwarded-For": "198.51.100.2"})
        assert odp.status_code == 409 and "innej sieci" in odp.json()["detail"]

    def test_podrobiony_poczatek_x_forwarded_for_nie_pomaga(self, srodowisko):
        """Liczy sie ostatni adres - ten dopisuje ALB, nie klient."""
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        kod = klient.post("/api/pomocnik/parowanie", json={"nazwa": "X"},
                          headers={"X-Forwarded-For": "203.0.113.7"}).json()["kod"]
        odp = klient.post("/api/urzadzenia/polacz", json={"kod": kod},
                          headers={**notariusz, "X-Forwarded-For": "203.0.113.7, 198.51.100.2"})
        assert odp.status_code == 409

    def test_cudzy_sekret_nie_odbierze_tokenu(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        kod = klient.post("/api/pomocnik/parowanie", json={"nazwa": "X"}).json()["kod"]
        klient.post("/api/urzadzenia/polacz", json={"kod": kod}, headers=notariusz)
        odp = klient.post(f"/api/pomocnik/parowanie/{kod}", json={"sekret": "zgadniety"})
        assert odp.status_code == 410

    def test_potwierdzenie_wymaga_zalogowania(self, srodowisko):
        klient, _, _, _ = srodowisko
        kod = klient.post("/api/pomocnik/parowanie", json={"nazwa": "X"}).json()["kod"]
        assert klient.post("/api/urzadzenia/polacz", json={"kod": kod}).status_code == 401

    def test_wygasly_kod(self, srodowisko, monkeypatch):
        klient, kancelaria, urzadzenia, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        kod = klient.post("/api/pomocnik/parowanie", json={"nazwa": "X"}).json()["kod"]
        monkeypatch.setattr(urzadzenia, "WAZNOSC_KODU_S", -1)
        odp = klient.post("/api/urzadzenia/polacz", json={"kod": kod}, headers=notariusz)
        assert odp.status_code == 409 and "wygasł" in odp.json()["detail"]

    def test_kod_dziala_raz(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        _, inny = kancelaria("Kancelaria Pawlak")
        kod = klient.post("/api/pomocnik/parowanie", json={"nazwa": "X"}).json()["kod"]
        klient.post("/api/urzadzenia/polacz", json={"kod": kod}, headers=notariusz)
        assert klient.post("/api/urzadzenia/polacz", json={"kod": kod},
                           headers=inny).status_code == 409

    def test_token_nie_lezy_w_s3_wprost(self, srodowisko):
        klient, kancelaria, _, atrapa = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        pomocnik, _ = _polacz(klient, notariusz)
        token = pomocnik["Authorization"][7:].encode()
        assert all(token not in tresc for tresc in atrapa.obiekty.values())

    def test_po_odbiorze_nie_zostaje_slad_parowania(self, srodowisko):
        klient, kancelaria, _, atrapa = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        _polacz(klient, notariusz)
        assert not [k for k in atrapa.obiekty if "/parowania/" in k]

    def test_zalew_prosb_o_kod_ograniczony(self, srodowisko, monkeypatch):
        klient, _, urzadzenia, _ = srodowisko
        monkeypatch.setattr(urzadzenia, "_LIMIT", 3)
        kody = [klient.post("/api/pomocnik/parowanie", json={"nazwa": "X"}).status_code
                for _ in range(4)]
        assert kody == [201, 201, 201, 429]


class TestTokenuPomocnika:
    def test_nie_otwiera_spraw(self, srodowisko):
        """Token wykradziony z komputera nie pozwala przegladac spraw."""
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        pomocnik, _ = _polacz(klient, notariusz)
        assert klient.get("/api/sprawy", headers=pomocnik).status_code == 403
        assert klient.get("/api/urzadzenia", headers=pomocnik).status_code == 403

    def test_odlaczenie_dziala_od_razu(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        pomocnik, identyfikator = _polacz(klient, notariusz)
        assert klient.delete(f"/api/urzadzenia/{identyfikator}",
                             headers=notariusz).status_code == 200
        assert klient.get("/api/pomocnik/zlecenia", headers=pomocnik).status_code == 401
        assert klient.get("/api/urzadzenia", headers=notariusz).json()["urzadzenia"] == []

    def test_odlaczenie_jednego_nie_rusza_drugiego(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        pierwszy, identyfikator = _polacz(klient, notariusz, "BIURO-1")
        drugi, _ = _polacz(klient, notariusz, "SEKRETARIAT")
        klient.delete(f"/api/urzadzenia/{identyfikator}", headers=notariusz)
        assert klient.get("/api/pomocnik/zlecenia", headers=drugi).status_code == 200

    def test_pomocnik_moze_odlaczyc_sam_siebie(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        pomocnik, _ = _polacz(klient, notariusz)
        assert klient.post("/api/pomocnik/odlacz", headers=pomocnik).json()["odlaczono"]
        assert klient.get("/api/pomocnik/zlecenia", headers=pomocnik).status_code == 401

    def test_inna_kancelaria_nie_odlaczy_cudzego_komputera(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        _, obcy = kancelaria("Kancelaria Pawlak")
        pomocnik, identyfikator = _polacz(klient, notariusz)
        assert klient.delete(f"/api/urzadzenia/{identyfikator}", headers=obcy).status_code == 404
        assert klient.get("/api/pomocnik/zlecenia", headers=pomocnik).status_code == 200

    def test_wylaczenie_kancelarii_odcina_pomocnika(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        id_k, notariusz = kancelaria("Kancelaria Sobczak")
        pomocnik, _ = _polacz(klient, notariusz)
        klient.delete(f"/api/admin/kancelarie/{id_k}", headers=ADMIN)
        assert klient.get("/api/pomocnik/zlecenia", headers=pomocnik).status_code == 401

    def test_obecnosc_nie_zapisuje_sie_przy_kazdym_pytaniu(self, srodowisko, monkeypatch):
        """Pomocnik pyta co 3 s; zapis do S3 za kazdym razem to koszt bez pozytku."""
        klient, kancelaria, _, atrapa = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        pomocnik, _ = _polacz(klient, notariusz)
        zapisy = []
        oryginal = atrapa.put_object
        monkeypatch.setattr(atrapa, "put_object",
                            lambda **kw: (zapisy.append(kw["Key"]), oryginal(**kw))[1])
        for _ in range(5):
            klient.get("/api/pomocnik/zlecenia", headers=pomocnik)
        assert len([k for k in zapisy if "/pomocnicy/" in k]) == 1


class TestKreatora:
    def test_kreator_widzi_pomocnika_z_tej_sieci(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        kod = klient.post("/api/pomocnik/parowanie", json={"nazwa": "BIURO-1"},
                          headers={"X-Forwarded-For": "203.0.113.7"}).json()["kod"]
        widziane = klient.get("/api/urzadzenia/oczekujace",
                              headers={**notariusz, "X-Forwarded-For": "203.0.113.7"}).json()
        assert [(w["kod"], w["nazwa"]) for w in widziane] == [(kod, "BIURO-1")]

    def test_kreator_nie_widzi_pomocnikow_z_innej_sieci(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        klient.post("/api/pomocnik/parowanie", json={"nazwa": "OBCY"},
                    headers={"X-Forwarded-For": "203.0.113.7"})
        assert klient.get("/api/urzadzenia/oczekujace",
                          headers={**notariusz, "X-Forwarded-For": "198.51.100.2"}).json() == []

    def test_polaczony_znika_z_oczekujacych(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        kod = klient.post("/api/pomocnik/parowanie", json={"nazwa": "X"}).json()["kod"]
        klient.post("/api/urzadzenia/polacz", json={"kod": kod}, headers=notariusz)
        assert klient.get("/api/urzadzenia/oczekujace", headers=notariusz).json() == []

    def test_karta_z_pomocnika_po_kreatorze_mowi_gotowe(self, srodowisko):
        """Kreator polaczyl, a pomocnik zdazyl otworzyc karte - to nie blad."""
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        kod = klient.post("/api/pomocnik/parowanie", json={"nazwa": "X"}).json()["kod"]
        assert klient.get(f"/api/urzadzenia/kod/{kod}", headers=notariusz).json()["potwierdzony"] is False
        klient.post("/api/urzadzenia/polacz", json={"kod": kod}, headers=notariusz)
        assert klient.get(f"/api/urzadzenia/kod/{kod}", headers=notariusz).json()["potwierdzony"] is True

    def test_odnosnik_do_pobrania_pomocnika(self, srodowisko, tmp_path, monkeypatch):
        klient, kancelaria, _, _ = srodowisko
        _, notariusz = kancelaria("Kancelaria Sobczak")
        import app as aplikacja
        monkeypatch.setattr(aplikacja, "_POBIERZ", tmp_path)
        assert klient.get("/api/urzadzenia", headers=notariusz).json()["pobierz"] is None
        (tmp_path / "notarai-pomocnik.exe").write_bytes(b"MZ" + bytes(2 * 1024 * 1024))
        (tmp_path / "notarai-pomocnik.json").write_text('{"wersja": "0.2", "sha256": "ab"}')
        pobierz = klient.get("/api/urzadzenia", headers=notariusz).json()["pobierz"]
        assert pobierz["adres"] == "/static/pobierz/notarai-pomocnik.exe"
        assert pobierz["wersja"] == "0.2" and pobierz["rozmiar_mb"] == 2.0
