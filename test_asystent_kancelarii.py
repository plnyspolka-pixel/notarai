"""Asystent kancelarii: notariusz mowi po swojemu, asystent od razu ustawia.

Model zastepuje scenariusz (lista tur z wywolaniami narzedzi) - testujemy
wykonanie narzedzi, uprawnienia, cofanie, anonimizacje prosb i endpoint.
"""
import pytest
from fastapi.testclient import TestClient

import asystent_kancelarii as ak
import ustawienia_kancelarii
import zasady


@pytest.fixture
def dane(tmp_path, monkeypatch):
    import config
    import magazyn
    monkeypatch.setattr(config, "DANE", tmp_path)
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    assert magazyn.TRYB == "lokalny"
    monkeypatch.delenv("PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN", raising=False)
    return tmp_path


def _model(monkeypatch, scenariusz):
    """Kolejne tury modelu: lista wywolan narzedzi [(nazwa, wejscie)], na koniec tekst."""
    kroki = list(scenariusz)
    widziane = []

    def tura(system, tury, narzedzia, **kw):
        widziane.append(tury[-1])
        krok = kroki.pop(0)
        if isinstance(krok, str):
            return {"wiadomosc": {"role": "assistant", "content": [{"text": krok}]}, "powod": "end_turn"}
        return {"wiadomosc": {"role": "assistant", "content": [
            {"toolUse": {"toolUseId": f"t{i}", "name": n, "input": w}} for i, (n, w) in enumerate(krok)]},
            "powod": "tool_use"}
    monkeypatch.setattr(ak.bedrock, "tura_z_narzedziami", tura)
    return widziane


def test_znak_zapytania_zamiast_brak_od_razu_i_cofanie(dane, monkeypatch):
    _model(monkeypatch, [[("zmien_ustawienie", {"klucz": "braki", "wartosc": "pytajnik"})], "Ustawione."])
    wynik = ak.rozmawiaj([], "w wordzie zamiast BRAK zostawiaj znak zapytania", moze_zmieniac=True)
    assert ustawienia_kancelarii.wczytaj()["braki"] == "pytajnik"
    assert wynik["zmiany"][0]["wynik"] == {"zmieniono": "braki", "bylo": "opis", "jest": "pytajnik"}

    _model(monkeypatch, [[("cofnij_ostatnia_zmiane", {})], "Cofnięte."])
    ak.rozmawiaj([], "cofnij", moze_zmieniac=True)
    assert ustawienia_kancelarii.wczytaj()["braki"] == "opis"


def test_zasada_zdaniem_notariusza_i_cofanie(dane, monkeypatch):
    _model(monkeypatch, [[("dodaj_zasade", {"zdanie": "Zamiast „w/w” pisz „wyżej wymieniony”"})], "Dodane."])
    wynik = ak.rozmawiaj([], "nie pisz w/w", moze_zmieniac=True)
    zasada = zasady.wczytaj()["zasady"][0]
    assert zasada["typ"] == "zamiana" and zasada["zrodlo"] == "asystent"
    assert wynik["zmiany"][0]["wynik"]["jak_rozumiem"]

    _model(monkeypatch, [[("cofnij_ostatnia_zmiane", {})], "ok"])
    ak.rozmawiaj([], "cofnij", moze_zmieniac=True)
    assert zasady.wczytaj()["zasady"] == []


def test_usuniecie_zasady_da_sie_cofnac(dane, monkeypatch):
    z = zasady.dodaj("Kwoty zawsze cyframi i słownie")["zasada"]
    assert ak.wykonaj("usun_zasade", {"id": z["id"]}, True) == {"usunieto": z["tekst"]}
    assert zasady.wczytaj()["zasady"] == []
    ak.wykonaj("cofnij_ostatnia_zmiane", {}, True)
    assert [x["tekst"] for x in zasady.wczytaj()["zasady"]] == [z["tekst"]]


def test_wylaczenie_kontroli_i_cofanie(dane):
    ak.wykonaj("ustaw_kontrole", {"kod": "numeracja_ustepow", "wlaczona": False}, True)
    assert "numeracja_ustepow" in zasady.wczytaj()["wbudowane_wylaczone"]
    ak.wykonaj("cofnij_ostatnia_zmiane", {}, True)
    assert "numeracja_ustepow" not in zasady.wczytaj().get("wbudowane_wylaczone", [])


