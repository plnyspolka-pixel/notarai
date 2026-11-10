"""SMS do klientow kancelarii: kod weryfikacyjny, potwierdzenie i przypomnienie
wizyty umowionej przez aplikacje notarai. Wysylka przez Twilio (REST, Basic auth).

Wzorowane na Finance You (finyou/src/lib/twilio-api.server.ts i sms-guard.server.ts),
ale na OSOBNYM koncie albo podkoncie Twilio i osobnym numerze: numer ma jeden
webhook, wiec wspolny numer kierowalby odpowiedzi klientow kancelarii do
systemu pozyczkowego. Zmienne srodowiskowe maja prefiks PIECZAPP_TWILIO_*,
zeby nie pomylic ich z TWILIO_* Finance You.

Tryby (PIECZAPP_SMS_TRYB):
  wylaczony - domyslnie; nic nie wychodzi, rezerwacje online sa wylaczone
  test      - nic nie wychodzi, wiadomosci trafiaja na liste `wyslane_testowo`
              (testy automatyczne i stanowisko deweloperskie)
  twilio    - prawdziwa wysylka

Hamulec (jedno miejsce, obowiazuje kazde zrodlo):
  krytyczny    - kod weryfikacyjny, potwierdzenie, odwolanie: bez okna godzinowego,
                 tylko limit na numer (ochrona przed nabijaniem kosztow)
  automatyczny - przypomnienia: okno 8-20 czasu warszawskiego, bez powtorki tej
                 samej tresci na ten sam numer w 24 h
Numer wypisany (odpowiedz STOP) nie dostaje niczego poza krytycznymi.

Zero danych osobowych w logach: numer telefonu ani tresc nie trafiaja do logow,
logujemy kategorie, status HTTP i identyfikator wiadomosci Twilio.
"""
import hashlib
import logging
import os
import re
import secrets
import threading
import time
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

log = logging.getLogger("pieczapp.sms")

STREFA = ZoneInfo("Europe/Warsaw")
TRYB = os.getenv("PIECZAPP_SMS_TRYB", "wylaczony").strip().lower()
KONTO = os.getenv("PIECZAPP_TWILIO_ACCOUNT_SID", "").strip()
TOKEN = os.getenv("PIECZAPP_TWILIO_AUTH_TOKEN", "").strip()
KLUCZ_SID = os.getenv("PIECZAPP_TWILIO_API_KEY_SID", "").strip()
KLUCZ_SEKRET = os.getenv("PIECZAPP_TWILIO_API_KEY_SECRET", "").strip()
NADAWCA = os.getenv("PIECZAPP_TWILIO_NUMER", "").strip()                  # +48..., numer notarai
USLUGA = os.getenv("PIECZAPP_TWILIO_MESSAGING_SERVICE", "").strip()        # albo MG... (Messaging Service)
OKNO_OD, OKNO_DO = (int(x) for x in os.getenv("PIECZAPP_SMS_OKNO", "8-20").split("-"))
NA_NUMER_GODZINA = int(os.getenv("PIECZAPP_SMS_NA_NUMER_GODZINA", "5"))
NA_DOBE = int(os.getenv("PIECZAPP_SMS_NA_DOBE", "2000"))
API = "https://api.twilio.com/2010-04-01/Accounts"
CZAS_S = 15.0

KRYTYCZNY = "krytyczny"
AUTOMATYCZNY = "automatyczny"

_transport: httpx.BaseTransport | None = None   # testy podstawiaja httpx.MockTransport
_blokada = threading.Lock()
_historia: dict[str, deque] = {}        # skrot numeru -> czasy wysylek (monotonic)
_tresci: dict[str, deque] = {}          # skrot numeru -> (czas, skrot tresci) z 24 h
_wszystkie: deque = deque()
wyslane_testowo: list[dict] = []        # tryb test: {"numer", "tresc", "kategoria"}

_OGONKI = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def wlaczone() -> bool:
    return TRYB in ("test", "twilio")


def testowy() -> bool:
    return TRYB == "test"


