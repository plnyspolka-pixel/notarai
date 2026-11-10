"""Tokenomia: cennik z narzutem >= 100%, licznik tokenow, portfel kredytow,
pobieranie w punktach API, pakiety ze Stripe i symulacja ekonomii.
Bez AWS i bez sieci: Bedrock i Stripe zastapione atrapami."""
import os
import sys
import threading
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import tokenomia as t

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
import symulacja_tokenomii as sym  # noqa: E402

KANCELARIA = "kancelaria-testowa"


@pytest.fixture
def portfele(tmp_path, monkeypatch):
    """Tokenomia wlaczona, portfele w katalogu tymczasowym, kancelaria testowa."""
    import config
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(t, "WLACZONA", True)
    monkeypatch.setattr(t, "DEBET_KREDYTOW", 0.0)
    monkeypatch.setattr(t, "_kancelaria", lambda: KANCELARIA)
    return tmp_path


# --- cennik ---------------------------------------------------------------------

@pytest.mark.parametrize("kod", [k for k, a in t.AKCJE.items() if not a.darmowa])
def test_kazda_akcja_ma_narzut_co_najmniej_100_procent(kod):
    a = t.AKCJE[kod]
    kredyty = a.kredyty()
    # (a) cena katalogowa pokrywa 2 x koszt nawet dla 90% najdrozszych wykonan,
    assert kredyty * t.CENA_KREDYTU_ZL >= 2 * a.koszt_zl(90) - 1e-9
    # (b) przy najtanszym kredycie (najwiekszy rabat) srednio dalej 2 x koszt.
    assert kredyty * t.najnizsza_cena_kredytu() >= 2 * a.koszt_sredni_zl() - 1e-9


def test_najnizsza_cena_kredytu_nie_schodzi_ponizej_zalozenia_cennika():
    assert t.najnizsza_cena_kredytu() >= t.NAJNIZSZA_CENA_KREDYTU_ZL - 1e-9


def test_wieksze_pakiety_i_plany_sa_tansze_za_kredyt():
    ceny = [p["cena_zl"] / p["kredyty"] for p in sorted(t.PAKIETY.values(), key=lambda p: p["kredyty"])]
    assert ceny == sorted(ceny, reverse=True)
    ceny = [p["cena_zl"] / p["pula"] for p in sorted(t.PLANY.values(), key=lambda p: p["cena_zl"])]
    assert ceny == sorted(ceny, reverse=True)


def test_koszt_tokenow():
    # Opus 4.6: 5 USD / 1M wejscia, premia regionalna 10%, kurs 3,70.
    assert t.koszt_tokenow_zl("eu.anthropic.claude-opus-4-6-v1", 1_000_000, 0) == pytest.approx(20.35)
    assert t.koszt_tokenow_zl("eu.anthropic.claude-opus-4-6-v1", 0, 1_000_000) == pytest.approx(101.75)
    # Odczyt z pamieci podrecznej to 10% ceny wejscia.
    assert t.koszt_tokenow_zl("eu.anthropic.claude-opus-4-6-v1", 0, 0, cache_odczyt=1_000_000) \
        == pytest.approx(2.035)


def test_nieznany_model_liczymy_jak_najdrozszy():
    assert t.ceny_modelu("eu.nieznany-model") == (10.0, 50.0)
    assert t.ceny_modelu("eu.anthropic.claude-sonnet-4-6") == (3.0, 15.0)
    assert t.ceny_modelu("eu.anthropic.claude-opus-5-5") == (4.0, 20.0)


def test_akcje_zgodnosci_sa_darmowe():
    assert t.AKCJE["krz_sprawdzenie"].kredyty() == 0


def test_dokladnosc_odczytu_zmienia_cene_strony():
    ceny = [t.AKCJE[t.akcja_odczytu(w)].kredyty() for w in ("medium", "high", "max")]
    assert ceny == sorted(ceny) and ceny[0] < ceny[-1]
    assert t.akcja_odczytu("nieznany") == "odczyt_strony_max"


def test_dluga_rozmowa_i_dlugi_wzor_kosztuja_wiecej():
    assert t.jednostki_rozmowy(1_000) == 1
    assert t.jednostki_rozmowy(t.TURA_KONTEKST_TOKENOW * t.ZNAKOW_NA_TOKEN * 2 + 1) == 3
    assert t.jednostki_projektu(30_000) == 0
    assert t.jednostki_projektu(40_001) == 1
    assert t.jednostki_projektu(65_000) == 3


