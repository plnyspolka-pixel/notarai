"""Skaner bezpieczenstwa strony i poczty kancelarii - publiczne API bez logowania.

POST /api/skan  {"adres": "kancelaria-x.pl", "email": "", "zgoda_wycieki": false}

Strona notarai.pl/bezpieczenstwo/ pokazuje wynik 0-100, ocene A-F i liste
ustalen z instrukcja naprawy.

Tylko kontrole PASYWNE - to samo, co widzi kazda przegladarka i kazdy serwer
poczty: rekordy DNS (SPF, DMARC, DKIM, MTA-STS, CAA, DNSSEC), certyfikat i
wersja TLS, naglowki odpowiedzi strony glownej, zasoby wpisane w jej kod.
NIE skanujemy portow, nie szukamy odslonietych plikow (.env, .git), nie
testujemy podatnosci. Na cudzej domenie, bez zgody wlasciciela, to bylby
test penetracyjny, a wynik zobaczylby kazdy, kto wpisze adres.

Ochrona przed SSRF: przed kazdym polaczeniem (takze po przekierowaniu) nazwa
musi wskazywac wylacznie adresy publiczne; tylko porty 80 i 443, tylko GET,
limit rozmiaru odpowiedzi.

RODO: nie zapisujemy i nie logujemy adresu domeny ani e-maila (w nazwie
domeny bywa imie i nazwisko notariusza). Do logow trafia wynik i czas.
Sprawdzenie e-maila w Have I Been Pwned tylko po zgodzie odwiedzajacego i
tylko gdy skonfigurowano klucz (PIECZAPP_HIBP_KLUCZ - w chmurze referencja
do sekretu w Secrets Manager, nie wartosc w env).
"""
from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from urllib.parse import quote, urljoin, urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import autoryzacja
from kalkulator import Limit

log = logging.getLogger("pieczapp.skan")

WLACZONY = os.getenv("PIECZAPP_SKAN", "true").lower() == "true"
NA_IP_GODZINA = int(os.getenv("PIECZAPP_SKAN_NA_IP", "12"))
NA_DOBE = int(os.getenv("PIECZAPP_SKAN_NA_DOBE", "600"))
HIBP_KLUCZ = os.getenv("PIECZAPP_HIBP_KLUCZ", "").strip()
CZAS = 6.0                 # s na jedno polaczenie
MAX_ODPOWIEDZ = 1_500_000  # bajtow HTML strony glownej
MAX_PRZEKIEROWAN = 5
CACHE_S = 900
AGENT = "notarai-skan-bezpieczenstwa/1.0 (+https://notarai.pl/bezpieczenstwo/)"

router = APIRouter(prefix="/api/skan", tags=["skan"])
limit_skanu = Limit(NA_IP_GODZINA, NA_DOBE)


class BladSkanu(Exception):
    """Komunikat dla odwiedzajacego (po polsku, bez szczegolow technicznych)."""


# --- adres i SSRF ----------------------------------------------------------

_ETYKIETA = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def normalizuj_domene(adres: str) -> str:
    """'https://www.Kancelaria-X.pl/kontakt' -> 'www.kancelaria-x.pl'."""
    tekst = (adres or "").strip().lower()
    if not tekst or len(tekst) > 300:
        raise BladSkanu("Podaj adres strony kancelarii, np. kancelaria-kowalski.pl.")
    if "://" not in tekst:
        tekst = "http://" + tekst
    try:
        czesci = urlsplit(tekst)
        host = (czesci.hostname or "").rstrip(".")
        if czesci.port not in (None, 80, 443):
            raise BladSkanu("Sprawdzamy tylko zwykłe adresy stron (bez numeru portu).")
        host = host.encode("idna").decode("ascii")
    except BladSkanu:
        raise
    except (ValueError, UnicodeError):
        raise BladSkanu("To nie wygląda na adres strony.") from None
    try:
        ipaddress.ip_address(host)
        raise BladSkanu("Podaj nazwę domeny, a nie adres IP.")
    except ValueError:
        pass
    etykiety = host.split(".")
    if len(etykiety) < 2 or len(host) > 253 or not all(_ETYKIETA.match(e) for e in etykiety) \
            or not re.match(r"^[a-z]{2,63}$|^xn--[a-z0-9-]+$", etykiety[-1]):
        raise BladSkanu("To nie wygląda na adres strony. Przykład: kancelaria-kowalski.pl.")
    if etykiety[-1] in ("local", "internal", "localhost", "lan", "home", "corp", "test", "invalid"):
        raise BladSkanu("Ten adres nie jest dostępny w internecie.")
    return host


def domena_glowna(host: str) -> str:
    """Domena do kontroli poczty i DNS: bez 'www.'."""
    return host[4:] if host.startswith("www.") and host.count(".") >= 2 else host


def adresy_publiczne(host: str) -> list[str]:
    """Adresy IP nazwy; BladSkanu, gdy nazwa nie istnieje albo wskazuje siec wewnetrzna."""
    try:
        adresy = sorted({a[4][0].split("%")[0] for a in socket.getaddrinfo(host, None)})
    except (OSError, UnicodeError):
        raise BladSkanu("Ta domena nie istnieje albo nie wskazuje żadnego serwera.") from None
    if not adresy or not all(ipaddress.ip_address(a).is_global for a in adresy):
        raise BladSkanu("Ten adres nie jest dostępny w internecie.")
    return adresy


# --- DNS -------------------------------------------------------------------