def gotowe() -> str:
    """Pusty tekst, gdy konfiguracja pozwala wysylac; inaczej opis braku."""
    if TRYB == "wylaczony":
        return "PIECZAPP_SMS_TRYB=wylaczony"
    if TRYB == "test":
        return ""
    if TRYB != "twilio":
        return f"nieznany tryb SMS: {TRYB}"
    if not KONTO or not (TOKEN or (KLUCZ_SID and KLUCZ_SEKRET)):
        return "brak PIECZAPP_TWILIO_ACCOUNT_SID i tokenu albo klucza API"
    if not NADAWCA and not USLUGA:
        return "brak PIECZAPP_TWILIO_NUMER albo PIECZAPP_TWILIO_MESSAGING_SERVICE"
    return ""


def bez_ogonkow(tekst: str) -> str:
    """Z polskimi znakami Twilio koduje SMS jako UCS-2 (70 znakow na segment
    zamiast 160) - jedna wiadomosc stalaby sie dwiema. Szablony trzymaja
    te sama konwencje co Finance You."""
    return tekst.translate(_OGONKI)


def normalizuj_numer(tekst) -> str | None:
    """Numer w postaci E.164 albo None, gdy to nie wyglada na numer telefonu.

    9 cyfr -> polski numer komorkowy/stacjonarny (+48). Zapis z 48, 0048 lub
    +48 na poczatku tez jest polski. Inne kraje: + i 8-15 cyfr.
    """
    surowy = str(tekst or "").strip()
    if not surowy:
        return None
    plus = surowy.startswith("+") or surowy.startswith("00")
    cyfry = re.sub(r"\D", "", surowy)
    if cyfry.startswith("00"):
        cyfry = cyfry[2:]
    if len(cyfry) == 9 and not plus:
        return "+48" + cyfry
    if len(cyfry) == 11 and cyfry.startswith("48"):
        return "+" + cyfry
    if plus and 8 <= len(cyfry) <= 15:
        return "+" + cyfry
    return None


def koncowka(numer: str) -> str:
    """Trzy ostatnie cyfry - tyle pokazujemy klientowi w komunikacie."""
    return re.sub(r"\D", "", numer or "")[-3:]


def skrot(numer: str) -> str:
    """Odcisk numeru do limitow i zapisu weryfikacji - zamiast samego numeru."""
    znormalizowany = normalizuj_numer(numer) or ""
    return hashlib.sha256(("notarai-sms:" + znormalizowany).encode()).hexdigest()


def kod_weryfikacyjny() -> str:
    return f"{secrets.randbelow(10 ** 6):06d}"


def w_oknie(teraz: datetime | None = None) -> bool:
    """Czy wolno teraz wysylac wiadomosci automatyczne (przypomnienia)."""
    godzina = (teraz or datetime.now(STREFA)).astimezone(STREFA).hour
    return OKNO_OD <= godzina < OKNO_DO


def _skrot_tresci(tresc: str) -> str:
    tekst = re.sub(r"https?://\S+", " ", tresc.lower())
    return hashlib.sha256(" ".join(re.sub(r"[^a-z0-9ąćęłńóśźż]+", " ", tekst).split()).encode()).hexdigest()


def _hamulec(klucz: str, tresc: str, kategoria: str) -> str:
    """Pusty tekst = wolno. Inaczej powod odmowy."""
    teraz = time.monotonic()
    with _blokada:
        while _wszystkie and teraz - _wszystkie[0] > 86400:
            _wszystkie.popleft()
        if len(_wszystkie) >= NA_DOBE:
            return "limit_dobowy"
        proby = _historia.setdefault(klucz, deque())
        while proby and teraz - proby[0] > 3600:
            proby.popleft()
        if len(proby) >= NA_NUMER_GODZINA:
            return "limit_numeru"
        if kategoria == AUTOMATYCZNY:
            if not w_oknie():
                return "poza_oknem"
            tresci = _tresci.setdefault(klucz, deque())
            while tresci and teraz - tresci[0][0] > 86400:
                tresci.popleft()
            odcisk = _skrot_tresci(tresc)
            if any(o == odcisk for _, o in tresci):
                return "powtorka"
            tresci.append((teraz, odcisk))
        proby.append(teraz)
        _wszystkie.append(teraz)
        if len(_historia) > 20000:
            for k in [k for k, p in _historia.items() if not p]:
                _historia.pop(k, None)
                _tresci.pop(k, None)
    return ""


