"""Rozmowa o sprawie i transkrypcja - testy na atrapach."""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app as aplikacja
import bedrock
import config
import prompty


@pytest.fixture
def klient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SPRAWY", tmp_path)
    (tmp_path / "abc123").mkdir()
    (tmp_path / "abc123" / "kontekst.txt").write_text("DANE: x", encoding="utf-8")
    return TestClient(aplikacja.app)


class TestRozmawiaj:
    def test_pierwsza_tura_bez_wiadomosci(self):
        with patch("bedrock._rozmowa", return_value="1. Jaka cena?") as r:
            assert bedrock.rozmawiaj("KONTEKST", [], None) == "1. Jaka cena?"
            system, tresc = r.call_args.args[:2]
            assert system == prompty.ROZMOWA
            assert "KONTEKST" in tresc[0]["text"] and r.call_args.kwargs["historia"] == []

    def test_naprzemienne_role(self):
        historia = [
            {"rola": "asystent", "tresc": "1. Jaka cena?"},
            {"rola": "uzytkownik", "tresc": "23000"},
            {"rola": "asystent", "tresc": "Dziekuje."},
        ]
        with patch("bedrock._rozmowa", return_value="OK") as r:
            bedrock.rozmawiaj("K", historia, "Mozna sporzadzac")
            role = [t["role"] for t in r.call_args.kwargs["historia"]]
            assert role == ["user", "assistant", "user", "assistant"]
            assert r.call_args.args[1] == [{"text": "Mozna sporzadzac"}]

    def test_dwie_tury_uzytkownika_pod_rzad_sklejone(self):
        historia = [{"rola": "asystent", "tresc": "?"}, {"rola": "uzytkownik", "tresc": "a"}]
        with patch("bedrock._rozmowa", return_value="OK") as r:
            bedrock.rozmawiaj("K", historia, "b")
            assert r.call_args.args[1] == [{"text": "a"}, {"text": "b"}]


class TestApiRozmowy:
    def test_wiadomosc_zapisuje_historie(self, klient, tmp_path):
        with patch("bedrock.rozmawiaj", return_value="Rozumiem, cena 23000."):
            odp = klient.post("/api/sprawy/abc123/rozmowa", json={"tresc": "Cena 23000 zl"})
        assert odp.status_code == 200
        assert odp.json()["odpowiedz"] == "Rozumiem, cena 23000."
        zapis = json.loads((tmp_path / "abc123" / "rozmowa.json").read_text("utf-8"))
        assert [w["rola"] for w in zapis] == ["uzytkownik", "asystent"]
        assert klient.get("/api/sprawy/abc123/rozmowa").json() == zapis

    def test_pusta_wiadomosc(self, klient):
        assert klient.post("/api/sprawy/abc123/rozmowa", json={"tresc": "  "}).status_code == 400

    def test_blad_modelu_bez_tresci_w_logu(self, klient, caplog):
        with patch("bedrock.rozmawiaj", side_effect=RuntimeError("PESEL 44051401359 w tresci bledu")):
            odp = klient.post("/api/sprawy/abc123/rozmowa", json={"tresc": "x"})
        assert odp.status_code == 502
        assert "44051401359" not in caplog.text and "44051401359" not in odp.text

    def test_projekt_dostaje_rozmowe(self, klient, tmp_path):
        (tmp_path / "abc123" / "wzor.txt").write_text("Cena {{cena}}", encoding="utf-8")
        (tmp_path / "abc123" / "rozmowa.json").write_text(
            json.dumps([{"rola": "uzytkownik", "tresc": "Zaplata gotowka"}]), encoding="utf-8")
        with patch("bedrock.sporzadz_projekt", return_value="Cena 1") as sp:
            odp = klient.post("/api/sprawy/abc123/projekt", json={"pola": [], "polecenie": ""})
        assert odp.status_code == 200
        assert sp.call_args.args[4][0]["tresc"] == "Zaplata gotowka"