def test_pracownik_bez_uprawnien_nie_zmienia(dane, monkeypatch):
    _model(monkeypatch, [[("zmien_ustawienie", {"klucz": "braki", "wartosc": "pytajnik"})],
                         "Zmiany wprowadza notariusz."])
    wynik = ak.rozmawiaj([], "daj znak zapytania", moze_zmieniac=False)
    assert ustawienia_kancelarii.wczytaj()["braki"] == "opis"
    assert wynik["zmiany"] == []


def test_zle_wartosci_wracaja_do_modelu_jako_blad(dane):
    assert "blad" in ak.wykonaj("zmien_ustawienie", {"klucz": "braki", "wartosc": "wykrzyknik"}, True)
    assert "blad" in ak.wykonaj("zmien_ustawienie", {"klucz": "haslo", "wartosc": "x"}, True)
    assert "blad" in ak.wykonaj("usun_zasade", {"id": "nie-ma"}, True)
    assert ak.wykonaj("cofnij_ostatnia_zmiane", {}, True)["cofnieto"] is None


def test_prosba_o_zmiane_programu_bez_danych_klientow(dane, monkeypatch):
    wyslane = []
    monkeypatch.setenv("PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN", "github_pat_test")
    monkeypatch.setattr(ak.samonaprawa, "_wyslij", wyslane.append)
    monkeypatch.setattr(ak.samonaprawa.threading, "Thread",
                        lambda target, args, **kw: type("T", (), {"start": lambda s: target(*args)})())
    wynik = ak.wykonaj("zglos_zmiane_programu", {
        "opis": "Paragrafy taksy u Jana Kowalskiego (PESEL 85010112345, jan@kowalski.pl) liczy jak paragrafy aktu"},
        moze_zmieniac=False)   # prosbe moze zglosic takze pracownik
    assert wynik["przyjeto"] is True
    tekst = wyslane[0]["uwagi"]
    for dane_osobowe in ("Kowalsk", "85010112345", "jan@kowalski.pl"):
        assert dane_osobowe not in tekst
    assert wyslane[0]["rodzaj"] == "reczne" and len(wyslane[0]["odcisk"]) == 12


def test_limit_prosb_na_dobe(dane):
    for i in range(ak.MAX_PROSB_NA_DOBE):
        assert ak.wykonaj("zglos_zmiane_programu", {"opis": f"prosba {i}"}, True)["przyjeto"]
    assert ak.wykonaj("zglos_zmiane_programu", {"opis": "jeszcze jedna"}, True)["przyjeto"] is False


def test_kazde_ustawienie_kancelarii_ma_opis_dla_asystenta():
    assert set(ustawienia_kancelarii.domyslne()) == set(ustawienia_kancelarii.OPISY_USTAWIEN)


def test_historia_naprzemienna_od_uzytkownika():
    tury = ak._tury([{"rola": "asystent", "tresc": "Dzień dobry"}, {"rola": "uzytkownik", "tresc": "a"},
                     {"rola": "uzytkownik", "tresc": "b"}], "c")
    assert [t["role"] for t in tury] == ["user"]
    assert tury[0]["content"][0]["text"] == "a\n\nb\n\nc"


def test_endpoint(dane, monkeypatch):
    import app as aplikacja
    _model(monkeypatch, [[("zmien_ustawienie", {"klucz": "braki", "wartosc": "pytajnik"})], "Ustawione."])
    klient = TestClient(aplikacja.app)
    odp = klient.post("/api/asystent-kancelarii", json={"wiadomosc": "znak zapytania zamiast BRAK"})
    assert odp.status_code == 200 and odp.json()["odpowiedz"] == "Ustawione."
    assert ustawienia_kancelarii.wczytaj()["braki"] == "pytajnik"
    assert klient.post("/api/asystent-kancelarii", json={"wiadomosc": "  "}).status_code == 400


def test_prosba_bez_tokenu_trafia_do_przegladu_samonaprawy(dane, caplog):
    """Bez tokenu GitHub prosba zostawia znacznik w logach - przeglad co 30 min ja podejmie."""
    import importlib.util
    import json
    import logging
    from pathlib import Path
    from unittest.mock import MagicMock
    spec = importlib.util.spec_from_file_location(
        "sn_zgloszenie_ak", Path(__file__).parent / "scripts/samonaprawa/zgloszenie.py")
    zgl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(zgl)

    caplog.set_level(logging.ERROR)
    wynik = ak.wykonaj("zglos_zmiane_programu",
                       {"opis": "Pan Jan Kowalski chce, żeby taksa nie liczyła się do numeracji"}, True)
    assert wynik["przyjeto"] and "przegląd co 30 minut" in wynik["co_dalej"]
    linia = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("samonaprawa {"))
    assert "Kowalski" not in linia
    klient = MagicMock()
    klient.filter_log_events.return_value = {"events": [{"message": "x ERROR " + linia, "timestamp": 1}]}
    kandydaci = zgl.kandydaci(40, klient=klient)
    assert kandydaci and kandydaci[0]["rodzaj"] == "reczne" and kandydaci[0]["odcisk"] == wynik["numer"]
    assert zgl.oczysc(kandydaci[0])["uwagi"]
    json.dumps(kandydaci)


