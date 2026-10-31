"""Kalendarz kancelarii - terminy czynnosci i spotkan.

Wpisy w kancelarie/{kancelaria}/kalendarz.json (S3) albo dane/kalendarz.json
(tryb lokalny). Wpis moze wskazywac sprawe - wtedy interfejs pokazuje przy nim
strony czynnosci z tej sprawy i ich telefony.

Rezerwacja zajmuje godziny od `godzina` do `koniec` (polgodzinne okienka
w oknie dnia). Dwie rezerwacje tego samego dnia nie moga na siebie nachodzic -
sprawdzamy to przy zapisie, wiec nie zarezerwuja tej samej godziny dwie osoby
z kancelarii naraz.
"""
import re
import uuid
from datetime import date, datetime

import magazyn

PLIK = "kalendarz"
RODZAJE = ("sprzedaż", "darowizna", "dział spadku", "poświadczenie podpisów",
           "testament", "pełnomocnictwo notarialne", "inne")
_GODZINA = r"([01]\d|2[0-3]):[0-5]\d"


def _jednolinijkowy(tekst, limit: int) -> str:
    return " ".join(str(tekst or "").split())[:limit]


def _sprawdz(dane: dict) -> dict:
    try:
        dzien = date.fromisoformat(str(dane.get("data", "")))
    except ValueError:
        raise ValueError("Podaj datę w postaci RRRR-MM-DD")
    godzina = str(dane.get("godzina") or "").strip()
    koniec = str(dane.get("koniec") or "").strip()
    if godzina and not re.fullmatch(_GODZINA, godzina):
        raise ValueError("Podaj godzinę w postaci GG:MM")
    if koniec and (not godzina or not re.fullmatch(_GODZINA, koniec) or koniec <= godzina):
        raise ValueError("Godzina zakończenia musi być późniejsza niż rozpoczęcia")
    tytul = _jednolinijkowy(dane.get("tytul"), 200)
    sprawa = str(dane.get("sprawa") or "")
    if sprawa and not sprawa.isalnum():
        raise ValueError("Nieprawidłowy identyfikator sprawy")
    rodzaj = str(dane.get("rodzaj") or "")
    if rodzaj and rodzaj not in RODZAJE:
        raise ValueError("Nieznany rodzaj czynności")
    rodzaj_inny = _jednolinijkowy(dane.get("rodzaj_inny"), 200) if rodzaj == "inne" else ""
    if rodzaj == "inne" and not rodzaj_inny:
        raise ValueError("Wpisz, jaka to czynność")
    uczestnicy = _jednolinijkowy(dane.get("uczestnicy"), 500)
    telefon = _jednolinijkowy(dane.get("telefon"), 100)
    if not (tytul or sprawa or rodzaj or uczestnicy):
        raise ValueError("Podaj nazwiska, rodzaj czynności albo wybierz sprawę")
    return {
        "data": dzien.isoformat(),
        "godzina": godzina,
        "koniec": koniec,
        "tytul": tytul,
        "rodzaj": rodzaj,
        "rodzaj_inny": rodzaj_inny,
        "uczestnicy": uczestnicy,
        "telefon": telefon,
        "sprawa": sprawa,
        "uwagi": str(dane.get("uwagi") or "").strip()[:2000],
    }


def _koniec(wpis: dict) -> str:
    """Termin z sama godzina rozpoczecia zajmuje jedno polgodzinne okienko."""
    if wpis.get("koniec"):
        return wpis["koniec"]
    godz, minuty = divmod(min(int(wpis["godzina"][:2]) * 60 + int(wpis["godzina"][3:]) + 30, 24 * 60 - 1), 60)
    return f"{godz:02d}:{minuty:02d}"


def _sprawdz_kolizje(wpisy: list[dict], nowy: dict, pomin: str = "") -> None:
    """Termin z godzina nie moze nachodzic na inny tego samego dnia."""
    if not nowy["godzina"]:
        return
    for wpis in wpisy:
        if (wpis["id"] != pomin and wpis["data"] == nowy["data"] and wpis.get("godzina")
                and wpis["godzina"] < _koniec(nowy) and nowy["godzina"] < _koniec(wpis)):
            raise ValueError(f"Godziny {wpis['godzina']}-{_koniec(wpis)} są już zajęte")


def lista() -> list[dict]:
    wpisy = magazyn.wczytaj_plik_kancelarii(PLIK, [])
    return sorted(wpisy, key=lambda w: (w["data"], w["godzina"] or "99:99"))


def dodaj(dane: dict) -> dict:
    wpis = {"id": uuid.uuid4().hex[:12], **_sprawdz(dane),
            "utworzono": datetime.now().isoformat(timespec="seconds")}

    def zmiana(wpisy):
        _sprawdz_kolizje(wpisy, wpis)
        wpisy.append(wpis)
    magazyn.zmien_plik_kancelarii(PLIK, zmiana, [])
    return wpis


def zmien(identyfikator: str, dane: dict) -> dict | None:
    nowe = _sprawdz(dane)

    def zmiana(wpisy):
        for wpis in wpisy:
            if wpis["id"] == identyfikator:
                _sprawdz_kolizje(wpisy, nowe, pomin=identyfikator)
                wpis.update(nowe)
                return wpis
        return None
    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, [])


def usun(identyfikator: str) -> bool:
    def zmiana(wpisy):
        przed = len(wpisy)
        wpisy[:] = [w for w in wpisy if w["id"] != identyfikator]
        return len(wpisy) != przed
    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, [])


def usun_sprawe(id_sprawy: str) -> None:
    """Usunieta sprawa nie zostawia po sobie wskazania w kalendarzu."""
    def zmiana(wpisy):
        for wpis in wpisy:
            if wpis.get("sprawa") == id_sprawy:
                wpis["sprawa"] = ""
    magazyn.zmien_plik_kancelarii(PLIK, zmiana, [])
