"""Abonament kancelarii oplacany przez Tpay (Open API).

Kancelaria placi za miesiac z gory: wlasciciel klika "Zaplac", my tworzymy
transakcje w Tpay i przekierowujemy go do panelu platnosci (karta, BLIK).
Po zaplacie Tpay wysyla powiadomienie na /api/tpay/powiadomienie, a my
przesuwamy kancelarii date "oplacono_do" o miesiac.

Konfiguracja (w chmurze z sekretu notarai/tpay w Secrets Manager):
  TPAY_CLIENT_ID, TPAY_CLIENT_SECRET   klucze Open API z panelu Tpay
  TPAY_KOD_BEZPIECZENSTWA             kod z panelu: Powiadomienia -> Bezpieczenstwo
                                      (opcjonalny, dodatkowa suma md5)
  TPAY_SRODOWISKO                     "produkcja" (domyslnie) albo "sandbox"
  PIECZAPP_ABONAMENT_ZL               cena miesiaca brutto, np. "199.00"
  PIECZAPP_ADRES                      publiczny adres aplikacji, np. https://app.notarai.pl

Powiadomieniu wierzymy tylko z waznym podpisem JWS. Certyfikat podpisu
pobieramy z adresu x5u, ale tylko z hosta Tpay, i sprawdzamy, ze wystawilo
go CA Tpay zapisane w repozytorium (certyfikaty/) - nie to pobrane z sieci.

Zero danych osobowych w logach: adres platnika idzie tylko do Tpay.
"""
import base64
import calendar
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

log = logging.getLogger("pieczapp.platnosci")

CLIENT_ID = os.getenv("TPAY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("TPAY_CLIENT_SECRET", "")
KOD_BEZPIECZENSTWA = os.getenv("TPAY_KOD_BEZPIECZENSTWA", "")
SANDBOX = os.getenv("TPAY_SRODOWISKO", "produkcja").lower() == "sandbox"
CENA = os.getenv("PIECZAPP_ABONAMENT_ZL", "")
ADRES = os.getenv("PIECZAPP_ADRES", "").rstrip("/")
# Po terminie kancelaria pracuje jeszcze kilka dni - przelew z banku albo
# zapomniany BLIK nie moze odciac notariusza w srodku aktu.
KARENCJA_DNI = int(os.getenv("PIECZAPP_KARENCJA_DNI", "3"))
OKRES_PROBNY_DNI = int(os.getenv("PIECZAPP_OKRES_PROBNY_DNI", "14"))

API = "https://openapi.sandbox.tpay.com" if SANDBOX else "https://api.tpay.com"
HOST_CERTYFIKATOW = "https://secure.sandbox.tpay.com" if SANDBOX else "https://secure.tpay.com"
NAZWA_CERTYFIKATU = "notification.sandbox.tpay.com" if SANDBOX else "notification.tpay.com"
_CA = Path(__file__).parent / "certyfikaty" / (
    "tpay-jws-root-sandbox.pem" if SANDBOX else "tpay-jws-root.pem")

PREFIKS_OPISU = "abonament|"


class BladPlatnosci(Exception):
    """Tpay odrzucil zadanie albo jest nieosiagalny."""


class BladPodpisu(Exception):
    """Powiadomienie bez waznego podpisu Tpay - nie wierzymy mu."""


def wlaczone() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET and CENA and ADRES)


def cena() -> str:
    return f"{float(CENA):.2f}" if CENA else ""


# --- daty abonamentu ---------------------------------------------------------


def dzis() -> date:
    return datetime.now(timezone.utc).date()


def _plus_miesiac(d: date) -> date:
    rok, miesiac = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(rok, miesiac, min(d.day, calendar.monthrange(rok, miesiac)[1]))


def przedluz(oplacono_do: str | None, teraz: date | None = None) -> str:
    """Nowa data po zaplacie za miesiac. Wplata przed terminem dolicza sie
    do konca biezacego okresu; po terminie miesiac liczy sie od dzis."""
    teraz = teraz or dzis()
    start = teraz
    if oplacono_do:
        start = max(teraz, date.fromisoformat(oplacono_do))
    return _plus_miesiac(start).isoformat()


