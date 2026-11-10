"""Rezerwacje klientow: aplikacja mobilna i strona notarai umawiaja wizyte
w kancelarii na konkretna godzine (jak Booksy), bez konta i bez logowania.

Przeplyw:
  1. GET  /api/klient/kancelarie        - kancelarie w miejscowosci albo najblizej
                                           (online = przyjmuja rezerwacje w notarai)
  2. GET  /api/klient/kancelarie/{id}/terminy - wolne godziny na kolejne dni
  3. POST /api/klient/weryfikacja       - SMS z kodem na numer klienta
  4. POST /api/klient/rezerwacje        - kod + dane -> wpis w kalendarzu kancelarii,
                                           SMS z potwierdzeniem, e-mail do kancelarii
  5. POST/PUT .../rezerwacje/{id}       - podglad, przelozenie, odwolanie tokenem
                                           z odpowiedzi (klient trzyma go w aplikacji)

Wolne godziny i kolizje liczy ten sam silnik co rezerwacje B2B
(rezerwacje_hurtowe.py): polityka kancelarii (dni, godziny, czas wizyty,
wyprzedzenie) plus wpisy kalendarza. Kancelaria wlacza rezerwacje klientow
osobnym przelacznikiem `klienci` w tej polityce - domyslnie wylaczone.
Kancelarie spoza notarai (baza seo/kancelarie.json) sa na liscie bez
terminarza; aplikacja wysyla do nich zgloszenie przez /api/wizyty.

Dane klienta (imie, telefon, e-mail) sa danymi osobowymi: trafiaja tylko do
wpisu w kalendarzu kancelarii (to kancelaria je przetwarza, klient wyraza
zgode w formularzu), nie do logow. Kod weryfikacyjny i numer leza w pliku
administracyjnym wylacznie jako odciski SHA-256, z terminem waznosci.
Przypomnienie dzien przed wizyta wychodzi SMS-em w oknie 8-20.
"""
import hashlib
import logging
import os
import re
import secrets
import threading
import time
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import autoryzacja
import dziennik
import kalendarz
import magazyn
import notariusze
import rezerwacje_hurtowe as hurtowe
import sms
import wizyty
from kalkulator import Limit

log = logging.getLogger("pieczapp.klient")

PLIK = "klienci"                     # obszar administracyjny: weryfikacje SMS i wypisy
WAZNOSC_KODU_S = int(os.getenv("PIECZAPP_KOD_WAZNOSC_S", "600"))
MAKS_PROB_KODU = 5
MAKS_DNI_ZAPYTANIA = 14
PRZYPOMNIENIE_CO_S = int(os.getenv("PIECZAPP_PRZYPOMNIENIA_CO_S", "900"))
ZRODLO = "klient"
STRONA = "https://notarai.pl"

limit_weryfikacji = Limit(int(os.getenv("PIECZAPP_KLIENT_WERYFIKACJE_NA_IP", "10")),
                          int(os.getenv("PIECZAPP_KLIENT_WERYFIKACJE_NA_DOBE", "2000")))
limit_rezerwacji = Limit(int(os.getenv("PIECZAPP_KLIENT_REZERWACJE_NA_IP", "20")),
                         int(os.getenv("PIECZAPP_KLIENT_REZERWACJE_NA_DOBE", "5000")))
_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")

router = APIRouter(prefix="/api/klient", tags=["klient"])
router_admina = APIRouter(prefix="/api/admin/klient", tags=["admin"])


# --- pomocnicze --------------------------------------------------------------


def _teraz() -> datetime:
    return datetime.now(hurtowe.STREFA)


def _linia(tekst, limit: int) -> str:
    return " ".join(str(tekst or "").split())[:limit]


def _sha(tekst: str) -> str:
    return hashlib.sha256(tekst.encode("utf-8")).hexdigest()


def _pusty() -> dict:
    return {"weryfikacje": [], "wypisy": []}


def _wczytaj() -> dict:
    dane = wizyty._w_obszarze_admina(magazyn.wczytaj_plik_kancelarii, PLIK, _pusty())
    dane.setdefault("weryfikacje", [])
    dane.setdefault("wypisy", [])
    return dane


def _zmien(zmiana):
    def opakowana(dane):
        dane.setdefault("weryfikacje", [])
        dane.setdefault("wypisy", [])
        granica = time.time() - 3600
        dane["weryfikacje"] = [w for w in dane["weryfikacje"] if w.get("wygasa", 0) > granica]
        return zmiana(dane)
    try:
        return wizyty._w_obszarze_admina(magazyn.zmien_plik_kancelarii, PLIK, opakowana, _pusty())
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))


def wypisany(numer: str) -> bool:
    try:
        return sms.skrot(numer) in _wczytaj()["wypisy"]
    except Exception as blad:  # noqa: BLE001 - brak pliku nie blokuje potwierdzen
        log.warning("klient: nie udalo sie odczytac wypisow (%s)", dziennik.opis_bledu(blad))
        return False


