"""Skan bezpieczenstwa kancelarii - backend dla landingu /bezpieczenstwo-danych/.

Dwa publiczne, bezstanowe punkty wolane przez strone notarai.pl (inna domena,
wiec CORS dodany w kalkulator.SCIEZKI_CORS):

  GET  /api/skan/ip          - echo adresu IP klienta (tyle widzi kazdy serwer)
  GET  /api/skan/hibp-haslo  - proxy do Have I Been Pwned w modelu k-anonimowosci:
                               przyjmuje 5 pierwszych znakow skrotu SHA-1 hasla,
                               nie haslo; oddaje liste sufiksow z HIBP

RODO: nie przyjmujemy ani nie zapisujemy danych osobowych. Haslo NIGDY nie
dociera do serwera - tu trafia wylacznie 5-znakowy prefiks jego skrotu.
Nie logujemy hasel ani prefiksow.
"""
import logging
import re

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

import autoryzacja
import kalkulator

log = logging.getLogger("pieczapp.skan")

HIBP_URL = "https://api.pwnedpasswords.com/range/"

# Podstawiany w testach (jak sledzenie.TRANSPORT); w produkcji None = realne laczenie.
TRANSPORT = None

# Limit na adres IP (na godzine) i na proces (na dobe).
limit_hibp = kalkulator.Limit(120, 3000)

PREFIKS_RE = re.compile(r"^[0-9A-Fa-f]{5}$")

router = APIRouter(prefix="/api/skan", tags=["skan"])


@router.get("/ip")
def ip(request: Request):
    """Adres, z ktorego klient laczy sie z internetem - tyle widzi kazdy serwer."""
    return {"ip": autoryzacja.adres_klienta(request)}


@router.get("/hibp-haslo", response_class=PlainTextResponse)
def hibp_haslo(prefiks: str, request: Request):
    """Proxy k-anonimowosci do HIBP. Przyjmuje 5 znakow skrotu, nie haslo."""
    limit_hibp.sprawdz(autoryzacja.adres_klienta(request), "Za duzo sprawdzen. Sprobuj za chwile.")
    if not PREFIKS_RE.match(prefiks or ""):
        raise HTTPException(400, "Nieprawidlowy prefiks skrotu.")
    try:
        with httpx.Client(timeout=6.0, transport=TRANSPORT) as klient:
            odp = klient.get(HIBP_URL + prefiks.upper(),
                             headers={"Add-Padding": "true", "User-Agent": "notarai-skan"})
    except httpx.HTTPError:
        raise HTTPException(502, "Usluga sprawdzania chwilowo niedostepna.")
    if odp.status_code != 200:
        raise HTTPException(502, "Usluga sprawdzania chwilowo niedostepna.")
    return PlainTextResponse(odp.text)
