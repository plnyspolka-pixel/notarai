"""Podpiecie skrzynki pocztowej kancelarii - tak, zeby wystarczyl adres e-mail.

Kreator w aplikacji prosi tylko o adres. Reszte ustalamy sami:
1. znani dostawcy po domenie (Gmail, Microsoft 365 / Outlook, Onet, WP, o2,
   Interia, iCloud, Yahoo, GMX, Zoho),
2. wlasna domena kancelarii: rekord MX (Google Workspace, Microsoft 365, OVH
   itd. rozpoznajemy po serwerze poczty),
3. baza autokonfiguracji Thunderbirda (autoconfig.thunderbird.net) i plik
   autoconfig domeny - te same zrodla, z ktorych korzystaja programy pocztowe,
4. na koniec proby: host MX, imap.<domena>, mail.<domena> - tylko z poprawnym
   certyfikatem TLS dla tej nazwy (bez certyfikatu nie wysylamy hasla).

Logowanie: haslo (albo haslo aplikacji) przez IMAP po TLS / STARTTLS, a dla
Microsoft 365 i Google - OAuth 2.0 (XOAUTH2). Microsoft nie przyjmuje juz
hasel w IMAP, wiec tam OAuth jest jedyna droga.

Do zewnetrznych uslug (DNS, autoconfig) wysylamy wylacznie domene kancelarii,
nigdy adresow klientow. W logach - tylko domena dostawcy i status.
"""
import base64
import hashlib
import imaplib
import logging
import os
import re
import secrets
import socket
import ssl
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx

log = logging.getLogger("pieczapp.skrzynki")

CZAS = float(os.getenv("PIECZAPP_SKRZYNKA_CZAS", "20"))
CZAS_PROBY = 4.0
# Testy podstawiaja httpx.MockTransport (autoconfig, tokeny OAuth).
TRANSPORT = None


class BladPolaczenia(RuntimeError):
    """Komunikat do pokazania w kreatorze (po polsku, z podpowiedzia)."""


# --- znani dostawcy ------------------------------------------------------------

