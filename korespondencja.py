"""Korespondencja e-mail w sprawach: skrzynka kancelarii -> propozycja sprawy
-> zatwierdzenie -> pliki sprawy i ustalenia ze zrodlem.

Przebieg:
1. „Sprawdź skrzynkę” pobiera nowe wiadomosci od dostawcy (IMAP po TLS albo
   katalog z plikami .eml - dane demo i testy). Wiadomosci trafiaja do
   skrzynki „Do przypisania” (plik kancelarii `skrzynka`). Niczego nie
   przypisujemy sami.
2. Do kazdej wiadomosci liczymy PROPOZYCJE spraw: sygnatura, numer ksiegi
   wieczystej, adres nadawcy/adresata znany w sprawie, odpowiedz w watku juz
   przypisanym do sprawy (In-Reply-To/References), nazwiska stron. Propozycja
   ma uzasadnienie i pewnosc; o przypisaniu decyduje czlowiek jednym klikiem.
3. Po zatwierdzeniu wiadomosc (.eml) i jej zalaczniki laduja w „Plikach
   sprawy” (zalaczniki/), a metadane - nadawca, data, temat, rola nadawcy
   w sprawie - w {sprawa}/korespondencja.json.
4. Ustalenia z tresci wyciaga model (Bedrock, eu-central-1) - osobnym
   klikiem, przez osobe z uprawnieniem do modelu. Ustalenia maja ZRODLO
   (kto napisal i jaka ma role w sprawie) i NIE zmieniaja pol odczytu ani
   projektu: pole bez wartosci zostaje w projekcie <<BRAK>>, dopoki
   notariusz sam go nie uzupelni po potwierdzeniu przez strone.

Dostawcy maja jeden interfejs (`nowe`, `pobierz`), wiec Microsoft 365 albo
Gmail (OAuth) dojda jako kolejna klasa bez zmian w reszcie modulu.

Hasla do skrzynki: w chmurze wylacznie AWS Secrets Manager
(notarai-skrzynka-<kancelaria>), lokalnie zmienna PIECZAPP_SKRZYNKA_HASLO
(nie w commitowanym .env). Haslo nigdy nie wraca do przegladarki.

RODO: tresc, tematy, adresy i nazwiska z korespondencji nie trafiaja do
logow - logujemy identyfikatory, liczby i statusy.
"""
import email
import email.policy
import email.utils
import html
import imaplib
import json
import logging
import os
import re
import ssl
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import config
import magazyn

log = logging.getLogger("pieczapp.korespondencja")

PLIK_SKRZYNKI = "skrzynka"
PLIK_USTAWIEN = "skrzynka_ustawienia"
PLIK_SPRAWY = "korespondencja.json"
ZALACZNIKI = "zalaczniki"           # ten sam folder co „Pliki sprawy” (app.py)
PREFIKS_SEKRETU = "notarai-skrzynka-"
CZAS = float(os.getenv("PIECZAPP_SKRZYNKA_CZAS", "30"))
NA_RAZ = int(os.getenv("PIECZAPP_SKRZYNKA_NA_RAZ", "50"))   # wiadomosci na jedno sprawdzenie
MAKS_ZNANYCH = 5000
MAKS_TEKSTU = 20000
# Katalog z plikami .eml zamiast prawdziwej skrzynki (demo, testy). Tylko lokalnie.
KATALOG_DEMO = os.getenv("PIECZAPP_SKRZYNKA_KATALOG", "")

# Rola nadawcy w sprawie. „strona” i „kupujacy” to strony czynnosci - tylko
# one moga potwierdzic ustalenie; reszta to zrodla posrednie.
ROLE = {
    "strona": "strona",
    "kupujacy": "kupujący",
    "pelnomocnik": "pełnomocnik",
    "kontakt": "osoba kontaktowa",
    "bank": "bank",
    "inny": "inny",
}
STRONY = ("strona", "kupujacy")

_KW = re.compile(r"\b[A-Z]{2}\d[A-Z]/\d{8}/\d\b")


class BladSkrzynki(RuntimeError):
    """Problem z polaczeniem albo odczytem skrzynki - tresc do pokazania."""


# --- parsowanie .eml ---------------------------------------------------------


def _bez_html(tekst: str) -> str:
    tekst = re.sub(r"(?is)<(script|style).*?</\1>", " ", tekst)
    tekst = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", tekst)
    tekst = re.sub(r"<[^>]+>", " ", tekst)
    return re.sub(r"[ \t]+", " ", html.unescape(tekst)).strip()


def _adresy(wartosci) -> list[dict]:
    return [{"imie": imie.strip(), "email": adres.strip().lower()}
            for imie, adres in email.utils.getaddresses([str(w) for w in wartosci if w]) if adres]


def _identyfikatory(naglowek) -> list[str]:
    return re.findall(r"<[^<>\s]+>", str(naglowek or ""))


