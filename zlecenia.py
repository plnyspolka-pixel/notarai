"""Kolejka zlecen dla pomocnika notariusza.

Czynnosci, ktore musza sie wydarzyc w przegladarce na komputerze notariusza -
sprawdzenie w KRZ, wpisanie numeru do modulu KRN - nie moga sie wykonac na
serwerze, bo serwer zadnej przegladarki nie ma. Serwer sklada wiec zlecenie,
a pomocnik je odbiera, wykonuje u siebie i odsyla raport.

Dlaczego przez S3, a nie w pamieci procesu: aplikacja chodzi w dwoch kopiach.
Zlecenie zlozone przez jedna z nich musi byc widoczne dla pomocnika, ktory
odpytuje druga. Pamiec procesu by tego nie zapewnila.

Uklad kluczy, izolacja per kancelaria jak przy sprawach:
  kancelarie/{kancelaria}/zlecenia/{id}.json

Zlecenie zyje krotko: pomocnik odbiera je w kilka sekund, a nieodebrane
przeterminowuje sie, zeby po tygodniu nie wrocilo znikad i nie wpisalo czegos
w otwarty formularz.

Dane osobowe: zlecenie niesie numery PESEL, bo bez nich nie ma czego sprawdzic.
Nie trafiaja one do logow - logujemy identyfikator zlecenia, rodzaj i liczby.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import magazyn

log = logging.getLogger("pieczapp.zlecenia")

WAZNOSC_MINUT = int(os.getenv("PIECZAPP_ZLECENIE_MINUT", "30"))
RODZAJE = ("krz", "formularz")
STANY = ("czeka", "wykonane")


def dostepne() -> bool:
    """Kolejka zyje w S3, wiec istnieje tylko w trybie SaaS.

    W kancelarii pieczapp dziala na komputerze notariusza i sam ma przegladarke -
    nie ma komu ani po co skladac zlecen.
    """
    return magazyn.TRYB == "s3"


def _klucz(kancelaria: str, identyfikator: str) -> str:
    return f"{magazyn.PREFIKS}/{kancelaria}/zlecenia/{identyfikator}.json"


def _teraz() -> datetime:
    return datetime.now(timezone.utc)


def _przeterminowane(zlecenie: dict) -> bool:
    try:
        zlozono = datetime.fromisoformat(zlecenie["zlozono"])
    except (KeyError, ValueError):
        return True
    return _teraz() - zlozono > timedelta(minutes=WAZNOSC_MINUT)


def zloz(rodzaj: str, sprawa: str, tresc: dict) -> dict:
    """Sklada zlecenie i zwraca je. Nie czeka na pomocnika."""
    if rodzaj not in RODZAJE:
        raise ValueError(f"Nieznany rodzaj zlecenia: {rodzaj}")
    kancelaria = magazyn.kancelaria()
    zlecenie = {
        "id": uuid.uuid4().hex[:12],
        "rodzaj": rodzaj,
        "sprawa": sprawa,
        "stan": "czeka",
        "zlozono": _teraz().isoformat(timespec="seconds"),
        "tresc": tresc,
    }
    _zapisz(kancelaria, zlecenie)
    log.info("zlecenie %s: zlozone, rodzaj=%s sprawa=%s", zlecenie["id"], rodzaj, sprawa)
    return zlecenie


def _zapisz(kancelaria: str, zlecenie: dict) -> None:
    magazyn._klient_s3().put_object(
        Bucket=magazyn.BUCKET,
        Key=_klucz(kancelaria, zlecenie["id"]),
        Body=json.dumps(zlecenie, ensure_ascii=False).encode("utf-8"),
        **magazyn._szyfrowanie(),
    )


def _wczytaj(kancelaria: str, identyfikator: str) -> dict | None:
    try:
        odpowiedz = magazyn._klient_s3().get_object(
            Bucket=magazyn.BUCKET, Key=_klucz(kancelaria, identyfikator)
        )
    except Exception:  # noqa: BLE001 - brak zlecenia to zwykly przypadek
        return None
    return json.loads(odpowiedz["Body"].read().decode("utf-8"))


def czekajace() -> list[dict]:
    """Zlecenia do wykonania przez pomocnika tej kancelarii.

    Przeterminowane sa po cichu kasowane - pomocnik ma dostac tylko to, czego
    notariusz faktycznie teraz oczekuje.
    """
    kancelaria = magazyn.kancelaria()
    prefiks = f"{magazyn.PREFIKS}/{kancelaria}/zlecenia/"
    klient = magazyn._klient_s3()
    wynik = []
    strony = klient.get_paginator("list_objects_v2").paginate(
        Bucket=magazyn.BUCKET, Prefix=prefiks
    )
    for strona in strony:
        for obiekt in strona.get("Contents", []):
            identyfikator = obiekt["Key"][len(prefiks):].removesuffix(".json")
            zlecenie = _wczytaj(kancelaria, identyfikator)
            if not zlecenie:
                continue
            if _przeterminowane(zlecenie):
                usun(identyfikator)
                continue
            if zlecenie.get("stan") == "czeka":
                wynik.append(zlecenie)
    wynik.sort(key=lambda z: z.get("zlozono", ""))
    return wynik


def wynik(identyfikator: str) -> dict | None:
    """Raport pomocnika, gdy juz jest. None, gdy zlecenie jeszcze czeka."""
    zlecenie = _wczytaj(magazyn.kancelaria(), identyfikator)
    if not zlecenie:
        return None
    if _przeterminowane(zlecenie) and zlecenie.get("stan") == "czeka":
        usun(identyfikator)
        return None
    return zlecenie


def zapisz_wynik(identyfikator: str, raport: dict) -> dict:
    """Pomocnik odeslal raport. Zlecenie przestaje czekac."""
    kancelaria = magazyn.kancelaria()
    zlecenie = _wczytaj(kancelaria, identyfikator)
    if not zlecenie:
        raise KeyError("Nie ma takiego zlecenia")
    zlecenie["stan"] = "wykonane"
    zlecenie["wykonano"] = _teraz().isoformat(timespec="seconds")
    zlecenie["raport"] = raport
    # Tresc zlecenia niosla numery PESEL. Po wykonaniu nie jest juz potrzebna,
    # wiec jej nie przechowujemy - zostaje sam raport.
    zlecenie["tresc"] = {}
    _zapisz(kancelaria, zlecenie)
    log.info("zlecenie %s: wykonane", identyfikator)
    return zlecenie


# --- Obecnosc pomocnika ----------------------------------------------------
# Przycisk "Sprawdz w KRZ" ma byc czynny wtedy i tylko wtedy, gdy jest komu
# zlecenie wykonac. Pomocnik odbijajac sie po zlecenia zostawia znacznik czasu;
# gdy przestanie, przycisk gasnie sam i notariusz nie sklada zlecen w prozne.

ODDECH_MINUT = int(os.getenv("PIECZAPP_POMOCNIK_MINUT", "3"))


def _klucz_pomocnika(kancelaria: str) -> str:
    return f"{magazyn.PREFIKS}/{kancelaria}/pomocnik.json"


def odnotuj_pomocnika(wersja: str = "") -> None:
    magazyn._klient_s3().put_object(
        Bucket=magazyn.BUCKET,
        Key=_klucz_pomocnika(magazyn.kancelaria()),
        Body=json.dumps({"widziany": _teraz().isoformat(timespec="seconds"),
                         "wersja": wersja}).encode("utf-8"),
        **magazyn._szyfrowanie(),
    )


def pomocnik_aktywny() -> bool:
    try:
        odpowiedz = magazyn._klient_s3().get_object(
            Bucket=magazyn.BUCKET, Key=_klucz_pomocnika(magazyn.kancelaria())
        )
        widziany = json.loads(odpowiedz["Body"].read().decode("utf-8"))["widziany"]
        return _teraz() - datetime.fromisoformat(widziany) < timedelta(minutes=ODDECH_MINUT)
    except Exception:  # noqa: BLE001 - brak znacznika znaczy po prostu "nie ma pomocnika"
        return False


def usun(identyfikator: str) -> None:
    magazyn._klient_s3().delete_objects(
        Bucket=magazyn.BUCKET,
        Delete={"Objects": [{"Key": _klucz(magazyn.kancelaria(), identyfikator)}],
                "Quiet": True},
    )