def _resolver():
    import dns.resolver
    r = dns.resolver.Resolver()
    r.timeout, r.lifetime = 2.5, 4.0
    return r


def txt(nazwa: str) -> list[str]:
    import dns.exception
    import dns.resolver
    try:
        odp = _resolver().resolve(nazwa, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return []
    except dns.exception.DNSException:
        return []
    return [b"".join(r.strings).decode("utf-8", "replace") for r in odp]


def rekordy(nazwa: str, typ: str) -> list[str]:
    import dns.exception
    try:
        return [r.to_text() for r in _resolver().resolve(nazwa, typ)]
    except dns.exception.DNSException:
        return []


DKIM_SELEKTORY = ("google", "selector1", "selector2", "default", "dkim", "mail", "k1", "k2",
                  "s1", "s2", "smtp", "key1", "mx", "zoho", "protonmail", "mxvault")


def zbierz_dns(domena: str) -> dict:
    """Wszystkie rekordy potrzebne do oceny - rownolegle, kazdy z limitem czasu."""
    zadania = {
        "mx": lambda: rekordy(domena, "MX"),
        "txt": lambda: txt(domena),
        "dmarc": lambda: txt("_dmarc." + domena),
        "mta_sts": lambda: txt("_mta-sts." + domena),
        "tls_rpt": lambda: txt("_smtp._tls." + domena),
        "caa": lambda: rekordy(domena, "CAA"),
        "dnskey": lambda: rekordy(domena, "DNSKEY"),
    }
    for s in DKIM_SELEKTORY:
        zadania["dkim:" + s] = (lambda s=s: txt(f"{s}._domainkey.{domena}"))
    with ThreadPoolExecutor(max_workers=12) as pula:
        przyszle = {k: pula.submit(f) for k, f in zadania.items()}
        wyniki = {}
        for k, p in przyszle.items():
            try:
                wyniki[k] = p.result(timeout=8)
            except Exception:  # noqa: BLE001 - brak odpowiedzi = brak rekordu
                wyniki[k] = []
    # Klucz z pustym "p=" jest odwolany - nie liczy sie.
    dkim = [s for s in DKIM_SELEKTORY
            if any(re.search(r"(?:^|;)\s*p=[A-Za-z0-9+/]", r) for r in wyniki.pop("dkim:" + s))]
    wyniki["dkim"] = dkim
    return wyniki


# --- HTTPS i strona --------------------------------------------------------


def sprawdz_tls(host: str) -> dict:
    """Certyfikat i wersja TLS z polaczenia na 443 (z weryfikacja jak w przegladarce)."""
    adresy_publiczne(host)
    kontekst = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=CZAS) as gniazdo:
            with kontekst.wrap_socket(gniazdo, server_hostname=host) as tls:
                cert = tls.getpeercert() or {}
                wersja = tls.version() or ""
    except ssl.SSLCertVerificationError as e:
        powod = (getattr(e, "verify_message", "") or str(e)).lower()
        if "expired" in powod:
            rodzaj = "wygasl"
        elif "hostname" in powod or "ip address mismatch" in powod:
            rodzaj = "inna_domena"
        elif "self" in powod:
            rodzaj = "samopodpisany"
        else:
            rodzaj = "nieprawidlowy"
        return {"dziala": False, "blad_certyfikatu": rodzaj}
    except (OSError, ssl.SSLError):
        return {"dziala": False}
    do = cert.get("notAfter")
    wazny_do = datetime.fromtimestamp(ssl.cert_time_to_seconds(do), tz=timezone.utc) if do else None
    wystawca = ""
    for pole in cert.get("issuer", ()):
        for klucz, wartosc in pole:
            if klucz == "organizationName":
                wystawca = wartosc
    return {"dziala": True, "wersja": wersja, "wystawca": wystawca,
            "wazny_do": wazny_do.date().isoformat() if wazny_do else None,
            "dni": (wazny_do - datetime.now(timezone.utc)).days if wazny_do else None}


def pobierz(url: str) -> dict:
    """GET z recznym sledzeniem przekierowan; kazdy host sprawdzony pod katem SSRF."""
    historia = []
    with httpx.Client(follow_redirects=False, timeout=CZAS, verify=True,
                      headers={"User-Agent": AGENT, "Accept": "text/html,*/*;q=0.5"}) as klient:
        for _ in range(MAX_PRZEKIEROWAN + 1):
            czesci = urlsplit(url)
            if czesci.scheme not in ("http", "https") or czesci.port not in (None, 80, 443):
                raise BladSkanu("Strona przekierowuje pod nietypowy adres.")
            adresy_publiczne(czesci.hostname or "")
            with klient.stream("GET", url) as odp:
                historia.append({"url": url, "status": odp.status_code})
                if odp.is_redirect and odp.headers.get("location"):
                    url = urljoin(url, odp.headers["location"])
                    continue
                tresc = b""
                for kawalek in odp.iter_bytes():
                    tresc += kawalek
                    if len(tresc) > MAX_ODPOWIEDZ:
                        break
                return {"url": url, "status": odp.status_code, "naglowki": odp.headers,
                        "ciasteczka": odp.headers.get_list("set-cookie"),
                        "html": tresc[:MAX_ODPOWIEDZ].decode(odp.encoding or "utf-8", "replace"),
                        "historia": historia}
    raise BladSkanu("Strona przekierowuje zbyt wiele razy.")


def sprobuj(url: str) -> dict | None:
    try:
        return pobierz(url)
    except BladSkanu:
        raise
    except (httpx.HTTPError, OSError, ssl.SSLError):
        return None