def parsuj(surowa: bytes) -> dict:
    """Wiadomosc .eml -> slownik (naglowki odkodowane, tekst, zalaczniki z danymi)."""
    wiad = email.message_from_bytes(surowa, policy=email.policy.default)
    nadawcy = _adresy(wiad.get_all("From", []))
    try:
        data = email.utils.parsedate_to_datetime(str(wiad["Date"])).isoformat(timespec="seconds")
    except (TypeError, ValueError, IndexError):
        data = ""
    tekst = ""
    cialo = wiad.get_body(preferencelist=("plain", "html"))
    if cialo is not None:
        try:
            tekst = cialo.get_content()
        except (LookupError, ValueError):
            tekst = cialo.get_payload(decode=True).decode("utf-8", "replace")
        if cialo.get_content_type() == "text/html":
            tekst = _bez_html(tekst)
    zalaczniki = []
    for czesc in wiad.iter_attachments():
        dane = czesc.get_payload(decode=True) or b""
        nazwa = czesc.get_filename() or f"zalacznik-{len(zalaczniki) + 1}"
        zalaczniki.append({"nazwa": nazwa, "typ": czesc.get_content_type(), "rozmiar": len(dane), "dane": dane})
    message_id = (_identyfikatory(wiad.get("Message-ID")) or [""])[0]
    return {
        "message_id": message_id,
        "in_reply_to": _identyfikatory(wiad.get("In-Reply-To")),
        "references": _identyfikatory(wiad.get("References")),
        "nadawca": nadawcy[0] if nadawcy else {"imie": "", "email": ""},
        "adresaci": _adresy(wiad.get_all("To", []) + wiad.get_all("Cc", [])),
        "data": data,
        "temat": str(wiad.get("Subject", "") or "").strip(),
        "tekst": tekst.strip()[:MAKS_TEKSTU],
        "zalaczniki": zalaczniki,
    }


# --- dostawcy ----------------------------------------------------------------


class DostawcaKatalog:
    """Pliki .eml z katalogu. Identyfikator wiadomosci = nazwa pliku."""

    rodzaj = "katalog"

    def __init__(self, katalog: str | Path):
        self.katalog = Path(katalog)

    def nowe(self, znane: set[str], limit: int = NA_RAZ) -> list[tuple[str, bytes]]:
        if not self.katalog.is_dir():
            raise BladSkrzynki("Katalog skrzynki testowej nie istnieje.")
        pliki = sorted(p.name for p in self.katalog.glob("*.eml") if p.is_file())
        return [(n, (self.katalog / n).read_bytes()) for n in pliki if n not in znane][:limit]

    def pobierz(self, identyfikator: str) -> bytes:
        plik = self.katalog / Path(identyfikator).name
        if not plik.is_file():
            raise BladSkrzynki("Tej wiadomości nie ma już w skrzynce.")
        return plik.read_bytes()


class DostawcaImap:
    """IMAP po TLS (domyslnie port 993), skrzynka otwierana tylko do odczytu.

    Pobieramy BODY.PEEK[], wiec wiadomosci nie zmieniaja stanu „przeczytana”
    w programie pocztowym kancelarii. Identyfikator = UIDVALIDITY:UID.
    """

    rodzaj = "imap"
    polacz = staticmethod(imaplib.IMAP4_SSL)   # testy podstawiaja atrape

    def __init__(self, host: str, port: int, uzytkownik: str, haslo: str, folder: str = "INBOX"):
        if not host or not uzytkownik or not haslo:
            raise BladSkrzynki("Skrzynka nie jest skonfigurowana (serwer, użytkownik, hasło).")
        self.host, self.port, self.uzytkownik, self.haslo = host, int(port or 993), uzytkownik, haslo
        self.folder = folder or "INBOX"

    def _sesja(self):
        try:
            imap = self.polacz(self.host, self.port, ssl_context=ssl.create_default_context(), timeout=CZAS)
        except (OSError, imaplib.IMAP4.error) as blad:
            raise BladSkrzynki(f"Brak połączenia z serwerem poczty ({type(blad).__name__}).") from None
        try:
            imap.login(self.uzytkownik, self.haslo)
        except imaplib.IMAP4.error:
            raise BladSkrzynki("Serwer poczty odrzucił użytkownika lub hasło.") from None
        typ, _ = imap.select(_cytuj(self.folder), readonly=True)
        if typ != "OK":
            imap.logout()
            raise BladSkrzynki("Nie ma takiego folderu w skrzynce.")
        odp = imap.response("UIDVALIDITY")[1]
        waznosc = (odp[0].decode() if odp and odp[0] else "0") if odp else "0"
        return imap, waznosc

    @staticmethod
    def _tresc(dane) -> bytes:
        for czesc in dane or []:
            if isinstance(czesc, tuple) and len(czesc) > 1:
                return czesc[1]
        return b""

    def nowe(self, znane: set[str], limit: int = NA_RAZ) -> list[tuple[str, bytes]]:
        imap, waznosc = self._sesja()
        try:
            typ, dane = imap.uid("SEARCH", None, "ALL")
            if typ != "OK":
                raise BladSkrzynki("Serwer poczty nie zwrócił listy wiadomości.")
            uidy = [u.decode() for u in (dane[0] or b"").split()]
            nowe = [u for u in uidy if f"{waznosc}:{u}" not in znane][-limit:]
            wynik = []
            for uid in nowe:
                typ, dane = imap.uid("FETCH", uid, "(BODY.PEEK[])")
                if typ == "OK":
                    wynik.append((f"{waznosc}:{uid}", self._tresc(dane)))
            return wynik
        finally:
            try:
                imap.logout()
            except (OSError, imaplib.IMAP4.error):
                pass

    def pobierz(self, identyfikator: str) -> bytes:
        waznosc_wiad, _, uid = identyfikator.partition(":")
        imap, waznosc = self._sesja()
        try:
            if waznosc != waznosc_wiad or not uid.isdigit():
                raise BladSkrzynki("Skrzynka zmieniła numerację wiadomości - sprawdź ją ponownie.")
            typ, dane = imap.uid("FETCH", uid, "(BODY.PEEK[])")
            tresc = self._tresc(dane) if typ == "OK" else b""
            if not tresc:
                raise BladSkrzynki("Tej wiadomości nie ma już w skrzynce.")
            return tresc
        finally:
            try:
                imap.logout()
            except (OSError, imaplib.IMAP4.error):
                pass