# --- kancelarie --------------------------------------------------------------


def _polityka_klientow(id_k: str) -> dict | None:
    with hurtowe._WBiurze(id_k):
        p = hurtowe._polityka()
    return p if p.get("klienci") else None


def _kancelarie_online() -> list[tuple[dict, dict]]:
    """(wpis rejestru, polityka) kancelarii, ktore przyjmuja rezerwacje klientow:
    aktywne, w chmurze, z oplaconym abonamentem i zawarta umowa."""
    if not sms.wlaczone():
        return []
    wynik = []
    try:
        rejestr = autoryzacja._wczytaj_rejestr()
    except Exception as blad:  # noqa: BLE001
        log.warning("klient: rejestr kancelarii niedostepny (%s)", dziennik.opis_bledu(blad))
        return []
    for wpis in rejestr.values():
        id_k = wpis["id"]
        if (not wpis.get("aktywna", True) or wpis.get("przechowywanie", "chmura") == "u-klienta"
                or not autoryzacja._oplacona(id_k) or not autoryzacja.umowa_zawarta(id_k)):
            continue
        try:
            p = _polityka_klientow(id_k)
        except Exception as blad:  # noqa: BLE001
            log.warning("kancelaria %s: polityka rezerwacji nieczytelna (%s)", id_k, dziennik.opis_bledu(blad))
            continue
        if p:
            wynik.append((wpis, p))
    return wynik


def _kancelaria_online(id_k: str) -> tuple[dict, dict]:
    for wpis, p in _kancelarie_online():
        if wpis["id"] == id_k:
            return wpis, p
    raise HTTPException(404, "Ta kancelaria nie przyjmuje rezerwacji online.")


def _wizytowka(wpis: dict, p: dict) -> dict:
    dane = wpis.get("dane") or {}
    mapa = wpis.get("mapa") or {}
    return {"id": wpis["id"], "online": True, "nazwa": wpis["nazwa"],
            "notariusze": dane.get("notariusze", ""),
            "adres": p.get("adres") or dane.get("adres", ""), "miasto": p.get("miasto", ""),
            "lat": mapa.get("lat"), "lon": mapa.get("lon"),
            "czas_minut": p.get("czas_minut", 60), "max_dni": p.get("max_dni", 60),
            "telefony": []}


def _z_bazy(k: dict) -> dict:
    return {"id": f"baza-{k['id']}", "baza_id": k["id"], "online": False, "nazwa": k["nazwa"],
            "notariusze": k.get("notariusze", ""), "adres": k.get("adres", ""),
            "miasto": k.get("miejscowosc", ""), "lat": None, "lon": None,
            "telefony": list(k.get("telefony") or []), "www": k.get("www", "")}


@router.get("/konfiguracja")
def konfiguracja():
    """Co aplikacja moze: rezerwacje online wymagaja dzialajacego SMS."""
    return {"rezerwacje_online": sms.wlaczone(), "rodzaje": list(kalendarz.RODZAJE),
            "waznosc_kodu_s": WAZNOSC_KODU_S, "strona": STRONA}


@router.get("/miejscowosci")
def miejscowosci(q: str = ""):
    """Podpowiedzi miejscowosci z bazy kancelarii (nazwa albo slug)."""
    szukane = _linia(q, 60).casefold()
    if len(szukane) < 2:
        return {"miejscowosci": []}
    b = wizyty.baza()
    wynik = [{"slug": m["slug"], "nazwa": m["nazwa"], "liczba": m.get("liczba", 0)}
             for m in b["miejscowosci"].values()
             if m["nazwa"].casefold().startswith(szukane) or m["slug"].startswith(szukane)]
    if len(wynik) < 10:
        wynik += [{"slug": m["slug"], "nazwa": m["nazwa"], "liczba": m.get("liczba", 0)}
                  for m in b["miejscowosci"].values()
                  if szukane in m["nazwa"].casefold() and not m["nazwa"].casefold().startswith(szukane)]
    wynik.sort(key=lambda m: (-m["liczba"], m["nazwa"]))
    return {"miejscowosci": wynik[:10]}


