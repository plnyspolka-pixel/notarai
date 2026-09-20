"""Walidacja twarda - to co da sie sprawdzic algorytmem, sprawdzamy algorytmem.

Model moze sie pomylic przy odczycie skanu. Suma kontrolna nie.
"""
import re
from datetime import date

WAGI_PESEL = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
WAGI_NIP = (6, 5, 7, 2, 3, 4, 5, 6, 7)

_ZNAKI_KW = "0123456789XABCDEFGHIJKLMNOPRSTUWYZ"


def pesel(wartosc: str) -> tuple[bool, str]:
    cyfry = re.sub(r"\D", "", wartosc or "")
    if len(cyfry) != 11:
        return False, "PESEL musi miec 11 cyfr"

    suma = sum(int(c) * w for c, w in zip(cyfry[:10], WAGI_PESEL))
    kontrolna = (10 - suma % 10) % 10
    if kontrolna != int(cyfry[10]):
        return False, "Bledna suma kontrolna PESEL"

    urodzenie = _data_z_peselu(cyfry)
    if urodzenie is None:
        return False, "PESEL zawiera niepoprawna date urodzenia"
    if urodzenie > date.today():
        return False, "Data urodzenia z PESEL jest w przyszlosci"

    plec = "M" if int(cyfry[9]) % 2 else "K"
    return True, f"ur. {urodzenie.isoformat()}, plec {plec}"


def _data_z_peselu(cyfry: str) -> date | None:
    rok, miesiac, dzien = int(cyfry[0:2]), int(cyfry[2:4]), int(cyfry[4:6])
    stulecia = {0: 1900, 1: 2000, 2: 2100, 3: 2200, 4: 1800}
    baza = stulecia.get(miesiac // 20)
    if baza is None:
        return None
    try:
        return date(baza + rok, miesiac % 20, dzien)
    except ValueError:
        return None


def nip(wartosc: str) -> tuple[bool, str]:
    cyfry = re.sub(r"\D", "", wartosc or "")
    if len(cyfry) != 10:
        return False, "NIP musi miec 10 cyfr"
    suma = sum(int(c) * w for c, w in zip(cyfry[:9], WAGI_NIP))
    if suma % 11 == 10 or suma % 11 != int(cyfry[9]):
        return False, "Bledna suma kontrolna NIP"
    return True, "NIP poprawny"


def ksiega_wieczysta(wartosc: str) -> tuple[bool, str]:
    """Format: XXXX/00000000/C - kod wydzialu, numer, cyfra kontrolna."""
    tekst = (wartosc or "").upper().replace(" ", "")
    dopasowanie = re.fullmatch(r"([A-Z0-9]{4})/(\d{8})/(\d)", tekst)
    if not dopasowanie:
        return False, "Format numeru KW: XXXX/00000000/C"

    kod, numer, kontrolna = dopasowanie.groups()
    suma = 0
    for i, znak in enumerate(kod + numer):
        if znak not in _ZNAKI_KW:
            return False, f"Niedozwolony znak w numerze KW: {znak}"
        waga = (1, 3, 7)[i % 3]
        suma += _ZNAKI_KW.index(znak) * waga
    if suma % 10 != int(kontrolna):
        return False, "Bledna cyfra kontrolna numeru KW"
    return True, "Numer KW poprawny"


def kwota(wartosc: str) -> tuple[bool, str]:
    tekst = re.sub(r"[\s\u00a0]", "", wartosc or "").replace(",", ".")
    tekst = re.sub(r"(zl|PLN)$", "", tekst, flags=re.I)
    try:
        liczba = float(tekst)
    except ValueError:
        return False, "Nie udalo sie odczytac kwoty"
    if liczba < 0:
        return False, "Kwota ujemna"
    return True, f"{liczba:.2f} zl"


# Klucze sa wzorcami wyrazen regularnych, bo pola nazywaja sie roznymi
# formami tego samego slowa: "ksiega wieczysta", "numer ksiegi wieczystej",
# "wpis w ksiedze". Dopasowanie po samym mianowniku przepuszczalo te pola
# bez zadnego sprawdzenia.
REGULY = {
    "pesel": pesel,
    "nip": nip,
    "ksie[gd][a-ząćęłńóśźż]*": ksiega_wieczysta,
    "kwot[a-ząćęłńóśźż]*": kwota,
    "cen[aeęy][a-ząćęłńóśźż]*": kwota,
    "wartosc[a-ząćęłńóśźż]*": kwota,
    "wartość[a-ząćęłńóśźż]*": kwota,
    "kw": ksiega_wieczysta,
}


def sprawdz_pole(nazwa: str, wartosc: str) -> tuple[bool | None, str]:
    """Dobiera walidator po nazwie pola. None = brak reguly."""
    if not wartosc:
        return None, ""
    klucz = nazwa.lower()
    if klucz.startswith("??"):
        # Pole nazwane z kontekstu ("??5: nr __, wazny do dnia __ r.), PESEL __").
        # Regule dobieramy tylko po slowach tuz przed luka, inaczej "PESEL"
        # z dalszej czesci zdania zwalidowalby date waznosci dowodu.
        przed_luka = re.search(r"((?:\S+\s+){0,2})__", klucz)
        klucz = przed_luka.group(1) if przed_luka else ""
    for wzorzec, funkcja in REGULY.items():
        if re.search(rf"(?<![a-ząćęłńóśźż0-9]){wzorzec}(?![a-ząćęłńóśźż0-9])", klucz):
            return funkcja(wartosc)
    return None, ""