def wyczysc() -> None:
    """Dla testow: zeruje limity i liste wiadomosci testowych."""
    with _blokada:
        _historia.clear()
        _tresci.clear()
        _wszystkie.clear()
        wyslane_testowo.clear()


def wyslij(numer: str, tresc: str, kategoria: str = KRYTYCZNY, wypisany: bool = False) -> dict:
    """Wysyla SMS. Nie rzuca - zwraca {"wyslano": bool, "powod": str, "sid": str}.
    `wypisany`: numer odpowiedzial STOP; dostaje tylko wiadomosci krytyczne."""
    if kategoria not in (KRYTYCZNY, AUTOMATYCZNY):
        raise ValueError("Nieznana kategoria SMS")
    brak = gotowe()
    if brak:
        return {"wyslano": False, "powod": "wylaczone", "sid": ""}
    do = normalizuj_numer(numer)
    if not do:
        return {"wyslano": False, "powod": "zly_numer", "sid": ""}
    if wypisany and kategoria != KRYTYCZNY:
        return {"wyslano": False, "powod": "wypisany", "sid": ""}
    tresc = bez_ogonkow(" ".join(str(tresc or "").split()))[:600]
    if not tresc:
        return {"wyslano": False, "powod": "pusta_tresc", "sid": ""}
    powod = _hamulec(skrot(do), tresc, kategoria)
    if powod:
        log.info("sms: odmowa (%s, %s)", kategoria, powod)
        return {"wyslano": False, "powod": powod, "sid": ""}
    if TRYB == "test":
        wyslane_testowo.append({"numer": do, "tresc": tresc, "kategoria": kategoria})
        log.info("sms: tryb testowy, wiadomosc %s odlozona", kategoria)
        return {"wyslano": True, "powod": "", "sid": "TEST", "tryb": "test"}
    return _twilio(do, tresc, kategoria)


def _twilio(do: str, tresc: str, kategoria: str) -> dict:
    uzytkownik, sekret = (KLUCZ_SID, KLUCZ_SEKRET) if KLUCZ_SID and KLUCZ_SEKRET else (KONTO, TOKEN)
    pola = {"To": do, "Body": tresc}
    if USLUGA:
        pola["MessagingServiceSid"] = USLUGA
    else:
        pola["From"] = NADAWCA
    try:
        with httpx.Client(timeout=CZAS_S, transport=_transport) as klient:
            odp = klient.post(f"{API}/{KONTO}/Messages.json", data=pola, auth=(uzytkownik, sekret))
    except httpx.HTTPError as blad:
        log.warning("sms: Twilio niedostepne (%s, %s)", kategoria, type(blad).__name__)
        return {"wyslano": False, "powod": "blad_sieci", "sid": ""}
    if odp.status_code >= 400:
        kod = ""
        try:
            kod = str(odp.json().get("code", ""))
        except ValueError:
            pass
        log.warning("sms: Twilio HTTP %s kod %s (%s)", odp.status_code, kod, kategoria)
        return {"wyslano": False, "powod": "blad_twilio", "sid": "", "http": odp.status_code, "kod": kod}
    try:
        dane = odp.json()
    except ValueError:
        dane = {}
    sid = str(dane.get("sid", ""))
    log.info("sms: wyslano %s (%s, status %s)", sid or "?", kategoria, dane.get("status", "?"))
    return {"wyslano": True, "powod": "", "sid": sid}


def stop_w_tresci(tresc: str) -> bool:
    """Odpowiedz klienta zaczynajaca sie od STOP/WYPISZ = wypis z wiadomosci
    automatycznych (ta sama regula co Finance You)."""
    return bool(re.match(r"^\s*(stop|wypisz|wypisuje|wypisuję|rezygnuje|rezygnuję|koniec)\b",
                         str(tresc or ""), re.IGNORECASE))
