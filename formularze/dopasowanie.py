"""Dobieranie wartosci pol formularza z tresci aktu.

Brakujace ogniwo miedzy aktem a systemem urzedowym. Silnik formularzy potrafi
wpisac wartosci do pol, ale oczekuje gotowego slownika. Pola w akcie nazywaja
sie jednak po swojemu ("??5: ..., PESEL __ , zamieszkaly"), wiec ktos musi
zdecydowac, co trafia do rubryki "Numer PESEL" w rejestrze.

Kolejnosc zrodel, od najpewniejszego:
  1. pole sprawy o nazwie dokladnie takiej, jak w mapowaniu,
  2. tresc aktu odczytana przez model, z cytatem uzasadniajacym,
  3. brak - i tak tez to nazywamy, zamiast zgadywac.

Kazda wartosc przechodzi przez walidacje (sumy kontrolne PESEL, NIP, numeru
ksiegi wieczystej). Bledna suma nie kasuje wartosci, tylko ja oznacza:
decyzje podejmuje notariusz, ale musi ja zobaczyc.

Zero danych osobowych w logach: zapisujemy liczby, nie wartosci.
"""
import logging

import walidacja

log = logging.getLogger("pieczapp.formularze.dopasowanie")


def dopasuj(mapowanie, tekst_aktu: str = "", pola_sprawy: dict | None = None,
            model=None) -> dict:
    """Zwraca {"dane": {zrodlo: wartosc}, "wpisy": [...]}.

    `model` to funkcja (tekst, pola) -> lista wpisow; wstrzykiwana, zeby
    dopasowanie dalo sie testowac bez sieci i zeby ten modul nie zalezal
    od Bedrock.
    """
    pola_sprawy = pola_sprawy or {}
    wpisy: list[dict] = []
    do_modelu = []

    for pole in mapowanie.pola:
        wartosc = pola_sprawy.get(pole.zrodlo)
        if wartosc not in (None, ""):
            wpisy.append(_wpis(pole, str(wartosc), "pole sprawy", "wysoka"))
        else:
            do_modelu.append(pole)

    if do_modelu and tekst_aktu.strip() and model is not None:
        opisy = [{"nazwa": p.nazwa, "opis": p.opis} for p in do_modelu]
        odpowiedzi = {w["pole"]: w for w in model(tekst_aktu, opisy)}
        for pole in do_modelu:
            w = odpowiedzi.get(pole.nazwa, {})
            wpisy.append(_wpis(
                pole, w.get("wartosc"), "tresc aktu",
                w.get("pewnosc", "niska"), w.get("cytat", ""), w.get("uwaga", ""),
            ))
    else:
        for pole in do_modelu:
            wpisy.append(_wpis(pole, None, "brak", "niska"))

    # Kolejnosc jak w mapowaniu, zeby zgadzala sie z formularzem na ekranie.
    porzadek = {p.nazwa: i for i, p in enumerate(mapowanie.pola)}
    wpisy.sort(key=lambda w: porzadek.get(w["pole"], 0))

    dane = {w["zrodlo"]: w["wartosc"] for w in wpisy if w["wartosc"] not in (None, "")}
    log.info("dopasowanie %s: pol=%d z aktu=%d z pol sprawy=%d bez wartosci=%d ostrzezen=%d",
             mapowanie.system, len(wpisy),
             sum(1 for w in wpisy if w["skad"] == "tresc aktu" and w["wartosc"]),
             sum(1 for w in wpisy if w["skad"] == "pole sprawy"),
             sum(1 for w in wpisy if not w["wartosc"]),
             sum(1 for w in wpisy if w["ostrzezenie"]))
    return {"dane": dane, "wpisy": wpisy}


def _wpis(pole, wartosc, skad, pewnosc, cytat="", uwaga="") -> dict:
    wartosc = None if wartosc in (None, "") else str(wartosc).strip()
    ostrzezenie = ""
    if wartosc:
        poprawne, komentarz = walidacja.sprawdz_pole(pole.nazwa, wartosc)
        if poprawne is False:
            ostrzezenie = komentarz or "Wartosc nie przeszla sprawdzenia"
    elif pole.wymagane:
        ostrzezenie = "Pole wymagane, a w akcie nie ma danych"
    return {
        "pole": pole.nazwa,
        "zrodlo": pole.zrodlo,
        "wartosc": wartosc,
        "skad": skad if wartosc else "brak",
        "pewnosc": pewnosc if wartosc else "niska",
        "cytat": cytat[:200],
        "uwaga": uwaga,
        "ostrzezenie": ostrzezenie,
        "wymagane": pole.wymagane,
    }