# --- znane zasoby zewnetrzne ----------------------------------------------

# sufiks hosta -> (nazwa, rodzaj). rodzaj: sledzenie | czcionki | osadzenie | cdn | czat
ZEWNETRZNE = (
    ("googletagmanager.com", "Google Tag Manager", "sledzenie"),
    ("google-analytics.com", "Google Analytics", "sledzenie"),
    ("analytics.google.com", "Google Analytics", "sledzenie"),
    ("doubleclick.net", "Google Ads (DoubleClick)", "sledzenie"),
    ("googleadservices.com", "Google Ads", "sledzenie"),
    ("connect.facebook.net", "Piksel Meta (Facebook)", "sledzenie"),
    ("facebook.com", "Facebook", "osadzenie"),
    ("hotjar.com", "Hotjar", "sledzenie"),
    ("clarity.ms", "Microsoft Clarity", "sledzenie"),
    ("snap.licdn.com", "LinkedIn Insight", "sledzenie"),
    ("analytics.tiktok.com", "Piksel TikTok", "sledzenie"),
    ("smartlook.com", "Smartlook", "sledzenie"),
    ("yandex.ru", "Yandex Metrica", "sledzenie"),
    ("mc.yandex.", "Yandex Metrica", "sledzenie"),
    ("fonts.googleapis.com", "Google Fonts", "czcionki"),
    ("fonts.gstatic.com", "Google Fonts", "czcionki"),
    ("use.typekit.net", "Adobe Fonts", "czcionki"),
    ("youtube.com", "YouTube", "osadzenie"),
    ("youtube-nocookie.com", "YouTube (bez ciasteczek)", "osadzenie"),
    ("ytimg.com", "YouTube", "osadzenie"),
    ("maps.googleapis.com", "Mapy Google", "osadzenie"),
    ("maps.google.com", "Mapy Google", "osadzenie"),
    ("google.com", "Google (mapy, reCAPTCHA)", "osadzenie"),
    ("gstatic.com", "Google (zasoby)", "osadzenie"),
    ("cdn.jsdelivr.net", "jsDelivr (CDN)", "cdn"),
    ("cdnjs.cloudflare.com", "cdnjs (CDN)", "cdn"),
    ("unpkg.com", "unpkg (CDN)", "cdn"),
    ("code.jquery.com", "jQuery CDN", "cdn"),
    ("ajax.googleapis.com", "Google CDN", "cdn"),
    ("embed.tawk.to", "Tawk.to (czat)", "czat"),
    ("livechatinc.com", "LiveChat", "czat"),
    ("smartsupp.com", "Smartsupp (czat)", "czat"),
)

_ZASOB = re.compile(r"""<(script|link|iframe|img|source|embed)\b[^>]*?\b(?:src|href)\s*=\s*["']([^"']+)["']""",
                    re.I)
_GENERATOR = re.compile(r"""<meta[^>]+name\s*=\s*["']generator["'][^>]*content\s*=\s*["']([^"']+)["']""", re.I)
_GENERATOR2 = re.compile(r"""<meta[^>]+content\s*=\s*["']([^"']+)["'][^>]*name\s*=\s*["']generator["']""", re.I)
_FORMULARZ = re.compile(r"""<form\b[^>]*\baction\s*=\s*["'](http://[^"']+)["']""", re.I)


def analizuj_html(html: str, url: str) -> dict:
    gospodarz = (urlsplit(url).hostname or "").lower()
    glowna = domena_glowna(gospodarz)
    zewnetrzne: dict[str, dict] = {}
    mieszane = 0
    for znacznik, adres in _ZASOB.findall(html):
        pelny = urljoin(url, adres.strip())
        czesci = urlsplit(pelny)
        if czesci.scheme not in ("http", "https"):
            continue
        host = (czesci.hostname or "").lower()
        if url.startswith("https:") and czesci.scheme == "http" and znacznik.lower() != "link":
            mieszane += 1
        if not host or host == gospodarz or host.endswith("." + glowna) or host == glowna:
            continue
        nazwa, rodzaj = host, "inne"
        for sufiks, n, r in ZEWNETRZNE:
            if host == sufiks or host.endswith("." + sufiks) or (sufiks.endswith(".") and sufiks in host):
                nazwa, rodzaj = n, r
                break
        wpis = zewnetrzne.setdefault(nazwa, {"nazwa": nazwa, "rodzaj": rodzaj, "hosty": []})
        if host not in wpis["hosty"]:
            wpis["hosty"].append(host)
    generator = (_GENERATOR.search(html) or _GENERATOR2.search(html))
    generator = generator.group(1).strip()[:80] if generator else ""
    cms = ""
    niski = html.lower()
    if "wordpress" in generator.lower() or "/wp-content/" in niski or "/wp-includes/" in niski:
        cms = "WordPress"
    elif "joomla" in generator.lower() or "/media/jui/" in niski:
        cms = "Joomla"
    elif "wix.com" in generator.lower() or "static.wixstatic.com" in niski:
        cms = "Wix"
    elif "drupal" in generator.lower():
        cms = "Drupal"
    elif "webwave" in niski:
        cms = "WebWave"
    return {"zewnetrzne": sorted(zewnetrzne.values(), key=lambda z: (z["rodzaj"] != "sledzenie", z["nazwa"])),
            "mieszane": mieszane, "generator": generator, "cms": cms,
            "formularze_http": len(_FORMULARZ.findall(html))}


# --- ocena -----------------------------------------------------------------

