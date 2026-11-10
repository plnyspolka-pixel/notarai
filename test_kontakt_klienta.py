"""Platne odsloniecie kontaktu klienta z zapytania (wizyty.py + tokenomia.py).

Sprawdzamy, ze telefon i e-mail klienta nie wyciekaja zadnym kanalem przed
odslonieciem (lista, e-mail do kancelarii, tresc wiadomosci, kalendarz), ze
pula w planie, duplikat i reklamacja dzialaja, i ze klient nie czeka w
nieskonczonosc (SLA). Dane fikcyjne, e-mail nie wychodzi."""
from datetime import datetime, timedelta

import pytest

import tokenomia as t
import wizyty
from test_wizyty import ZGLOSZENIE, klient  # noqa: F401 - wspolna atrapa bazy i rejestru

KANCELARIA = "lokalna"      # w atrapie rejestru z test_wizyty


@pytest.fixture
def platny(klient, monkeypatch):  # noqa: F811
    """Tokenomia wlaczona dla kancelarii z atrapy (w trybie lokalnym zwykle wylaczona)."""
    monkeypatch.setattr(t, "WLACZONA", True)
    monkeypatch.setattr(t, "DEBET_KREDYTOW", 0.0)
    monkeypatch.setattr(t, "egzekwowana", lambda k: t.wczytaj_portfel(k) if k else None)
    monkeypatch.setattr(t, "_kancelaria", lambda: KANCELARIA)
    t.odnow_pule(KANCELARIA, "start", znacznik="in_test")     # 2 kontakty w planie
    return klient


def _zgloszenie(k, **zmiany):
    odp = k.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, **zmiany})
    assert odp.status_code == 201, odp.text
    return odp.json()["id"]


def _lista(k):
    return {z["id"]: z for z in k.get("/api/zapytania").json()}


def _wyczerp_pule():
    t.zmien_portfel(KANCELARIA, lambda p: p.setdefault("liczniki", {}).update(
        {t._miesiac(): {"kontakt_klienta": t.PLANY["start"]["kontakty"]}}))


# --- nic nie wycieka przed odslonieciem ---------------------------------------------

def test_lista_bez_kontaktu_ale_z_tym_co_potrzebne_do_decyzji(platny):
    ident = _zgloszenie(platny, wiadomosc="Prosze dzwonic po 17: 601 234 567. Cena 450 000 zł.")
    z = _lista(platny)[ident]
    assert z["zakryty"] is True
    assert z["klient"]["telefon"] == "" and z["klient"]["email"] == ""
    assert z["klient"]["ma_telefon"] and z["klient"]["ma_email"] and z["klient"]["imie"] == "Zenobiusz"
    assert "601 234 567" not in z["wiadomosc"] and "450 000 zł" in z["wiadomosc"]
    assert z["czynnosc"] and z["wartosc"] == 450000.0 and z["kalkulacja"]      # decyzja bez kontaktu


def test_email_do_kancelarii_nie_omija_odsloniecia(platny):
    _zgloszenie(platny, wiadomosc="mail: zenek@prywatny.test, tel 601234567")
    do_kancelarii = next(tresc for do, _, tresc in platny.wyslane if do == ["anna@kancelaria-testowa.test"])
    for dane in ("600 700 800", "zenobiusz@klient.test", "zenek@prywatny.test", "601234567"):
        assert dane not in do_kancelarii
    assert "odsłoń w aplikacji" in do_kancelarii
    do_klienta = next(tresc for do, _, tresc in platny.wyslane if do == ["zenobiusz@klient.test"])
    assert "600 700 800" in do_klienta                                       # klient widzi swoje dane


def test_bez_odsloniecia_nie_ma_statusu_kontaktu_ani_terminu(platny):
    ident = _zgloszenie(platny)
    assert platny.put(f"/api/zapytania/{ident}", json={"status": "kontakt"}).status_code == 409
    odp = platny.put(f"/api/zapytania/{ident}", json={"status": "umowiona", "data": "2026-12-01", "godzina": "10:00"})
    assert odp.status_code == 409                                            # kalendarz wydalby telefon
    assert platny.put(f"/api/zapytania/{ident}", json={"status": "odrzucona"}).status_code == 200


# --- odsloniecie ------------------------------------------------------------------