# --- licznik --------------------------------------------------------------------

class AtrapaStrumienia:
    def __init__(self, wejscie, wyjscie):
        self.uzycie = {"inputTokens": wejscie, "outputTokens": wyjscie}

    def converse_stream(self, **_):
        return {"stream": [{"contentBlockDelta": {"delta": {"text": "ok"}}},
                           {"messageStop": {"stopReason": "end_turn"}},
                           {"metadata": {"usage": self.uzycie}}]}


def test_wywolanie_modelu_trafia_do_licznika_akcji():
    import bedrock
    with patch.object(bedrock, "_klient", return_value=AtrapaStrumienia(10_000, 2_000)):
        with t.akcja("rozmowa_tura") as a:
            assert bedrock._rozmowa("system", [{"text": "x"}]) == "ok"
            bedrock._rozmowa("system", [{"text": "y"}])
    assert (a.licznik.wejscie, a.licznik.wyjscie, a.licznik.wywolan) == (20_000, 4_000, 2)
    assert a.licznik.koszt_zl == pytest.approx(t.koszt_tokenow_zl(bedrock.config.MODEL, 20_000, 4_000))


def test_licznik_dziala_w_watkach_rownoleglego_odczytu():
    """Paczki stron czyta pula watkow - kontekst akcji musi do nich dojsc."""
    import bedrock
    strony = [{"dokument": "a.pdf", "strona": i} for i in range(1, 9)]

    def paczka(p, wysilek=None, proby=3):
        t.dolicz("eu.anthropic.claude-opus-4-6-v1", {"inputTokens": 1000 * len(p), "outputTokens": 100})
        return [{"dokument": s["dokument"], "strona": s["strona"], "tresc": "x"} for s in p]
    with patch.object(bedrock, "_transkrybuj_z_ponowieniem", side_effect=paczka):
        with t.akcja("odczyt_strony_max", len(strony)) as a:
            wynik = bedrock.transkrybuj_strony(strony)
    assert len(wynik) == 8
    assert a.licznik.wejscie == 8000 and a.licznik.wywolan == 2


def test_bez_akcji_licznik_niczego_nie_liczy():
    t.dolicz("eu.anthropic.claude-opus-4-6-v1", {"inputTokens": 5})   # nie rzuca, nie liczy


# --- portfel --------------------------------------------------------------------

def test_kancelaria_bez_portfela_nie_jest_blokowana(portfele):
    with t.akcja("projekt") as a:
        pass
    assert a.pobrano == 0 and t.wczytaj_portfel(KANCELARIA) is None


def test_pobranie_po_udanej_akcji(portfele):
    t.doladuj(KANCELARIA, 50, "test")
    cena = t.AKCJE["projekt"].kredyty()
    with t.akcja("projekt", sprawa="sprawa abc") as a:
        t.dolicz("eu.anthropic.claude-opus-4-6-v1", {"inputTokens": 30_000, "outputTokens": 20_000})
    portfel = t.wczytaj_portfel(KANCELARIA)
    assert a.pobrano == cena and t.saldo(portfel) == pytest.approx(50 - cena)
    ostatni = portfel["historia"][-1]
    assert ostatni["akcja"] == "projekt" and ostatni["kredyty"] == -cena and ostatni["koszt_zl"] > 0
    assert set(ostatni) <= {"czas", "akcja", "ilosc", "kredyty", "koszt_zl", "sprawa"}   # bez danych osobowych
    miesiac = t.podsumowanie_miesiaca(portfel)
    assert miesiac["akcje"]["projekt"]["ile"] == 1 and miesiac["narzut"] > 1


def test_nieudana_akcja_nic_nie_kosztuje(portfele):
    t.doladuj(KANCELARIA, 50, "test")
    with pytest.raises(RuntimeError):
        with t.akcja("projekt"):
            raise RuntimeError("Bedrock niedostepny")
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == 50


def test_brak_kredytow_to_402_przed_wywolaniem_modelu(portfele):
    t.doladuj(KANCELARIA, 1, "test")
    wywolano = []
    with pytest.raises(t.BrakKredytow) as blad:
        with t.akcja("projekt"):
            wywolano.append(1)
    assert blad.value.status_code == 402 and not wywolano
    assert "Brak kredytów" in blad.value.detail


