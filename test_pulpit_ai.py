"""Chat-first NotarAI: testy bez sieci, tokenów, danych rzeczywistych i AWS."""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import pulpit_ai as p
import stanowiska
import ustawienia_kancelarii
from app import app


def _model_scenariusz(monkeypatch, kroki):
    scenariusz = iter(kroki)
    def model(system, tury, narzedzia, **kwargs):
        krok = next(scenariusz)
        if isinstance(krok, str):
            return {"wiadomosc": {"role": "assistant", "content": [{"text": krok}]},
                    "powod": "end_turn"}
        return {"wiadomosc": {"role": "assistant", "content": [
            {"toolUse": {"toolUseId": str(i), "name": n, "input": x}}
            for i, (n, x) in enumerate(krok)
        ]}, "powod": "tool_use"}
    monkeypatch.setattr(p.bedrock, "tura_z_narzedziami", model)


def test_domyslnie_czat_i_pelny_katalog_nawigacji():
    assert ustawienia_kancelarii.domyslne()["widok_startowy"] == "chat"
    assert len(p.KATALOG) >= 15
    assert {"giif", "ksiegi", "kalendarz", "pomocnik", "klikamy", "poczta"} <= set(p.KATALOG_MAPA)
    assert len(set(p.KATALOG_MAPA)) == len(p.KATALOG)


def test_sekretariat_nie_widzi_giif_rejestrow_ani_projektow():
    stanowisko = stanowiska.UPRAWNIENIA["sekretariat"]
    dostepne = p._dostepne(stanowisko)
    nazwy = {x["id"] for x in dostepne}
    assert "kalendarz" in nazwy and "poczta" in nazwy
    assert not {"giif", "ksiegi", "rejestry", "klikamy", "projekt"} & nazwy
    akcje = []
    blad = p._wykonaj("otworz_modul", {"modul": "giif"}, dostepne, stanowisko, akcje)
    assert "blad" in blad and not akcje
    narzedzia = p._narzedzia(dostepne, stanowisko)
    assert "przygotuj_polecenie_windows" not in [x["name"] for x in narzedzia]


def test_chat_samo_otwiera_kalendarz_bez_efektow_zewnetrznych(monkeypatch):
    _model_scenariusz(monkeypatch, [
        [("otworz_modul", {"modul": "kalendarz"})],
        "Otwieram kalendarz."
    ])
    with TestClient(app) as klient:
        odp = klient.post("/api/pulpit-ai/rozmowa", json={"wiadomosc": "otwórz kalendarz"})
    assert odp.status_code == 200
    assert odp.json()["akcje"] == [{"typ": "otworz", "ekran": "kalendarz"}]
    assert "Otwieram" in odp.json()["odpowiedz"]


def test_wyszukanie_sprawy_limit_i_kontrola_roli(monkeypatch):
    with patch("app.lista_spraw", return_value=[
        {"id": "abc123", "nazwa": "Testowa umowa", "sygnatura": "Rep. A 11/2026", "etap": 2},
        {"id": "def456", "nazwa": "Inna", "sygnatura": "Rep. A 12/2026", "etap": 3}
    ]):
        wynik = p._wykonaj("wyszukaj_sprawy", {"szukaj": "testowa"}, p._dostepne(
            stanowiska.UPRAWNIENIA["sekretariat"]), frozenset(), [])
    assert [x["id"] for x in wynik["sprawy"]] == ["abc123"]
    assert "skany" not in wynik["sprawy"][0]