# ------------------------------------------------------------------ profil interfejsu

def test_profil_interfejsu_zdaniem(dane, monkeypatch):
    """'Większy tekst, start od kalendarza i schowaj GIIF' - trzy ustawienia, kazde do cofniecia."""
    _model(monkeypatch, [[("zmien_ustawienie", {"klucz": "rozmiar_tekstu", "wartosc": "duzy"}),
                          ("zmien_ustawienie", {"klucz": "widok_startowy", "wartosc": "kalendarz"}),
                          ("zmien_ustawienie", {"klucz": "ukryte_narzedzia", "wartosc": "GIIF, klikamy"})],
                         "Ustawione."])
    wynik = ak.rozmawiaj([], "większy tekst, zaczynaj od kalendarza i schowaj GIIF i Klikamy", True)
    u = ustawienia_kancelarii.wczytaj()
    assert (u["rozmiar_tekstu"], u["widok_startowy"], u["ukryte_narzedzia"]) == ("duzy", "kalendarz", "giif, klikamy")
    assert len(wynik["zmiany"]) == 3
    ak.wykonaj("cofnij_ostatnia_zmiane", {}, True)
    assert ustawienia_kancelarii.wczytaj()["ukryte_narzedzia"] == ""


def test_profil_interfejsu_odrzuca_nieznane(dane):
    assert "blad" in ak.wykonaj("zmien_ustawienie", {"klucz": "ukryte_narzedzia", "wartosc": "wszystko"}, True)
    assert "blad" in ak.wykonaj("zmien_ustawienie", {"klucz": "rozmiar_tekstu", "wartosc": "gigant"}, True)
    assert "blad" in ak.wykonaj("zmien_ustawienie", {"klucz": "widok_startowy", "wartosc": "admin"}, True)
    assert ustawienia_kancelarii._oczysc({"ukryte_narzedzia": "giif, nieznane"})["ukryte_narzedzia"] == ""


def test_kazde_narzedzie_menu_ma_odpowiednik_w_przegladarce():
    """Nazwy z ustawienia_kancelarii musza byc w MENU_NARZEDZI / EKRAN_STARTOWY w index.html."""
    from pathlib import Path
    html = (Path(__file__).parent / "static/index.html").read_text(encoding="utf-8")
    poczatek = html.index("const MENU_NARZEDZI")
    blok = html[poczatek:html.index("function zastosujProfilInterfejsu")]
    for nazwa in ustawienia_kancelarii.NARZEDZIA_MENU:
        assert f"{nazwa}:" in blok, nazwa
    for nazwa in ustawienia_kancelarii.WIDOKI_STARTOWE:
        assert f"{nazwa}:" in blok, nazwa
    for nazwa in ustawienia_kancelarii.ROZMIARY_TEKSTU:
        assert f"{nazwa}:" in blok, nazwa


# ------------------------------------------------------------------ postep prosb

def test_postep_prosby_etapy_i_czas():
    from datetime import datetime, timezone
    teraz = datetime(2026, 11, 23, 14, 0, tzinfo=timezone.utc)
    p = {"odcisk": "abc123def456", "czas": "2026-11-23T13:50:00", "opis": "x", "wyslano": False}
    kolejka = ak.postep_prosby(p, None, teraz)
    assert kolejka["etap"] == "w_kolejce" and kolejka["pozostalo_min"] > 30
    natychmiast = ak.postep_prosby(dict(p, wyslano=True), None, teraz)
    assert natychmiast["pozostalo_min"] < kolejka["pozostalo_min"]
    analiza = ak.postep_prosby(p, {"etap": "analiza", "czas": "2026-11-23T13:55:00Z"}, teraz)
    wdrazanie = ak.postep_prosby(p, {"etap": "wdrazanie", "czas": "2026-11-23T13:58:00Z"}, teraz)
    assert analiza["procent"] < wdrazanie["procent"] < 100
    assert analiza["pozostalo_min"] > wdrazanie["pozostalo_min"] > 0
    gotowe = ak.postep_prosby(p, {"etap": "gotowe", "czas": ""}, teraz)
    assert gotowe["zakonczona"] and gotowe["procent"] == 100
    decyzja = ak.postep_prosby(p, {"etap": "do_decyzji", "czas": "", "opis": "czeka"}, teraz)
    assert decyzja["zakonczona"] and decyzja["pozostalo_min"] is None and decyzja["uwaga"] == "czeka"