def test_debet_pozwala_dokonczyc_czynnosc(portfele, monkeypatch):
    monkeypatch.setattr(t, "DEBET_KREDYTOW", 30.0)
    t.doladuj(KANCELARIA, 1, "test")
    with t.akcja("projekt"):
        pass
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == pytest.approx(1 - t.AKCJE["projekt"].kredyty())


def test_najpierw_pula_abonamentu_potem_dokupione(portfele):
    t.odnow_pule(KANCELARIA, "start", znacznik="in_1")
    t.doladuj(KANCELARIA, 100, "pakiet")
    portfel = t.wczytaj_portfel(KANCELARIA)
    pula = t.PLANY["start"]["pula"]
    t._pobierz(portfel, pula + 50)
    assert portfel["pula"] == 0 and t.dokupione(portfel) == 50


def test_odnowienie_puli_raz_na_fakture_i_debet_nie_znika(portfele):
    t.odnow_pule(KANCELARIA, "start", znacznik="in_1")
    t.zmien_portfel(KANCELARIA, lambda p: p.update(pula=-12.0))
    t.odnow_pule(KANCELARIA, "start", znacznik="in_2")
    t.odnow_pule(KANCELARIA, "start", znacznik="in_2")      # powtorzony webhook
    portfel = t.wczytaj_portfel(KANCELARIA)
    # Dlug z poprzedniego okresu pomniejsza nowa pule - nie znika.
    assert portfel["pula"] == t.PLANY["start"]["pula"] - 12


def test_kredyty_probne_tylko_raz(portfele):
    t.zaloz_portfel_probny(KANCELARIA)
    t.zaloz_portfel_probny(KANCELARIA)
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == t.KREDYTY_PROBNE


def test_rownoczesne_pobrania_nie_gubia_sie(portfele):
    t.doladuj(KANCELARIA, 1000, "test")
    cena = t.AKCJE["formularz"].kredyty()

    def praca():
        with t.akcja("formularz"):
            pass
    watki = [threading.Thread(target=praca) for _ in range(20)]
    [w.start() for w in watki]
    [w.join() for w in watki]
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == pytest.approx(1000 - 20 * cena)


def test_obciazenie_po_wykonaniu(portfele):
    t.doladuj(KANCELARIA, 10, "test")
    assert t.obciaz("przesylka", 4) == 4 * t.AKCJE["przesylka"].kredyty()
    assert t.obciaz("przesylka", 0) == 0


# --- Stripe: pakiety kredytow ------------------------------------------------------

def _sesja(stan="paid", identyfikator="cs_1"):
    return {"id": identyfikator, "payment_status": stan,
            "metadata": {"typ": "kredyty", "kancelaria": KANCELARIA, "pakiet": "500"}}


def test_zaplacony_pakiet_dopisuje_kredyty_raz(portfele):
    assert t.z_platnosci_stripe(_sesja()) is True
    assert t.z_platnosci_stripe(_sesja()) is True          # powtorzony webhook
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == 500


def test_niezaplacony_pakiet_nic_nie_dopisuje(portfele):
    assert t.z_platnosci_stripe(_sesja("unpaid")) is True
    assert t.wczytaj_portfel(KANCELARIA) is None


def test_sesja_abonamentu_to_nie_pakiet(portfele):
    assert t.z_platnosci_stripe({"id": "cs_2", "payment_status": "paid", "metadata": {}}) is False


def test_checkout_pakietu_w_stripe(monkeypatch):
    import platnosci
    for k, v in {"KLUCZ": "sk_test", "WEBHOOK_SEKRET": "whsec", "CENA_ID": "price_x",
                 "ADRES": "https://app.notarai.test"}.items():
        monkeypatch.setattr(platnosci, k, v)
    wyslane = {}

    def stripe(sciezka, dane):
        wyslane.update(dane)
        return {"url": "https://checkout.stripe.test/s"}
    monkeypatch.setattr(platnosci, "_stripe", stripe)
    wynik = platnosci.utworz_checkout_kredytow("k1", "a@b.test", "", "500", 500, 450)
    assert wynik["adres"].startswith("https://checkout.stripe.test")
    assert wyslane["mode"] == "payment"
    assert wyslane["line_items"][0]["price_data"]["unit_amount"] == 45000
    assert wyslane["metadata"] == {"kancelaria": "k1", "typ": "kredyty", "pakiet": "500"}