@router.get("/kancelarie")
def kancelarie(miasto: str = "", lat: float | None = None, lon: float | None = None):
    """Kancelarie dla klienta. `miasto` (slug z /miejscowosci): kancelarie
    notarai z terminarzem online na gorze, potem reszta z bazy (zgloszenie).
    `lat`+`lon`: kancelarie online od najblizszej, z odlegloscia w km."""
    if (lat is None) != (lon is None):
        raise HTTPException(400, "Podaj lat i lon razem.")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(400, "Współrzędne poza zakresem.")
    online = [_wizytowka(w, p) for w, p in _kancelarie_online()]
    if lat is not None:
        z_polozeniem = [k for k in online if k["lat"] is not None]
        for k in z_polozeniem:
            k["odleglosc_km"] = round(notariusze.odleglosc_km(lat, lon, k["lat"], k["lon"]), 1)
        z_polozeniem.sort(key=lambda k: (k["odleglosc_km"], k["nazwa"].lower()))
        return {"kancelarie": z_polozeniem[:30], "miejscowosc": None}
    slug = _linia(miasto, 80).casefold()
    if not slug:
        online.sort(key=lambda k: k["nazwa"].lower())
        return {"kancelarie": online, "miejscowosc": None}
    b = wizyty.baza()
    miejscowosc = b["miejscowosci"].get(slug)
    if not miejscowosc:
        raise HTTPException(404, "Nie znamy takiej miejscowości.")
    powiazane = {v: k for k, v in wizyty.kancelarie_notarai().items()}   # id notarai -> id bazy
    w_miescie = [k for k in online if k["miasto"].casefold() == miejscowosc["nazwa"].casefold()]
    pominac = {powiazane[k["id"]] for k in w_miescie if k["id"] in powiazane}
    for k in w_miescie:
        if k["id"] in powiazane:
            k["baza_id"] = powiazane[k["id"]]
            baza_k = b["kancelarie"].get(powiazane[k["id"]])
            if baza_k and not k["telefony"]:
                k["telefony"] = list(baza_k.get("telefony") or [])
    reszta = [_z_bazy(b["kancelarie"][i]) for i in b["wg_miejscowosci"].get(slug, []) if i not in pominac]
    w_miescie.sort(key=lambda k: k["nazwa"].lower())
    reszta.sort(key=lambda k: k["nazwa"].lower())
    return {"kancelarie": w_miescie + reszta,
            "miejscowosc": {"slug": slug, "nazwa": miejscowosc["nazwa"]}}


@router.get("/kancelarie/{id_k}/terminy")
def terminy(id_k: str, od: str = "", dni: int = 7):
    """Wolne godziny kancelarii online na kolejne dni (najwyzej 14)."""
    wpis, p = _kancelaria_online(id_k)
    dni = max(1, min(dni, MAKS_DNI_ZAPYTANIA))
    start = hurtowe._data(od) if od else _teraz().date()
    dzis = _teraz().date()
    if start < dzis:
        start = dzis
    with hurtowe._WBiurze(id_k):
        wpisy = magazyn.wczytaj_plik_kancelarii("kalendarz", [])
        opisy = kalendarz.dni()
    wynik = []
    for i in range(dni):
        d = start + timedelta(days=i)
        dzien = d.isoformat()
        nieczynne = bool(opisy.get(dzien, {}).get("nieczynne"))
        sloty = [] if nieczynne else hurtowe._dostepne(wpisy, p, dzien)
        wynik.append({"data": dzien, "nieczynne": nieczynne,
                      "terminy": [{"godzina": s["godzina"], "koniec": s["koniec"]} for s in sloty]})
    return {"kancelaria": _wizytowka(wpis, p), "czas_minut": p["czas_minut"],
            "od": start.isoformat(), "max_dni": p["max_dni"], "dni": wynik}


# --- weryfikacja numeru ------------------------------------------------------


class Weryfikacja(BaseModel):
    telefon: str = Field(min_length=7, max_length=40)
    strona: str = ""                  # pulapka na automaty


@router.post("/weryfikacja", status_code=201)
def weryfikacja(dane: Weryfikacja, request: Request):
    """SMS z szesciocyfrowym kodem. Zwraca identyfikator weryfikacji; kod
    i numer leza w pliku tylko jako odciski."""
    if dane.strona:
        return {"id": "", "wygasa_s": WAZNOSC_KODU_S, "koncowka": ""}
    if not sms.wlaczone():
        raise HTTPException(503, "Rezerwacje online są chwilowo niedostępne. Zostaw zgłoszenie, kancelaria oddzwoni.")
    numer = sms.normalizuj_numer(dane.telefon)
    if not numer:
        raise HTTPException(400, "Podaj numer telefonu komórkowego, np. 600 000 000.")
    limit_weryfikacji.sprawdz(autoryzacja.adres_klienta(request),
                              "Za dużo prób weryfikacji. Spróbuj za godzinę.")
    odcisk = sms.skrot(numer)
    teraz = time.time()
    aktywne = [w for w in _wczytaj()["weryfikacje"]
               if w["numer"] == odcisk and w["wygasa"] > teraz and not w.get("uzyta")]
    if len(aktywne) >= 3:
        raise HTTPException(429, "Kod już został wysłany. Poczekaj chwilę i sprawdź SMS.")
    kod = sms.kod_weryfikacyjny()
    wynik = sms.wyslij(numer, f"notarai: Twoj kod do umowienia wizyty u notariusza: {kod}. "
                              f"Wazny {WAZNOSC_KODU_S // 60} minut.", sms.KRYTYCZNY)
    if not wynik["wyslano"]:
        powod = wynik["powod"]
        if powod == "limit_numeru":
            raise HTTPException(429, "Za dużo SMS-ów na ten numer. Spróbuj za godzinę.")
        raise HTTPException(502, "Nie udało się wysłać SMS-a. Sprawdź numer albo spróbuj za chwilę.")
    w = {"id": uuid.uuid4().hex[:16], "numer": odcisk, "kod": _sha(kod), "proby": 0,
         "uzyta": None, "wygasa": teraz + WAZNOSC_KODU_S, "rezerwacja": None}

    def dodaj(d):
        d["weryfikacje"].append(w)
    _zmien(dodaj)
    log.info("klient: weryfikacja %s wyslana (%s)", w["id"], wynik.get("tryb", "twilio"))
    odpowiedz = {"id": w["id"], "wygasa_s": WAZNOSC_KODU_S, "koncowka": sms.koncowka(numer)}
    if sms.testowy():
        odpowiedz["kod_testowy"] = kod   # tylko PIECZAPP_SMS_TRYB=test, nic nie wychodzi
    return odpowiedz