class TestUstalenia:
    def test_tekst_ustalen(self):
        t = prompty.ustalenia_z_rozmowy([{"rola": "asystent", "tresc": "?"}, {"rola": "uzytkownik", "tresc": "tak"}])
        assert "ASYSTENT: ?" in t and "NOTARIUSZ: tak" in t

    def test_limit_odpowiedzi_w_rozmowie(self):
        with patch("bedrock._rozmowa", return_value="OK") as r:
            bedrock.rozmawiaj("K", [], "a")
        assert r.call_args.kwargs["max_tokenow"] == bedrock.MAX_TOKENOW_ROZMOWY > 2000

    def test_generowanie_dostaje_podsumowanie_zamiast_zapisu(self):
        rozmowa = [
            {"rola": "asystent", "tresc": "1. Jaka cena?"},
            {"rola": "uzytkownik", "tresc": "Cena 400 000"},
            {"rola": "uzytkownik", "tresc": "Jednak 450 000"},
        ]
        odpowiedzi = iter(["- Cena: 450 000 zl\nNIEROZSTRZYGNIETE: brak", "AKT"])
        with patch("bedrock._rozmowa", side_effect=lambda *a, **k: next(odpowiedzi)) as r:
            assert bedrock.sporzadz_projekt("WZOR", [], "", rozmowa=rozmowa) == "AKT"
        podsumowanie, generowanie = r.call_args_list
        assert podsumowanie.args[0] == prompty.PODSUMOWANIE_ROZMOWY
        assert "NOTARIUSZ: Jednak 450 000" in podsumowanie.args[1][0]["text"]
        prompt = generowanie.args[1][0]["text"]
        assert "- Cena: 450 000 zl" in prompt
        assert "400 000" not in prompt and "NOTARIUSZ:" not in prompt

    def test_same_pytania_asystenta_bez_podsumowania(self):
        with patch("bedrock._rozmowa", return_value="AKT") as r:
            bedrock.sporzadz_projekt("WZOR", [], "", rozmowa=[{"rola": "asystent", "tresc": "?"}])
        assert r.call_count == 1
        assert "USTALENIA" not in r.call_args.args[1][0]["text"]

    def test_nieudane_podsumowanie_daje_pelny_zapis(self, caplog):
        rozmowa = [{"rola": "uzytkownik", "tresc": "Zaplata gotowka, PESEL 44051401359"}]
        odpowiedzi = iter([ValueError("ucieta"), "AKT"])

        def atrapa(*a, **k):
            w = next(odpowiedzi)
            if isinstance(w, Exception):
                raise w
            return w

        with patch("bedrock._rozmowa", side_effect=atrapa) as r:
            assert bedrock.sporzadz_projekt("WZOR", [], "", rozmowa=rozmowa) == "AKT"
        assert "NOTARIUSZ: Zaplata gotowka" in r.call_args.args[1][0]["text"]
        assert "podsumowanie rozmowy nieudane" in caplog.text
        assert "44051401359" not in caplog.text

    def test_kontekst_oznacza_niska_pewnosc(self):
        k = prompty.kontekst_rozmowy([{"nazwa": "rok", "wartosc": "1897", "pewnosc": "niska"}], ["x"], [], "op")
        assert "[NISKA PEWNOSC]" in k and "- x" in k


class TestTranskrypcja:
    def test_brak_biblioteki_503(self, klient):
        with patch("transkrypcja.dostepna", return_value=False):
            odp = klient.post("/api/transkrypcja", files={"audio": ("n.webm", b"abc", "audio/webm")})
        assert odp.status_code == 503

    def test_transkrypcja_zwraca_tekst(self, klient):
        with patch("transkrypcja.dostepna", return_value=True), \
             patch("transkrypcja.transkrybuj", return_value="cena dwadziescia trzy tysiace"):
            odp = klient.post("/api/transkrypcja", files={"audio": ("n.webm", b"abc", "audio/webm")})
        assert odp.json() == {"tekst": "cena dwadziescia trzy tysiace"}


