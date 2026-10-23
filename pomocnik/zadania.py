"""Co pomocnik potrafi wykonac dla notarai.

Kazdy wykonawca dostaje zlecenie (slownik z serwera) i zwraca raport (slownik).
Nic tu nie wie o HTTP ani o kolejce - to robota klient.py.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import krz_portal
from pomocnik import cdp, klikamy as silnik_klikania, krz_cdp

log = logging.getLogger("notarai.pomocnik.zadania")


def katalog_zrzutow(sprawa: str) -> Path:
    """Gdzie ladują zrzuty ze sprawdzen.

    Zostaja na komputerze notariusza. To dowod starannosci, wiec musi byc
    dostepny od razu - przesylanie ich do sprawy w chmurze dolozymy osobno,
    a do tego czasu lepiej, zeby lezaly u niego niz nigdzie.
    """
    baza = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "notarai" / "zrzuty"
    katalog = baza / (sprawa or "bez-sprawy")
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog


def krz(zlecenie: dict, notarai=None, polacz=cdp.polacz,
        portal_z=krz_cdp.StronaKRZ) -> dict:
    """Sprawdzenie w Krajowym Rejestrze Zadluzonych dla kazdej osoby ze zlecenia.

    Blad przy jednej osobie nie przerywa pozostalych: notariusz woli dostac
    siedem wynikow z osmiu i wyraznie zaznaczony jeden brak, niz nic.
    """
    osoby = (zlecenie.get("tresc") or {}).get("osoby") or []
    sprawa = zlecenie.get("sprawa", "")
    if not osoby:
        return {"sprawdzenia": [], "bledy": ["Zlecenie nie wskazuje zadnej osoby."]}

    katalog = katalog_zrzutow(sprawa)
    sprawdzenia: list[dict] = []
    bledy: list[str] = []

    polaczenie, strona = polacz()
    try:
        portal = portal_z(strona)
        for osoba in osoby:
            etykieta = osoba.get("etykieta", "")
            try:
                wynik = krz_portal.przebieg(
                    portal, osoba.get("pesel", ""), etykieta,
                    zrzut_do=lambda nazwa: katalog / nazwa,
                )
            except Exception as blad:  # noqa: BLE001 - bez numeru w komunikacie
                log.error("krz: %s", type(blad).__name__)
                bledy.append(f"{etykieta or 'jedna ze stron'}: "
                             f"nie dokonczylem sprawdzenia ({type(blad).__name__})")
                continue
            sprawdzenia.append({
                "rejestr": "KRZ",
                "pesel": osoba.get("pesel", ""),
                "status": wynik["status"],
                "szczegoly": wynik["szczegoly"],
                "etykieta": etykieta,
                "zrodlo": krz_portal.ADRES,
            })
    finally:
        polaczenie.zamknij()

    log.info("krz: osob=%d sprawdzen=%d bledow=%d", len(osoby), len(sprawdzenia), len(bledy))
    return {"sprawdzenia": sprawdzenia, "bledy": bledy, "zrzuty_w": str(katalog)}


def klikamy(zlecenie: dict, notarai=None, polacz=cdp.polacz) -> dict:
    """Prowadzenie przegladarki wedlug polecenia notariusza.

    Petla jest tutaj, a model na serwerze: po kazdym kroku pokazujemy notarai,
    co widac na stronie, i dostajemy jedna czynnosc do wykonania. Dzieki temu
    komputer notariusza nie potrzebuje zadnego dostepu do modelu.

    Zabezpieczenia pilnuje silnik (pomocnik/klikamy.py), nie polecenie dla
    modelu: w przycisk, ktory wysyla albo podpisuje, nie da sie kliknac, a poza
    dozwolone adresy agent nie wyjdzie.
    """
    tresc = zlecenie.get("tresc") or {}
    cel = tresc.get("cel", "")
    if not cel:
        return {"bledy": ["Zlecenie nie mowi, co zrobic."]}
    if notarai is None:
        return {"bledy": ["Pomocnik nie ma polaczenia z notarai, wiec nie ma kogo "
                          "zapytac o kolejny krok."]}

    def model(cel, stan, kroki):
        return notarai.krok_klikania(zlecenie.get("id", ""), cel, stan,
                                     [vars(k) for k in kroki])

    polaczenie, strona = polacz()
    try:
        przebieg = silnik_klikania.prowadz(
            cel, strona, model,
            dozwolone_hosty=tuple(tresc.get("dozwolone_hosty") or ()),
        )
    finally:
        polaczenie.zamknij()

    log.info("klikamy: krokow=%d pytanie=%s", len(przebieg.kroki),
             bool(przebieg.pytanie))
    return {
        "kroki": [vars(k) for k in przebieg.kroki],
        "podsumowanie": przebieg.podsumowanie,
        "pytanie": przebieg.pytanie,
        "bledy": [przebieg.zatrzymano] if przebieg.zatrzymano else [],
    }


WYKONAWCY = {"krz": krz, "klikamy": klikamy}
