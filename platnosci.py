"""Bramka platnosci TPay (Open API) - jedyny sposob zakupu w notarai.

Kancelaria nie ma abonamentu: placi wylacznie kredytami (tokenomia.py),
a kredyty kupuje jednorazowo w pakietach. Wlasciciel wybiera pakiet, my
zakladamy transakcje w TPay i przekierowujemy go na strone platnosci
(BLIK, przelew, karta). O zaplacie dowiadujemy sie z powiadomienia TPay
(POST na /api/tpay/powiadomienie), nie z powrotu przegladarki.

Powiadomieniu wierzymy dopiero, gdy:
  1. zgadza sie md5sum = md5(id + tr_id + tr_amount + tr_crc + kod bezpieczenstwa),
  2. tr_crc wskazuje nasze zamowienie, a kwota zgadza sie z zamowieniem,
  3. TPay zapytany wprost (GET /transactions/{id}) potwierdza status "correct".
Krok 3 sprawia, ze nawet wyciek kodu bezpieczenstwa nie pozwala dopisac
kredytow bez prawdziwej wplaty.

Konfiguracja (w chmurze z sekretu notarai/tpay w Secrets Manager):
  TPAY_CLIENT_ID            identyfikator klucza Open API (panel TPay: Integracja > API)
  TPAY_CLIENT_SECRET        sekret klucza Open API
  TPAY_KOD_BEZPIECZENSTWA   kod z panelu TPay: Powiadomienia > Bezpieczenstwo
  TPAY_API                  domyslnie https://api.tpay.com (sandbox: https://openapi.sandbox.tpay.com)
  PIECZAPP_ADRES            publiczny adres aplikacji, np. https://app.notarai.pl
  PIECZAPP_VAT              stawka VAT doliczana do ceny pakietu. Domyslnie 0: Uslugodawca
                            (Fundacja) korzysta ze zwolnienia podmiotowego z art. 113 ust. 1
                            ustawy o VAT. Po utracie zwolnienia: 0.23 (i zmiana Regulaminu).

Zero danych osobowych w logach: adres platnika idzie tylko do TPay.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading
import time
from decimal import ROUND_HALF_UP, Decimal

import httpx

log = logging.getLogger("pieczapp.platnosci")

CLIENT_ID = os.getenv("TPAY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("TPAY_CLIENT_SECRET", "")
KOD_BEZPIECZENSTWA = os.getenv("TPAY_KOD_BEZPIECZENSTWA", "")
API = os.getenv("TPAY_API", "https://api.tpay.com").rstrip("/")
ADRES = os.getenv("PIECZAPP_ADRES", "").rstrip("/")
VAT = Decimal(os.getenv("PIECZAPP_VAT", "0"))

# Status transakcji w TPay po zaksiegowaniu wplaty.
OPLACONA = "correct"


class BladPlatnosci(Exception):
    """TPay odrzucil zadanie albo jest nieosiagalny."""


class BladPodpisu(Exception):
    """Powiadomienie bez waznej sumy kontrolnej - nie wierzymy mu."""


def wlaczone() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET and KOD_BEZPIECZENSTWA and ADRES)


def grosze(kwota) -> Decimal:
    return Decimal(str(kwota)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def brutto(netto) -> Decimal:
    """Cena dla platnika: netto + VAT (przy zwolnieniu VAT = 0), do grosza."""
    return grosze(Decimal(str(netto)) * (1 + VAT))


# --- API TPay ----------------------------------------------------------------

_token: dict = {"wartosc": "", "wygasa": 0.0}
_blokada_tokenu = threading.Lock()


def _klient() -> httpx.Client:
    return httpx.Client(timeout=20)


def _token_dostepu() -> str:
    with _blokada_tokenu:
        if _token["wartosc"] and _token["wygasa"] > time.time() + 60:
            return _token["wartosc"]
        with _klient() as http:
            odp = http.post(f"{API}/oauth/auth",
                            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET})
        if odp.status_code >= 300:
            log.warning("tpay: autoryzacja odrzucona (HTTP %s)", odp.status_code)
            raise BladPlatnosci("Bramka płatności jest chwilowo niedostępna. Spróbuj za chwilę.")
        dane = odp.json()
        _token["wartosc"] = dane["access_token"]
        _token["wygasa"] = time.time() + float(dane.get("expires_in") or 3600)
        return _token["wartosc"]


def _tpay(metoda: str, sciezka: str, dane: dict | None = None) -> dict:
    with _klient() as http:
        odp = http.request(metoda, f"{API}{sciezka}", json=dane,
                           headers={"Authorization": f"Bearer {_token_dostepu()}"})
    try:
        tresc = odp.json()
    except ValueError:
        tresc = {}
    if odp.status_code >= 300 or (isinstance(tresc, dict) and tresc.get("result") == "failed"):
        # Kody bledow TPay nie zawieraja danych osobowych, opisy pol - moga.
        bledy = [b.get("errorCode") for b in (tresc.get("errors") or [])] if isinstance(tresc, dict) else []
        log.warning("tpay: %s %s odrzucone (HTTP %s, %s)", metoda, sciezka, odp.status_code, bledy)
        raise BladPlatnosci("Bramka płatności nie przyjęła zlecenia. Spróbuj za chwilę.")
    return tresc


def utworz_transakcje(kwota_brutto: Decimal, opis: str, znacznik: str, email: str,
                      platnik: str) -> dict:
    """Transakcja w TPay. `znacznik` wraca w powiadomieniu jako tr_crc.
    Zwraca adres strony platnosci i identyfikator transakcji."""
    if not wlaczone():
        raise BladPlatnosci("Płatności nie są skonfigurowane na tym serwerze.")
    tresc = _tpay("POST", "/transactions", {
        "amount": float(kwota_brutto),
        "description": opis[:128],
        "hiddenDescription": znacznik,
        "lang": "pl",
        "payer": {"email": email, "name": (platnik or email)[:255]},
        "callbacks": {
            "payerUrls": {"success": f"{ADRES}/?kredyty=ok", "error": f"{ADRES}/?kredyty=blad"},
            "notification": {"url": f"{ADRES}/api/tpay/powiadomienie"},
        },
    })
    if not tresc.get("transactionPaymentUrl"):
        raise BladPlatnosci("Bramka płatności nie zwróciła adresu płatności.")
    log.info("tpay: transakcja %s utworzona", tresc.get("title") or tresc.get("transactionId"))
    return {"adres": tresc["transactionPaymentUrl"], "transakcja": tresc.get("transactionId", ""),
            "tytul": tresc.get("title", "")}


def pobierz_transakcje(transakcja: str) -> dict:
    return _tpay("GET", f"/transactions/{transakcja}")


# --- powiadomienie -----------------------------------------------------------


def sprawdz_powiadomienie(pola: dict, kod: str | None = None) -> None:
    """md5sum = md5(id + tr_id + tr_amount + tr_crc + kod bezpieczenstwa)."""
    kod = KOD_BEZPIECZENSTWA if kod is None else kod
    if not kod:
        raise BladPodpisu("brak kodu bezpieczenstwa")
    podany = str(pola.get("md5sum") or "")
    oczekiwany = hashlib.md5("".join(str(pola.get(k) or "") for k in ("id", "tr_id", "tr_amount", "tr_crc"))
                             .encode("utf-8") + kod.encode("utf-8")).hexdigest()
    if not podany or not hmac.compare_digest(oczekiwany, podany.lower()):
        raise BladPodpisu("suma kontrolna sie nie zgadza")
