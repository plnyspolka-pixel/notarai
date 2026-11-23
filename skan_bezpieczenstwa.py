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
import os
import re
import time

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

import autoryzacja
import kalkulator

log = logging.getLogger("pieczapp.skan")

HIBP_URL = "https://api.pwnedpasswords.com/range/"
# Oficjalny, darmowy katalog aktywnie wykorzystywanych luk (CISA KEV).
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
KEV_TTL = int(os.getenv("PIECZAPP_SKAN_KEV_TTL", "21600"))  # odswiezanie co 6 h

# Podstawiany w testach (jak sledzenie.TRANSPORT); w produkcji None = realne laczenie.
TRANSPORT = None

# Limit na adres IP (na godzine) i na proces (na dobe).
limit_hibp = kalkulator.Limit(120, 3000)
limit_luki = kalkulator.Limit(120, 5000)

PREFIKS_RE = re.compile(r"^[0-9A-Fa-f]{5}$")

# Cache KEV w procesie: {ts, dane}. Gdy feedu nie da sie pobrac, uzywamy snapshotu.
_kev_cache = {"ts": 0.0, "dane": None}

# Zweryfikowane recznie (MSRC + CISA KEV) - awaryjnie, gdy feed nieosiagalny.
KEV_FALLBACK = [
    {"id": "CVE-2026-96951", "dataDodania": "2026-10-13",
     "opis": "Windows Shell: obejscie „Mark of the Web” — plik pobrany z internetu uruchamia sie bez ostrzezenia.",
     "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-96951"},
    {"id": "CVE-2025-62215", "dataDodania": "2025-11-12",
     "opis": "Jadro Windows: podniesienie uprawnien do SYSTEM — pelna kontrola nad komputerem.",
     "url": "https://nvd.nist.gov/vuln/detail/CVE-2025-62215"},
]

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


def _pobierz_kev() -> list[dict]:
    """Sciaga katalog CISA KEV i zostawia tylko luki Microsoft/Windows."""
    with httpx.Client(timeout=10.0, transport=TRANSPORT) as klient:
        odp = klient.get(KEV_URL, headers={"User-Agent": "notarai-skan"})
    odp.raise_for_status()
    dane = odp.json()
    luki = []
    for v in dane.get("vulnerabilities", []):
        if v.get("vendorProject") != "Microsoft":
            continue
        tekst = ((v.get("product") or "") + " " + (v.get("vulnerabilityName") or "")).lower()
        if "windows" not in tekst:
            continue
        cve = v.get("cveID")
        if not cve:
            continue
        luki.append({
            "id": cve,
            "dataDodania": v.get("dateAdded") or "",
            "opis": (v.get("shortDescription") or v.get("vulnerabilityName") or "")[:240],
            "url": "https://nvd.nist.gov/vuln/detail/" + cve,
        })
    luki.sort(key=lambda x: x["dataDodania"], reverse=True)
    return luki


def _kev(teraz: float | None = None) -> tuple[list[dict], str]:
    """Zwraca liste luk z cache; odswieza co KEV_TTL. Gdy feed pada - snapshot."""
    t = teraz if teraz is not None else time.time()
    if _kev_cache["dane"] is None or t - _kev_cache["ts"] > KEV_TTL:
        try:
            _kev_cache["dane"] = _pobierz_kev()
            _kev_cache["ts"] = t
        except Exception:  # noqa: BLE001 - feed bywa niedostepny, nie wywalamy strony
            log.warning("skan: nie udalo sie pobrac CISA KEV, uzywam snapshotu")
            if _kev_cache["dane"] is None:
                return list(KEV_FALLBACK), "snapshot"
    return _kev_cache["dane"], "CISA KEV"


@router.get("/luki")
def luki(po: str = "", request: Request = None):
    """Aktywnie wykorzystywane luki Windows z CISA KEV. `po` = data (YYYY-MM-DD)
    konca wsparcia wykrytego systemu - zwracamy tylko nowsze."""
    if request is not None:
        limit_luki.sprawdz(autoryzacja.adres_klienta(request), "Za duzo zapytan. Sprobuj za chwile.")
    dane, zrodlo = _kev()
    if po:
        dane = [l for l in dane if (l.get("dataDodania") or "") >= po]
    return {"zrodlo": zrodlo, "luki": dane[:20]}