def _sprawdz_kod(identyfikator: str, kod: str, numer: str) -> dict:
    """Zuzywa kod. Zwraca wpis weryfikacji (z ewentualna wczesniejsza rezerwacja)."""
    odcisk_numeru, odcisk_kodu = sms.skrot(numer), _sha(str(kod or "").strip())
    teraz = time.time()

    def zmien(d):
        """Zwraca (wpis, None) albo (None, blad). Bledna proba musi zostac
        ZAPISANA, wiec wyjatek leci dopiero po zapisie pliku."""
        for w in d["weryfikacje"]:
            if w["id"] == identyfikator and w["numer"] == odcisk_numeru:
                if w.get("uzyta"):
                    if secrets.compare_digest(w["kod"], odcisk_kodu) and w.get("rezerwacja"):
                        return dict(w), None       # powtorka tego samego zadania - idempotentna
                    return None, HTTPException(400, "Ten kod został już wykorzystany. Poproś o nowy.")
                if w["wygasa"] < teraz:
                    return None, HTTPException(400, "Kod wygasł. Poproś o nowy.")
                if w["proby"] >= MAKS_PROB_KODU:
                    return None, HTTPException(429, "Za dużo prób. Poproś o nowy kod.")
                if not secrets.compare_digest(w["kod"], odcisk_kodu):
                    w["proby"] += 1
                    return None, HTTPException(400, "Nieprawidłowy kod.")
                w["uzyta"] = teraz
                return dict(w), None
        return None, HTTPException(400, "Najpierw potwierdź numer telefonu kodem z SMS-a.")
    wpis, blad = _zmien(zmien)
    if blad:
        raise blad
    return wpis


def _odnotuj_rezerwacje(identyfikator: str, rezerwacja: dict) -> None:
    def zmien(d):
        for w in d["weryfikacje"]:
            if w["id"] == identyfikator:
                w["rezerwacja"] = rezerwacja
    _zmien(zmien)


# --- rezerwacja --------------------------------------------------------------


class Rezerwacja(BaseModel):
    kancelaria: str = Field(min_length=1, max_length=100)
    data: str
    godzina: str
    rodzaj: str
    rodzaj_inny: str = Field(default="", max_length=200)
    imie: str = Field(min_length=2, max_length=80)
    telefon: str = Field(min_length=7, max_length=40)
    email: str = Field(default="", max_length=120)
    uwagi: str = Field(default="", max_length=1000)
    zgoda: bool = False
    weryfikacja: str = Field(min_length=1, max_length=40)
    kod: str = Field(min_length=4, max_length=12)
    strona: str = ""


class Dostep(BaseModel):
    kancelaria: str = Field(min_length=1, max_length=100)
    token: str = Field(min_length=20, max_length=120)


class Przelozenie(Dostep):
    data: str
    godzina: str


def _publiczny(w: dict, wpis_k: dict, p: dict) -> dict:
    return {"id": w["id"], "status": w.get("status", "potwierdzona"),
            "data": w["data"], "godzina": w["godzina"], "koniec": w.get("koniec", ""),
            "rodzaj": w.get("rodzaj", ""), "rodzaj_inny": w.get("rodzaj_inny", ""),
            "utworzono": w.get("utworzono", ""),
            "kancelaria": {k: v for k, v in _wizytowka(wpis_k, p).items()
                           if k in ("id", "nazwa", "adres", "miasto", "lat", "lon", "telefony")}}