def test_odsloniecie_z_puli_planu_bez_kredytow(platny):
    ident = _zgloszenie(platny)
    z = platny.post(f"/api/zapytania/{ident}/odslon").json()
    assert z["zakryty"] is False and z["klient"]["telefon"] == "600 700 800"
    assert z["odsloniecie"]["tryb"] == "pula" and z["odsloniecie"]["kredyty"] == 0
    portfel = t.wczytaj_portfel(KANCELARIA)
    assert t.licznik_miesiaca(portfel, "kontakt_klienta") == 1 and t.saldo(portfel) == t.PLANY["start"]["pula"]
    # Drugie odsloniecie tego samego zapytania - nic nie kosztuje i nic nie liczy.
    platny.post(f"/api/zapytania/{ident}/odslon")
    assert t.licznik_miesiaca(t.wczytaj_portfel(KANCELARIA), "kontakt_klienta") == 1


def test_po_puli_odsloniecie_za_kredyty(platny):
    _wyczerp_pule()
    ident = _zgloszenie(platny)
    z = platny.post(f"/api/zapytania/{ident}/odslon").json()
    cena = t.AKCJE["kontakt_klienta"].kredyty()
    assert z["odsloniecie"] == {**z["odsloniecie"], "tryb": "platne", "kredyty": cena}
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == t.PLANY["start"]["pula"] - cena


def test_brak_kredytow_402_i_kontakt_dalej_ukryty(platny):
    _wyczerp_pule()
    t.zmien_portfel(KANCELARIA, lambda p: p.update(pula=1.0))
    ident = _zgloszenie(platny)
    odp = platny.post(f"/api/zapytania/{ident}/odslon")
    assert odp.status_code == 402
    assert _lista(platny)[ident]["zakryty"] is True


def test_ten_sam_klient_drugi_raz_bez_oplaty(platny):
    _wyczerp_pule()
    pierwsze = _zgloszenie(platny)
    platny.post(f"/api/zapytania/{pierwsze}/odslon")
    saldo = t.saldo(t.wczytaj_portfel(KANCELARIA))
    drugie = _zgloszenie(platny, czynnosc="darowizna", telefon="+48 600-700-800", email="")
    z = platny.post(f"/api/zapytania/{drugie}/odslon").json()
    assert z["odsloniecie"]["tryb"] == "duplikat"
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == saldo


def test_cena_nie_zalezy_od_czynnosci_ani_wartosci(platny):
    """Neutralnosc (zakaz reklamy): oplata uslugowa, nie prowizja od sprawy."""
    _wyczerp_pule()
    ceny = []
    for wartosc, email in ((50_000, "a@k.test"), (5_000_000, "b@k.test")):
        ident = _zgloszenie(platny, wartosc=wartosc, telefon="", email=email, parametry=None)
        ceny.append(platny.post(f"/api/zapytania/{ident}/odslon").json()["odsloniecie"]["kredyty"])
    assert ceny[0] == ceny[1] > 0


def test_inna_kancelaria_nie_odslania_cudzego(platny, monkeypatch):
    ident = _zgloszenie(platny)
    import magazyn
    znacznik = magazyn.kancelaria_var.set("inna-kancelaria")
    try:
        assert platny.post(f"/api/zapytania/{ident}/odslon").status_code == 404
    finally:
        magazyn.kancelaria_var.reset(znacznik)


def test_bez_tokenomii_wszystko_jak_dawniej(klient):  # noqa: F811
    ident = _zgloszenie(klient)
    z = _lista(klient)[ident]
    assert z["zakryty"] is False and z["klient"]["telefon"] == "600 700 800"


# --- reklamacja ---------------------------------------------------------------------

def test_reklamacja_zwraca_kredyty_raz(platny):
    _wyczerp_pule()
    ident = _zgloszenie(platny)
    platny.post(f"/api/zapytania/{ident}/odslon")
    przed = t.saldo(t.wczytaj_portfel(KANCELARIA))
    odp = platny.post(f"/api/zapytania/{ident}/reklamacja", json={"powod": "falszywy_kontakt"})
    assert odp.status_code == 200 and odp.json()["status"] == "zamknieta"
    assert t.saldo(t.wczytaj_portfel(KANCELARIA)) == przed + t.AKCJE["kontakt_klienta"].kredyty()
    assert platny.post(f"/api/zapytania/{ident}/reklamacja", json={"powod": "spam"}).status_code == 409