KATEGORIE = (
    ("poczta", "Poczta i podszywanie się"),
    ("https", "Szyfrowanie i certyfikat"),
    ("naglowki", "Ochrona w przeglądarce"),
    ("prywatnosc", "RODO i ujawnione informacje"),
    ("domena", "Domena"),
)

# PHP: koniec wsparcia bezpieczenstwa (php.net/supported-versions)
PHP_KONIEC = {"7.4": date(2022, 11, 28), "8.0": date(2023, 11, 26), "8.1": date(2025, 12, 31),
              "8.2": date(2026, 12, 31), "8.3": date(2027, 12, 31), "8.4": date(2028, 12, 31)}


class Ocena:
    def __init__(self):
        self.ustalenia: list[dict] = []
        self.punkty = {k: [0.0, 0.0] for k, _ in KATEGORIE}

    def dodaj(self, kategoria: str, id_: str, poziom: str, tytul: str, opis: str,
              naprawa: str = "", zdobyte: float = 0, maks: float = 0) -> None:
        self.punkty[kategoria][0] += zdobyte
        self.punkty[kategoria][1] += maks
        self.ustalenia.append({"id": id_, "kategoria": kategoria, "poziom": poziom,
                               "tytul": tytul, "opis": opis, "naprawa": naprawa})


def ocen_poczte(o: Ocena, domena: str, dns_: dict) -> None:
    mx = dns_.get("mx", [])
    spf = [r for r in dns_.get("txt", []) if r.lower().startswith("v=spf1")]
    dmarc = [r for r in dns_.get("dmarc", []) if r.lower().replace(" ", "").startswith("v=dmarc1")]
    adres = f"biuro@{domena}"
    if mx:
        o.dodaj("poczta", "mx", "info", "Domena odbiera pocztę",
                f"Serwery poczty: {', '.join(sorted(m.split()[-1].rstrip('.') for m in mx)[:4])}.")
    else:
        o.dodaj("poczta", "mx", "info", "Domena nie odbiera poczty",
                "Brak rekordu MX. Jeśli kancelaria nie używa poczty w tej domenie, i tak warto ją zablokować "
                "rekordami SPF „v=spf1 -all” i DMARC „p=reject”, żeby nikt nie wysyłał z niej fałszywych wiadomości.")

    # SPF
    if not spf:
        o.dodaj("poczta", "spf", "krytyczne", "Brak rekordu SPF",
                "Serwery poczty nie wiedzą, kto może wysyłać wiadomości z Twojej domeny.",
                "Dodaj w DNS rekord TXT, np. „v=spf1 include:<serwer Twojej poczty> -all”. "
                "Dostawca poczty (home.pl, OVH, Google, Microsoft) podaje gotową wartość.", 0, 10)
    elif len(spf) > 1:
        o.dodaj("poczta", "spf", "krytyczne", "Kilka rekordów SPF naraz",
                "Przy dwóch rekordach SPF serwery poczty uznają oba za błędne - tak, jakby SPF nie było.",
                "Połącz wpisy w jeden rekord TXT zaczynający się od „v=spf1”.", 0, 10)
    else:
        rekord = spf[0].lower()
        if "+all" in rekord or rekord.rstrip().endswith(" all"):
            o.dodaj("poczta", "spf", "krytyczne", "SPF pozwala wysyłać każdemu („+all”)",
                    "Rekord SPF wprost zezwala dowolnemu serwerowi na świecie na wysyłanie poczty z Twojej domeny.",
                    "Zmień końcówkę rekordu na „-all” (albo „~all”).", 0, 10)
        elif "?all" in rekord:
            o.dodaj("poczta", "spf", "uwaga", "SPF bez rozstrzygnięcia („?all”)",
                    "Rekord nie mówi, co zrobić z pocztą z obcych serwerów, więc nic nie blokuje.",
                    "Zmień końcówkę na „-all” albo „~all”.", 3, 10)
        elif "~all" in rekord:
            o.dodaj("poczta", "spf", "ok", "SPF ustawiony („~all”)",
                    "Obce serwery są oznaczane jako podejrzane. Pełną ochronę daje dopiero razem z DMARC.",
                    "Gdy DMARC działa bez zastrzeżeń, rozważ zaostrzenie do „-all”.", 9, 10)
        elif "-all" in rekord:
            o.dodaj("poczta", "spf", "ok", "SPF ustawiony rygorystycznie („-all”)",
                    "Tylko wskazane serwery mogą wysyłać pocztę z Twojej domeny.", "", 10, 10)
        else:
            o.dodaj("poczta", "spf", "uwaga", "SPF bez końcówki „all”",
                    "Rekord nie określa, co zrobić z pocztą z pozostałych serwerów.",
                    "Dodaj na końcu „-all” albo „~all”.", 4, 10)

    # DMARC
    polityka = ""
    if dmarc:
        m = re.search(r"(?:^|;)\s*p\s*=\s*(\w+)", dmarc[0].lower())
        polityka = m.group(1) if m else ""
    if not dmarc:
        o.dodaj("poczta", "dmarc", "krytyczne", f"Każdy może podszyć się pod {adres}",
                "Domena nie ma rekordu DMARC. Oszust może wysłać do klienta e-mail „z kancelarii” "
                "- np. z innym numerem rachunku do wpłaty ceny albo taksy - a skrzynka klienta go przyjmie.",
                f"Dodaj rekord TXT „_dmarc.{domena}” o treści „v=DMARC1; p=quarantine; rua=mailto:dmarc@{domena}”. "
                "Po kilku tygodniach bez problemów zmień na „p=reject”.", 0, 14)
    elif polityka == "reject":
        o.dodaj("poczta", "dmarc", "ok", "DMARC odrzuca fałszywe wiadomości („p=reject”)",
                "Najlepsze ustawienie: poczta podszywająca się pod kancelarię jest odrzucana.", "", 14, 14)
    elif polityka == "quarantine":
        o.dodaj("poczta", "dmarc", "ok", "DMARC kieruje fałszywki do spamu („p=quarantine”)",
                "Dobra ochrona. Fałszywe wiadomości trafiają do spamu zamiast do skrzynki odbiorczej.",
                "Gdy raporty DMARC nie pokazują problemów, zmień na „p=reject”.", 11, 14)
    else:
        o.dodaj("poczta", "dmarc", "uwaga", "DMARC tylko obserwuje („p=none”)",
                f"Rekord DMARC istnieje, ale niczego nie blokuje - fałszywe wiadomości „od {adres}” nadal dochodzą.",
                "Zmień „p=none” na „p=quarantine”, a potem na „p=reject”.", 5, 14)
    if dmarc and "rua=" not in dmarc[0].lower():
        o.dodaj("poczta", "dmarc_rua", "info", "DMARC nie wysyła raportów",
                "Bez adresu „rua=” nie dowiesz się, kto próbuje wysyłać pocztę w Twoim imieniu.",
                "Dopisz „rua=mailto:adres@twojadomena.pl”. Raporty czyta np. darmowy parsedmarc.")

    # DKIM
    if dns_.get("dkim"):
        o.dodaj("poczta", "dkim", "ok", "Poczta jest podpisywana (DKIM)",
                f"Znaleziono klucz DKIM (selektor: {', '.join(dns_['dkim'][:3])}).", "", 4, 4)
    elif mx:
        o.dodaj("poczta", "dkim", "uwaga", "Nie znaleźliśmy podpisu DKIM",
                "Sprawdziliśmy najczęstsze selektory. Klucz może istnieć pod inną nazwą - jeśli nie istnieje, "
                "wiadomości kancelarii łatwiej sfałszować i częściej trafiają do spamu.",
                "Włącz DKIM w panelu dostawcy poczty i dodaj podany przez niego rekord TXT.", 0, 4)

    # MTA-STS
    if mx:
        if any(r.lower().startswith("v=stsv1") for r in dns_.get("mta_sts", [])):
            o.dodaj("poczta", "mta_sts", "ok", "Szyfrowanie poczty wymuszone (MTA-STS)",
                    "Serwery wysyłające muszą łączyć się z Twoją pocztą szyfrowanym kanałem.", "", 2, 2)
        else:
            o.dodaj("poczta", "mta_sts", "info", "Brak MTA-STS",
                    "Poczta do kancelarii może być w drodze przechwycona przez wymuszenie połączenia bez szyfrowania.",
                    "Włącz MTA-STS (Google Workspace i Microsoft 365 to obsługują) - to krok dla zaawansowanych.", 0, 2)


