"""Abonament kancelarii w Stripe (subskrypcja miesieczna, faktury ze Stripe).

Wlasciciel kancelarii klika "Wlacz abonament", my tworzymy sesje Stripe
Checkout w trybie subskrypcji i przekierowujemy go na strone platnosci.
Stripe co miesiac sam pobiera oplate z karty, wystawia fakture i wysyla ja
e-mailem. Kazda oplacona faktura przychodzi do nas webhookiem invoice.paid,
a my ustawiamy kancelarii "oplacono_do" na koniec oplaconego okresu.
Zmiane karty, faktury i rezygnacje notariusz zalatwia w portalu klienta
Stripe.

Konfiguracja (w chmurze z sekretu notarai/stripe w Secrets Manager):
  STRIPE_KLUCZ            klucz tajny API (sk_live_... albo rk_live_...)
  STRIPE_WEBHOOK_SEKRET   klucz podpisu webhooka (whsec_...)
  STRIPE_CENA             identyfikator ceny abonamentu (price_..., jawny)
  PIECZAPP_ABONAMENT_ZL   cena do wyswietlenia, np. "600.00"
  PIECZAPP_ADRES          publiczny adres aplikacji, np. https://app.notarai.pl

Webhookowi wierzymy tylko z waznym podpisem (HMAC-SHA256 kluczem whsec,
znacznik czasu nie starszy niz 5 minut). Zero danych osobowych w logach:
adres platnika idzie tylko do Stripe.
"""
import calendar
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

log = logging.getLogger("pieczapp.platnosci")

KLUCZ = os.getenv("STRIPE_KLUCZ", "")
WEBHOOK_SEKRET = os.getenv("STRIPE_WEBHOOK_SEKRET", "")
CENA_ID = os.getenv("STRIPE_CENA", "")
CENA = os.getenv("PIECZAPP_ABONAMENT_ZL", "")
ADRES = os.getenv("PIECZAPP_ADRES", "").rstrip("/")
# Po terminie kancelaria pracuje jeszcze kilka dni - Stripe ponawia nieudane
# obciazenie karty, a notariusz nie moze stracic dostepu w srodku aktu.
KARENCJA_DNI = int(os.getenv("PIECZAPP_KARENCJA_DNI", "3"))
OKRES_PROBNY_DNI = int(os.getenv("PIECZAPP_OKRES_PROBNY_DNI", "14"))

API = "https://api.stripe.com/v1"
# Ta sama wersja co webhook notarai-aplikacja w panelu Stripe - inaczej
# ksztalt obiektow w odpowiedziach i zdarzeniach moglby sie roznic.
WERSJA_API = "2026-04-22.dahlia"
TOLERANCJA_S = 300


class BladPlatnosci(Exception):
    """Stripe odrzucil zadanie albo jest nieosiagalny."""


class BladPodpisu(Exception):
    """Webhook bez waznego podpisu Stripe - nie wierzymy mu."""


def wlaczone() -> bool:
    return bool(KLUCZ and WEBHOOK_SEKRET and CENA_ID and ADRES)


def cena() -> str:
    return f"{float(CENA):.2f}" if CENA else ""


# --- daty abonamentu ---------------------------------------------------------


def dzis() -> date:
    return datetime.now(timezone.utc).date()


def na_probe(teraz: date | None = None) -> str:
    return ((teraz or dzis()) + timedelta(days=OKRES_PROBNY_DNI)).isoformat()


def stan(wpis: dict, teraz: date | None = None) -> dict:
    """Stan abonamentu kancelarii. Bez daty "oplacono_do" kancelaria nie
    placi w aplikacji (np. umowa poza systemem) i nic jej nie blokujemy."""
    teraz = teraz or dzis()
    do = wpis.get("oplacono_do")
    if not do:
        return {"wymagany": False, "oplacono_do": None, "wazny": True, "po_terminie": False}
    koniec = date.fromisoformat(do)
    return {
        "wymagany": True,
        "oplacono_do": do,
        "wazny": teraz <= koniec + timedelta(days=KARENCJA_DNI),
        "po_terminie": teraz > koniec,
        "dni_do_konca": (koniec - teraz).days,
    }


def _data(znacznik: int) -> str:
    return datetime.fromtimestamp(znacznik, timezone.utc).date().isoformat()


# --- API Stripe --------------------------------------------------------------


def _klient() -> httpx.Client:
    return httpx.Client(timeout=20)


def _formularz(dane: dict, prefiks: str = "") -> list[tuple[str, str]]:
    """{"a": {"b": [1]}} -> [("a[b][0]", "1")] - format zadan API Stripe."""
    pary = []
    elementy = dane.items() if isinstance(dane, dict) else enumerate(dane)
    for klucz, wartosc in elementy:
        nazwa = f"{prefiks}[{klucz}]" if prefiks else str(klucz)
        if isinstance(wartosc, (dict, list)):
            pary += _formularz(wartosc, nazwa)
        elif isinstance(wartosc, bool):
            pary.append((nazwa, "true" if wartosc else "false"))
        elif wartosc is not None:
            pary.append((nazwa, str(wartosc)))
    return pary