class TestListaSpraw:
    def test_lista_i_wczytanie(self, klient, tmp_path):
        import json
        k = tmp_path / "abc123"
        (k / "sprawa.json").write_text(json.dumps({"id": "abc123", "sygnatura": "Rep. A 1/2026", "utworzono": "2026-09-17T10:00:00", "wzor": "wzor.docx", "skany": ["a.pdf"], "stron": 3}), encoding="utf-8")
        (k / "odczyt.json").write_text(json.dumps({"pola": [{"nazwa": "x", "wartosc": "1"}], "braki": [], "rozbieznosci": []}), encoding="utf-8")
        (k / "projekt.txt").write_text("AKT <<BRAK: cena>>", encoding="utf-8")
        lista = klient.get("/api/sprawy").json()
        assert lista[0]["id"] == "abc123" and lista[0]["etap"] == 3 and lista[0]["sygnatura"] == "Rep. A 1/2026"
        w = klient.get("/api/sprawy/abc123").json()
        assert w["pola"][0]["wartosc"] == "1" and w["projekt"].startswith("AKT") and w["brakujace"] == 1
        assert w["plik"] is None  # brak docx

    def test_zmiana_sygnatury(self, klient, tmp_path):
        import json
        (tmp_path / "abc123" / "sprawa.json").write_text(json.dumps({"id": "abc123", "sygnatura": ""}), encoding="utf-8")
        assert klient.put("/api/sprawy/abc123/sygnatura", json={"sygnatura": " Rep. A 5/2026 "}).json() == {"sygnatura": "Rep. A 5/2026"}
        assert klient.get("/api/sprawy").json()[0]["sygnatura"] == "Rep. A 5/2026"

    def test_projekt_zapisuje_poprawione_pola(self, klient, tmp_path):
        import json
        k = tmp_path / "abc123"
        (k / "wzor.txt").write_text("Cena {{cena}}", encoding="utf-8")
        (k / "odczyt.json").write_text(json.dumps({"pola": [{"nazwa": "cena", "wartosc": None}], "braki": ["b"], "rozbieznosci": []}), encoding="utf-8")
        with patch("bedrock.sporzadz_projekt", return_value="Cena 5"):
            klient.post("/api/sprawy/abc123/projekt", json={"pola": [{"nazwa": "cena", "wartosc": "5"}], "polecenie": ""})
        zapis = json.loads((k / "odczyt.json").read_text("utf-8"))
        assert zapis["pola"][0]["wartosc"] == "5" and zapis["braki"] == ["b"]
        assert (k / "projekt.txt").read_text("utf-8") == "Cena 5"


class TestNazwaSprawyApi:
    def test_stara_sprawa_dostaje_nazwe_z_plikow(self, klient, tmp_path):
        import json
        k = tmp_path / "abc123"
        (k / "skany").mkdir()
        (k / "skany" / "Sobczak Tomasz - Pawlak Grzegorz - sprzedaż RI - Zalesie.pdf").write_bytes(b"%PDF")
        (k / "sprawa.json").write_text(json.dumps({"id": "abc123", "utworzono": "2026-09-16T22:00:00"}), encoding="utf-8")
        assert klient.get("/api/sprawy").json()[0]["nazwa"] == "Sobczak – Pawlak"
        assert json.loads((k / "sprawa.json").read_text("utf-8"))["nazwa"] == "Sobczak – Pawlak"

    def test_reczna_nazwa_i_powrot(self, klient, tmp_path):
        import json
        k = tmp_path / "abc123"
        (k / "odczyt.json").write_text(json.dumps({"pola": [{"nazwa": "aaa: zbywca", "wartosc": "Jan Kowalski"}]}), encoding="utf-8")
        (k / "sprawa.json").write_text(json.dumps({"id": "abc123", "utworzono": "x"}), encoding="utf-8")
        assert klient.put("/api/sprawy/abc123/nazwa", json={"nazwa": "Darowizna Kowalskich"}).json() == {"nazwa": "Darowizna Kowalskich"}
        assert klient.get("/api/sprawy").json()[0]["nazwa"] == "Darowizna Kowalskich"
        assert klient.put("/api/sprawy/abc123/nazwa", json={"nazwa": ""}).json() == {"nazwa": "Kowalski"}