def ocen_https(o: Ocena, tls: dict, http: dict | None, https: dict | None) -> None:
    if not tls.get("dziala"):
        rodzaj = tls.get("blad_certyfikatu")
        opisy = {"wygasl": "Certyfikat strony wygasł. Przeglądarki pokazują klientom czerwone ostrzeżenie.",
                 "inna_domena": "Certyfikat jest wystawiony na inną domenę. Przeglądarki ostrzegają o próbie oszustwa.",
                 "samopodpisany": "Certyfikat jest samopodpisany - przeglądarki mu nie ufają."}
        o.dodaj("https", "https", "krytyczne",
                "Strona nie działa bezpiecznie przez HTTPS" if not rodzaj else "Nieprawidłowy certyfikat strony",
                opisy.get(rodzaj, "Połączenie z kancelarią nie jest szyfrowane. Dane z formularzy można podsłuchać."),
                "Włącz darmowy certyfikat Let's Encrypt w panelu hostingu i ustaw przekierowanie na https://.", 0, 26)
        return
    o.dodaj("https", "https", "ok", "Strona działa przez HTTPS",
            f"Certyfikat wystawił: {tls.get('wystawca') or 'nieznany wystawca'}.", "", 10, 10)
    dni = tls.get("dni")
    if dni is not None and dni < 14:
        o.dodaj("https", "cert_dni", "uwaga", f"Certyfikat wygasa za {max(dni, 0)} dni",
                "Po wygaśnięciu przeglądarki zablokują stronę ostrzeżeniem.",
                "Sprawdź, czy hosting odnawia certyfikat automatycznie.", 2, 4)
    else:
        o.dodaj("https", "cert_dni", "ok", "Certyfikat ważny",
                f"Ważny do {tls.get('wazny_do')}." if tls.get("wazny_do") else "Certyfikat jest ważny.", "", 4, 4)
    wersja = tls.get("wersja", "")
    if wersja in ("TLSv1.3", "TLSv1.2"):
        o.dodaj("https", "tls", "ok", f"Nowoczesne szyfrowanie ({wersja.replace('v', ' ')})", "", "", 4, 4)
    elif wersja:
        o.dodaj("https", "tls", "krytyczne", f"Przestarzałe szyfrowanie ({wersja})",
                "Serwer używa wersji TLS uznanej za niebezpieczną.",
                "Wyłącz TLS 1.0 i 1.1 w ustawieniach serwera albo poproś o to hosting.", 0, 4)
    if http is not None:
        if http["url"].startswith("https://"):
            o.dodaj("https", "przekierowanie", "ok", "Wersja http:// przekierowuje na https://", "", "", 4, 4)
        else:
            o.dodaj("https", "przekierowanie", "uwaga", "Strona działa też bez szyfrowania (http://)",
                    "Klient, który wpisze adres bez „https”, łączy się bez szyfrowania.",
                    "Ustaw stałe przekierowanie (301) z http:// na https://.", 0, 4)
    if https is not None:
        hsts = https["naglowki"].get("strict-transport-security", "")
        m = re.search(r"max-age\s*=\s*(\d+)", hsts)
        if m and int(m.group(1)) >= 15552000:
            o.dodaj("https", "hsts", "ok", "HSTS włączony", "Przeglądarka zawsze łączy się ze stroną szyfrowanym połączeniem.", "", 4, 4)
        elif m:
            o.dodaj("https", "hsts", "uwaga", "HSTS z krótkim czasem", "Ochrona wygasa zbyt szybko.",
                    "Ustaw „Strict-Transport-Security: max-age=31536000”.", 2, 4)
        else:
            o.dodaj("https", "hsts", "uwaga", "Brak HSTS",
                    "Przeglądarka może dać się nakłonić do połączenia bez szyfrowania (np. w publicznym Wi-Fi).",
                    "Dodaj nagłówek „Strict-Transport-Security: max-age=31536000”.", 0, 4)