ZNANI = {
    "gmail": {
        "nazwa": "Gmail / Google Workspace", "host": "imap.gmail.com", "port": 993, "tls": "ssl", "oauth": "google",
        "domeny": ("gmail.com", "googlemail.com"), "mx": ("google.com", "googlemail.com"),
        "pomoc": "Google przyjmie tu tylko hasło aplikacji: w koncie Google włącz weryfikację dwuetapową "
                 "i utwórz hasło na stronie myaccount.google.com/apppasswords. W Google Workspace "
                 "administrator musi mieć włączony IMAP.",
    },
    "microsoft": {
        "nazwa": "Microsoft 365 / Outlook.com", "host": "outlook.office365.com", "port": 993, "tls": "ssl",
        "oauth": "microsoft", "tylko_oauth": True,
        "domeny": ("outlook.com", "outlook.pl", "hotmail.com", "hotmail.pl", "live.com", "msn.com"),
        "mx": ("outlook.com", "protection.outlook.com"),
        "pomoc": "Microsoft nie przyjmuje już haseł w programach pocztowych - zaloguj się przyciskiem "
                 "„Zaloguj przez Microsoft”. W firmie administrator Microsoft 365 może musieć raz zatwierdzić dostęp.",
    },
    "onet": {
        "nazwa": "Onet Poczta", "host": "imap.poczta.onet.pl", "port": 993, "tls": "ssl",
        "domeny": ("onet.pl", "op.pl", "vp.pl", "onet.eu", "onet.com.pl", "poczta.onet.pl", "spoko.pl",
                   "autograf.pl", "buziaczek.pl", "amorki.pl"),
        "mx": ("onet.pl",),
        "pomoc": "W Poczcie Onet włącz dostęp z programów pocztowych (Ustawienia → Konto → IMAP).",
    },
    "wp": {
        "nazwa": "WP Poczta", "host": "imap.wp.pl", "port": 993, "tls": "ssl",
        "domeny": ("wp.pl", "wp.eu"), "mx": ("wp.pl",),
        "pomoc": "W WP Poczcie włącz w ustawieniach dostęp z programów pocztowych (IMAP).",
    },
    "o2": {
        "nazwa": "Poczta o2", "host": "poczta.o2.pl", "port": 993, "tls": "ssl",
        "domeny": ("o2.pl", "tlen.pl", "go2.pl", "prokonto.pl"), "mx": ("o2.pl",),
        "pomoc": "W Poczcie o2 włącz w ustawieniach dostęp przez IMAP.",
    },
    "interia": {
        "nazwa": "Poczta Interia", "host": "poczta.interia.pl", "port": 993, "tls": "ssl",
        "domeny": ("interia.pl", "interia.eu", "poczta.fm", "intmail.pl", "adresik.net", "vip.interia.pl",
                   "pacz.to", "interiowy.pl", "ogarnij.se"),
        "mx": ("interia.pl",),
        "pomoc": "W Poczcie Interia włącz w ustawieniach dostęp przez IMAP.",
    },
    "icloud": {
        "nazwa": "iCloud", "host": "imap.mail.me.com", "port": 993, "tls": "ssl",
        "domeny": ("icloud.com", "me.com", "mac.com"), "mx": ("icloud.com",),
        "pomoc": "Apple przyjmie tu tylko hasło dla aplikacji (appleid.apple.com → Hasła dla aplikacji).",
    },
    "yahoo": {
        "nazwa": "Yahoo Mail", "host": "imap.mail.yahoo.com", "port": 993, "tls": "ssl",
        "domeny": ("yahoo.com", "yahoo.pl", "ymail.com"), "mx": ("yahoodns.net",),
        "pomoc": "Yahoo przyjmie tu tylko hasło aplikacji (Ustawienia konta → Bezpieczeństwo).",
    },
    "gmx": {
        "nazwa": "GMX", "host": "imap.gmx.net", "port": 993, "tls": "ssl",
        "domeny": ("gmx.com", "gmx.net", "gmx.de", "gmx.at"), "mx": ("gmx.net",),
        "pomoc": "W GMX włącz dostęp przez IMAP w ustawieniach poczty.",
    },
    "zoho": {
        "nazwa": "Zoho Mail", "host": "imap.zoho.eu", "port": 993, "tls": "ssl",
        "domeny": ("zoho.com", "zohomail.eu", "zoho.eu"), "mx": ("zoho.eu", "zoho.com"),
        "pomoc": "W Zoho Mail włącz dostęp IMAP (Ustawienia → Mail Accounts → IMAP).",
    },
    "ovh": {
        "nazwa": "OVHcloud (MX Plan)", "host": "ssl0.ovh.net", "port": 993, "tls": "ssl",
        "domeny": (), "mx": ("ovh.net",),
        "pomoc": "Użytkownikiem jest pełny adres e-mail, hasło to hasło skrzynki z panelu OVH.",
    },
}


def domena(email: str) -> str:
    adres = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[a-z0-9.-]+\.[a-z]{2,}", adres):
        raise BladPolaczenia("To nie wygląda na adres e-mail.")
    return adres.split("@", 1)[1]


def rekordy_mx(dom: str) -> list[str]:
    """Hosty MX od najwyzszego priorytetu. Pusta lista, gdy DNS nie odpowie."""
    try:
        import dns.resolver
        odp = dns.resolver.resolve(dom, "MX", lifetime=CZAS_PROBY)
        return [str(r.exchange).rstrip(".").lower() for r in sorted(odp, key=lambda r: r.preference)]
    except Exception:  # noqa: BLE001 - brak MX to nie blad kreatora
        return []


def _po_mx(mx: list[str]) -> str | None:
    for host in mx:
        for ident, d in ZNANI.items():
            if any(host == s or host.endswith("." + s) for s in d.get("mx", ())):
                return ident
    return None


def autoconfig(dom: str) -> dict | None:
    """Ustawienia IMAP z autokonfiguracji (domena kancelarii, potem baza Thunderbirda)."""
    adresy = [f"https://autoconfig.{dom}/mail/config-v1.1.xml",
              f"https://{dom}/.well-known/autoconfig/mail/config-v1.1.xml",
              f"https://autoconfig.thunderbird.net/v1.1/{dom}"]
    with httpx.Client(timeout=CZAS_PROBY, transport=TRANSPORT, follow_redirects=True) as klient:
        for adres in adresy:
            try:
                odp = klient.get(adres)
            except httpx.HTTPError:
                continue
            if odp.status_code != 200:
                continue
            wynik = _z_autoconfig(odp.content, dom)
            if wynik:
                return wynik
    return None