def _stripe(sciezka: str, dane: dict) -> dict:
    with _klient() as http:
        odp = http.post(f"{API}{sciezka}", content=urlencode(_formularz(dane)),
                        headers={"Authorization": f"Bearer {KLUCZ}", "Stripe-Version": WERSJA_API,
                                 "Content-Type": "application/x-www-form-urlencoded"})
    tresc = odp.json() if odp.headers.get("content-type", "").startswith("application/json") else {}
    if odp.status_code >= 300:
        # Kod i typ bledu Stripe nie zawieraja danych osobowych, komunikat - moze.
        blad = tresc.get("error", {}) if isinstance(tresc, dict) else {}
        log.warning("stripe: %s odrzucone (HTTP %s, %s/%s)", sciezka, odp.status_code,
                    blad.get("type"), blad.get("code"))
        raise BladPlatnosci("Bramka platnosci nie przyjela zlecenia. Sprobuj za chwile.")
    return tresc


def utworz_checkout(kancelaria: str, email: str, klient: str = "",
                    oplacono_do: str | None = None) -> dict:
    """Sesja Checkout zakladajaca subskrypcje. Zwraca adres strony platnosci.

    Kancelaria jedzie w metadanych subskrypcji, wiec kazda jej faktura
    (invoice.paid) wskazuje kancelarie bez zgadywania. Trwajacy okres probny
    przechodzi do Stripe - pierwsza oplata dopiero po jego koncu.
    """
    if not wlaczone():
        raise BladPlatnosci("Platnosci nie sa skonfigurowane na tym serwerze.")
    dane = {
        "mode": "subscription",
        "line_items": [{"price": CENA_ID, "quantity": 1}],
        "client_reference_id": kancelaria,
        "metadata": {"kancelaria": kancelaria},
        "subscription_data": {"metadata": {"kancelaria": kancelaria}},
        "success_url": f"{ADRES}/?platnosc=ok",
        "cancel_url": f"{ADRES}/?platnosc=blad",
        "locale": "pl",
        # Faktura z NIP-em i adresem kancelarii; VAT liczy Stripe Tax.
        "automatic_tax": {"enabled": True},
        "tax_id_collection": {"enabled": True},
        "billing_address_collection": "required",
    }
    if klient:
        dane["customer"] = klient
        dane["customer_update"] = {"address": "auto", "name": "auto"}
    else:
        dane["customer_email"] = email
    if oplacono_do:
        # Stripe przyjmuje koniec okresu probnego najwczesniej za 48 h.
        koniec = datetime.combine(date.fromisoformat(oplacono_do), datetime.min.time(), timezone.utc)
        if koniec.timestamp() - time.time() > 2 * 86400 + 600:
            dane["subscription_data"]["trial_end"] = int(koniec.timestamp())
    sesja = _stripe("/checkout/sessions", dane)
    log.info("stripe: sesja platnosci dla kancelarii %s", kancelaria)
    return {"adres": sesja["url"]}


def utworz_portal(klient: str) -> dict:
    """Portal klienta Stripe: karta, faktury, rezygnacja."""
    if not wlaczone():
        raise BladPlatnosci("Platnosci nie sa skonfigurowane na tym serwerze.")
    sesja = _stripe("/billing_portal/sessions", {"customer": klient, "return_url": f"{ADRES}/",
                                                 "locale": "pl"})
    return {"adres": sesja["url"]}


# --- webhook -----------------------------------------------------------------


def sprawdz_podpis(tresc: bytes, naglowek: str, sekret: str | None = None,
                   teraz: float | None = None) -> None:
    """Naglowek Stripe-Signature: t=<czas>,v1=<hmac>[,v1=...]. Podpisane jest
    "<czas>.<surowa tresc>" kluczem whsec_."""
    sekret = WEBHOOK_SEKRET if sekret is None else sekret
    czesci = [p.split("=", 1) for p in (naglowek or "").split(",") if "=" in p]
    znacznik = next((v for k, v in czesci if k.strip() == "t"), "")
    podpisy = [v for k, v in czesci if k.strip() == "v1"]
    if not sekret or not znacznik.isdigit() or not podpisy:
        raise BladPodpisu("brak podpisu")
    if abs((teraz or time.time()) - int(znacznik)) > TOLERANCJA_S:
        raise BladPodpisu("podpis przeterminowany")
    oczekiwany = hmac.new(sekret.encode(), znacznik.encode() + b"." + tresc, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(oczekiwany, p) for p in podpisy):
        raise BladPodpisu("podpis sie nie zgadza")


def odczytaj_zdarzenie(tresc: bytes, naglowek: str) -> dict:
    sprawdz_podpis(tresc, naglowek)
    try:
        zdarzenie = json.loads(tresc)
    except ValueError:
        raise BladPodpisu("tresc to nie JSON")
    if not isinstance(zdarzenie, dict) or "type" not in zdarzenie:
        raise BladPodpisu("to nie zdarzenie Stripe")
    return zdarzenie


def kancelaria_faktury(faktura: dict) -> str:
    """Kancelaria z metadanych subskrypcji, ktore Stripe kopiuje na fakture."""
    szczegoly = ((faktura.get("parent") or {}).get("subscription_details") or {})
    return (szczegoly.get("metadata") or {}).get("kancelaria", "")


def subskrypcja_faktury(faktura: dict) -> str:
    szczegoly = ((faktura.get("parent") or {}).get("subscription_details") or {})
    return szczegoly.get("subscription") or ""


def koniec_okresu(faktura: dict) -> str | None:
    """Do kiedy faktura oplaca dostep: najpozniejszy koniec okresu jej pozycji."""
    konce = [((p.get("period") or {}).get("end") or 0)
             for p in ((faktura.get("lines") or {}).get("data") or [])]
    konce = [k for k in konce if k]
    return _data(max(konce)) if konce else None
