"""Sprawdzenia w rejestrach publicznych - model wyniku i slad audytowy.

Zgodnie ze SPEC A3: jednolity wynik dla kazdego rejestru, PESEL zapisywany
zamaskowany, wpis w dane/sprawy/<id>/sprawdzenia.json jako dowod starannosci.
Sam kontakt z rejestrem odbywa sie w przegladarce notariusza (formularze/),
ten modul niczego nie odpytuje.
"""
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import config

REJESTRY = ("KRZ", "ZASTRZEZENIA_PESEL", "SANKCJE", "PEP", "CRBR")
DECYZJE = ("", "falszywe_trafienie", "potwierdzone")
STATUSY = ("brak_wpisu", "wpis", "niedostepny", "blad")


def maskuj_pesel(pesel: str) -> str:
    """'12345678901' -> '1234*******'. Cokolwiek innego - w calosci gwiazdki."""
    cyfry = re.sub(r"\D", "", pesel or "")
    if len(cyfry) == 11:
        return cyfry[:4] + "*" * 7
    return "*" * max(len(cyfry), 1)


@dataclass
class WynikSprawdzenia:
    rejestr: str
    zapytanie: str            # PESEL JUZ zamaskowany - nigdy pelny
    status: str
    szczegoly: str = ""
    sprawdzono: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    zrodlo: str = ""
    kto: str = ""             # kto zatwierdzil sprawdzenie (na przyszlosc: konta)
    # Ktorej strony czynnosci dotyczy wpis - nazwa pola ze sprawy. PESEL
    # zapisujemy zamaskowany, a same cztery koncowe cyfry nie rozroznia stron,
    # gdy w akcie jest ich kilkanascie. Bez tego status "sprawdzony" moglby
    # sie pokazac przy niewlasciwej osobie.
    etykieta: str = ""
    # Listy sankcyjne i PEP: trafienia do decyzji notariusza (nazwa z listy,
    # zrodlo, wynik 0-100). Zadnych pelnych PESEL-i - pilnuje __post_init__.
    trafienia: list = field(default_factory=list)
    # Decyzja notariusza o wczesniejszym wpisie (indeks w `dotyczy`):
    # falszywe_trafienie albo potwierdzone. Pusta = zwykle sprawdzenie.
    decyzja: str = ""
    dotyczy: int | None = None

    def __post_init__(self):
        if self.rejestr not in REJESTRY:
            raise ValueError(f"Nieznany rejestr: {self.rejestr}")
        if self.status not in STATUSY:
            raise ValueError(f"Nieznany status: {self.status}")
        if self.decyzja not in DECYZJE:
            raise ValueError(f"Nieznana decyzja: {self.decyzja}")
        if re.search(r"\d{11}", self.zapytanie or "") or re.search(r"\d{11}", json.dumps(self.trafienia)):
            raise ValueError("Zapytanie zawiera pelny PESEL - zamaskuj przed zapisem")


def zapisz_sprawdzenie(identyfikator: str, wynik: WynikSprawdzenia) -> Path:
    plik = config.SPRAWY / identyfikator / "sprawdzenia.json"
    plik.parent.mkdir(parents=True, exist_ok=True)
    wpisy = json.loads(plik.read_text("utf-8")) if plik.exists() else []
    wpisy.append(asdict(wynik))
    plik.write_text(json.dumps(wpisy, ensure_ascii=False, indent=2), encoding="utf-8")
    return plik


def wczytaj_sprawdzenia(identyfikator: str) -> list[dict]:
    plik = config.SPRAWY / identyfikator / "sprawdzenia.json"
    return json.loads(plik.read_text("utf-8")) if plik.exists() else []