def test_windows_tylko_przygotowanie_bez_wyslania(monkeypatch):
    monkeypatch.setattr(p.urzadzenia, "dostepne", lambda: True)
    monkeypatch.setattr(p.urzadzenia, "lista", lambda _: [
        {"id": "pc1", "nazwa": "Komputer kancelarii", "polaczony": True}])
    akcje = []
    dostepne = p._dostepne(frozenset(stanowiska.WSZYSTKIE))
    with patch("zlecenia.zloz") as wyslij:
        rezultat = p._wykonaj("przygotuj_polecenie_windows",
                              {"komputer": "pc1", "cel": "Otwórz oficjalny formularz"},
                              dostepne, frozenset(stanowiska.WSZYSTKIE), akcje)
        wyslij.assert_not_called()
    assert rezultat["stan"] == "czeka_na_zatwierdzenie_uzytkownika"
    assert akcje[0]["typ"] == "potwierdz_windows"
    assert akcje[0]["komputer"] == "pc1"
    assert "blad" in p._wykonaj("przygotuj_polecenie_windows",
                                 {"komputer": "pc1", "cel": "Wyślij pismo"},
                                 dostepne, frozenset(stanowiska.WSZYSTKIE), akcje)


def test_windows_izolacja_komputera_innej_kancelarii(monkeypatch):
    monkeypatch.setattr(p.urzadzenia, "dostepne", lambda: True)
    monkeypatch.setattr(p.urzadzenia, "lista", lambda _: [
        {"id": "pc1", "nazwa": "Sparowany", "polaczony": True}])
    akcje = []
    wynik = p._wykonaj("przygotuj_polecenie_windows",
                        {"komputer": "inny-pc", "cel": "Otwórz rejestr"},
                        p._dostepne(frozenset(stanowiska.WSZYSTKIE)),
                        frozenset(stanowiska.WSZYSTKIE), akcje)
    assert "blad" in wynik and akcje == []


def test_serwis_i_token_pomocnika_odrzucone(monkeypatch):
    monkeypatch.setattr(p.autoryzacja, "MULTI", True)
    class Stan:
        kancelaria = "k1"
        email = "operator@example.invalid"
        komputer = "pc123"
        serwis = False
    class Zapytanie:
        state = Stan()
    with pytest.raises(Exception) as blad:
        p._uprawnienia(Zapytanie())
    assert blad.value.status_code == 403
    Stan.komputer = None
    Stan.serwis = True
    with pytest.raises(Exception) as blad:
        p._uprawnienia(Zapytanie())
    assert blad.value.status_code == 403


def test_glos_optout_wymagany_w_saas(monkeypatch):
    monkeypatch.setattr(p.magazyn, "TRYB", "s3")
    monkeypatch.setattr(p.magazyn, "u_klienta", lambda: False)
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    monkeypatch.delenv("PIECZAPP_TRANSCRIBE_OPTOUT", raising=False)
    assert not p._glos_dostepny()
    monkeypatch.setenv("PIECZAPP_TRANSCRIBE_OPTOUT", "1")
    assert p._glos_dostepny()


def test_glos_nie_zostawia_nagrania_po_odczycie(monkeypatch):
    monkeypatch.setattr(p.magazyn, "TRYB", "s3")
    monkeypatch.setattr(p.magazyn, "u_klienta", lambda: False)
    monkeypatch.setenv("PIECZAPP_TRANSCRIBE_OPTOUT", "1")
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    class S3:
        def __init__(self):
            self.klucze = []
        def get_paginator(self, nazwa):
            return self
        def paginate(self, **kw):
            return []
        def put_object(self, **kw):
            self.klucze.append(kw["Key"])
    class Transcribe:
        def __init__(self):
            self.rozpoczete = []
        def start_transcription_job(self, **kw):
            self.rozpoczete.append(kw)
    s3, transcribe = S3(), Transcribe()
    monkeypatch.setattr(p.magazyn, "_klient_s3", lambda: s3)
    monkeypatch.setattr(p.stenogramy, "_klient_transcribe", lambda: transcribe)
    klient = TestClient(app)
    odp = klient.post("/api/pulpit-ai/glos",
                      files={"audio": ("g.webm", b"test audio", "audio/webm")})
    assert odp.status_code == 202
    ident = odp.json()["zadanie"]
    assert len(ident) == 32 and s3.klucze
    assert transcribe.rozpoczete[0]["LanguageCode"] == "pl-PL"
    assert transcribe.rozpoczete[0]["OutputBucketName"] == p.magazyn.BUCKET
    monkeypatch.setattr(p.stenogramy, "_stan_zadania",
                        lambda *args: {"TranscriptionJobStatus": "COMPLETED"})
    monkeypatch.setattr(p.magazyn, "czytaj_obiekt", lambda _: json.dumps({
        "results": {"transcripts": [{"transcript": "Otwórz kalendarz"}]}
    }).encode())
    usuniete = []
    monkeypatch.setattr(p, "_glos_sprzataj", usuniete.append)
    wynik = klient.get("/api/pulpit-ai/glos/" + ident)
    assert wynik.status_code == 200 and wynik.json()["tekst"] == "Otwórz kalendarz"
    assert usuniete == [ident]


