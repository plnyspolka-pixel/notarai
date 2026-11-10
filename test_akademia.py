"""Akademia notarai: quiz po stronie serwera, nagrody z limitami, sciezka
wdrozenia na faktach, polecenia, premia stazowa, zaswiadczenie AI Act."""
from datetime import datetime, timedelta, timezone

import pytest

import akademia as a
import tokenomia as t

KANCELARIA = "kancelaria-akademia"


@pytest.fixture
def kredyty(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(t, "WLACZONA", True)
    monkeypatch.setattr(t, "_kancelaria", lambda: KANCELARIA)
    t.odnow_pule(KANCELARIA, "kancelaria", znacznik="in_0")
    return tmp_path


def _dobre(kod):
    return [p["poprawna"] for p in a._MODULY[kod]["pytania"]]


def _cofnij_probe(kod, email):
    """Symuluje uplyw przerwy miedzy probami."""
    stare = (datetime.now(timezone.utc) - timedelta(minutes=a.PRZERWA_MINUT + 1)).isoformat(timespec="seconds")
    a._zmien(KANCELARIA, lambda d: d["osoby"][a._sha(email)]["proby"].update({kod: stare}))


# --- tresc i quiz ---------------------------------------------------------------------

def test_przegladarka_nie_dostaje_poprawnych_odpowiedzi():
    for m in a.MODULY:
        widok = a.modul_dla_przegladarki(m)
        assert all("poprawna" not in p for p in widok["pytania"])
        assert len(m["pytania"]) == 4 and all(0 <= p["poprawna"] < len(p["odpowiedzi"]) for p in m["pytania"])


def test_zaliczenie_daje_kredyty_raz(kredyty):
    przed = t.saldo(t.wczytaj_portfel(KANCELARIA))
    w = a.zalicz(KANCELARIA, "anna@k.test", "co_robi_model", _dobre("co_robi_model"), w_zespole=True)
    assert w["zaliczony"] and w["nagroda"] == 15
    w2 = a.zalicz(KANCELARIA, "anna@k.test", "co_robi_model", _dobre("co_robi_model"), w_zespole=True)
    assert w2["juz_zaliczony"] and w2["nagroda"] == 0
    portfel = t.wczytaj_portfel(KANCELARIA)
    assert t.saldo(portfel) == przed + 15
    assert any(p["zrodlo"] == "nagroda" for p in portfel["partie"])           # partia z terminem


def test_niezaliczenie_pokazuje_bledne_pytania_ale_nie_odpowiedzi(kredyty):
    zle = [(x + 1) % 2 for x in _dobre("sprawdzenie")]
    w = a.zalicz(KANCELARIA, "anna@k.test", "sprawdzenie", zle, w_zespole=True)
    assert not w["zaliczony"] and w["nagroda"] == 0 and w["bledne"]
    assert "poprawna" not in str(w)


def test_przerwa_miedzy_probami_utrudnia_zgadywanie(kredyty):
    zle = [9, 9, 9, 9]
    a.zalicz(KANCELARIA, "anna@k.test", "pomocnik", zle, w_zespole=True)
    with pytest.raises(Exception) as blad:
        a.zalicz(KANCELARIA, "anna@k.test", "pomocnik", _dobre("pomocnik"), w_zespole=True)
    assert blad.value.status_code == 429
    _cofnij_probe("pomocnik", "anna@k.test")
    assert a.zalicz(KANCELARIA, "anna@k.test", "pomocnik", _dobre("pomocnik"), w_zespole=True)["zaliczony"]


def test_prog_zaliczenia_trzy_z_czterech(kredyty):
    odp = _dobre("dane_klientow")
    odp[0] = 9
    assert a.zalicz(KANCELARIA, "anna@k.test", "dane_klientow", odp, w_zespole=True)["zaliczony"]


def test_osoba_spoza_zespolu_uczy_sie_bez_nagrody(kredyty):
    w = a.zalicz(KANCELARIA, "obcy@x.test", "co_robi_model", _dobre("co_robi_model"), w_zespole=False)
    assert w["zaliczony"] and w["nagroda"] == 0


def test_limit_nagradzanych_osob(kredyty, monkeypatch):
    monkeypatch.setattr(a, "MAKS_NAGRADZANYCH_OSOB", 2)
    nagrody = [a.zalicz(KANCELARIA, f"osoba{i}@k.test", "co_robi_model", _dobre("co_robi_model"), True)["nagroda"]
               for i in range(4)]
    assert nagrody == [15, 15, 0, 0]
    # Juz nagradzana osoba dalej dostaje za kolejne moduly.
    assert a.zalicz(KANCELARIA, "osoba0@k.test", "sprawdzenie", _dobre("sprawdzenie"), True)["nagroda"] == 15


def test_bez_tokenomii_zaliczenie_bez_kredytow(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(t, "WLACZONA", False)
    w = a.zalicz("k-bez", "anna@k.test", "co_robi_model", _dobre("co_robi_model"), True)
    assert w["zaliczony"] and w["nagroda"] == 0


def test_w_pliku_akademii_nie_ma_adresow_email(kredyty):
    a.zalicz(KANCELARIA, "anna@k.test", "co_robi_model", _dobre("co_robi_model"), True)
    import json
    assert "anna@k.test" not in json.dumps(a.wczytaj(KANCELARIA))


def test_nagrody_kosztuja_nas_malo():
    """Cala Akademia dla jednej osoby to ok. 100 kr; dla kancelarii najwyzej
    MAKS_NAGRADZANYCH_OSOB osob + sciezka. Koszt AI tych kredytow to ulamek."""
    na_osobe = sum(m["nagroda"] for m in a.MODULY)
    maks = na_osobe * a.MAKS_NAGRADZANYCH_OSOB + a.NAGRODA_WDROZENIA
    assert na_osobe == 100 and maks <= 700


# --- zaswiadczenie ------------------------------------------------------------------------

def test_zaswiadczenie_ai_act(kredyty):
    a.zalicz(KANCELARIA, "anna@k.test", "co_robi_model", _dobre("co_robi_model"), True)
    tekst = a.zaswiadczenie("Kancelaria Testowa", "anna@k.test", a.wczytaj(KANCELARIA))
    assert "art. 4" in tekst and "[x] Co model robi" in tekst and "[ ] Sprawdzenie" in tekst


# --- sciezka wdrozenia ---------------------------------------------------------------------

def _wpis(**zmiany):
    return {"id": KANCELARIA, "nazwa": "Testowa", "umowa": {"zaakceptowano": "2026-11-01"},
            "zespol": [{"email": "anna@k.test", "rola": "wlasciciel", "dolaczyl": "2026-11-01"}], **zmiany}


def test_sciezka_startuje_z_postepem_i_nazywa_nastepny_krok(kredyty):
    s = a.sciezka(KANCELARIA, _wpis())
    assert s["gotowe"] == 1 and s["nastepny"]["kod"] == "pierwsza_sprawa" and s["nastepny"]["jak"]


def test_sciezka_liczy_fakty_a_nie_deklaracje(kredyty, monkeypatch):
    with t.akcja("odczyt_strony_max", 3):
        pass
    with t.akcja("projekt"):
        pass
    import urzadzenia
    monkeypatch.setattr(urzadzenia, "lista", lambda k: [{"id": "komp"}])
    wpis = _wpis(zespol=[{"email": "anna@k.test", "rola": "wlasciciel", "dolaczyl": "2026-11-01"},
                         {"email": "piotr@k.test", "rola": "czlonek", "dolaczyl": "2026-11-02"}])
    stan = a.kroki_sciezki(KANCELARIA, wpis)
    assert stan == {"umowa": True, "pierwsza_sprawa": True, "pierwszy_projekt": True,
                    "zespol": True, "pomocnik": True, "akademia": False}
    przed = t.saldo(t.wczytaj_portfel(KANCELARIA))
    for m in a.MODULY:
        a.zalicz(KANCELARIA, "anna@k.test", m["kod"], _dobre(m["kod"]), True)
    s = a.sciezka(KANCELARIA, wpis)
    assert s["gotowe"] == 6 and s["przyznano"] == a.NAGRODA_WDROZENIA
    assert a.sciezka(KANCELARIA, wpis)["przyznano"] == 0                      # raz
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == pytest.approx(przed + 100 + a.NAGRODA_WDROZENIA)


def test_zaproszony_ale_niedolaczony_sie_nie_liczy(kredyty):
    wpis = _wpis(zespol=[{"email": "anna@k.test", "rola": "wlasciciel", "dolaczyl": "2026-11-01"},
                         {"email": "piotr@k.test", "rola": "czlonek", "dolaczyl": None}])
    assert a.kroki_sciezki(KANCELARIA, wpis)["zespol"] is False


# --- polecenia i staz ----------------------------------------------------------------------

def _rejestr(nip_a="5250000000", nip_b="7770000000"):
    return {"s1": {"id": "polecajaca", "aktywna": True, "dane": {"nip": nip_a}},
            "s2": {"id": "polecona", "aktywna": True, "dane": {"nip": nip_b}, "polecil": "polecajaca"}}


def test_kod_polecenia_wskazuje_kancelarie():
    rejestr = _rejestr()
    assert a.kancelaria_z_kodu(rejestr, a.kod_polecenia("polecajaca").lower()) == "polecajaca"
    assert a.kancelaria_z_kodu(rejestr, "XXXXXXXX") is None


def test_polecenie_nagradza_obie_strony_raz(kredyty):
    t.odnow_pule("polecajaca", "start", znacznik="a")
    t.odnow_pule("polecona", "start", znacznik="b")
    rejestr = _rejestr()
    assert a.nagrodz_polecenie(rejestr, rejestr["s2"]) == a.NAGRODA_POLECENIA
    assert a.nagrodz_polecenie(rejestr, rejestr["s2"]) == 0                   # druga faktura
    for k in ("polecajaca", "polecona"):
        assert t.saldo(t.wczytaj_portfel(k)) == t.PLANY["start"]["pula"] + a.NAGRODA_POLECENIA


def test_polecenie_tej_samej_firmy_bez_nagrody(kredyty):
    t.odnow_pule("polecajaca", "start", znacznik="a")
    rejestr = _rejestr(nip_a="5250000000", nip_b="5250000000")
    assert a.nagrodz_polecenie(rejestr, rejestr["s2"]) == 0
    assert t.saldo(t.wczytaj_portfel("polecajaca")) == t.PLANY["start"]["pula"]


def test_limit_polecen_rocznie(kredyty, monkeypatch):
    monkeypatch.setattr(a, "MAKS_POLECEN_ROCZNIE", 1)
    t.odnow_pule("polecajaca", "start", znacznik="a")
    rejestr = _rejestr()
    rejestr["s3"] = {"id": "polecona2", "aktywna": True, "dane": {"nip": "1110000000"}, "polecil": "polecajaca"}
    assert a.nagrodz_polecenie(rejestr, rejestr["s2"]) > 0
    assert a.nagrodz_polecenie(rejestr, rejestr["s3"]) == 0


def test_premia_stazowa_i_nastepny_prog():
    assert a.premia_stazu(5, 700) == 0
    assert a.premia_stazu(6, 700) == 35
    assert a.premia_stazu(12, 700) == 70
    assert a.nastepna_premia(4) == {"za_okresow": 2, "procent": 5}
    assert a.nastepna_premia(13) is None


# --- przeplyw przez API (SaaS, webhook Stripe) -------------------------------------------

from test_logowanie import _przywroc_moduly  # noqa: E402,F401
from test_platnosci import (ADMIN, CZLONEK, WLASCICIEL, _faktura, _wyslij, jako,  # noqa: E402,F401
                            logowanie_atrapa, serwer)


@pytest.fixture
def serwer_akademii(serwer, monkeypatch):
    monkeypatch.setattr(t, "WLACZONA", True)
    klient, id_k = serwer
    klient.app.include_router(a.router)
    t.odnow_pule(id_k, "kancelaria", znacznik="start")
    return klient, id_k


def test_api_stan_quiz_zaswiadczenie(serwer_akademii):
    klient, id_k = serwer_akademii
    stan = klient.get("/api/akademia", headers=jako(CZLONEK, id_k)).json()
    assert stan["wszystkie"] == 6 and stan["nagrody_do_zdobycia"] == 100
    assert all("poprawna" not in p for m in stan["moduly"] for p in m["pytania"])
    assert len(stan["polecenie"]["kod"]) == 8
    odp = klient.post("/api/akademia/co_robi_model", headers=jako(CZLONEK, id_k),
                      json={"odpowiedzi": _dobre("co_robi_model")})
    assert odp.json()["nagroda"] == 15
    tekst = klient.get("/api/akademia/zaswiadczenie", headers=jako(CZLONEK, id_k)).text
    assert CZLONEK in tekst and "[x] Co model robi" in tekst


def test_api_postep_zespolu_tylko_dla_wlasciciela(serwer_akademii):
    klient, id_k = serwer_akademii
    assert klient.get("/api/akademia/zespol/postep", headers=jako(CZLONEK, id_k)).status_code == 403
    osoby = klient.get("/api/akademia/zespol/postep", headers=jako(WLASCICIEL, id_k)).json()["osoby"]
    assert {o["email"] for o in osoby} == {WLASCICIEL, CZLONEK}


def test_premia_stazowa_z_faktury(serwer_akademii):
    klient, id_k = serwer_akademii
    for i in range(6):
        _wyslij(klient, "invoice.paid", _faktura(id_k, f"in_s{i}"))
    portfel = t.wczytaj_portfel(id_k)
    premie = [w for w in portfel["historia"] if str(w.get("powod", "")).startswith("premia stazowa")]
    assert len(premie) == 1 and premie[0]["kredyty"] == a.premia_stazu(6, t.PLANY["kancelaria"]["pula"])


def test_nagrody_zwracaja_sie_w_pierwszym_miesiacu():
    """Koszt AI nagrod (Akademia + polecenie) mniejszy niz miesieczna marza
    najmniejszej kancelarii - grywalizacja to tani koszt pozyskania."""
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
    import symulacja_tokenomii as sym
    dodatki = sym.ekonomia_dodatkow()["profile"]["mala"]
    marza = sym.ekonomia_modeli()["modele"]["mala (25 spraw/mies.)"]["A_abonament_z_pula"]["marza_po_wsparciu_zl"]
    assert dodatki["koszt_nagrod_jednorazowo_zl"] + dodatki["koszt_polecenia_zl"] < marza
