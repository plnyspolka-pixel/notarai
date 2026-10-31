"""Kalendarz kancelarii - terminy czynnosci i spotkan.

Wpisy w kancelarie/{kancelaria}/kalendarz.json (S3) albo dane/kalendarz.json
(tryb lokalny). Wpis moze wskazywac sprawe - wtedy interfejs pokazuje przy nim
strony czynnosci z tej sprawy i ich telefony.
"""
import re
import uuid
from datetime import date, datetime

import magazyn

PLIK = "kalendarz"


def _sprawdz(dane: dict) -> dict:
    try:
        dzien = date.fromisoformat(str(dane.get("data", "")))
    except ValueError:
        raise ValueError("Podaj datę w postaci RRRR-MM-DD")
    godzina = str(dane.get("godzina") or "").strip()
    if godzina and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", godzina):
        raise ValueError("Podaj godzinę w postaci GG:MM")
    tytul = " ".join(str(dane.get("tytul") or "").split())[:200]
    sprawa = str(dane.get("sprawa") or "")
    if sprawa and not sprawa.isalnum():
        raise ValueError("Nieprawidłowy identyfikator sprawy")
    if not tytul and not sprawa:
        raise ValueError("Podaj tytuł albo wybierz sprawę")
    return {
        "data": dzien.isoformat(),
        "godzina": godzina,
        "tytul": tytul,
        "sprawa": sprawa,
        "uwagi": str(dane.get("uwagi") or "").strip()[:2000],
    }


def lista() -> list[dict]:
    wpisy = magazyn.wczytaj_plik_kancelarii(PLIK, [])
    return sorted(wpisy, key=lambda w: (w["data"], w["godzina"] or "99:99"))


def dodaj(dane: dict) -> dict:
    wpis = {"id": uuid.uuid4().hex[:12], **_sprawdz(dane),
            "utworzono": datetime.now().isoformat(timespec="seconds")}
    magazyn.zmien_plik_kancelarii(PLIK, lambda wpisy: wpisy.append(wpis), [])
    return wpis


def zmien(identyfikator: str, dane: dict) -> dict | None:
    nowe = _sprawdz(dane)

    def zmiana(wpisy):
        for wpis in wpisy:
            if wpis["id"] == identyfikator:
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