def test_endpoint_prosb_z_postepem(dane, monkeypatch):
    import app as aplikacja
    monkeypatch.setattr(ak, "_parametr_postepu",
                        lambda odcisk: {"etap": "kontrola", "czas": "2026-11-23T13:55:00Z"})
    ak.wykonaj("zglos_zmiane_programu", {"opis": "przycisk Sporządź projekt na górze"}, True)
    odp = TestClient(aplikacja.app).get("/api/asystent-kancelarii/prosby")
    assert odp.status_code == 200
    prosba = odp.json()["prosby"][0]
    assert prosba["etap"] == "kontrola" and "Testy" in prosba["etykieta"] and prosba["pozostalo_min"] >= 1


# ------------------------------------------------------------------ zbudowane = wlaczone

def test_zbudowana_zmiana_wlacza_sie_sama_u_prosiacej_kancelarii(dane, monkeypatch):
    """Decyzja wlasciciela: notariusz prosi raz - po wdrozeniu zmiana jest u niego wlaczona."""
    numer = ak.wykonaj("zglos_zmiane_programu", {"opis": "w Wordzie znak zapytania"}, True)["numer"]
    stany = {"etap": "analiza", "czas": "2026-11-23T14:00:00Z"}
    monkeypatch.setattr(ak, "_parametr_postepu", lambda odcisk: dict(stany))
    assert ak.odswiez_prosby()[0]["etap"] == "analiza"
    assert ustawienia_kancelarii.wczytaj()["braki"] == "opis"

    stany.update(etap="obserwacja", wlacz={"klucz": "braki", "wartosc": "pytajnik"})
    prosba = ak.odswiez_prosby()[0]
    assert prosba["wlaczono"] is True and "włączona" in prosba["etykieta"]
    assert ustawienia_kancelarii.wczytaj()["braki"] == "pytajnik"
    # bez drugiego wlaczania i z mozliwoscia cofniecia
    ak.odswiez_prosby()
    ak.wykonaj("cofnij_ostatnia_zmiane", {}, True)
    assert ustawienia_kancelarii.wczytaj()["braki"] == "opis"
    assert numer


def test_nieznane_ustawienie_z_raportu_nie_jest_wlaczane(dane, monkeypatch):
    ak.wykonaj("zglos_zmiane_programu", {"opis": "cos"}, True)
    monkeypatch.setattr(ak, "_parametr_postepu",
                        lambda o: {"etap": "gotowe", "czas": "", "wlacz": {"klucz": "haslo_admina", "wartosc": "x"}})
    prosba = ak.odswiez_prosby()[0]
    assert "wlaczono" not in prosba and "haslo_admina" not in ustawienia_kancelarii.wczytaj()


def test_zakonczona_prosba_nie_odpytuje_juz_aws(dane, monkeypatch):
    ak.wykonaj("zglos_zmiane_programu", {"opis": "cos"}, True)
    wolania = []
    monkeypatch.setattr(ak, "_parametr_postepu",
                        lambda o: wolania.append(o) or {"etap": "gotowe", "czas": "2026-11-23T14:00:00Z"})
    ak.odswiez_prosby()
    ak.odswiez_prosby()
    assert len(wolania) == 1


def test_start_aplikacji_wlacza_gotowe_zmiany(dane, monkeypatch):
    import app as aplikacja
    ak.wykonaj("zglos_zmiane_programu", {"opis": "wiekszy tekst"}, True)
    monkeypatch.setattr(ak, "_parametr_postepu",
                        lambda o: {"etap": "gotowe", "czas": "", "wlacz": {"klucz": "rozmiar_tekstu", "wartosc": "duzy"}})
    odp = TestClient(aplikacja.app).get("/api/ustawienia")
    assert odp.json()["ogolne"]["rozmiar_tekstu"] == "duzy"