# --- punkty API --------------------------------------------------------------------

@pytest.fixture
def klient(portfele, monkeypatch):
    import config
    import app as aplikacja
    monkeypatch.setattr(config, "SPRAWY", portfele / "sprawy", raising=False)
    return TestClient(aplikacja.app)


def test_rozmowa_pobiera_kredyty(klient):
    t.doladuj(KANCELARIA, 20, "test")
    with patch("bedrock.rozmawiaj", return_value="Rozumiem."):
        odp = klient.post("/api/rozmowa", json={"kontekst": "DANE: x", "tresc": "Cena 50 000"})
    assert odp.status_code == 200
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == 20 - t.AKCJE["rozmowa_tura"].kredyty()


def test_rozmowa_bez_kredytow_402_i_model_nie_wolany(klient):
    t.doladuj(KANCELARIA, 0.5, "test")
    with patch("bedrock.rozmawiaj", return_value="x") as model:
        odp = klient.post("/api/rozmowa", json={"kontekst": "DANE: x", "tresc": "Cena"})
    assert odp.status_code == 402 and "Brak kredytów" in odp.json()["detail"]
    model.assert_not_called()


def test_blad_modelu_nie_pobiera_kredytow(klient):
    t.doladuj(KANCELARIA, 20, "test")
    with patch("bedrock.rozmawiaj", side_effect=RuntimeError("awaria")):
        odp = klient.post("/api/rozmowa", json={"kontekst": "DANE: x", "tresc": "Cena"})
    assert odp.status_code == 502
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == 20


def test_odczyt_pobiera_za_strony_i_zestawienie(klient):
    from test_bez_zapisu import ODCZYT, _skan, _wzor
    t.doladuj(KANCELARIA, 100, "test")
    with patch("bedrock.odczytaj_sprawe", return_value=(ODCZYT, [])), \
         patch("bedrock.rozmawiaj", return_value="Pytania?"):
        odp = klient.post("/api/odczyt", files=[("wzor", _wzor()), ("skany", _skan()), ("skany", _skan())],
                          data={"wysilek": "medium"})
    assert odp.status_code == 200, odp.text
    oczekiwane = 2 * t.AKCJE["odczyt_strony_medium"].kredyty() + t.AKCJE["zalozenie_sprawy"].kredyty()
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == pytest.approx(100 - oczekiwane)


def test_strumien_odczytu_bez_kredytow_konczy_sie_402(klient):
    from test_bez_zapisu import _skan, _wzor
    t.doladuj(KANCELARIA, 1, "test")
    with patch("bedrock.odczytaj_sprawe") as model:
        odp = klient.post("/api/odczyt", files=[("wzor", _wzor()), ("skany", _skan())],
                          headers={"Accept": "application/x-ndjson"})
    assert '"kod": 402' in odp.text
    model.assert_not_called()


def test_projekt_pobiera_kredyty(klient):
    from test_bez_zapisu import _wzor
    t.doladuj(KANCELARIA, 40, "test")
    with patch("bedrock.sporzadz_projekt", return_value="Akt."):
        odp = klient.post("/api/projekt", files={"wzor": _wzor()}, data={"pola": "[]"})
    assert odp.status_code == 200
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == 40 - t.AKCJE["projekt"].kredyty()


def test_widok_kredytow_i_ustawienia(klient):
    t.doladuj(KANCELARIA, 15, "test")
    widok = klient.get("/api/kredyty").json()
    assert widok["egzekwowana"] and widok["saldo"] == 15
    assert {c["kod"] for c in widok["cennik"]} == set(t.AKCJE)
    assert "koszt_p90_zl" not in widok["cennik"][0]          # koszty widzi tylko administrator
    assert klient.get("/api/ustawienia").json()["kredyty"] == 15


def test_panel_admina_tokenomii_wymaga_admina(klient):
    assert klient.get("/api/admin/tokenomia").status_code in (401, 403, 503)


# --- kalibracja i symulacja ------------------------------------------------------------

def test_kalibracja_wykrywa_niedoszacowany_koszt():
    drogie = [(7.0, 60_000, 70_000, 12.5)] * 30           # projekt kosztuje 7 zl, cena 12,5 kr
    wynik = {w["akcja"]: w for w in t.kalibracja({"projekt": drogie})}
    assert wynik["projekt"]["ok"] is False
    assert wynik["projekt"]["zalecane_kredyty"] * t.CENA_KREDYTU_ZL >= 2 * 7.0