def test_glos_zly_format_i_dlugosc(monkeypatch):
    monkeypatch.setattr(p.magazyn, "TRYB", "s3")
    monkeypatch.setattr(p.magazyn, "u_klienta", lambda: False)
    monkeypatch.setenv("PIECZAPP_TRANSCRIBE_OPTOUT", "1")
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    klient = TestClient(app)
    odp = klient.post("/api/pulpit-ai/glos", files={"audio": ("g.txt", b"abc", "text/plain")})
    assert odp.status_code == 415
    assert klient.get("/api/pulpit-ai/glos/../../admin").status_code in (404, 405)


def test_nie_ma_slepego_wywolywania_api():
    assert not any(w["name"] in ("wykonaj_url", "wykonaj_api", "exec", "eval")
                   for w in p._narzedzia(p._dostepne(frozenset(stanowiska.WSZYSTKIE)),
                                         frozenset(stanowiska.WSZYSTKIE)))


# ---------------------------------------------------------------- samonaprawa -- tylko glowny Chat AI

def test_naprawa_model_przygotowuje_ale_nie_uruchamia(monkeypatch):
    monkeypatch.setattr(p.magazyn, "u_klienta", lambda: False)
    monkeypatch.setattr(p.samonaprawa, "wlaczona", lambda: True)
    wywolania = []
    monkeypatch.setattr(p.asystent_kancelarii, "wykonaj",
                        lambda *args, **kwargs: wywolania.append(args))
    akcje = []
    wynik = p._wykonaj("przygotuj_zgloszenie_samonaprawy",
                        {"opis": "Kalendarz nie zapisuje terminu, powinien go zapisywać."},
                        p._dostepne(frozenset(stanowiska.WSZYSTKIE)),
                        frozenset(stanowiska.WSZYSTKIE), akcje)
    assert wynik["stan"] == "czeka_na_potwierdzenie"
    assert akcje[0]["typ"] == "potwierdz_naprawe"
    assert not wywolania


def test_naprawa_blokuje_logowanie_i_platnosci():
    for opis in ("Nie mogę się zalogować do NotarAI", "System nie pobiera płatności"):
        wynik, blad = p._opis_naprawy(opis)
        assert wynik == "" and "zespołem NotarAI" in blad


def test_naprawa_zgloszenie_dopiero_po_zatwierdzeniu(monkeypatch):
    monkeypatch.setattr(p.magazyn, "u_klienta", lambda: False)
    monkeypatch.setattr(p.samonaprawa, "wlaczona", lambda: True)
    monkeypatch.setattr(p.magazyn, "wczytaj_plik_kancelarii",
                        lambda *args: {"zmiany": [], "prosby": []})
    przekazano = []
    def wykonaj(nazwa, wejscie, moze_zmieniac):
        przekazano.append((nazwa, wejscie, moze_zmieniac))
        return {"przyjeto": True, "numer": "abc123def456", "co_dalej": "W kolejce"}
    monkeypatch.setattr(p.asystent_kancelarii, "wykonaj", wykonaj)
    klient = TestClient(app)
    odp = klient.post("/api/pulpit-ai/samonaprawa/zglos", json={
        "opis": "W kalendarzu nie zapisuje się termin spotkania."})
    assert odp.status_code == 200
    assert odp.json()["numer"] == "abc123def456"
    assert przekazano and przekazano[0][0] == "zglos_zmiane_programu"
    assert przekazano[0][2] is False