def _cytuj(folder: str) -> str:
    return '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --- haslo: Secrets Manager w chmurze, zmienna srodowiskowa lokalnie ----------


class SejfSkrzynki:
    def _klient(self):
        import boto3
        sesja = boto3.Session(profile_name=config.PROFIL_AWS or None)
        return sesja.client("secretsmanager", region_name=config.REGION)

    def nazwa(self, kancelaria: str) -> str:
        return PREFIKS_SEKRETU + re.sub(r"[^A-Za-z0-9_+=.@-]", "-", kancelaria)

    @staticmethod
    def _brak(blad: Exception) -> bool:
        return type(blad).__name__ == "ResourceNotFoundException" or "ResourceNotFound" in str(getattr(blad, "response", ""))

    def wczytaj(self, kancelaria: str) -> str:
        try:
            odp = self._klient().get_secret_value(SecretId=self.nazwa(kancelaria))
        except Exception as blad:  # noqa: BLE001
            if self._brak(blad):
                return ""
            raise
        return json.loads(odp["SecretString"]).get("haslo", "")

    def zapisz(self, kancelaria: str, haslo: str) -> None:
        klient, nazwa, tresc = self._klient(), self.nazwa(kancelaria), json.dumps({"haslo": haslo})
        try:
            klient.put_secret_value(SecretId=nazwa, SecretString=tresc)
        except Exception as blad:  # noqa: BLE001
            if not self._brak(blad):
                raise
            klient.create_secret(Name=nazwa, SecretString=tresc,
                                 Description="notarai - haslo skrzynki pocztowej kancelarii (IMAP)",
                                 Tags=[{"Key": "projekt", "Value": "notarai"}, {"Key": "kancelaria", "Value": kancelaria}])

    def usun(self, kancelaria: str) -> None:
        try:
            self._klient().delete_secret(SecretId=self.nazwa(kancelaria), RecoveryWindowInDays=7)
        except Exception as blad:  # noqa: BLE001
            if not self._brak(blad):
                raise


sejf = SejfSkrzynki()


def _w_chmurze() -> bool:
    return magazyn.TRYB == "s3"


def haslo() -> str:
    if _w_chmurze():
        return sejf.wczytaj(magazyn.kancelaria())
    return os.getenv("PIECZAPP_SKRZYNKA_HASLO", "")


# --- ustawienia i dostawca ----------------------------------------------------


def _ustawienia_domyslne() -> dict:
    return {"dostawca": "", "host": "", "port": 993, "uzytkownik": "", "folder": "INBOX", "haslo_zapisane": False}


def ustawienia() -> dict:
    return {**_ustawienia_domyslne(), **magazyn.wczytaj_plik_kancelarii(PLIK_USTAWIEN, {})}


def dostawca():
    """Dostawca dla biezacej kancelarii (katalog demo ma pierwszenstwo, tylko lokalnie)."""
    if KATALOG_DEMO and not _w_chmurze():
        return DostawcaKatalog(KATALOG_DEMO)
    u = ustawienia()
    if u["dostawca"] == "imap":
        return DostawcaImap(u["host"], u["port"], u["uzytkownik"], haslo(), u["folder"])
    raise BladSkrzynki("Skrzynka kancelarii nie jest skonfigurowana.")


# --- skrzynka „Do przypisania” -------------------------------------------------


def _pusta_skrzynka() -> dict:
    return {"znane": [], "wiadomosci": [], "watki": {}}


