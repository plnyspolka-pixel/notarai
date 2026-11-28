"""Co pomocnik potrafi wykonac dla notarai.

Kazdy wykonawca dostaje zlecenie (slownik z serwera) i zwraca raport (slownik).
Nic tu nie wie o HTTP ani o kolejce - to robota klient.py.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import krz_portal
from pomocnik import cdp, klikamy as silnik_klikania, krz_cdp, pulpit as silnik_pulpitu

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

    Zabezpieczenia pilnuje silnik (pomocnik/klikamy.py): podpisy i platnosci
    pozostaja zablokowane, a wyslanie wymaga jednorazowej zgody z telefonu.
    Poza dozwolone adresy agent nie wyjdzie.
    """
    tresc = zlecenie.get("tresc") or {}
    cel = tresc.get("cel", "")
    if not cel:
        return {"bledy": ["Zlecenie nie mowi, co zrobic."]}
    if notarai is None:
        return {"bledy": ["Pomocnik nie ma polaczenia z notarai, wiec nie ma kogo "
                          "zapytac o kolejny krok."]}

    model, zatwierdz = _model_i_zgoda(zlecenie, notarai)

    polaczenie, strona = polacz()
    try:
        przebieg = silnik_klikania.prowadz(
            cel, strona, model,
            dozwolone_hosty=tuple(tresc.get("dozwolone_hosty") or ()),
            zatwierdz_wysylke=zatwierdz,
        )
    finally:
        polaczenie.zamknij()

    log.info("klikamy: krokow=%d pytanie=%s", len(przebieg.kroki),
             bool(przebieg.pytanie))
    return _raport(przebieg)


def _model_i_zgoda(zlecenie: dict, notarai):
    """Model pyta notarai o kolejny krok; zgoda na wysylke idzie przez telefon."""
    tresc = zlecenie.get("tresc") or {}

    def model(cel, stan, kroki):
        return notarai.krok_klikania(zlecenie.get("id", ""), cel, stan,
                                     [vars(k) for k in kroki])

    zatwierdz = None
    if tresc.get("docelowy_komputer") and hasattr(notarai, "zgoda_na_wyslanie"):
        zatwierdz = lambda host, etykieta: notarai.zgoda_na_wyslanie(
            zlecenie.get("id", ""), host, etykieta)
    return model, zatwierdz


def _raport(przebieg) -> dict:
    return {
        "kroki": [vars(k) for k in przebieg.kroki],
        "podsumowanie": przebieg.podsumowanie,
        "pytanie": przebieg.pytanie,
        "bledy": [przebieg.zatrzymano] if przebieg.zatrzymano else [],
    }


def pulpit(zlecenie: dict, notarai=None, winapp=None, dozwolone=None) -> dict:
    """Klikamy w programie kancelaryjnym Windows (np. Rejent) przez winapp CLI.

    Ta sama petla i te same blokady co w przegladarce, plus blokady pulpitu
    z pomocnik/pulpit.py. Ktory program wolno prowadzic, decyduje lista na tym
    komputerze - zlecenie z serwera moze ja tylko wskazac, nie poszerzyc.
    """
    tresc = zlecenie.get("tresc") or {}
    cel = tresc.get("cel", "")
    if not cel:
        return {"bledy": ["Zlecenie nie mowi, co zrobic."]}
    if notarai is None:
        return {"bledy": ["Pomocnik nie ma polaczenia z notarai, wiec nie ma kogo "
                          "zapytac o kolejny krok."]}
    try:
        okno = silnik_pulpitu.OknoProgramu.polacz(
            tresc.get("program", ""), winapp=winapp, dozwolone=dozwolone)
    except (silnik_pulpitu.OdmowaPulpitu, silnik_pulpitu.BladWinapp) as blad:
        log.warning("pulpit: nie polaczono (%s)", type(blad).__name__)
        return {"bledy": [str(blad)]}

    model, zatwierdz = _model_i_zgoda(zlecenie, notarai)
    try:
        przebieg = silnik_klikania.prowadz(cel, okno, model, dozwolone_hosty=(),
                                           zatwierdz_wysylke=zatwierdz)
    except silnik_pulpitu.BladWinapp as blad:
        # Odczyt okna padl w trakcie (np. program zamknieto) - bez tresci okna.
        log.warning("pulpit: przerwano (%s)", blad.kod)
        return {"bledy": [str(blad)]}
    finally:
        okno.zakoncz()

    log.info("pulpit: krokow=%d pytanie=%s", len(przebieg.kroki),
             bool(przebieg.pytanie))
    return _raport(przebieg)


def karty(zlecenie: dict, notarai=None) -> dict:
    """Otwieranie adresu i nowych kart w wydzielonej przegladarce Windows."""
    from pomocnik import przegladarka
    import time

    tresc = zlecenie.get("tresc") or {}
    adres = tresc.get("adres", "")
    try:
        if not adres.startswith("https://"):
            return {"bledy": ["Dozwolone sa tylko strony HTTPS."]}
        try:
            cdp.karty()
        except cdp.BladPrzegladarki:
            przegladarka.uruchom()
            time.sleep(2)
        if tresc.get("nowa_karta"):
            cdp.nowa_karta(adres)
            opis = "Otworzono nowa karte."
        else:
            polaczenie, strona = cdp.polacz()
            try:
                strona.otworz(adres)
            finally:
                polaczenie.zamknij()
            opis = "Przeszedlem na wskazany adres."
        return {"kroki": [{"nr": 1, "akcja": "otworz", "cel": adres.split("/")[2]}],
                "podsumowanie": opis, "bledy": []}
    except (OSError, RuntimeError, ValueError) as blad:
        log.warning("karty: %s", type(blad).__name__)
        return {"bledy": ["Nie udalo sie otworzyc strony na tym komputerze."]}


WYKONAWCY = {"krz": krz, "klikamy": klikamy, "karty": karty, "pulpit": pulpit}
