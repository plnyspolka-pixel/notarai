"""Jednorazowa zgoda na wyslanie formularza z pilota telefonu.

Pomocnik nie ma prawa sam zaakceptowac operacji. Zglasza konkretny przycisk
i domenę, a osoba zalogowana do tej samej kancelarii zatwierdza ja w NotarAI.
Brak odpowiedzi, utrata polaczenia i uplyw terminu oznaczaja odmowe.

To nie jest pelnomocnictwo do podpisu, platnosci ani kasowania danych.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

import magazyn

WAZNOSC_S = 120


class BladZgody(RuntimeError):
    pass


def _teraz() -> datetime:
    return datetime.now(timezone.utc)


def _klucz(zlecenie: str) -> str:
    return f"{magazyn.PREFIKS}/{magazyn.kancelaria()}/zgody-pilota/{zlecenie}.json"


def _czytaj(zlecenie: str) -> dict | None:
    try:
        odp = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=_klucz(zlecenie))
    except Exception as blad:
        if type(blad).__name__ in ("NoSuchKey", "ClientError"):
            return None
        raise
    return json.loads(odp["Body"].read().decode("utf-8"))


def _pisz(zlecenie: str, wpis: dict) -> None:
    magazyn._klient_s3().put_object(
        Bucket=magazyn.BUCKET, Key=_klucz(zlecenie),
        Body=json.dumps(wpis, ensure_ascii=False).encode("utf-8"),
        **magazyn._szyfrowanie(),
    )


def _wazna(wpis: dict) -> bool:
    try:
        data = datetime.fromisoformat(wpis["utworzono"])
        return _teraz() - data <= timedelta(seconds=WAZNOSC_S)
    except (KeyError, ValueError, TypeError):
        return False


def rozpocznij(zlecenie: str, komputer: str, host: str, etykieta: str) -> dict:
    """Nowa zgoda jest tworzona przez sparowany komputer dla konkretnego zadania."""
    istnieje = _czytaj(zlecenie)
    if istnieje and istnieje.get("stan") == "czeka" and _wazna(istnieje):
        raise BladZgody("Inna operacja w tym zadaniu juz czeka na zgode.")
    wpis = {
        "id": secrets.token_urlsafe(18), "komputer": komputer,
        "host": host[:150], "etykieta": etykieta[:120],
        "stan": "czeka", "utworzono": _teraz().isoformat(timespec="seconds"),
    }
    _pisz(zlecenie, wpis)
    return {"id": wpis["id"], "stan": "czeka", "wazny_s": WAZNOSC_S}


def oczekujaca(zlecenie: str) -> dict | None:
    wpis = _czytaj(zlecenie)
    if not wpis or wpis["stan"] != "czeka" or not _wazna(wpis):
        return None
    return {k: wpis[k] for k in ("id", "host", "etykieta", "utworzono")}


def decyzja(zlecenie: str, identyfikator: str, zgoda: bool, zatwierdzil: str) -> dict:
    wpis = _czytaj(zlecenie)
    if not wpis or not secrets.compare_digest(wpis["id"], identyfikator):
        raise BladZgody("Nieaktualne potwierdzenie.")
    if wpis.get("stan") != "czeka" or not _wazna(wpis):
        raise BladZgody("Zgoda wygasla albo zostala juz rozpatrzona.")
    wpis["stan"] = "zgoda" if zgoda else "odmowa"
    wpis["zatwierdzil"] = zatwierdzil
    wpis["rozpatrzono"] = _teraz().isoformat(timespec="seconds")
    _pisz(zlecenie, wpis)
    return {"stan": wpis["stan"]}


def odbierz(zlecenie: str, identyfikator: str, komputer: str) -> dict:
    """Odbior przez docelowego pomocnika; pojedynczy krok, pojedyncza zgoda."""
    wpis = _czytaj(zlecenie)
    if not wpis or not secrets.compare_digest(wpis["id"], identyfikator):
        raise BladZgody("Nieznane potwierdzenie.")
    if wpis.get("komputer") != komputer:
        raise BladZgody("Potwierdzenie nalezy do innego komputera.")
    if not _wazna(wpis):
        return {"stan": "wygasla"}
    stan = wpis.get("stan")
    if stan in ("zgoda", "odmowa"):
        wpis["stan"] = "odebrana"
        _pisz(zlecenie, wpis)
        return {"stan": stan}
    if stan == "odebrana":
        return {"stan": "odebrana"}
    return {"stan": "czeka"}