def wczytaj_skrzynke() -> dict:
    return {**_pusta_skrzynka(), **magazyn.wczytaj_plik_kancelarii(PLIK_SKRZYNKI, {})}


def _zmien_skrzynke(zmiana):
    def opakowanie(dane):
        for k, v in _pusta_skrzynka().items():
            dane.setdefault(k, v)
        return zmiana(dane)
    return magazyn.zmien_plik_kancelarii(PLIK_SKRZYNKI, opakowanie, {})


def pobierz_nowe() -> dict:
    """Pobiera od dostawcy wiadomosci, ktorych jeszcze nie widzielismy."""
    dost = dostawca()
    stan = wczytaj_skrzynke()
    znane = set(stan["znane"])
    pobrane = dost.nowe(znane)
    wpisy = []
    for identyfikator, surowa in pobrane:
        try:
            p = parsuj(surowa)
        except Exception:  # noqa: BLE001 - uszkodzona wiadomosc nie blokuje reszty
            log.warning("skrzynka: wiadomosci nie da sie odczytac, pomijam")
            wpisy.append({"ident": identyfikator, "pomin": True})
            continue
        wpisy.append({
            "id": uuid.uuid4().hex[:12], "ident": identyfikator, "message_id": p["message_id"],
            "in_reply_to": p["in_reply_to"], "references": p["references"],
            "nadawca": p["nadawca"], "adresaci": p["adresaci"], "data": p["data"], "temat": p["temat"],
            "tekst": p["tekst"], "zalaczniki": [{"nazwa": z["nazwa"], "rozmiar": z["rozmiar"]} for z in p["zalaczniki"]],
            "pobrano": datetime.now().isoformat(timespec="seconds"), "dostawca": dost.rodzaj,
        })

    def zmiana(dane):
        juz = {w.get("message_id") for w in dane["wiadomosci"] if w.get("message_id")} | set(dane["watki"])
        dodane = 0
        for w in wpisy:
            dane["znane"].append(w["ident"])
            if w.get("pomin") or (w["message_id"] and w["message_id"] in juz):
                continue
            dane["wiadomosci"].append(w)
            dodane += 1
        dane["znane"] = dane["znane"][-MAKS_ZNANYCH:]
        return dodane

    dodane = _zmien_skrzynke(zmiana) if wpisy else 0
    log.info("skrzynka %s: pobrano %d, nowych do przypisania %d", magazyn.kancelaria(), len(pobrane), dodane)
    return {"pobrano": len(pobrane), "nowe": dodane}


# --- dane spraw do dopasowania -------------------------------------------------


def _norm(tekst: str) -> str:
    return "-" + re.sub(r"[^0-9A-ZĄĆĘŁŃÓŚŹŻ]+", "-", (tekst or "").upper()).strip("-") + "-"


def wczytaj_sprawy_korespondencji(katalog: Path) -> dict:
    plik = katalog / PLIK_SPRAWY
    try:
        dane = json.loads(plik.read_text("utf-8")) if plik.exists() else {}
    except ValueError:
        dane = {}
    return {"osoby": dane.get("osoby", []), "wiadomosci": dane.get("wiadomosci", [])}


def _zapisz_sprawy(katalog: Path, dane: dict) -> None:
    (katalog / PLIK_SPRAWY).write_text(json.dumps(dane, ensure_ascii=False, indent=2), encoding="utf-8")


def _czytaj_json(plik: Path) -> dict:
    try:
        return json.loads(plik.read_text("utf-8")) if plik.exists() else {}
    except ValueError:
        return {}


def _nazwiska(*teksty: str) -> set[str]:
    wynik = set()
    for t in teksty:
        for slowo in re.findall(r"[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ-]{2,}", t or ""):
            wynik.add(slowo.upper())
    return wynik


def indeks_spraw() -> list[dict]:
    """To, po czym rozpoznajemy sprawe: sygnatura, KW, osoby, watki."""
    baza = config.SPRAWY
    wynik = []
    for identyfikator in magazyn.identyfikatory_spraw(baza):
        katalog = baza / identyfikator
        meta = _czytaj_json(katalog / "sprawa.json")
        if not meta:
            continue
        odczyt = _czytaj_json(katalog / "odczyt.json")
        kor = wczytaj_sprawy_korespondencji(katalog)
        wartosci = " ".join(str(p.get("wartosc") or "") for p in odczyt.get("pola", []))
        wynik.append({
            "id": meta.get("id", identyfikator), "nazwa": meta.get("nazwa", ""), "sygnatura": meta.get("sygnatura", ""),
            "kw": set(_KW.findall(wartosci)),
            "osoby": {o["email"].lower(): o for o in kor["osoby"] if o.get("email")},
            "nazwiska": _nazwiska(meta.get("nazwa", ""), *(o.get("imie", "") for o in kor["osoby"])),
            "watki": {w["message_id"] for w in kor["wiadomosci"] if w.get("message_id")},
        })
    return wynik