def ocen_naglowki(o: Ocena, odp: dict | None) -> None:
    if odp is None:
        return
    n = odp["naglowki"]
    csp = n.get("content-security-policy", "")
    if csp:
        o.dodaj("naglowki", "csp", "ok", "Polityka treści (CSP) ustawiona", "", "", 5, 5)
    else:
        o.dodaj("naglowki", "csp", "uwaga", "Brak polityki treści (CSP)",
                "Gdy ktoś wstrzyknie na stronę obcy skrypt (np. przez dziurawą wtyczkę), przeglądarka go wykona.",
                "Dodaj nagłówek Content-Security-Policy - zacznij od trybu Report-Only.", 0, 5)
    if "frame-ancestors" in csp.lower() or n.get("x-frame-options"):
        o.dodaj("naglowki", "ramki", "ok", "Strona chroniona przed osadzaniem w ramce", "", "", 4, 4)
    else:
        o.dodaj("naglowki", "ramki", "uwaga", "Stronę można osadzić na cudzej witrynie",
                "Oszust może wyświetlić Twoją stronę w ramce na swojej stronie (clickjacking).",
                "Dodaj „X-Frame-Options: SAMEORIGIN” albo „frame-ancestors 'self'” w CSP.", 0, 4)
    if n.get("x-content-type-options", "").lower() == "nosniff":
        o.dodaj("naglowki", "nosniff", "ok", "X-Content-Type-Options ustawiony", "", "", 2, 2)
    else:
        o.dodaj("naglowki", "nosniff", "uwaga", "Brak X-Content-Type-Options",
                "Przeglądarka może zinterpretować plik inaczej, niż zamierzono.",
                "Dodaj „X-Content-Type-Options: nosniff”.", 0, 2)
    if n.get("referrer-policy"):
        o.dodaj("naglowki", "referrer", "ok", "Referrer-Policy ustawiony", "", "", 2, 2)
    else:
        o.dodaj("naglowki", "referrer", "info", "Brak Referrer-Policy",
                "Adresy podstron kancelarii mogą trafiać do obcych serwisów, do których prowadzą linki.",
                "Dodaj „Referrer-Policy: strict-origin-when-cross-origin”.", 0, 2)
    ciasteczka = odp.get("ciasteczka", [])
    slabe = [c for c in ciasteczka
             if "secure" not in c.lower() or "httponly" not in c.lower()]
    if ciasteczka and slabe and odp["url"].startswith("https://"):
        o.dodaj("naglowki", "ciasteczka", "uwaga", f"Ciasteczka bez pełnej ochrony ({len(slabe)})",
                "Ciasteczka bez flag Secure i HttpOnly łatwiej przechwycić albo odczytać skryptem.",
                "Ustaw flagi Secure, HttpOnly i SameSite dla ciasteczek sesji.", 1, 3)
    elif ciasteczka:
        o.dodaj("naglowki", "ciasteczka", "ok", "Ciasteczka z flagami ochronnymi", "", "", 3, 3)