def na_probe(teraz: date | None = None) -> str:
    return ((teraz or dzis()) + timedelta(days=OKRES_PROBNY_DNI)).isoformat()


def stan(wpis: dict, teraz: date | None = None) -> dict:
    """Stan abonamentu kancelarii. Bez daty "oplacono_do" kancelaria nie
    placi przez Tpay (np. umowa poza systemem) i nic jej nie blokujemy."""
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


# --- Open API ----------------------------------------------------------------

_TOKEN: dict = {"wartosc": "", "wygasa": 0.0}
_ZAMEK = threading.Lock()


def _klient() -> httpx.Client:
    return httpx.Client(timeout=20)


def _token() -> str:
    """Token OAuth (client_credentials). Zyje ok. 2 h - odnawiamy z zapasem."""
    with _ZAMEK:
        if _TOKEN["wartosc"] and time.monotonic() < _TOKEN["wygasa"]:
            return _TOKEN["wartosc"]
        with _klient() as http:
            odp = http.post(f"{API}/oauth/auth",
                            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET})
        if odp.status_code != 200:
            log.warning("tpay: autoryzacja odrzucona (HTTP %s)", odp.status_code)
            raise BladPlatnosci("Bramka platnosci odrzucila klucze. Sprawdz sekret notarai/tpay.")
        dane = odp.json()
        _TOKEN["wartosc"] = dane["access_token"]
        _TOKEN["wygasa"] = time.monotonic() + max(60, int(dane.get("expires_in", 7200)) - 300)
        return _TOKEN["wartosc"]


def utworz_transakcje(kancelaria: str, nazwa: str, email: str) -> dict:
    """Transakcja za jeden miesiac. Zwraca adres panelu platnosci Tpay.

    Kancelarie rozpoznajemy po hiddenDescription - Tpay odsyla go w
    powiadomieniu jako tr_crc. Klientow nie widza tego pola.
    """
    if not wlaczone():
        raise BladPlatnosci("Platnosci nie sa skonfigurowane na tym serwerze.")
    tresc = {
        "amount": float(cena()),
        "description": "notarai - abonament na 1 miesiac",
        "hiddenDescription": f"{PREFIKS_OPISU}{kancelaria}|{secrets.token_hex(4)}",
        "payer": {"email": email, "name": nazwa[:255]},
        "callbacks": {
            "payerUrls": {"success": f"{ADRES}/?platnosc=ok", "error": f"{ADRES}/?platnosc=blad"},
            "notification": {"url": f"{ADRES}/api/tpay/powiadomienie"},
        },
    }
    with _klient() as http:
        odp = http.post(f"{API}/transactions", json=tresc,
                        headers={"Authorization": f"Bearer {_token()}"})
    dane = odp.json() if odp.headers.get("content-type", "").startswith("application/json") else {}
    if odp.status_code >= 300 or not dane.get("transactionPaymentUrl"):
        # Kody bledow Tpay nie zawieraja danych osobowych, tresc zadania - tak.
        kody = [b.get("errorCode") for b in dane.get("errors", []) if isinstance(b, dict)]
        log.warning("tpay: transakcja odrzucona (HTTP %s, %s)", odp.status_code, kody)
        raise BladPlatnosci("Bramka platnosci nie przyjela zlecenia. Sprobuj za chwile.")
    log.info("tpay: transakcja %s dla kancelarii %s", dane.get("title", "?"), kancelaria)
    return {"adres": dane["transactionPaymentUrl"], "tytul": dane.get("title", "")}


# --- powiadomienia -----------------------------------------------------------

_CERTYFIKATY: dict[str, tuple[float, x509.Certificate]] = {}
_DOBA = 24 * 3600


def _b64url(dane: str) -> bytes:
    return base64.urlsafe_b64decode(dane + "=" * (-len(dane) % 4))


def _zaufane_ca() -> list[x509.Certificate]:
    return x509.load_pem_x509_certificates(_CA.read_bytes())