def zaproponuj(wiad: dict, sprawy: list[dict], watki: dict | None = None) -> list[dict]:
    """Propozycje spraw dla wiadomosci: [{sprawa, nazwa, sygnatura, punkty, pewnosc, uzasadnienie}]."""
    watki = watki or {}
    tekst = (wiad.get("temat") or "") + "\n" + (wiad.get("tekst") or "")
    znormalizowany = _norm(tekst)
    kw_w_tekscie = set(_KW.findall(tekst))
    slowa = _nazwiska(tekst, wiad.get("nadawca", {}).get("imie", ""))
    poprzednie = set(wiad.get("in_reply_to") or []) | set(wiad.get("references") or [])
    nadawca = (wiad.get("nadawca") or {}).get("email", "").lower()
    adresaci = {a["email"].lower() for a in wiad.get("adresaci") or []}
    wynik = []
    for s in sprawy:
        punkty, powody = 0, []
        if poprzednie & (s["watki"] | {m for m, sid in watki.items() if sid == s["id"]}):
            punkty += 60
            powody.append("odpowiedź w wątku już przypisanym do tej sprawy")
        if s["sygnatura"] and _norm(s["sygnatura"]) != "--" and _norm(s["sygnatura"]) in znormalizowany:
            punkty += 60
            powody.append(f"sygnatura {s['sygnatura']} w temacie lub treści")
        for kw in sorted(kw_w_tekscie & s["kw"]):
            punkty += 50
            powody.append(f"numer księgi wieczystej {kw}")
        if nadawca in s["osoby"]:
            o = s["osoby"][nadawca]
            punkty += 35
            powody.append(f"nadawca jest w sprawie: {o.get('imie') or nadawca} ({ROLE.get(o.get('rola'), 'inny')})")
        wspolni = sorted(adresaci & set(s["osoby"]))
        if wspolni:
            punkty += 15
            powody.append("adresat jest w sprawie: " + ", ".join(s["osoby"][a].get("imie") or a for a in wspolni))
        nazwiska = sorted(slowa & s["nazwiska"])
        if nazwiska:
            punkty += min(20, 10 * len(nazwiska))
            powody.append("nazwisko w wiadomości: " + ", ".join(n.capitalize() for n in nazwiska))
        if punkty >= 10:
            wynik.append({"sprawa": s["id"], "nazwa": s["nazwa"], "sygnatura": s["sygnatura"], "punkty": punkty,
                          "pewnosc": "wysoka" if punkty >= 60 else "średnia" if punkty >= 30 else "niska",
                          "uzasadnienie": powody})
    wynik.sort(key=lambda p: -p["punkty"])
    return wynik[:3]


def do_przypisania() -> list[dict]:
    """Skrzynka z propozycjami liczonymi na biezacym stanie spraw."""
    stan = wczytaj_skrzynke()
    sprawy = indeks_spraw()
    wynik = []
    for w in stan["wiadomosci"]:
        wynik.append({**{k: v for k, v in w.items() if k not in ("ident",)},
                      "propozycje": zaproponuj(w, sprawy, stan["watki"])})
    wynik.sort(key=lambda w: w.get("data") or w.get("pobrano") or "", reverse=True)
    return wynik


def pomin(id_wiad: str) -> None:
    def zmiana(dane):
        przed = len(dane["wiadomosci"])
        dane["wiadomosci"] = [w for w in dane["wiadomosci"] if w.get("id") != id_wiad]
        return przed != len(dane["wiadomosci"])
    if not _zmien_skrzynke(zmiana):
        raise KeyError(id_wiad)
    log.info("skrzynka %s: wiadomosc %s pominieta", magazyn.kancelaria(), id_wiad)


# --- przypisanie (po zatwierdzeniu) --------------------------------------------


def _bezpieczna_nazwa(nazwa: str) -> str:
    czysta = re.sub(r"[^\w .()\-]", "_", Path(nazwa or "").name).strip(" ._")[:110]
    return czysta or "plik"


def _wolna(folder: Path, nazwa: str) -> Path:
    cel, numer = folder / nazwa, 2
    while cel.exists():
        cel = folder / f"{Path(nazwa).stem} ({numer}){Path(nazwa).suffix}"
        numer += 1
    return cel


def rola_nadawcy(osoby: list[dict], adres: str) -> str:
    for o in osoby:
        if (o.get("email") or "").lower() == (adres or "").lower():
            return o.get("rola") or "inny"
    return "inny"


