"""Bramka Bedrock dla trybu chronionego. Bez Nitro i bez sieci w przygotowaniu.

Tylko serwerowy, uprawniony przeplyw moze przygotowac operacje po przegladzie
calego tekstu. Nie wystawiac jako publicznego API ani nie traktowac flagi
potwierdzenia klienta jako autoryzacji. Brak przegladu = odmowa.
"""
import contextvars
import hashlib
import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass

import magazyn
from pseudonimizacja_aktu import WymagaWeryfikacji


def chroniony():
    # Nieznana konfiguracja nie moze przypadkowo wlaczyc trybu jawnego.
    return os.getenv("PIECZAPP_BEDROCK_CHRONIONY", "0") != "0"


def _hash(value):
    try:
        body = json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise WymagaWeryfikacji("UNSUPPORTED_PAYLOAD") from None
    return hashlib.sha256(body).digest()


def odcisk_tekstu(tekst):
    return hashlib.sha256(tekst.encode("utf-8")).hexdigest()


@dataclass(frozen=True, repr=False)
class PrzejrzanyTekst:
    """Lokalny zapis przegladu konkretnej wersji tekstu, nie token dostepu."""
    tekst: str
    odcisk: str
    wystapienia: tuple = ()
    dodatkowe: tuple = ()

    def maskuj(self, sesja):
        if self.odcisk != odcisk_tekstu(self.tekst):
            raise WymagaWeryfikacji("REVIEW_STALE")
        return sesja.pseudonimizuj(self.tekst, potwierdzone=self.wystapienia,
                                   dodatkowe=self.dodatkowe)


@dataclass(frozen=True, repr=False)
class _Zezwolenie:
    tenant: str
    watek: int
    metoda: str
    odcisk: bytes


_zezwolenie = contextvars.ContextVar("bedrock_chroniony", default=None)


@contextmanager
def _zezwol(metoda, zadanie):
    if metoda not in ("converse", "converse_stream"):
        raise WymagaWeryfikacji("UNSUPPORTED_OPERATION")
    z = _zezwolenie.set(_Zezwolenie(magazyn.kancelaria(), threading.get_ident(),
                                   metoda, _hash(zadanie)))
    try:
        yield
    finally:
        _zezwolenie.reset(z)


def sprawdz(metoda, zadanie):
    if not chroniony():
        return
    z = _zezwolenie.get()
    if (z is None or z.tenant != magazyn.kancelaria()
            or z.watek != threading.get_ident() or z.metoda != metoda
            or z.odcisk != _hash(zadanie)):
        raise WymagaWeryfikacji("BEDROCK_REVIEW_REQUIRED")


class ChronionyKlient:
    """Nie udostepnia surowego SDK przez publiczne metody adaptera."""

    def __init__(self, klient):
        self._surowy = klient

    def converse(self, **zadanie):
        sprawdz("converse", zadanie)
        return self._surowy.converse(**zadanie)

    def converse_stream(self, **zadanie):
        sprawdz("converse_stream", zadanie)
        return self._surowy.converse_stream(**zadanie)

    def __getattr__(self, nazwa):
        raise WymagaWeryfikacji("UNSUPPORTED_PROTECTED_SDK_METHOD")


def rozmowa(klient, sesja, system, tury, *, model, max_tokenow):
    """Jeden wewnetrzny tekstowy przeplyw z recznym przegladem.

    Wszystkie bloki, takze system i historia, sa wersjonowane i maskowane.
    Nie przyjmuje obrazow, narzedzi, dowolnych pol SDK ani metadanych.
    Sesja nalezy do jednej operacji; zamyka ja wywolujacy.
    """
    if not chroniony():
        raise WymagaWeryfikacji("PROTECTED_MODE_REQUIRED")
    if not model.startswith("eu.") or not 0 < max_tokenow <= 64000:
        raise WymagaWeryfikacji("INVALID_PROTECTED_MODEL_CONFIG")
    wiadomosci = []
    for rola, tresc in tury:
        if rola not in ("user", "assistant") or not isinstance(tresc, PrzejrzanyTekst):
            raise WymagaWeryfikacji("INVALID_REVIEWED_TURN")
        wiadomosci.append({"role": rola, "content": [{"text": tresc.maskuj(sesja)}]})
    if not wiadomosci or wiadomosci[-1]["role"] != "user":
        raise WymagaWeryfikacji("MISSING_USER_TURN")
    zadanie = {
        "modelId": model,
        "system": [{"text": system.maskuj(sesja) +
                    "\nZachowaj znaczniki [[NA_...]] dokladnie. Nie zgaduj ich tresci; "
                    "identyczny Pxxx oznacza te sama osobe. Nie zamieniaj rol ani znacznikow."}],
        "messages": wiadomosci,
        "inferenceConfig": {"maxTokens": max_tokenow},
    }
    # Uprawnienie jest ograniczone do dokladnie tego payloadu i watku.
    try:
        with _zezwol("converse", zadanie):
            sprawdz("converse", zadanie)
            odpowiedz = klient.converse(**zadanie)
    except Exception:
        # SDK moze w wyjatku przytoczyc prompt. Nie propagowac jego tresci.
        raise WymagaWeryfikacji("PROTECTED_MODEL_ERROR") from None
    if odpowiedz.get("stopReason") != "end_turn":
        raise WymagaWeryfikacji("PROTECTED_INCOMPLETE_RESPONSE")
    bloki = odpowiedz["output"]["message"]["content"]
    if not bloki or any(set(b) != {"text"} for b in bloki):
        raise WymagaWeryfikacji("UNSUPPORTED_MODEL_OUTPUT")
    return sesja.przywroc("".join(b["text"] for b in bloki)), odpowiedz.get("usage", {})