def ocen_prywatnosc(o: Ocena, odp: dict | None, html: dict, dzis: date) -> None:
    if odp is None:
        return
    sledzace = [z["nazwa"] for z in html["zewnetrzne"] if z["rodzaj"] == "sledzenie"]
    czcionki = [z["nazwa"] for z in html["zewnetrzne"] if z["rodzaj"] == "czcionki"]
    if sledzace:
        o.dodaj("prywatnosc", "sledzenie", "uwaga", f"Narzędzia śledzące w kodzie strony ({len(sledzace)})",
                f"{', '.join(dict.fromkeys(sledzace))}. Skrypty wpisane wprost w kod zwykle uruchamiają się, zanim "
                "odwiedzający wyrazi zgodę, a takie narzędzia wymagają wcześniejszej zgody (Prawo komunikacji elektronicznej, RODO).",
                "Ładuj narzędzia analityczne dopiero po zgodzie z banera cookies.", 0, 5)
    else:
        o.dodaj("prywatnosc", "sledzenie", "ok", "Brak narzędzi śledzących w kodzie strony",
                "Nie znaleźliśmy w kodzie strony głównej skryptów reklamowych ani analitycznych.", "", 5, 5)
    if czcionki:
        o.dodaj("prywatnosc", "czcionki", "uwaga", "Czcionki ładowane z serwerów zewnętrznych",
                f"{', '.join(dict.fromkeys(czcionki))}: przeglądarka klienta wysyła jego adres IP do Google bez zgody. "
                "Sąd w Monachium (2022) uznał to za naruszenie RODO.",
                "Pobierz pliki czcionek i udostępniaj je z własnego serwera.", 1, 3)
    else:
        o.dodaj("prywatnosc", "czcionki", "ok", "Czcionki z własnego serwera", "", "", 3, 3)

    n = odp["naglowki"]
    ujawnione = []
    serwer = n.get("server", "")
    if re.search(r"\d", serwer):
        ujawnione.append(f"serwer: {serwer[:40]}")
    zasilane = n.get("x-powered-by", "")
    if zasilane:
        ujawnione.append(f"X-Powered-By: {zasilane[:40]}")
    if html["generator"] and re.search(r"\d", html["generator"]):
        ujawnione.append(f"generator: {html['generator']}")
    m = re.search(r"php/(\d+)\.(\d+)", zasilane.lower() + " " + serwer.lower())
    if m:
        wersja = f"{m.group(1)}.{m.group(2)}"
        koniec = PHP_KONIEC.get(wersja, date(2000, 1, 1) if float(wersja) < 7.4 else None)
        if koniec and koniec < dzis:
            o.dodaj("prywatnosc", "php", "krytyczne", f"PHP {wersja} bez poprawek bezpieczeństwa",
                    f"Wsparcie bezpieczeństwa dla PHP {wersja} skończyło się {koniec.strftime('%d.%m.%Y')}. "
                    "Nowe luki w tej wersji nie są już łatane.",
                    "Przełącz wersję PHP w panelu hostingu na aktualną (8.3 lub nowszą) i sprawdź działanie strony.", 0, 4)
    if ujawnione:
        o.dodaj("prywatnosc", "wersje", "uwaga", "Strona zdradza wersje oprogramowania",
                f"Publicznie widać: {'; '.join(ujawnione)}. Atakujący od razu wie, jakich luk szukać.",
                "Wyłącz w konfiguracji serwera i CMS pokazywanie numerów wersji.", 0, 3)
    else:
        o.dodaj("prywatnosc", "wersje", "ok", "Strona nie zdradza wersji oprogramowania", "", "", 3, 3)
    if html["cms"]:
        o.dodaj("prywatnosc", "cms", "info", f"Strona działa na {html['cms']}",
                "Systemy CMS i ich wtyczki to najczęstsza droga włamania na strony małych firm.",
                "Włącz automatyczne aktualizacje CMS i wtyczek, usuń nieużywane wtyczki, włącz 2FA dla administratora.")
    if html["formularze_http"] or html["mieszane"]:
        o.dodaj("prywatnosc", "mieszane", "uwaga", "Część treści idzie bez szyfrowania",
                "Na stronie są formularze albo pliki ładowane przez http:// - te dane można podejrzeć w drodze.",
                "Zmień wszystkie adresy w kodzie strony na https://.", 0, 3)
    elif odp["url"].startswith("https://"):
        o.dodaj("prywatnosc", "mieszane", "ok", "Wszystkie zasoby przez https://", "", "", 3, 3)


def ocen_domene(o: Ocena, dns_: dict) -> None:
    if dns_.get("dnskey"):
        o.dodaj("domena", "dnssec", "ok", "DNSSEC włączony",
                "Odpowiedzi DNS domeny są podpisane, trudniej je podrobić.", "", 3, 3)
    else:
        o.dodaj("domena", "dnssec", "info", "DNSSEC wyłączony",
                "Odpowiedzi DNS nie są podpisane. Atak na DNS mógłby skierować klientów lub pocztę na obcy serwer.",
                "Włącz DNSSEC w panelu rejestratora domeny (zwykle jeden przycisk).", 0, 3)
    if dns_.get("caa"):
        o.dodaj("domena", "caa", "ok", "Rekord CAA ustawiony",
                "Tylko wskazane urzędy mogą wystawić certyfikat dla domeny.", "", 2, 2)
    else:
        o.dodaj("domena", "caa", "info", "Brak rekordu CAA",
                "Dowolny urząd certyfikacji może wystawić certyfikat dla Twojej domeny.",
                "Dodaj rekord CAA, np. „0 issue \"letsencrypt.org\"”.", 0, 2)


def podsumuj(o: Ocena) -> dict:
    zdobyte = sum(z for z, _ in o.punkty.values())
    maks = sum(m for _, m in o.punkty.values()) or 1
    wynik = round(100 * zdobyte / maks)
    krytyczne = sum(1 for u in o.ustalenia if u["poziom"] == "krytyczne")
    # Kazdy krytyczny problem obniza ocene o jedna litere wzgledem samego wyniku.
    progi = ((90, "A"), (75, "B"), (60, "C"), (45, "D"), (30, "E"), (0, "F"))
    litery = [l for _, l in progi]
    litera = next(l for p, l in progi if wynik >= p)
    litera = litery[min(len(litery) - 1, litery.index(litera) + min(krytyczne, 2))]
    werdykty = {"A": "Wzorowo", "B": "Dobrze, z drobnymi lukami", "C": "Przeciętnie - są luki",
                "D": "Słabo - łatwy cel", "E": "Poważne luki", "F": "Stan opłakany"}
    kolejnosc = {"krytyczne": 0, "uwaga": 1, "info": 2, "ok": 3}
    return {
        "wynik": wynik, "ocena": litera, "werdykt": werdykty[litera], "krytyczne": krytyczne,
        "do_poprawy": sum(1 for u in o.ustalenia if u["poziom"] == "uwaga"),
        "kategorie": [{"id": k, "nazwa": n, "zdobyte": round(o.punkty[k][0], 1), "maks": o.punkty[k][1],
                       "procent": round(100 * o.punkty[k][0] / o.punkty[k][1]) if o.punkty[k][1] else None}
                      for k, n in KATEGORIE],
        "ustalenia": sorted(o.ustalenia, key=lambda u: kolejnosc[u["poziom"]]),
    }