def _certyfikat(x5u: str) -> x509.Certificate:
    """Certyfikat podpisu z x5u - tylko z hosta Tpay, sprawdzony wzgledem CA
    z repozytorium. Pamietamy go przez dobe."""
    # Ukosnik po hoscie: sam prefiks przepuscilby secure.tpay.com.zly.pl.
    if not x5u.startswith(HOST_CERTYFIKATOW + "/"):
        raise BladPodpisu("x5u spoza Tpay")
    zapis = _CERTYFIKATY.get(x5u)
    if zapis and time.monotonic() - zapis[0] < _DOBA:
        return zapis[1]
    with _klient() as http:
        odp = http.get(x5u)
    if odp.status_code != 200:
        raise BladPodpisu("nie pobrano certyfikatu")
    cert = x509.load_pem_x509_certificate(odp.content)
    sprawdz_certyfikat(cert)
    _CERTYFIKATY[x5u] = (time.monotonic(), cert)
    return cert


def sprawdz_certyfikat(cert: x509.Certificate, ca: list[x509.Certificate] | None = None) -> None:
    ca = _zaufane_ca() if ca is None else ca
    teraz = datetime.now(timezone.utc)
    if not cert.not_valid_before_utc <= teraz <= cert.not_valid_after_utc:
        raise BladPodpisu("certyfikat poza okresem waznosci")
    nazwy = [a.value for a in cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)]
    if nazwy != [NAZWA_CERTYFIKATU]:
        raise BladPodpisu("certyfikat nie dla powiadomien Tpay")
    for wystawca in ca:
        try:
            cert.verify_directly_issued_by(wystawca)
            return
        except Exception:  # noqa: BLE001 - nie ten wystawca, probujemy dalej
            continue
    raise BladPodpisu("certyfikat nie od CA Tpay")


def sprawdz_podpis(tresc: bytes, jws: str, cert: x509.Certificate | None = None) -> None:
    """JWS z odlaczona trescia (RFC 7515): naglowek..podpis, a podpisane
    jest naglowek + "." + base64url(surowa tresc zadania)."""
    czesci = (jws or "").split(".")
    if len(czesci) != 3 or not czesci[0] or not czesci[2]:
        raise BladPodpisu("brak podpisu JWS")
    try:
        naglowek = json.loads(_b64url(czesci[0]))
    except ValueError:
        raise BladPodpisu("zly naglowek JWS")
    if naglowek.get("alg") not in (None, "RS256"):
        raise BladPodpisu("nieznany algorytm podpisu")
    cert = cert or _certyfikat(str(naglowek.get("x5u", "")))
    podpisane = (czesci[0] + "." + base64.urlsafe_b64encode(tresc).decode().rstrip("=")).encode()
    try:
        cert.public_key().verify(_b64url(czesci[2]), podpisane, padding.PKCS1v15(), hashes.SHA256())
    except Exception:  # noqa: BLE001 - InvalidSignature i zle zakodowany podpis
        _CERTYFIKATY.clear()   # moze Tpay wymienil certyfikat
        raise BladPodpisu("podpis sie nie zgadza")


def odczytaj_powiadomienie(tresc: bytes, jws: str) -> dict:
    """Pola powiadomienia o rozliczeniu, po sprawdzeniu podpisu i sumy md5."""
    sprawdz_podpis(tresc, jws)
    pola = {k: v[0] for k, v in parse_qs(tresc.decode("utf-8"), keep_blank_values=True).items()}
    for wymagane in ("id", "tr_id", "tr_amount", "tr_crc", "tr_status"):
        if wymagane not in pola:
            raise BladPodpisu(f"brak pola {wymagane}")
    if KOD_BEZPIECZENSTWA:
        kwota = f"{float(pola['tr_amount']):.2f}"
        suma = hashlib.md5(
            (pola["id"] + pola["tr_id"] + kwota + pola["tr_crc"] + KOD_BEZPIECZENSTWA).encode()
        ).hexdigest()
        if not secrets.compare_digest(suma, pola.get("md5sum", "")):
            raise BladPodpisu("suma md5 sie nie zgadza")
    return pola


def kancelaria_z_opisu(tr_crc: str) -> str:
    """"abonament|<kancelaria>|<losowe>" -> identyfikator kancelarii albo ""."""
    if not tr_crc.startswith(PREFIKS_OPISU):
        return ""
    return tr_crc[len(PREFIKS_OPISU):].split("|", 1)[0]