def _opis_dla_kancelarii(w: dict, kiedy: str) -> str:
    k = w.get("klient") or {}
    linie = [f"Termin: {w['data']} {w['godzina']}-{w.get('koniec', '')}",
             f"Czynność: {w.get('rodzaj_inny') or w.get('rodzaj', '')}",
             f"Klient: {k.get('imie', '')}", f"Telefon: {k.get('telefon') or 'nie podano'}",
             f"E-mail: {k.get('email') or 'nie podano'}"]
    if k.get("uwagi"):
        linie.append(f"Uwagi klienta: {k['uwagi']}")
    linie += ["", f"Rezerwacja {w['id']} z aplikacji notarai, {kiedy}. Numer telefonu klient potwierdził kodem SMS.",
              "Wizyta jest w Twoim kalendarzu w aplikacji notarai."]
    return "\n".join(linie)


def _email_do_kancelarii(id_k: str, temat: str, tresc: str) -> bool:
    return wizyty._wyslij_email(wizyty._emaile_kancelarii(id_k), temat, tresc)


def _sms_potwierdzenia(w: dict, wpis_k: dict, p: dict) -> dict:
    k = w.get("klient") or {}
    return sms.wyslij(k.get("telefon", ""),
                      f"notarai: wizyta potwierdzona. {wpis_k['nazwa']}, {p.get('adres', '')}, "
                      f"{w['data']} godz. {w['godzina']}. Wez dowod osobisty. "
                      f"Zmiana lub odwolanie: w aplikacji notarai.", sms.KRYTYCZNY)


def _sprawdz_rezerwacje(dane: Rezerwacja) -> dict:
    if not dane.zgoda:
        raise HTTPException(400, "Potrzebna jest zgoda na przekazanie danych kancelarii.")
    if dane.rodzaj not in kalendarz.RODZAJE:
        raise HTTPException(400, "Nieznany rodzaj czynności.")
    if dane.rodzaj == "inne" and len(_linia(dane.rodzaj_inny, 200)) < 2:
        raise HTTPException(400, "Napisz, jakiej czynności dotyczy wizyta.")
    imie = _linia(dane.imie, 80)
    if len(imie) < 2:
        raise HTTPException(400, "Podaj imię i nazwisko.")
    telefon = sms.normalizuj_numer(dane.telefon)
    if not telefon:
        raise HTTPException(400, "Numer telefonu wygląda na niepełny.")
    email = _linia(dane.email, 120).lower()
    if email and not _EMAIL.match(email):
        raise HTTPException(400, "To nie wygląda na adres e-mail.")
    hurtowe._data(dane.data)
    hurtowe._minuty(dane.godzina)
    return {"imie": imie, "telefon": telefon, "email": email, "uwagi": str(dane.uwagi or "").strip()[:1000]}


@router.post("/rezerwacje", status_code=201)
def rezerwuj(dane: Rezerwacja, request: Request):
    if dane.strona:
        return {"id": "", "token": "", "komunikat": "Dziękujemy."}
    klient = _sprawdz_rezerwacje(dane)
    limit_rezerwacji.sprawdz(autoryzacja.adres_klienta(request), "Za dużo prób. Spróbuj za godzinę.")
    wpis_k, p = _kancelaria_online(dane.kancelaria)
    weryfikacja = _sprawdz_kod(dane.weryfikacja, dane.kod, klient["telefon"])
    if weryfikacja.get("rezerwacja"):
        poprzednia = weryfikacja["rezerwacja"]
        if poprzednia.get("kancelaria") == dane.kancelaria:
            return poprzednia["odpowiedz"]
        raise HTTPException(400, "Ten kod został już wykorzystany. Poproś o nowy.")
    token = secrets.token_urlsafe(32)
    rodzaj_inny = _linia(dane.rodzaj_inny, 200) if dane.rodzaj == "inne" else ""
    teraz_iso = _teraz().isoformat(timespec="seconds")

    with hurtowe._WBiurze(dane.kancelaria):
        if kalendarz.dni().get(dane.data, {}).get("nieczynne"):
            raise HTTPException(409, "Kancelaria jest tego dnia nieczynna.")

        def zmiana(wpisy):
            if dane.godzina not in {s["godzina"] for s in hurtowe._dostepne(wpisy, p, dane.data)}:
                raise HTTPException(409, "Ten termin został właśnie zajęty. Wybierz inną godzinę.")
            m = hurtowe._minuty(dane.godzina)
            opis = rodzaj_inny or dane.rodzaj
            nowy = kalendarz._sprawdz({
                "data": dane.data, "godzina": dane.godzina, "koniec": hurtowe._hhmm(m + p["czas_minut"]),
                "tytul": f"Wizyta z aplikacji: {opis} ({klient['imie']})",
                "rodzaj": dane.rodzaj, "rodzaj_inny": rodzaj_inny,
                "uczestnicy": klient["imie"],
                "telefony": [{"imie": klient["imie"], "numer": klient["telefon"]}],
                "uwagi": ("Rezerwacja z aplikacji notarai. Klient potwierdził numer telefonu kodem SMS.\n"
                          + (f"E-mail klienta: {klient['email']}\n" if klient["email"] else "")
                          + (f"Uwagi klienta: {klient['uwagi']}" if klient["uwagi"] else "")).strip(),
            })
            w = {"id": uuid.uuid4().hex[:12], **nowy, "zrodlo": ZRODLO, "status": "potwierdzona",
                 "klient": klient, "token": _sha(token), "weryfikacja": dane.weryfikacja,
                 "przypomnienie": None, "utworzono": teraz_iso}
            kalendarz._sprawdz_kolizje(wpisy, w)
            wpisy.append(w)
            return w
        w = hurtowe._zapisz_kalendarz(zmiana)

    odpowiedz = {**_publiczny(w, wpis_k, p), "token": token,
                 "komunikat": f"Wizyta w kancelarii {wpis_k['nazwa']} jest umówiona na {w['data']} o {w['godzina']}."}
    _odnotuj_rezerwacje(dane.weryfikacja, {"kancelaria": dane.kancelaria, "odpowiedz": odpowiedz})
    wyslany = _sms_potwierdzenia(w, wpis_k, p)
    email = _email_do_kancelarii(dane.kancelaria, f"Nowa wizyta z aplikacji: {w['data']} {w['godzina']}",
                                 "Klient umówił wizytę przez aplikację notarai.\n\n" + _opis_dla_kancelarii(w, teraz_iso))
    log.info("klient: rezerwacja %s w kancelarii %s (sms=%s, e-mail=%s)", w["id"], dane.kancelaria,
             "tak" if wyslany["wyslano"] else wyslany["powod"], "tak" if email else "nie")
    return odpowiedz