def _z_autoconfig(xml: bytes, dom: str) -> dict | None:
    try:
        korzen = ET.fromstring(xml)
    except ET.ParseError:
        return None
    for serwer in korzen.iter("incomingServer"):
        if serwer.get("type") != "imap":
            continue
        tryb = (serwer.findtext("socketType") or "").upper()
        if tryb not in ("SSL", "STARTTLS"):
            continue            # bez szyfrowania nie laczymy sie wcale
        host = (serwer.findtext("hostname") or "").replace("%EMAILDOMAIN%", dom).strip().lower()
        if not host:
            continue
        uzytkownik = (serwer.findtext("username") or "%EMAILADDRESS%").strip()
        return {"host": host, "port": int(serwer.findtext("port") or (993 if tryb == "SSL" else 143)),
                "tls": "ssl" if tryb == "SSL" else "starttls",
                "uzytkownik": "lokalna" if uzytkownik == "%EMAILLOCALPART%" else "adres"}
    return None


def ma_certyfikat(host: str, port: int = 993) -> bool:
    """Czy pod host:port jest IMAP po TLS z certyfikatem wystawionym na te nazwe."""
    try:
        with socket.create_connection((host, port), timeout=CZAS_PROBY) as gniazdo:
            with ssl.create_default_context().wrap_socket(gniazdo, server_hostname=host):
                return True
    except (OSError, ssl.SSLError):
        return False


def wykryj(email: str) -> dict:
    """{dostawca, nazwa, host, port, tls, uzytkownik, pomoc, oauth, tylko_oauth, zrodlo}."""
    dom = domena(email)
    ident = next((i for i, d in ZNANI.items() if dom in d["domeny"]), None)
    zrodlo = "znany dostawca"
    mx: list[str] = []
    if ident is None:
        mx = rekordy_mx(dom)
        ident = _po_mx(mx)
        zrodlo = "rekord MX domeny"
    if ident:
        d = ZNANI[ident]
        wynik = {"dostawca": ident, "nazwa": d["nazwa"], "host": d["host"], "port": d["port"], "tls": d["tls"],
                 "uzytkownik": "adres", "pomoc": d["pomoc"], "oauth": d.get("oauth", ""),
                 "tylko_oauth": bool(d.get("tylko_oauth")), "zrodlo": zrodlo}
    else:
        wynik = None
        ustawienia = autoconfig(dom)
        if ustawienia:
            wynik = {**ustawienia, "zrodlo": "autokonfiguracja poczty"}
        else:
            for host in [*mx[:1], f"imap.{dom}", f"mail.{dom}"]:
                if ma_certyfikat(host):
                    wynik = {"host": host, "port": 993, "tls": "ssl", "uzytkownik": "adres",
                             "zrodlo": "serwer z certyfikatem TLS dla tej nazwy"}
                    break
        if wynik is None:
            wynik = {"host": "", "port": 993, "tls": "ssl", "uzytkownik": "adres", "zrodlo": ""}
        wynik.update({"dostawca": "inny", "nazwa": "Serwer poczty domeny " + dom,
                      "pomoc": "Hasło to hasło skrzynki (to samo, co w programie pocztowym). "
                               "Jeśli nie zadziała, dane serwera IMAP poda firma hostingowa.",
                      "oauth": "", "tylko_oauth": False})
    log.info("skrzynka: wykryto dostawce %s (%s)", wynik["dostawca"], wynik["zrodlo"] or "brak")
    return wynik


# --- polaczenie IMAP --------------------------------------------------------------


def polacz_imap(host: str, port: int, tls: str):
    kontekst = ssl.create_default_context()
    try:
        if tls == "starttls":
            imap = imaplib.IMAP4(host, int(port), timeout=CZAS)
            imap.starttls(ssl_context=kontekst)
        else:
            imap = imaplib.IMAP4_SSL(host, int(port), ssl_context=kontekst, timeout=CZAS)
    except ssl.SSLCertVerificationError:
        raise BladPolaczenia(f"Serwer {host} nie ma poprawnego certyfikatu - ze względów bezpieczeństwa "
                             "nie wysyłamy do niego hasła.") from None
    except (OSError, imaplib.IMAP4.error) as blad:
        raise BladPolaczenia(f"Nie udało się połączyć z serwerem {host}:{port} ({type(blad).__name__}). "
                             "Sprawdź nazwę serwera albo spróbuj za chwilę.") from None
    return imap