# --- wycieki (Have I Been Pwned) ------------------------------------------

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,253}\.[a-z]{2,63}$", re.I)


def sprawdz_wycieki(email: str) -> dict:
    if not HIBP_KLUCZ:
        return {"dostepne": False}
    try:
        odp = httpx.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}",
                        params={"truncateResponse": "false"}, timeout=CZAS,
                        headers={"hibp-api-key": HIBP_KLUCZ, "User-Agent": AGENT})
    except httpx.HTTPError:
        return {"dostepne": True, "blad": True}
    if odp.status_code == 404:
        return {"dostepne": True, "liczba": 0, "wycieki": []}
    if odp.status_code != 200:
        return {"dostepne": True, "blad": True}
    wycieki = [{"nazwa": w.get("Title") or w.get("Name", ""), "data": w.get("BreachDate", ""),
                "dane": (w.get("DataClasses") or [])[:6]} for w in odp.json()]
    wycieki.sort(key=lambda w: w["data"], reverse=True)
    return {"dostepne": True, "liczba": len(wycieki), "wycieki": wycieki[:20]}


# --- caly skan -------------------------------------------------------------

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_BLOKADA = threading.Lock()


def skanuj(adres: str, dzis: date | None = None) -> dict:
    host = normalizuj_domene(adres)
    with _CACHE_BLOKADA:
        zapis = _CACHE.get(host)
        if zapis and time.monotonic() - zapis[0] < CACHE_S:
            return zapis[1]
    adresy = adresy_publiczne(host)
    domena = domena_glowna(host)
    with ThreadPoolExecutor(max_workers=4) as pula:
        p_dns = pula.submit(zbierz_dns, domena)
        p_tls = pula.submit(sprawdz_tls, host)
        p_http = pula.submit(sprobuj, f"http://{host}/")
        p_https = pula.submit(sprobuj, f"https://{host}/")
        dns_, tls, http, https = p_dns.result(), p_tls.result(), p_http.result(), p_https.result()
    if https is None and http is not None and http["url"].startswith("https://"):
        https = http
    strona = https or http
    if strona is None and not dns_.get("mx") and not dns_.get("txt"):
        raise BladSkanu("Nie udało się połączyć ze stroną ani odczytać rekordów domeny. Sprawdź adres.")
    html = analizuj_html(strona["html"], strona["url"]) if strona else \
        {"zewnetrzne": [], "mieszane": 0, "generator": "", "cms": "", "formularze_http": 0}

    o = Ocena()
    ocen_poczte(o, domena, dns_)
    ocen_https(o, tls, http, https)
    ocen_naglowki(o, strona)
    ocen_prywatnosc(o, strona, html, dzis or date.today())
    ocen_domene(o, dns_)
    wynik = podsumuj(o)
    wynik.update({
        "domena": host,
        "sprawdzono": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fakty": {
            "ip": adresy[:4],
            "serwer": (strona["naglowki"].get("server", "") if strona else "")[:60],
            "cms": html["cms"],
            "certyfikat": {k: tls.get(k) for k in ("wystawca", "wazny_do", "dni", "wersja")} if tls.get("dziala") else None,
            "poczta": sorted(m.split()[-1].rstrip(".") for m in dns_.get("mx", []))[:5],
            "zewnetrzne": html["zewnetrzne"][:25],
        },
    })
    with _CACHE_BLOKADA:
        if len(_CACHE) > 2000:
            _CACHE.clear()
        _CACHE[host] = (time.monotonic(), wynik)
    return wynik


class Zapytanie(BaseModel):
    adres: str
    email: str = ""
    zgoda_wycieki: bool = False


@router.post("")
def skan(z: Zapytanie, request: Request):
    if not WLACZONY:
        raise HTTPException(503, "Skaner jest chwilowo wyłączony.")
    limit_skanu.sprawdz(autoryzacja.adres_klienta(request),
                        "Za dużo sprawdzeń z tego adresu. Spróbuj ponownie za godzinę.")
    email = z.email.strip()
    if email and not _EMAIL.match(email):
        raise HTTPException(400, "Adres e-mail wygląda na niepoprawny.")
    if email and not z.zgoda_wycieki:
        raise HTTPException(400, "Zaznacz zgodę na sprawdzenie adresu e-mail w bazie wycieków.")
    start = time.monotonic()
    try:
        wynik = dict(skanuj(z.adres))
    except BladSkanu as e:
        raise HTTPException(400, str(e)) from None
    wynik["wycieki"] = sprawdz_wycieki(email) if email else None
    # Bez domeny i e-maila w logach (RODO) - tylko liczby.
    log.info("skan: ocena=%s wynik=%s krytyczne=%s czas=%.1fs", wynik["ocena"], wynik["wynik"],
             wynik["krytyczne"], time.monotonic() - start)
    return wynik