def _z_tokenem(id_k: str, id_w: str, token: str, zmiana=None) -> dict:
    """Odczyt albo zmiana wlasnej rezerwacji. Token z odpowiedzi rezerwacji."""
    wpis_k, p = _kancelaria_online(id_k)
    odcisk = _sha(token)

    def znajdz(wpisy):
        w = next((x for x in wpisy if x["id"] == id_w and x.get("zrodlo") == ZRODLO), None)
        if not w or not secrets.compare_digest(w.get("token", ""), odcisk):
            raise HTTPException(404, "Nie znaleziono takiej rezerwacji.")
        if zmiana:
            zmiana(wpisy, w)
        return dict(w)
    with hurtowe._WBiurze(id_k):
        if zmiana:
            w = hurtowe._zapisz_kalendarz(znajdz)
        else:
            w = znajdz(magazyn.wczytaj_plik_kancelarii("kalendarz", []))
    return {"wpis": w, "kancelaria": wpis_k, "polityka": p}


@router.post("/rezerwacje/{id_w}/podglad")
def podglad(id_w: str, dane: Dostep):
    """Token idzie w ciele zadania, nie w adresie: adresy trafiaja do logow
    dostepowych serwera i load balancera, a token daje prawo odwolania wizyty."""
    r = _z_tokenem(dane.kancelaria, id_w, dane.token)
    return _publiczny(r["wpis"], r["kancelaria"], r["polityka"])


@router.post("/rezerwacje/{id_w}/anuluj")
def anuluj(id_w: str, dane: Dostep):
    kiedy = _teraz().isoformat(timespec="seconds")
    odwolano = []

    def zmiana(wpisy, w):
        if w.get("status") == "anulowana":
            return
        w["status"] = "anulowana"
        w["anulowano"] = kiedy
        w["anulowal"] = "klient"
        odwolano.append(w["id"])
    r = _z_tokenem(dane.kancelaria, id_w, dane.token, zmiana)
    w, wpis_k, p = r["wpis"], r["kancelaria"], r["polityka"]
    if odwolano:
        sms.wyslij((w.get("klient") or {}).get("telefon", ""),
                   f"notarai: wizyta {w['data']} godz. {w['godzina']} w kancelarii {wpis_k['nazwa']} "
                   f"zostala odwolana na Twoja prosbe.", sms.KRYTYCZNY)
        _email_do_kancelarii(dane.kancelaria, f"Klient odwołał wizytę: {w['data']} {w['godzina']}",
                             "Klient odwołał wizytę umówioną przez aplikację notarai. Termin jest znów wolny.\n\n"
                             + _opis_dla_kancelarii(w, kiedy))
        log.info("klient: rezerwacja %s odwolana przez klienta", id_w)
    return _publiczny(w, wpis_k, p)