def przypisz(id_wiad: str, katalog: Path, rola: str | None = None, kto: str = "") -> dict:
    """Zatwierdzenie: .eml i zalaczniki do Plikow sprawy, metadane do korespondencja.json."""
    if rola and rola not in ROLE:
        raise ValueError("Nieznana rola nadawcy")
    stan = wczytaj_skrzynke()
    wpis = next((w for w in stan["wiadomosci"] if w.get("id") == id_wiad), None)
    if wpis is None:
        raise KeyError(id_wiad)
    surowa = dostawca().pobierz(wpis["ident"])
    p = parsuj(surowa)
    if wpis.get("message_id") and p["message_id"] != wpis["message_id"]:
        raise BladSkrzynki("W skrzynce pod tym numerem jest teraz inna wiadomość - sprawdź skrzynkę ponownie.")

    dane = wczytaj_sprawy_korespondencji(katalog)
    nadawca = p["nadawca"]
    osoba = next((o for o in dane["osoby"] if nadawca["email"]
                  and (o.get("email") or "").lower() == nadawca["email"]), None)
    if osoba is None and nadawca["email"]:
        osoba = {"imie": nadawca["imie"], "email": nadawca["email"], "rola": rola or "inny", "opis": ""}
        dane["osoby"].append(osoba)
    elif osoba is not None and rola:
        osoba["rola"] = rola          # rola wskazana przy zatwierdzeniu jest rozstrzygajaca
    rola = rola or (osoba or {}).get("rola") or "inny"

    folder = katalog / ZALACZNIKI
    folder.mkdir(exist_ok=True)
    dzien = (p["data"] or datetime.now().isoformat())[:10]
    kto_pisze = nadawca["imie"] or nadawca["email"].split("@")[0]
    plik_eml = _wolna(folder, _bezpieczna_nazwa(f"{dzien} e-mail {kto_pisze} - {p['temat'] or 'bez tematu'}"[:100]) + ".eml")
    plik_eml.write_bytes(surowa)
    pliki_zal = []
    for z in p["zalaczniki"]:
        cel = _wolna(folder, _bezpieczna_nazwa(f"{dzien} zał. {z['nazwa']}"))
        cel.write_bytes(z["dane"])
        pliki_zal.append(cel.name)

    wiadomosc = {
        "id": id_wiad, "message_id": p["message_id"], "in_reply_to": p["in_reply_to"],
        "nadawca": nadawca, "adresaci": p["adresaci"], "rola": rola, "data": p["data"], "temat": p["temat"],
        "plik": plik_eml.name, "zalaczniki": pliki_zal, "przypisal": kto,
        "przypisano": datetime.now().isoformat(timespec="seconds"),
        "ustalenia": [], "ustalenia_stan": "czeka",
    }
    dane["wiadomosci"].append(wiadomosc)
    _zapisz_sprawy(katalog, dane)
    magazyn.utrwal_sprawe(katalog)

    def zmiana(s):
        s["wiadomosci"] = [w for w in s["wiadomosci"] if w.get("id") != id_wiad]
        if p["message_id"]:
            s["watki"][p["message_id"]] = katalog.name
    _zmien_skrzynke(zmiana)
    log.info("sprawa %s: przypisano wiadomosc %s (zalacznikow %d)", katalog.name, id_wiad, len(pliki_zal))
    return wiadomosc


# --- ustalenia ze zrodlem --------------------------------------------------------


def _pola_sprawy(katalog: Path) -> list[str]:
    odczyt = _czytaj_json(katalog / "odczyt.json")
    nazwy = [p["nazwa"] for p in odczyt.get("pola", []) if p.get("nazwa")]
    return nazwy or list(_czytaj_json(katalog / "sprawa.json").get("pola_wzoru", []))


def wyciagnij_ustalenia(katalog: Path, id_wiad: str) -> dict:
    """Model czyta tresc wiadomosci i zwraca ustalenia dot. pol sprawy.
    Zapis TYLKO w korespondencja.json - odczyt.json i projekt zostaja bez zmian."""
    import bedrock

    dane = wczytaj_sprawy_korespondencji(katalog)
    wiad = next((w for w in dane["wiadomosci"] if w.get("id") == id_wiad), None)
    if wiad is None:
        raise KeyError(id_wiad)
    plik = katalog / ZALACZNIKI / wiad["plik"]
    if not plik.is_file():
        raise BladSkrzynki("Plik wiadomości został usunięty z plików sprawy.")
    p = parsuj(plik.read_bytes())
    pola = _pola_sprawy(katalog)
    try:
        ustalenia = bedrock.wyciagnij_ustalenia(p["tekst"], p["temat"], pola)
    except Exception:
        wiad["ustalenia_stan"] = "blad"
        _zapisz_sprawy(katalog, dane)
        magazyn.utrwal_sprawe(katalog)
        log.warning("sprawa %s: ustalenia z wiadomosci %s - blad modelu", katalog.name, id_wiad)
        raise
    wiad["ustalenia"] = ustalenia
    wiad["ustalenia_stan"] = "gotowe"
    wiad["ustalenia_z"] = datetime.now().isoformat(timespec="seconds")
    _zapisz_sprawy(katalog, dane)
    magazyn.utrwal_sprawe(katalog)
    log.info("sprawa %s: ustalenia z wiadomosci %s: %d", katalog.name, id_wiad, len(ustalenia))
    return wiad