def xoauth2(uzytkownik: str, token: str) -> bytes:
    return f"user={uzytkownik}\x01auth=Bearer {token}\x01\x01".encode()


def zaloguj(imap, uzytkownik: str, haslo: str = "", token: str = "", pomoc: str = "") -> None:
    try:
        if token:
            imap.authenticate("XOAUTH2", lambda _: xoauth2(uzytkownik, token))
        else:
            imap.login(uzytkownik, haslo)
    except imaplib.IMAP4.error as blad:
        tekst = str(blad)
        if "application-specific" in tekst.lower() or "web login" in tekst.lower():
            pomoc = pomoc or ZNANI["gmail"]["pomoc"]
        raise BladPolaczenia("Serwer odrzucił logowanie. " + (pomoc or "Sprawdź adres i hasło.")) from None


_LISTA = re.compile(rb'\((?P<flagi>[^)]*)\) (?:"(?:[^"\\]|\\.)*"|NIL) (?P<nazwa>.+)$')


def dekoduj_utf7(nazwa: str) -> str:
    """Nazwa folderu IMAP (modified UTF-7, RFC 3501) -> tekst."""
    def zamien(m):
        srodek = m.group(1)
        if not srodek:
            return "&"
        dane = srodek.replace(",", "/")
        dane += "=" * (-len(dane) % 4)
        return base64.b64decode(dane).decode("utf-16-be")
    return re.sub(r"&([^-]*)-", zamien, nazwa)