@router.put("/rezerwacje/{id_w}")
def przeloz(id_w: str, dane: Przelozenie):
    hurtowe._data(dane.data)
    hurtowe._minuty(dane.godzina)
    _, p = _kancelaria_online(dane.kancelaria)
    with hurtowe._WBiurze(dane.kancelaria):
        if kalendarz.dni().get(dane.data, {}).get("nieczynne"):
            raise HTTPException(409, "Kancelaria jest tego dnia nieczynna.")
    stary = {}

    def zmiana(wpisy, w):
        if w.get("status") == "anulowana":
            raise HTTPException(409, "Odwołanej wizyty nie da się przełożyć. Umów nową.")
        stary.update(data=w["data"], godzina=w["godzina"])
        inne = [x for x in wpisy if x["id"] != w["id"]]
        if dane.godzina not in {s["godzina"] for s in hurtowe._dostepne(inne, p, dane.data)}:
            raise HTTPException(409, "Ten termin nie jest już dostępny.")
        m = hurtowe._minuty(dane.godzina)
        w.update(data=dane.data, godzina=dane.godzina, koniec=hurtowe._hhmm(m + p["czas_minut"]),
                 przypomnienie=None, przelozono=_teraz().isoformat(timespec="seconds"))
        kalendarz._sprawdz_kolizje(wpisy, w, pomin=w["id"])
    r = _z_tokenem(dane.kancelaria, id_w, dane.token, zmiana)
    w, wpis_k = r["wpis"], r["kancelaria"]
    if stary and (stary["data"], stary["godzina"]) != (w["data"], w["godzina"]):
        sms.wyslij((w.get("klient") or {}).get("telefon", ""),
                   f"notarai: wizyta w kancelarii {wpis_k['nazwa']} przelozona na {w['data']} godz. {w['godzina']}.",
                   sms.KRYTYCZNY)
        _email_do_kancelarii(dane.kancelaria, f"Klient przełożył wizytę na {w['data']} {w['godzina']}",
                             f"Poprzedni termin: {stary['data']} {stary['godzina']}.\n\n"
                             + _opis_dla_kancelarii(w, w["przelozono"]))
        log.info("klient: rezerwacja %s przelozona przez klienta", id_w)
    return _publiczny(w, wpis_k, p)


# --- zmiany po stronie kancelarii -------------------------------------------


def odwolaj_przez_kancelarie(id_w: str) -> bool:
    """Kancelaria usuwa w kalendarzu wizyte klienta z aplikacji. Wpis nie znika,
    tylko dostaje status "anulowana" (jak przy odwolaniu przez klienta): z
    kalendarza kancelarii i z wolnych terminow schodzi tak samo, a aplikacja
    klienta po odswiezeniu pokazuje "Odwolana" zamiast nieaktualnego potwierdzenia."""
    kiedy = _teraz().isoformat(timespec="seconds")

    def zmiana(wpisy):
        for w in wpisy:
            if w["id"] == id_w and w.get("zrodlo") == ZRODLO and w.get("status") != "anulowana":
                w.update(status="anulowana", anulowano=kiedy, anulowal="kancelaria", przypomnienie=None)
                return True
        return False
    return magazyn.zmien_plik_kancelarii("kalendarz", zmiana, [])


def powiadom_o_zmianie_kancelarii(stary: dict | None, nowy: dict | None) -> None:
    """Kancelaria usunela albo przesunela wizyte klienta w swoim kalendarzu:
    klient dostaje SMS. Wolane z app.py; bledy nie przerywaja zapisu."""
    try:
        if not stary or stary.get("zrodlo") != ZRODLO or stary.get("status") == "anulowana":
            return
        telefon = (stary.get("klient") or {}).get("telefon", "")
        nazwa = ""
        try:
            _, wpis_k = autoryzacja._znajdz(autoryzacja._wczytaj_rejestr(), magazyn.kancelaria())
            nazwa = (wpis_k or {}).get("nazwa", "")
        except Exception:  # noqa: BLE001
            pass
        gdzie = f" w kancelarii {nazwa}" if nazwa else ""
        if nowy is None:
            tresc = (f"notarai: kancelaria{gdzie} odwolala wizyte {stary['data']} godz. {stary['godzina']}. "
                     "Umow nowy termin w aplikacji albo skontaktuj sie z kancelaria.")
        elif (nowy.get("data"), nowy.get("godzina")) != (stary.get("data"), stary.get("godzina")):
            tresc = (f"notarai: kancelaria{gdzie} przeniosla Twoja wizyte na {nowy['data']} godz. {nowy['godzina']}. "
                     "Jesli termin nie pasuje, skontaktuj sie z kancelaria.")
        else:
            return
        wynik = sms.wyslij(telefon, tresc, sms.KRYTYCZNY)
        log.info("klient: zmiana wizyty %s przez kancelarie, sms=%s", stary.get("id"),
                 "tak" if wynik["wyslano"] else wynik["powod"])
    except Exception as blad:  # noqa: BLE001
        log.warning("klient: powiadomienie o zmianie nie wyszlo (%s)", dziennik.opis_bledu(blad))


# --- przypomnienia -----------------------------------------------------------