def test_kalibracja_potwierdza_trafny_cennik():
    tanie = [(1.0, 20_000, 10_000, 12.5)] * 30
    assert all(w["ok"] for w in t.kalibracja({"projekt": tanie}))


def test_kalibracja_pomija_malo_pomiarow():
    assert t.kalibracja({"projekt": [(1.0, 1, 1, 1)] * 3}) == []


def test_symulacja_cennik_v2_trzyma_narzut_a_v0_nie():
    r = sym.symuluj(n=4000, ziarno=3)
    assert r["v2"]["narzut_portfela_tani"] >= 1.0        # przy najtanszym kredycie
    assert r["v2"]["spraw_ze_strata_tani"] == 0
    assert r["v2"]["spraw_ponizej_100_katalog"] < 0.02
    assert r["v0"]["spraw_ponizej_100_tani"] > 0.5         # dlaczego odrzucilismy cennik naiwny
    assert r["v2"]["kredyty_srednio"] < r["v1"]["kredyty_srednio"]


def test_kazdy_model_biznesowy_ma_narzut_100_procent_na_kosztach_ai():
    e = sym.ekonomia_modeli()
    for profil, modele in e["modele"].items():
        for nazwa, m in modele.items():
            assert m["narzut_na_koszcie_ai"] >= 1.0, (profil, nazwa)
            assert m["marza_po_wsparciu_zl"] > 0, (profil, nazwa)


# --- webhook Stripe i konta kancelarii (pelny przeplyw z test_platnosci) --------------

from test_logowanie import _przywroc_moduly  # noqa: E402,F401 - sprzata po trybie SaaS
from test_platnosci import (ADMIN, CZLONEK, WLASCICIEL, _faktura, _wyslij, jako,  # noqa: E402,F401
                            logowanie_atrapa, serwer, stripe_atrapa)


@pytest.fixture
def serwer_z_kredytami(serwer, monkeypatch):
    monkeypatch.setattr(t, "WLACZONA", True)
    klient, id_k = serwer
    klient.app.include_router(t.router)
    klient.app.include_router(t.router_admina)
    return klient, id_k


def test_nowa_kancelaria_dostaje_kredyty_probne(serwer_z_kredytami):
    klient, _ = serwer_z_kredytami
    odp = klient.post("/api/admin/kancelarie", headers=ADMIN, json={"nazwa": "Nowak"})
    assert t.saldo(t.wczytaj_portfel(odp.json()["id"])) == t.KREDYTY_PROBNE


def test_oplacona_faktura_odnawia_pule_planu(serwer_z_kredytami):
    klient, id_k = serwer_z_kredytami
    assert _wyslij(klient, "invoice.paid", _faktura(id_k, "in_7")).status_code == 200
    assert _wyslij(klient, "invoice.paid", _faktura(id_k, "in_7")).status_code == 200
    portfel = t.wczytaj_portfel(id_k)
    assert portfel["pula"] == t.PLANY[t.PLAN_DOMYSLNY]["pula"] and portfel["plan"] == t.PLAN_DOMYSLNY
    assert sum(1 for w in portfel["historia"] if w["akcja"] == "odnowienie_puli") == 1


def test_pakiet_z_webhooka_nie_rusza_subskrypcji(serwer_z_kredytami):
    import autoryzacja
    klient, id_k = serwer_z_kredytami
    sesja = {"id": "cs_9", "payment_status": "paid", "customer": "cus_9", "mode": "payment",
             "metadata": {"typ": "kredyty", "kancelaria": id_k, "pakiet": "100"}}
    assert _wyslij(klient, "checkout.session.completed", sesja).status_code == 200
    portfel = t.wczytaj_portfel(id_k)
    assert t.dokupione(portfel) == 100
    wpis = autoryzacja._znajdz(autoryzacja._wczytaj_rejestr(), id_k)[1]
    assert not (wpis.get("stripe") or {}).get("status")


