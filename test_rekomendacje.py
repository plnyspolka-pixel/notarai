"""Neutralna kolejnosc kancelarii i sprawiedliwy przydzial (rekomendacje.py).
Dane fikcyjne."""
import inspect
import random
from collections import Counter
from datetime import date, datetime, timedelta

import rekomendacje as r

KANCELARIE = [{"id": i} for i in range(1, 9)]


def test_ta_sama_kolejnosc_dla_wszystkich_danego_dnia():
    dzien = date(2026, 11, 8)
    a = r.kolejnosc(KANCELARIE, "lublin", dzien)
    b = r.kolejnosc(list(reversed(KANCELARIE)), "lublin", dzien)
    assert [k["id"] for k in a] == [k["id"] for k in b]


def test_rotacja_daje_kazdemu_rowne_szanse_na_pierwsze_miejsce():
    pierwsze = Counter()
    sredni = Counter()
    start = date(2026, 1, 1)
    dni = 4000
    for n in range(dni):
        lista = r.kolejnosc(KANCELARIE, "lublin", start + timedelta(days=n))
        pierwsze[lista[0]["id"]] += 1
        for miejsce, k in enumerate(lista):
            sredni[k["id"]] += miejsce
    oczekiwane = dni / len(KANCELARIE)
    assert all(abs(v - oczekiwane) < 0.2 * oczekiwane for v in pierwsze.values())
    srodek = (len(KANCELARIE) - 1) / 2
    assert all(abs(v / dni - srodek) < 0.25 for v in sredni.values())


def test_nazwa_alfabetycznie_pierwsza_nie_ma_przewagi():
    lista = [{"id": "Anna Abacka"}, {"id": "Zenon Zybert"}]
    pierwsze = Counter(r.kolejnosc(lista, "x", date(2026, 1, 1) + timedelta(days=n))[0]["id"] for n in range(1000))
    assert 400 < pierwsze["Anna Abacka"] < 600


def test_odleglosc_w_pasmach_i_brak_kontaktu_na_koniec():
    lista = [{"id": 1, "odleglosc_km": 9.0}, {"id": 2, "odleglosc_km": 0.3},
             {"id": 3, "odleglosc_km": 1.6}, {"id": 4, "odleglosc_km": 0.5, "brak_kontaktu": True}]
    wynik = [k["id"] for k in r.kolejnosc(lista, "mapa", date(2026, 11, 8))]
    assert set(wynik[:2]) == {2, 3}          # 0,3 i 1,6 km to to samo pasmo - decyduje rotacja
    assert wynik[2:] == [4, 1]               # w pasmie bez kontaktu na koniec, potem dalsze pasmo


def test_pola_platnosci_nie_wplywaja_na_kolejnosc():
    dzien = date(2026, 11, 8)
    bez = [{"id": i} for i in range(1, 6)]
    z = [{"id": i, "notarai": i == 5, "abonament": "premium" if i == 5 else None, "wazny": True} for i in range(1, 6)]
    assert [k["id"] for k in r.kolejnosc(bez, "x", dzien)] == [k["id"] for k in r.kolejnosc(z, "x", dzien)]
    # i nie ma ich w kodzie modulu poza dokumentacja
    kod = inspect.getsource(r.kolejnosc) + inspect.getsource(r.przydziel)
    assert "platnosci" not in kod and "abonament" not in kod and "notarai" not in kod.replace('"notarai|', "")


def test_przydzial_po_rowno():
    teraz = datetime(2026, 11, 8, 12)
    historia = []
    for n in range(300):
        k = r.przydziel([1, 2, 3], historia, "lublin", teraz + timedelta(minutes=n))
        historia.append({"baza_id": k, "utworzono": (teraz + timedelta(minutes=n)).isoformat(),
                         "przydzial": {"sposob": "kolejka"}})
    assert Counter(z["baza_id"] for z in historia) == {1: 100, 2: 100, 3: 100}


def test_przydzial_nie_liczy_wyborow_klienta_ani_starych():
    teraz = datetime(2026, 11, 8, 12)
    stare = (teraz - timedelta(days=r.OKNO_DNI + 1)).isoformat()
    historia = ([{"baza_id": 1, "utworzono": teraz.isoformat()}] * 5                       # klient sam wybral
                + [{"baza_id": 2, "utworzono": stare, "przydzial": {"sposob": "kolejka"}}] * 5)  # poza oknem
    wyniki = Counter(r.przydziel([1, 2], historia, "x", teraz + timedelta(days=d)) for d in range(200))
    assert wyniki[1] > 50 and wyniki[2] > 50


def test_przydzial_bez_kandydatow():
    assert r.przydziel([], [], "x") is None


def test_losowa_historia_wyrownuje_sie():
    rng = random.Random(7)
    teraz = datetime(2026, 11, 8)
    historia = [{"baza_id": rng.choice([1, 2]), "utworzono": teraz.isoformat(), "przydzial": {"sposob": "kolejka"}}
                for _ in range(10)] + [{"baza_id": 1, "utworzono": teraz.isoformat(), "przydzial": {"sposob": "kolejka"}}] * 4
    przewaga = Counter(z["baza_id"] for z in historia)
    nastepne = [r.przydziel([1, 2, 3], historia, "x", teraz)]
    assert nastepne[0] == min([1, 2, 3], key=lambda k: przewaga.get(k, 0))