def wyslij_przypomnienia(teraz: datetime | None = None) -> dict:
    """SMS dzien przed wizyta, raz na wizyte. Najpierw atomowo oznaczamy wpis
    (warunkowy zapis S3), potem wysylamy - dwie kopie aplikacji nie wysla
    dwa razy. Poza oknem 8-20 nic nie robi."""
    teraz = teraz or _teraz()
    wynik = {"wyslane": 0, "pominiete": 0, "kancelarie": 0}
    if not sms.wlaczone() or not sms.w_oknie(teraz):
        return wynik
    jutro = (teraz + timedelta(days=1)).date().isoformat()
    for wpis_k, p in _kancelarie_online():
        wynik["kancelarie"] += 1
        do_wyslania: list[dict] = []
        znacznik = teraz.isoformat(timespec="seconds")

        def zmiana(wpisy):
            for w in wpisy:
                if (w.get("zrodlo") == ZRODLO and w.get("status") == "potwierdzona"
                        and w.get("data") == jutro and not w.get("przypomnienie")):
                    w["przypomnienie"] = znacznik
                    do_wyslania.append(dict(w))
        try:
            with hurtowe._WBiurze(wpis_k["id"]):
                magazyn.zmien_plik_kancelarii("kalendarz", zmiana, [])
        except Exception as blad:  # noqa: BLE001
            log.warning("kancelaria %s: przypomnienia nie oznaczone (%s)", wpis_k["id"], dziennik.opis_bledu(blad))
            continue
        for w in do_wyslania:
            telefon = (w.get("klient") or {}).get("telefon", "")
            r = sms.wyslij(telefon, f"notarai: przypominamy o wizycie jutro {w['data']} o {w['godzina']} "
                                    f"w kancelarii {wpis_k['nazwa']}, {p.get('adres', '')}. Wez dowod osobisty.",
                           sms.AUTOMATYCZNY, wypisany=wypisany(telefon))
            wynik["wyslane" if r["wyslano"] else "pominiete"] += 1
    if do_wyslania_lacznie := wynik["wyslane"] + wynik["pominiete"]:
        log.info("klient: przypomnienia %s wyslane, %s pominiete", wynik["wyslane"], do_wyslania_lacznie - wynik["wyslane"])
    return wynik


_watek: threading.Thread | None = None


def uruchom_przypomnienia_w_tle() -> bool:
    """Watek sprawdzajacy co PRZYPOMNIENIE_CO_S, czy sa wizyty do przypomnienia.
    Tylko gdy SMS dziala i PIECZAPP_PRZYPOMNIENIA nie jest "0"."""
    global _watek
    if not sms.wlaczone() or os.getenv("PIECZAPP_PRZYPOMNIENIA", "1") == "0" or _watek:
        return False

    def petla():
        while True:
            time.sleep(PRZYPOMNIENIE_CO_S)
            try:
                wyslij_przypomnienia()
            except Exception as blad:  # noqa: BLE001
                log.warning("klient: przypomnienia nie poszly (%s)", dziennik.opis_bledu(blad))
    _watek = threading.Thread(target=petla, name="przypomnienia-sms", daemon=True)
    _watek.start()
    return True


# --- odpowiedzi SMS (webhook Twilio) ----------------------------------------
# Numer notarai ma wlasny webhook (nie wspolny z Finance You). STOP wypisuje
# numer z przypomnien; inne tresci ignorujemy - kancelaria kontaktuje sie sama.

WEBHOOK_TOKEN = os.getenv("PIECZAPP_TWILIO_WEBHOOK_TOKEN", "")


@router.post("/sms-przychodzacy")
async def sms_przychodzacy(request: Request, token: str = ""):
    if not WEBHOOK_TOKEN or not secrets.compare_digest(token, WEBHOOK_TOKEN):
        raise HTTPException(403, "Brak dostępu.")
    formularz = await request.form()
    numer = sms.normalizuj_numer(str(formularz.get("From", "")))
    tresc = str(formularz.get("Body", ""))
    if numer and sms.stop_w_tresci(tresc):
        odcisk = sms.skrot(numer)

        def zmiana(d):
            if odcisk not in d["wypisy"]:
                d["wypisy"].append(odcisk)
        _zmien(zmiana)
        log.info("klient: numer wypisany z przypomnien SMS")
    from fastapi.responses import Response
    return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="text/xml")


# --- administrator -----------------------------------------------------------


@router_admina.post("/przypomnienia")
def przypomnienia_teraz(request: Request):
    autoryzacja._wymagaj_admina(request)
    return wyslij_przypomnienia()


@router_admina.get("/stan")
def stan(request: Request):
    autoryzacja._wymagaj_admina(request)
    brak = sms.gotowe()
    return {"sms": {"tryb": sms.TRYB, "gotowe": not brak, "brak": brak},
            "kancelarie_online": [{"id": w["id"], "nazwa": w["nazwa"], "miasto": p.get("miasto", "")}
                                  for w, p in _kancelarie_online()],
            "przypomnienia_w_tle": bool(_watek and _watek.is_alive())}
