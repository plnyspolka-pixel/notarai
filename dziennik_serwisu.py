"""Dziennik dostepu serwisowego - tylko dopisywanie, wpisy spiete skrotami.

Dostep serwisowy to jedyna droga administratora do tresci spraw wewnatrz
aplikacji (umowa powierzenia par. 5 ust. 4). Historie w rejestrze kancelarii
aplikacja moze nadpisac, wiec nie nadaje sie na dowod. Tutaj kazde zdarzenie
(wlaczenie, odwolanie, wejscie administratora, poszerzenie zakresu) jest
osobnym wpisem, ktory:

  - niesie skrot poprzedniego wpisu, wiec usuniecie albo zmiana dowolnego
    wpisu zrywa lancuch;
  - zapisuje sie pod kolejnym numerem bez mozliwosci nadpisania (S3: zapis
    warunkowy If-None-Match; lokalnie: tworzenie pliku na wylacznosc);
  - zostawia swiadka w dzienniku aplikacji (CloudWatch): numer, rodzaj,
    kancelaria i skrot. Wpisow w CloudWatch nie da sie edytowac, a usuniecie
    strumienia zostaje w sladzie CloudTrail. infra/raport_dostepu.py czyta
    swiadkow i sprawdza lancuch bez dostepu do bucketa spraw.

W swiadku nie ma adresow e-mail ani niczego o tresci spraw - tylko
identyfikatory. Adres administratora jest we wpisie (i w skrocie).
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import magazyn

log = logging.getLogger("pieczapp.serwis")

RODZAJE = ("wlaczono", "odwolano", "wejscie", "zakres")
POCZATEK = "0" * 64          # "poprzedni" pierwszego wpisu
ZNACZNIK = "serwis-dziennik"  # po tym slowie raport znajduje swiadkow w logach
_PROB = 8

_blokada = threading.Lock()
_glowa: tuple[int, str] | None = None   # (numer ostatniego wpisu, jego skrot)


_LITERY = str.maketrans("0123456789", "ghijklmnop")


def bez_cyfr(szesnastkowo: str) -> str:
    """Skrot zapisany samymi literami. Dziennik aplikacji maskuje kazdy ciag
    11 cyfr jako numer PESEL, a taki ciag moze sie trafic w zapisie
    szesnastkowym - swiadek bylby wtedy nie do odczytania."""
    return szesnastkowo.translate(_LITERY)


class BladDziennika(RuntimeError):
    """Wpisu nie udalo sie zapisac - dostepu serwisowego nie wolno wtedy dac."""


def skrot(wpis: dict) -> str:
    """SHA-256 wpisu bez pola "skrot", w zapisie kanonicznym."""
    tresc = {k: v for k, v in wpis.items() if k != "skrot"}
    kanon = json.dumps(tresc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(kanon.encode("utf-8")).hexdigest()


def _nazwa(nr: int) -> str:
    return f"{nr:010d}.json"


def _katalog() -> Path:
    import config
    katalog = config.DANE / "serwis-dziennik"
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog


def _prefiks() -> str:
    return f"{magazyn.PREFIKS}/admin/serwis-dziennik/"


def _numery() -> list[int]:
    if magazyn.TRYB == "s3":
        strony = magazyn._klient_s3().get_paginator("list_objects_v2")
        nazwy = [o["Key"].rsplit("/", 1)[-1]
                 for s in strony.paginate(Bucket=magazyn.BUCKET, Prefix=_prefiks())
                 for o in s.get("Contents", [])]
    else:
        nazwy = [p.name for p in _katalog().glob("*.json")]
    return sorted(int(n[:-5]) for n in nazwy if n[:-5].isdigit())


def _czytaj(nr: int) -> dict:
    if magazyn.TRYB == "s3":
        tresc = magazyn._klient_s3().get_object(
            Bucket=magazyn.BUCKET, Key=_prefiks() + _nazwa(nr))["Body"].read()
    else:
        tresc = (_katalog() / _nazwa(nr)).read_bytes()
    return json.loads(tresc)


def _zapisz_nowy(nr: int, wpis: dict) -> bool:
    """True, gdy wpis zapisano; False, gdy ten numer jest juz zajety."""
    tresc = json.dumps(wpis, ensure_ascii=False, indent=2).encode("utf-8")
    if magazyn.TRYB == "s3":
        from botocore.exceptions import ClientError
        try:
            magazyn._klient_s3().put_object(
                Bucket=magazyn.BUCKET, Key=_prefiks() + _nazwa(nr), Body=tresc,
                IfNoneMatch="*", **magazyn._szyfrowanie())
        except ClientError as blad:
            if blad.response.get("Error", {}).get("Code") in (
                    "PreconditionFailed", "ConditionalRequestConflict"):
                return False
            raise
        return True
    try:
        with open(_katalog() / _nazwa(nr), "xb") as plik:
            plik.write(tresc)
    except FileExistsError:
        return False
    return True


def _odswiez_glowe() -> tuple[int, str]:
    numery = _numery()
    if not numery:
        return 0, POCZATEK
    return numery[-1], _czytaj(numery[-1])["skrot"]


def dopisz(rodzaj: str, kancelaria: str, **pola) -> dict:
    """Dopisuje wpis na koncu lancucha i zostawia swiadka w dzienniku aplikacji.

    Rzuca BladDziennika, gdy zapis sie nie udal - wolajacy ma wtedy odmowic
    dostepu (brak wpisu = brak dostepu).
    """
    global _glowa
    if rodzaj not in RODZAJE:
        raise ValueError(f"Nieznany rodzaj wpisu: {rodzaj}")
    with _blokada:
        try:
            for proba in range(_PROB):
                # Druga kopia aplikacji mogla dopisac w miedzyczasie - po
                # nieudanej probie czytamy koniec lancucha od nowa.
                if _glowa is None or proba:
                    _glowa = _odswiez_glowe()
                nr, poprzedni = _glowa[0] + 1, _glowa[1]
                wpis = {"nr": nr, "czas": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "rodzaj": rodzaj, "kancelaria": kancelaria, **pola, "poprzedni": poprzedni}
                wpis["skrot"] = skrot(wpis)
                if _zapisz_nowy(nr, wpis):
                    _glowa = (nr, wpis["skrot"])
                    log.info("%s nr=%d rodzaj=%s kancelaria=%s skrot=%s poprzedni=%s",
                             ZNACZNIK, nr, rodzaj, kancelaria, bez_cyfr(wpis["skrot"]),
                             bez_cyfr(poprzedni))
                    return wpis
        except Exception as blad:  # noqa: BLE001
            _glowa = None
            raise BladDziennika(type(blad).__name__) from None
        _glowa = None
        raise BladDziennika("kolizja numerow")


def wpisy() -> list[dict]:
    return [_czytaj(nr) for nr in _numery()]


def sprawdz(lista: list[dict]) -> dict:
    """Czy lancuch jest caly: numery po kolei, skroty zgodne, kazdy wpis wskazuje poprzedni."""
    bledy, poprzedni = [], POCZATEK
    for i, wpis in enumerate(lista, start=1):
        if wpis.get("nr") != i:
            bledy.append(f"wpis {i}: numer {wpis.get('nr')} (brak albo przestawienie)")
        if wpis.get("skrot") != skrot(wpis):
            bledy.append(f"wpis {wpis.get('nr')}: tresc nie zgadza sie ze skrotem")
        if wpis.get("poprzedni") != poprzedni:
            bledy.append(f"wpis {wpis.get('nr')}: nie wskazuje poprzedniego wpisu")
        poprzedni = wpis.get("skrot")
    return {"caly": not bledy, "wpisow": len(lista), "glowa": poprzedni, "bledy": bledy}


def _zeruj() -> None:
    """Dla testow: zapomnij koniec lancucha."""
    global _glowa
    _glowa = None
