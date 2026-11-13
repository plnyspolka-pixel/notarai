"""Platnosci za kredyty przez Finance You (konto TPay Fundacji) - jedyny sposob
zakupu w notarai.

Kancelaria nie ma abonamentu: placi wylacznie kredytami (tokenomia.py), a
kredyty kupuje jednorazowo w pakietach. Sprzedawca jest Fundacja Krzewienia
Edukacji Finansowej - ta sama, ktora sprzedaje przez Finance You - wiec nie
mamy osobnego konta TPay: zamowienie zakladamy w Finance You
(POST /api/public/partner-platnosci), a Finance You tworzy transakcje TPay,
odbiera powiadomienie TPay, sprawdza je w API TPay i wystawia fakture (KSeF).

O zaplacie Finance You daje znac "pingiem" na /api/finyou/platnosc. Ping
niczego nie przesadza: stan zamowienia czytamy zawsze sami
(GET /api/public/partner-platnosci) tokenem partnera. Gdy ping zginie,
saldo uzgadnia sie przy najblizszym otwarciu okna "Kredyty".

Konfiguracja - ta sama co dostawca tresci KW (ekw.py), w chmurze z sekretu
notarai/finyou:
  PIECZAPP_FINYOU_URL     adres Finance You, np. https://finyou.pl
  PIECZAPP_FINYOU_TOKEN   token partnera (KW_PARTNER_TOKEN / PARTNER_PLATNOSCI_TOKEN)
  PIECZAPP_ADRES          publiczny adres aplikacji, np. https://app.notarai.pl
  PIECZAPP_VAT            stawka VAT doliczana do ceny pakietu. Domyslnie 0:
                          Fundacja korzysta ze zwolnienia podmiotowego (art. 113
                          ust. 1 ustawy o VAT). Po utracie zwolnienia: 0.23.

Zero danych osobowych w logach: dane nabywcy ida tylko do Finance You.
"""
from __future__ import annotations

import logging
import os
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import quote

import httpx

log = logging.getLogger("pieczapp.platnosci")

ADRES = os.getenv("PIECZAPP_ADRES", "").rstrip("/")
VAT = Decimal(os.getenv("PIECZAPP_VAT", "0"))
SCIEZKA = "/api/public/partner-platnosci"


class BladPlatnosci(Exception):
    """Finance You / TPay odrzucil zadanie albo jest nieosiagalny."""


def finyou_adres() -> str:
    return os.getenv("PIECZAPP_FINYOU_URL", "").strip().rstrip("/")


def finyou_token() -> str:
    return os.getenv("PIECZAPP_FINYOU_TOKEN", "").strip()


def wlaczone() -> bool:
    return bool(finyou_adres() and finyou_token() and ADRES)


def grosze(kwota) -> Decimal:
    return Decimal(str(kwota)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def brutto(netto) -> Decimal:
    """Cena dla platnika: netto + VAT (przy zwolnieniu VAT = 0), do grosza."""
    return grosze(Decimal(str(netto)) * (1 + VAT))


def _klient() -> httpx.Client:
    # Token w naglowku, nie w adresie: adres trafia do komunikatow bledow httpx.
    return httpx.Client(base_url=finyou_adres(), timeout=httpx.Timeout(30, connect=10),
                        headers={"Authorization": "Bearer " + finyou_token(), "Accept": "application/json"})


def _odpowiedz(odp: httpx.Response, co: str) -> dict:
    try:
        tresc = odp.json()
    except ValueError:
        tresc = {}
    if odp.status_code >= 300 or not isinstance(tresc, dict) or not tresc.get("ok"):
        # Komunikat Finance You nie zawiera danych nabywcy, ale go nie logujemy.
        log.warning("finyou: %s odrzucone (HTTP %s)", co, odp.status_code)
        raise BladPlatnosci("Bramka płatności nie przyjęła zlecenia. Spróbuj za chwilę.")
    return tresc


def utworz_zamowienie(numer: str, kredyty: float, kwota: Decimal, opis: str, nabywca: dict) -> dict:
    """Zamowienie w Finance You. `numer` = "<kancelaria>:<numer>". Zwraca adres
    strony platnosci TPay i numer transakcji."""
    if not wlaczone():
        raise BladPlatnosci("Płatności nie są skonfigurowane na tym serwerze.")
    try:
        with _klient() as http:
            odp = http.post(SCIEZKA, json={
                "zamowienie": numer,
                "kredyty": int(kredyty),
                "kwota_grosz": int(grosze(kwota) * 100),
                "opis": opis,
                "nabywca": nabywca,
                "powrot_ok": f"{ADRES}/?kredyty=ok",
                "powrot_blad": f"{ADRES}/?kredyty=blad",
                "powiadomienie": f"{ADRES}/api/finyou/platnosc",
            })
    except httpx.HTTPError:
        log.warning("finyou: brak polaczenia przy zakladaniu zamowienia")
        raise BladPlatnosci("Bramka płatności jest chwilowo niedostępna. Spróbuj za chwilę.")
    tresc = _odpowiedz(odp, "zamowienie")
    if not tresc.get("adres"):
        raise BladPlatnosci("Bramka płatności nie zwróciła adresu płatności.")
    log.info("finyou: zamowienie kredytow utworzone (%s)", tresc.get("transakcja") or "-")
    return tresc


def pobierz_zamowienie(numer: str) -> dict | None:
    """Stan zamowienia w Finance You albo None, gdy go tam nie ma."""
    if not wlaczone():
        raise BladPlatnosci("Płatności nie są skonfigurowane na tym serwerze.")
    try:
        with _klient() as http:
            odp = http.get(f"{SCIEZKA}?zamowienie={quote(numer, safe='')}")
    except httpx.HTTPError:
        raise BladPlatnosci("Bramka płatności jest chwilowo niedostępna.")
    if odp.status_code == 404:
        return None
    return _odpowiedz(odp, "odczyt zamowienia")


_KOD_POCZTOWY = r"(\d{2}-\d{3})"


def adres_nabywcy(adres: str) -> dict:
    """'ul. Testowa 1, 00-001 Warszawa' -> ulica, kod, miasto (do faktury)."""
    import re
    adres = " ".join((adres or "").split())
    m = re.search(_KOD_POCZTOWY + r"\s+(.+)$", adres)
    if not m:
        return {"ulica": adres or None, "kod": None, "miasto": None}
    ulica = adres[:m.start()].strip(" ,") or None
    return {"ulica": ulica, "kod": m.group(1), "miasto": m.group(2).strip(" ,") or None}