def test_pakiet_kupuje_tylko_wlasciciel(serwer_z_kredytami, stripe_atrapa):
    klient, id_k = serwer_z_kredytami
    assert klient.post("/api/kredyty/pakiet", headers=jako(CZLONEK, id_k), json={"pakiet": "500"}).status_code == 403
    assert klient.post("/api/kredyty/pakiet", headers=jako(WLASCICIEL, id_k), json={"pakiet": "zly"}).status_code == 400
    odp = klient.post("/api/kredyty/pakiet", headers=jako(WLASCICIEL, id_k), json={"pakiet": "500"})
    assert odp.status_code == 201 and odp.json()["adres"].startswith("https://checkout.stripe.com/")


def test_admin_doladowuje_i_widzi_marze(serwer_z_kredytami):
    klient, id_k = serwer_z_kredytami
    odp = klient.post(f"/api/admin/kancelarie/{id_k}/kredyty", headers=ADMIN, json={"kredyty": 250})
    assert odp.status_code == 200 and odp.json()["saldo"] == 250
    assert klient.post(f"/api/admin/kancelarie/{id_k}/kredyty", headers=jako(WLASCICIEL, id_k),
                       json={"kredyty": 250}).status_code in (401, 403)
    widok = klient.get("/api/admin/tokenomia", headers=ADMIN).json()
    assert widok["najnizsza_cena_kredytu"] >= t.NAJNIZSZA_CENA_KREDYTU_ZL
    assert any(k["id"] == id_k and k["saldo"] == 250 for k in widok["kancelarie"])
    assert "koszt_p90_zl" in widok["cennik"][0]


def test_kancelaria_widzi_swoje_kredyty(serwer_z_kredytami):
    klient, id_k = serwer_z_kredytami
    t.doladuj(id_k, 42, "test")
    widok = klient.get("/api/kredyty", headers=jako(CZLONEK, id_k)).json()
    assert widok["saldo"] == 42 and widok["egzekwowana"]


# --- zabezpieczenia portfela (druga runda) ------------------------------------------

def test_partie_wygasaja_i_trafiaja_do_historii(portfele):
    t.doladuj(KANCELARIA, 40, "nagroda", zrodlo="nagroda", dni=-1)     # juz po terminie
    t.doladuj(KANCELARIA, 60, "pakiet")
    portfel = t.wczytaj_portfel(KANCELARIA)
    assert t.saldo(portfel) == 60                                      # wygasla sie nie liczy
    t.zmien_portfel(KANCELARIA, lambda p: None)                        # kazdy zapis sprzata
    portfel = t.wczytaj_portfel(KANCELARIA)
    assert any(w["akcja"] == "wygasniecie" and w["kredyty"] == -40 for w in portfel["historia"])


def test_najpierw_wydajemy_to_co_wygasa_najwczesniej(portfele):
    t.doladuj(KANCELARIA, 100, "pakiet")                               # 365 dni
    t.doladuj(KANCELARIA, 20, "nagroda", zrodlo="nagroda")             # 90 dni
    portfel = t.wczytaj_portfel(KANCELARIA)
    t._pobierz(portfel, 30)
    zostalo = {p["zrodlo"]: p["kredyty"] for p in portfel["partie"]}
    assert zostalo == {"pakiet": 90}


def test_stary_format_portfela_przechodzi_na_partie(portfele):
    import json
    t._plik(KANCELARIA).write_text(json.dumps({"plan": "start", "pula": 5, "doladowane": 70}))
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == 75
    t.zmien_portfel(KANCELARIA, lambda p: None)
    portfel = t.wczytaj_portfel(KANCELARIA)
    assert "doladowane" not in portfel and t.dokupione(portfel) == 70


def test_kredyty_probne_przetrwaja_pierwsza_fakture(portfele):
    t.zaloz_portfel_probny(KANCELARIA)
    t.odnow_pule(KANCELARIA, "start", znacznik="in_1")
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == t.KREDYTY_PROBNE + t.PLANY["start"]["pula"]


def test_kredyty_probne_raz_na_nip(portfele):
    t.zaloz_portfel_probny("kancelaria-a", nip="525-000-00-00")
    t.zaloz_portfel_probny("kancelaria-b", nip="5250000000")           # ten sam NIP, inny zapis
    assert t.saldo(t.wczytaj_portfel("kancelaria-a")) == t.KREDYTY_PROBNE
    assert t.saldo(t.wczytaj_portfel("kancelaria-b")) == 0
    import json
    assert "5250000000" not in json.dumps(t.wczytaj_portfel(t.REJESTR_PROB))   # tylko skrot