def foldery(imap) -> list[dict]:
    """[{id (do SELECT), nazwa (do pokazania)}], INBOX pierwszy."""
    typ, dane = imap.list()
    wynik = []
    for wiersz in dane or []:
        if not isinstance(wiersz, bytes):
            continue
        m = _LISTA.match(wiersz)
        if not m or b"\\Noselect" in m.group("flagi"):
            continue
        surowa = m.group("nazwa").decode("ascii", "replace").strip()
        if surowa.startswith('"') and surowa.endswith('"'):
            surowa = surowa[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        wynik.append({"id": surowa, "nazwa": "Odebrane" if surowa.upper() == "INBOX" else dekoduj_utf7(surowa)})
    wynik.sort(key=lambda f: (f["id"].upper() != "INBOX", f["nazwa"].lower()))
    return wynik


def data_imap(dni_wstecz: int) -> str:
    miesiace = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    d = datetime.now() - timedelta(days=dni_wstecz)
    return f"{d.day:02d}-{miesiace[d.month - 1]}-{d.year}"


# --- OAuth 2.0 (Microsoft 365, Google) ---------------------------------------------

OAUTH = {
    "microsoft": {
        "nazwa": "Microsoft",
        "autoryzacja": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "zakres": "https://outlook.office.com/IMAP.AccessAsUser.All offline_access openid email",
        "klient_env": "PIECZAPP_OAUTH_MS_KLIENT", "sekret_env": "PIECZAPP_OAUTH_MS_SEKRET",
        "host": "outlook.office365.com", "dodatkowe": {"prompt": "select_account"},
    },
    "google": {
        "nazwa": "Google",
        "autoryzacja": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "zakres": "https://mail.google.com/ openid email",
        "klient_env": "PIECZAPP_OAUTH_GOOGLE_KLIENT", "sekret_env": "PIECZAPP_OAUTH_GOOGLE_SEKRET",
        "host": "imap.gmail.com", "dodatkowe": {"access_type": "offline", "prompt": "consent select_account"},
    },
}


def oauth_dostepne() -> dict:
    return {k: bool(os.getenv(d["klient_env"]) and os.getenv(d["sekret_env"])) for k, d in OAUTH.items()}


def adres_powrotu() -> str:
    baza = os.getenv("PIECZAPP_ADRES", "").rstrip("/") or f"http://127.0.0.1:{os.getenv('PIECZAPP_PORT', '8000')}"
    return baza + "/api/korespondencja/oauth/powrot"


def pkce() -> tuple[str, str]:
    weryfikator = secrets.token_urlsafe(48)
    wyzwanie = base64.urlsafe_b64encode(hashlib.sha256(weryfikator.encode()).digest()).rstrip(b"=").decode()
    return weryfikator, wyzwanie


def adres_logowania(dostawca: str, stan: str, wyzwanie: str, email: str) -> str:
    d = OAUTH[dostawca]
    parametry = {"client_id": os.getenv(d["klient_env"], ""), "response_type": "code",
                 "redirect_uri": adres_powrotu(), "scope": d["zakres"], "state": stan,
                 "code_challenge": wyzwanie, "code_challenge_method": "S256", "login_hint": email,
                 **d["dodatkowe"]}
    return d["autoryzacja"] + "?" + urlencode(parametry)


def _token(dostawca: str, dane: dict) -> dict:
    d = OAUTH[dostawca]
    dane = {"client_id": os.getenv(d["klient_env"], ""), "client_secret": os.getenv(d["sekret_env"], ""), **dane}
    try:
        with httpx.Client(timeout=CZAS, transport=TRANSPORT) as klient:
            odp = klient.post(d["token"], data=dane)
    except httpx.HTTPError:
        raise BladPolaczenia(f"Brak połączenia z {d['nazwa']} - spróbuj za chwilę.") from None
    if odp.status_code != 200:
        kod = ""
        try:
            kod = odp.json().get("error", "")
        except ValueError:
            pass
        log.warning("oauth %s: odmowa tokenu (%s)", dostawca, kod or odp.status_code)
        if kod == "invalid_grant":
            raise BladPolaczenia(f"Dostęp do skrzynki w {d['nazwa']} wygasł albo został cofnięty - "
                                 "połącz skrzynkę ponownie.")
        raise BladPolaczenia(f"{d['nazwa']} nie wydał dostępu do skrzynki ({kod or odp.status_code}).")
    return odp.json()


def _email_z_id_token(id_token: str) -> str:
    try:
        ladunek = id_token.split(".")[1]
        import json
        dane = json.loads(base64.urlsafe_b64decode(ladunek + "=" * (-len(ladunek) % 4)))
    except (IndexError, ValueError):
        return ""
    return str(dane.get("email") or dane.get("preferred_username") or "").lower()


def wymien_kod(dostawca: str, kod: str, weryfikator: str) -> dict:
    """Kod z przekierowania -> {refresh_token, access_token, wygasa, email}."""
    odp = _token(dostawca, {"grant_type": "authorization_code", "code": kod, "redirect_uri": adres_powrotu(),
                            "code_verifier": weryfikator})
    if not odp.get("refresh_token"):
        raise BladPolaczenia("Dostawca nie wydał stałego dostępu (brak refresh token). Spróbuj połączyć ponownie.")
    return {"refresh_token": odp["refresh_token"], "access_token": odp.get("access_token", ""),
            "wygasa": time.time() + int(odp.get("expires_in", 3600)) - 60,
            "email": _email_z_id_token(odp.get("id_token", ""))}


_TOKENY: dict[str, tuple[str, float]] = {}


def token_dostepu(klucz: str, dostawca: str, refresh_token: str, zapisz_nowy=None) -> str:
    """Krotki token dostepu z odswiezajacego; nowy odswiezajacy (rotacja) idzie do zapisz_nowy."""
    token, wygasa = _TOKENY.get(klucz, ("", 0.0))
    if token and wygasa > time.time():
        return token
    odp = _token(dostawca, {"grant_type": "refresh_token", "refresh_token": refresh_token,
                            "scope": OAUTH[dostawca]["zakres"]})
    if odp.get("refresh_token") and odp["refresh_token"] != refresh_token and zapisz_nowy:
        zapisz_nowy(odp["refresh_token"])
    _TOKENY[klucz] = (odp["access_token"], time.time() + int(odp.get("expires_in", 3600)) - 60)
    return odp["access_token"]


@dataclass
class Proba:
    """Wynik testu polaczenia (bez hasla)."""
    host: str
    port: int
    tls: str
    uzytkownik: str
    foldery: list = field(default_factory=list)
    wiadomosci: int = 0