def _klucz_wartosci(wartosc: str) -> str:
    return re.sub(r"\s+", " ", str(wartosc or "")).strip().lower().rstrip(".")


def ustalenia_pol(dane: dict) -> dict:
    """{pole: [{wartosc, zrodla: [...], strony_potwierdzajace: [...], brak_potwierdzenia: [...],
    potwierdzone: bool}]} - kto co napisal i ktora strona tego NIE potwierdzila."""
    strony = [o for o in dane["osoby"] if o.get("rola") in STRONY]
    wynik: dict[str, dict[str, dict]] = {}
    for w in dane["wiadomosci"]:
        adres = (w.get("nadawca") or {}).get("email", "").lower()
        osoba = next((o for o in dane["osoby"] if (o.get("email") or "").lower() == adres), {})
        rola = osoba.get("rola") or w.get("rola") or "inny"
        for u in w.get("ustalenia") or []:
            pole, wartosc = u.get("pole"), u.get("wartosc")
            if not pole or not wartosc:
                continue
            grupa = wynik.setdefault(pole, {}).setdefault(_klucz_wartosci(wartosc), {
                "wartosc": wartosc, "zrodla": []})
            grupa["zrodla"].append({
                "wiadomosc": w["id"], "imie": osoba.get("imie") or (w.get("nadawca") or {}).get("imie") or adres,
                "email": adres, "rola": rola, "rola_opis": ROLE.get(rola, "inny"), "opis": osoba.get("opis", ""),
                "data": w.get("data", ""), "temat": w.get("temat", ""), "cytat": u.get("cytat", ""),
                "relacja": bool(u.get("relacja")), "czyje": u.get("czyje", ""), "atrapa": bool(u.get("atrapa")),
            })
    gotowe = {}
    for pole, grupy in wynik.items():
        gotowe[pole] = []
        for g in grupy.values():
            # Strona potwierdza tylko wlasnym listem - relacja („mama sie zgadza”) nie jest potwierdzeniem.
            potwierdzajacy = {z["email"] for z in g["zrodla"] if z["rola"] in STRONY and not z["relacja"]}
            g["strony_potwierdzajace"] = [o.get("imie") or o.get("email") for o in strony
                                          if (o.get("email") or "").lower() in potwierdzajacy]
            g["brak_potwierdzenia"] = [{"imie": o.get("imie") or o.get("email"), "opis": o.get("opis", ""),
                                        "rola_opis": ROLE.get(o.get("rola"), "")}
                                       for o in strony if (o.get("email") or "").lower() not in potwierdzajacy]
            g["potwierdzone"] = bool(strony) and not g["brak_potwierdzenia"]
            g["zrodla"].sort(key=lambda z: z["data"])
            gotowe[pole].append(g)
    return gotowe


def stan_sprawy(katalog: Path) -> dict:
    dane = wczytaj_sprawy_korespondencji(katalog)
    wiadomosci = sorted(dane["wiadomosci"], key=lambda w: w.get("data") or "", reverse=True)
    return {"osoby": dane["osoby"], "wiadomosci": wiadomosci, "ustalenia_pol": ustalenia_pol(dane),
            "role": ROLE}


def ustaw_osoby(katalog: Path, osoby: list[dict]) -> list[dict]:
    czyste = []
    for o in osoby:
        rola = o.get("rola") or "inny"
        if rola not in ROLE:
            raise ValueError("Nieznana rola osoby")
        czyste.append({"imie": str(o.get("imie", "")).strip()[:120], "email": str(o.get("email", "")).strip().lower()[:200],
                       "rola": rola, "opis": str(o.get("opis", "")).strip()[:120]})
    dane = wczytaj_sprawy_korespondencji(katalog)
    dane["osoby"] = czyste
    _zapisz_sprawy(katalog, dane)
    magazyn.utrwal_sprawe(katalog)
    log.info("sprawa %s: osob w korespondencji %d", katalog.name, len(czyste))
    return czyste


def opis_plikow(katalog: Path) -> dict:
    """{nazwa pliku: metadane z e-maila} - do listy „Pliki sprawy”."""
    wynik = {}
    for w in wczytaj_sprawy_korespondencji(katalog)["wiadomosci"]:
        meta = {"nadawca": (w.get("nadawca") or {}).get("imie") or (w.get("nadawca") or {}).get("email", ""),
                "rola": ROLE.get(w.get("rola"), "inny"), "data": w.get("data", ""), "temat": w.get("temat", "")}
        for nazwa in [w.get("plik")] + list(w.get("zalaczniki") or []):
            if nazwa:
                wynik[nazwa] = meta
    return wynik


# --- API ----------------------------------------------------------------------

router = APIRouter(tags=["korespondencja"])