def test_rownolegle_akcje_nie_przekraczaja_salda(portfele):
    t.doladuj(KANCELARIA, 20, "test")
    cena = t.AKCJE["projekt"].kredyty()
    wejscie, wyniki = threading.Barrier(5), []

    def praca():
        try:
            with t.akcja("projekt"):
                wejscie.wait(timeout=1)
            wyniki.append("ok")
        except t.BrakKredytow:
            wyniki.append("402")
        except threading.BrokenBarrierError:
            wyniki.append("ok")
    watki = [threading.Thread(target=praca) for _ in range(5)]
    [w.start() for w in watki]
    [w.join() for w in watki]
    assert wyniki.count("ok") == int(20 // cena)
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) >= 0
    assert t.zarezerwowane(KANCELARIA) == 0


def test_wycena_przed_czynnoscia(klient):
    t.doladuj(KANCELARIA, 10, "test")
    odp = klient.post("/api/kredyty/wycena", json={"pozycje": [{"kod": "odczyt_strony_max", "ilosc": 12}]})
    w = odp.json()
    assert w["kredyty"] == 12 * t.AKCJE["odczyt_strony_max"].kredyty() and w["wystarczy"] is False
    assert klient.post("/api/kredyty/wycena", json={"pozycje": [{"kod": "nie-ma", "ilosc": 1}]}).status_code == 400


def test_niskie_saldo_w_widoku(klient):
    t.doladuj(KANCELARIA, 5, "test")
    assert klient.get("/api/kredyty").json()["niskie"] is True


def test_ksiega_drugi_raz_w_ciagu_doby_bez_oplaty(portfele):
    t.doladuj(KANCELARIA, 20, "test")
    assert not t.kw_juz_oplacona("sprawa1", "WA1M/00012345/6")
    t.zapamietaj_kw("sprawa1", "WA1M/00012345/6")
    assert t.kw_juz_oplacona("sprawa1", "WA1M/00012345/6")
    assert not t.kw_juz_oplacona("sprawa2", "WA1M/00012345/6")         # inna sprawa = nowa oplata
    import json
    assert "00012345" not in json.dumps(t.wczytaj_portfel(KANCELARIA))


def test_cena_ksiegi_to_wartosc_nie_koszt():
    kw = t.AKCJE["ekw_ksiega"]
    assert kw.koszt_sredni_zl() < 0.5                                  # Apify ~0,13 zl, czasem EasyMKW
    assert kw.kredyty() >= 5 and kw.kredyty() * t.CENA_KREDYTU_ZL >= 2 * kw.koszt_zl(90)


def test_limit_krokow_asystenta():
    for _ in range(t.MAKS_KROKOW_ZLECENIA):
        t.krok_zlecenia("zl-test-limit")
    with pytest.raises(Exception) as blad:
        t.krok_zlecenia("zl-test-limit")
    assert blad.value.status_code == 429


def test_budzet_publicznego_kalkulatora(monkeypatch):
    monkeypatch.setattr(t, "_BUDZET", {})
    monkeypatch.setattr(t, "BUDZET_PUBLICZNY_ZL", 1.0)
    assert t.budzet_publiczny_ok()
    t.dolicz_publiczny(1.2)
    assert not t.budzet_publiczny_ok()


def test_kalkulator_po_budzecie_odsyla_do_formularza(monkeypatch):
    import kalkulator
    from fastapi import FastAPI
    monkeypatch.setattr(t, "budzet_publiczny_ok", lambda: False)
    monkeypatch.setattr(kalkulator, "WLACZONY", True)
    app = FastAPI()
    app.include_router(kalkulator.router)
    with patch("bedrock.rozmowa_kalkulatora") as model:
        odp = TestClient(app).post("/api/taksa/rozmowa", json={"wiadomosc": "Sprzedaz mieszkania za 500 tys."})
    assert odp.status_code == 503 and "formularza" in odp.json()["detail"]
    model.assert_not_called()


def test_plan_ogranicza_liczbe_osob(portfele):
    t.odnow_pule(KANCELARIA, "start", znacznik="in_1")
    t.limit_zespolu(KANCELARIA, 1)
    with pytest.raises(Exception) as blad:
        t.limit_zespolu(KANCELARIA, t.PLANY["start"]["uzytkownikow"])
    assert blad.value.status_code == 402