def test_reklamacja_z_puli_oddaje_miejsce_w_puli(platny):
    ident = _zgloszenie(platny)
    platny.post(f"/api/zapytania/{ident}/odslon")
    platny.post(f"/api/zapytania/{ident}/reklamacja", json={"powod": "spam"})
    assert t.licznik_miesiaca(t.wczytaj_portfel(KANCELARIA), "kontakt_klienta") == 0


def test_reklamacje_maja_limit_i_termin(platny, monkeypatch):
    monkeypatch.setattr(t, "REKLAMACJE_W_MIESIACU", 1)
    a, b = _zgloszenie(platny, email="a@k.test", telefon=""), _zgloszenie(platny, email="b@k.test", telefon="")
    for ident in (a, b):
        platny.post(f"/api/zapytania/{ident}/odslon")
    assert platny.post(f"/api/zapytania/{a}/reklamacja", json={"powod": "spam"}).status_code == 200
    assert platny.post(f"/api/zapytania/{b}/reklamacja", json={"powod": "spam"}).status_code == 429
    assert platny.post(f"/api/zapytania/{b}/reklamacja", json={"powod": "bo tak"}).status_code == 400
    # Po 7 dniach od odsloniecia - za pozno.
    stare = (datetime.now() - timedelta(days=8)).isoformat(timespec="seconds")
    wizyty._zmien(lambda d: [z["odsloniecie"].update(czas=stare) for z in d["zgloszenia"] if z["id"] == b])
    assert platny.post(f"/api/zapytania/{b}/reklamacja", json={"powod": "spam"}).status_code == 409


def test_nieodsloniete_nie_da_sie_reklamowac(platny):
    ident = _zgloszenie(platny)
    assert platny.post(f"/api/zapytania/{ident}/reklamacja", json={"powod": "spam"}).status_code == 404


# --- klient nie czeka w nieskonczonosc -----------------------------------------------

def test_po_sla_klient_dostaje_publiczny_kontakt_kancelarii(platny):
    ident = _zgloszenie(platny)
    stare = (datetime.now() - timedelta(hours=wizyty.SLA_GODZIN + 1)).isoformat(timespec="seconds")
    wizyty._zmien(lambda d: [z.update(utworzono=stare) for z in d["zgloszenia"] if z["id"] == ident])
    platny.wyslane.clear()
    platny.get("/api/zapytania")
    platny.get("/api/zapytania")                                             # raz, nie przy kazdym odczycie
    do_klienta = [tresc for do, temat, tresc in platny.wyslane if do == ["zenobiusz@klient.test"]]
    assert len(do_klienta) == 1 and "81 000 00 00" in do_klienta[0]


def test_odsloniete_nie_dostaje_przypomnienia(platny):
    ident = _zgloszenie(platny)
    platny.post(f"/api/zapytania/{ident}/odslon")
    stare = (datetime.now() - timedelta(hours=wizyty.SLA_GODZIN + 1)).isoformat(timespec="seconds")
    wizyty._zmien(lambda d: [z.update(utworzono=stare) for z in d["zgloszenia"] if z["id"] == ident])
    platny.wyslane.clear()
    assert wizyty.przypomnij_klientom() == 0 and platny.wyslane == []


# --- maskowanie tekstu -------------------------------------------------------------

@pytest.mark.parametrize("tekst,ukryte,zostaje", [
    ("dzwon 601 234 567", "601 234 567", "dzwon"),
    ("+48 (22) 123-45-67 po 16", "123-45-67", "po 16"),
    ("tel601234567", "601234567", "tel"),
    ("pisz: jan.k@wp.pl", "jan.k@wp.pl", "pisz"),
    ("cena 1 250 000 zł", None, "1 250 000 zł"),
    ("termin 12.03.2026, 54 m2", None, "12.03.2026"),
])
def test_maskowanie_kontaktu_w_wiadomosci(tekst, ukryte, zostaje):
    wynik = wizyty.maskuj_tekst(tekst)
    assert zostaje in wynik
    if ukryte:
        assert ukryte not in wynik and wizyty.UKRYTE in wynik
    else:
        assert wynik == tekst