def test_naprawa_deduplikacja_w_kancelarii(monkeypatch):
    monkeypatch.setattr(p.magazyn, "u_klienta", lambda: False)
    monkeypatch.setattr(p.samonaprawa, "wlaczona", lambda: True)
    opis = "W kalendarzu nie zapisuje się termin spotkania."
    monkeypatch.setattr(p.magazyn, "wczytaj_plik_kancelarii",
                        lambda *args: {"zmiany": [], "prosby": [
                            {"opis": p.samonaprawa.anonimizuj(opis),
                             "odcisk": "abc123def456"}]})
    monkeypatch.setattr(p.asystent_kancelarii, "wykonaj",
                        lambda *args, **kwargs: pytest.fail("Duplikat uruchomił naprawę"))
    odp = TestClient(app).post("/api/pulpit-ai/samonaprawa/zglos",
                               json={"opis": opis})
    assert odp.status_code == 200
    assert odp.json()["duplikat"] is True


def test_naprawa_postep_z_prawdziwego_modulu(monkeypatch):
    monkeypatch.setattr(p.magazyn, "u_klienta", lambda: False)
    monkeypatch.setattr(p.asystent_kancelarii, "prosby_z_postepem",
                        lambda limit: [{"numer": "abc123def456", "etap": "kontrola",
                                        "etykieta": "Testy i kontrola bezpieczeństwa zmiany",
                                        "procent": 42, "zakonczona": False,
                                        "opis": "Poufna treść poza API"}])
    akcje = []
    wynik = p._wykonaj("sprawdz_postep_samonaprawy", {},
                        p._dostepne(frozenset(stanowiska.WSZYSTKIE)),
                        frozenset(stanowiska.WSZYSTKIE), akcje)
    assert wynik["liczba"] == 1 and wynik["naprawy"][0]["procent"] == 42
    assert "opis" not in wynik["naprawy"][0]
    assert akcje[0]["typ"] == "postep_napraw"
    odp = TestClient(app).get("/api/pulpit-ai/samonaprawa")
    assert odp.status_code == 200 and odp.json()["naprawy"][0]["etap"] == "kontrola"


def test_naprawa_modele_zawsze_maja_narzedzia(monkeypatch):
    monkeypatch.setattr(p.urzadzenia, "dostepne", lambda: False)
    nazwy = [n["name"] for n in p._narzedzia(
        p._dostepne(stanowiska.UPRAWNIENIA["sekretariat"]),
        stanowiska.UPRAWNIENIA["sekretariat"])]
    assert "sprawdz_postep_samonaprawy" in nazwy
    assert "przygotuj_zgloszenie_samonaprawy" in nazwy


def test_naprawa_tryb_u_klienta_odrzuca_zgloszenie(monkeypatch):
    monkeypatch.setattr(p.magazyn, "u_klienta", lambda: True)
    wynik = p._wykonaj("przygotuj_zgloszenie_samonaprawy",
                        {"opis": "Repertorium nie zapisuje nowego rekordu."},
                        [], frozenset(), [])
    assert "blad" in wynik
    odp = TestClient(app).post("/api/pulpit-ai/samonaprawa/zglos",
                               json={"opis": "Repertorium nie zapisuje nowego rekordu."})
    assert odp.status_code == 409


def test_naprawa_nie_modyfikuje_glownego_silnika():
    from pathlib import Path
    js = (Path(__file__).parent / "static/pulpit-ai.js").read_text("utf-8")
    html = (Path(__file__).parent / "static/index.html").read_text("utf-8")
    assert "/api/pulpit-ai/samonaprawa/zglos" in js
    assert 'id="pai-naprawa-zgoda"' in html
    assert "Potwierdź zgłoszenie" in html
    assert "pokolenieCzatu" in js