def _katalog(identyfikator: str) -> Path:
    if not identyfikator.isalnum():
        raise HTTPException(400, "Nieprawidlowy identyfikator sprawy")
    katalog = config.SPRAWY / identyfikator
    if not magazyn.pobierz_sprawe(katalog):
        raise HTTPException(404, "Nie znaleziono sprawy")
    return katalog


def _wykonaj(funkcja, *argumenty):
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie - poczta wymaga zapisu na serwerze.")
    try:
        return funkcja(*argumenty)
    except BladSkrzynki as blad:
        raise HTTPException(502, str(blad))
    except KeyError:
        raise HTTPException(404, "Nie ma takiej wiadomości")
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))
    except ValueError as blad:
        raise HTTPException(400, str(blad))


class UstawieniaSkrzynki(BaseModel):
    dostawca: str = "imap"
    host: str = ""
    port: int = 993
    uzytkownik: str = ""
    folder: str = "INBOX"
    haslo: str = ""          # puste = bez zmiany hasla


class Przypisanie(BaseModel):
    sprawa: str
    rola: str | None = None


class OsobaKorespondencji(BaseModel):
    imie: str = ""
    email: str = ""
    rola: str = "inny"
    opis: str = ""


class OsobyKorespondencji(BaseModel):
    osoby: list[OsobaKorespondencji]


def _publiczne_ustawienia() -> dict:
    u = ustawienia()
    return {**u, "chmura": _w_chmurze(), "demo": bool(KATALOG_DEMO and not _w_chmurze()),
            "haslo_lokalne": bool(os.getenv("PIECZAPP_SKRZYNKA_HASLO")) and not _w_chmurze(),
            "role": ROLE}


@router.get("/api/korespondencja")
def lista_do_przypisania():
    return _wykonaj(lambda: {"wiadomosci": do_przypisania(), "ustawienia": _publiczne_ustawienia()})


@router.post("/api/korespondencja/pobierz")
def sprawdz_skrzynke():
    return _wykonaj(lambda: {**pobierz_nowe(), "wiadomosci": do_przypisania()})


@router.get("/api/korespondencja/ustawienia")
def pokaz_ustawienia():
    return _publiczne_ustawienia()


@router.put("/api/korespondencja/ustawienia")
def zapisz_ustawienia(dane: UstawieniaSkrzynki):
    def zapis():
        if dane.dostawca not in ("imap", ""):
            raise ValueError("Na razie obsługujemy skrzynki IMAP (Microsoft 365 i Gmail przez OAuth - wkrótce).")
        if dane.haslo:
            if not _w_chmurze():
                raise ValueError("Lokalnie hasło skrzynki podaj w zmiennej PIECZAPP_SKRZYNKA_HASLO "
                                 "(nie w pliku commitowanym do repozytorium).")
            sejf.zapisz(magazyn.kancelaria(), dane.haslo)

        def zmiana(u):
            u.update({"dostawca": dane.dostawca, "host": dane.host.strip(), "port": int(dane.port or 993),
                      "uzytkownik": dane.uzytkownik.strip(), "folder": dane.folder.strip() or "INBOX"})
            if dane.haslo:
                u["haslo_zapisane"] = True
        magazyn.zmien_plik_kancelarii(PLIK_USTAWIEN, zmiana, {})
        log.info("skrzynka %s: zapisano ustawienia (dostawca %s)", magazyn.kancelaria(), dane.dostawca or "brak")
        return _publiczne_ustawienia()
    return _wykonaj(zapis)


@router.post("/api/korespondencja/{id_wiad}/pomin")
def pomin_wiadomosc(id_wiad: str):
    _wykonaj(pomin, id_wiad)
    return {"pominieto": id_wiad}


@router.post("/api/korespondencja/{id_wiad}/przypisz")
def przypisz_do_sprawy(request: Request, id_wiad: str, dane: Przypisanie):
    katalog = _katalog(dane.sprawa)
    kto = str(getattr(request.state, "email", "") or "")
    return _wykonaj(przypisz, id_wiad, katalog, dane.rola, kto)


@router.get("/api/sprawy/{identyfikator}/korespondencja")
def korespondencja_sprawy(identyfikator: str):
    return stan_sprawy(_katalog(identyfikator))


@router.post("/api/sprawy/{identyfikator}/korespondencja/{id_wiad}/ustalenia")
def ustalenia_z_wiadomosci(identyfikator: str, id_wiad: str):
    katalog = _katalog(identyfikator)
    try:
        _wykonaj(wyciagnij_ustalenia, katalog, id_wiad)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - blad modelu: stan „blad” juz zapisany
        raise HTTPException(502, "Model nie odpowiedział - spróbuj ponownie za chwilę.")
    return stan_sprawy(katalog)


@router.put("/api/sprawy/{identyfikator}/korespondencja/osoby")
def osoby_sprawy(identyfikator: str, dane: OsobyKorespondencji):
    katalog = _katalog(identyfikator)
    _wykonaj(ustaw_osoby, katalog, [o.model_dump() for o in dane.osoby])
    return stan_sprawy(katalog)
