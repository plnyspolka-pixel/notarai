"""Gielda leadow: zapytanie klienta otwarte dla wszystkich kancelarii przez godzine.

Lead to podstawowa jednostka, ktora dajemy kancelariom: imie i nazwisko,
kontakt, rodzaj sprawy, opis, miejscowosc (+ co dalo sie wyciagnac z Meta).
Zrodla: formularz leadowy Meta (webhook /api/meta/leadgen), strona notarai.pl
("dowolna kancelaria w miejscowosci"), teczka sprawy bez wybranej kancelarii.

Zasada:
  1. OKNO (domyslnie 60 min) - kazda kancelaria z wykazu w miejscowosci
     klienta dostaje e-mail z SAMA sprawa (rodzaj, opis, miejscowosc, bez
     kontaktu) i jednorazowym linkiem. Kto odpowie w oknie, dostaje kontakt
     klienta, a jego odpowiedz idzie do klienta. Wszyscy na rownych zasadach,
     placacy i nieplacacy; kolejnosc wysylki to rotacja (rekomendacje.py).
  2. ARCHIWUM - po oknie lead z kontaktem widza juz tylko kancelarie
     z oplaconym abonamentem notarai (z tej samej izby notarialnej).

Kontakt klienta nigdy nie trafia do e-maila wysylanego do wszystkich: inaczej
archiwum nie mialoby wartosci. Dane klienta nie trafiaja do logow.
"""
import hashlib
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import autoryzacja
import dziennik
import magazyn
import rekomendacje
import taksa
import wizyty

log = logging.getLogger("pieczapp.leady")

PLIK = "leady"
OKNO_MIN = int(os.getenv("PIECZAPP_LEADY_OKNO_MIN", "60"))
RETENCJA_DNI = int(os.getenv("PIECZAPP_LEADY_RETENCJA_DNI", "180"))
MAKS_ADRESATOW = int(os.getenv("PIECZAPP_LEADY_MAKS_ADRESATOW", "60"))
STRONA_ODPOWIEDZI = f"{wizyty.STRONA}/lead/#"

# Rodzaje spraw, jak w formularzu Meta i na stronie. Slowa -> rodzaj.
SPRAWY = {
    "sprzedaz": ("Sprzedaż / kupno nieruchomości", ("sprzeda", "kupn", "kupuj", "zakup", "nabyc")),
    "darowizna": ("Darowizna", ("darow",)),
    "spadek": ("Spadek, poświadczenie dziedziczenia", ("spadk", "dziedzicz", "zgon", "zmarł", "zmarl")),
    "dzial": ("Dział spadku, zniesienie współwłasności", ("dział", "dzial", "zniesien", "współwłas", "wspolwlas")),
    "testament": ("Testament", ("testament",)),
    "pelnomocnictwo": ("Pełnomocnictwo", ("pełnomoc", "pelnomoc")),
    "przedwstepna": ("Umowa przedwstępna", ("przedwstęp", "przedwstep")),
    "deweloper": ("Umowa deweloperska", ("deweloper",)),
    "hipoteka": ("Hipoteka, kredyt", ("hipotek", "kredyt")),
    "majatkowa": ("Intercyza (umowa majątkowa małżeńska)", ("intercyz", "majątkow", "majatkow", "rozdzielno")),
    "spolka": ("Spółka", ("spółk", "spolk")),
    "sluzebnosc": ("Służebność, dożywocie", ("służebn", "sluzebn", "dożywoc", "dozywoc")),
    "poswiadczenie": ("Poświadczenie podpisu lub dokumentu", ("poświadcz", "poswiadcz", "podpis", "odpis")),
    "inne": ("Inna sprawa", ()),
}


def rodzaj_sprawy(tekst: str) -> str:
    t = (tekst or "").lower()
    if t in SPRAWY:
        return t
    for klucz, (nazwa, slowa) in SPRAWY.items():
        if nazwa.lower() == t or any(s in t for s in slowa):
            return klucz
    return "inne"


# ---------------------------------------------------------------- magazyn


def _wczytaj() -> dict:
    return wizyty._w_obszarze_admina(magazyn.wczytaj_plik_kancelarii, PLIK, {"leady": []})


def _zmien(zmiana):
    def opakowana(dane):
        dane.setdefault("leady", [])
        granica = (datetime.now() - timedelta(days=RETENCJA_DNI)).isoformat(timespec="seconds")
        dane["leady"] = [l for l in dane["leady"] if l.get("utworzono", "") >= granica]
        return zmiana(dane)
    try:
        return wizyty._w_obszarze_admina(magazyn.zmien_plik_kancelarii, PLIK, opakowana, {"leady": []})
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))


def _teraz() -> datetime:
    return datetime.now()


def _skrot(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def w_oknie(lead: dict, teraz: datetime | None = None) -> bool:
    return (teraz or _teraz()).isoformat(timespec="seconds") < lead["okno_do"]


def _linia(tekst, limit: int) -> str:
    return " ".join(str(tekst or "").split())[:limit]


# ---------------------------------------------------------------- tworzenie i rozsylka


def adresaci(slug: str) -> list[dict]:
    """Kancelarie z wykazu w miejscowosci, ktore maja e-mail. Kolejnosc
    wysylki: rotacja dnia (nikt nie dostaje maila stale pierwszy)."""
    b = wizyty.baza()
    lista = [b["kancelarie"][i] for i in b["wg_miejscowosci"].get(slug, []) if b["kancelarie"][i].get("email")]
    return rekomendacje.kolejnosc(lista, kontekst=f"leady|{slug}")[:MAKS_ADRESATOW]


def _anonim(lead: dict) -> dict:
    """To, co widzi kazda kancelaria przed odpowiedzia: bez kontaktu i nazwiska."""
    return {"id": lead["id"], "sprawa": SPRAWY[lead["sprawa"]][0], "opis": lead["opis"],
            "miejscowosc": lead["miejscowosc_nazwa"], "utworzono": lead["utworzono"], "okno_do": lead["okno_do"],
            "zapytanie": lead.get("zapytanie", ""), "odpowiedzi": len(lead["odpowiedzi"])}


def _pelny(lead: dict) -> dict:
    return {**_anonim(lead), "klient": lead["klient"], "zrodlo": lead["zrodlo"]}


def _mail_do_kancelarii(lead: dict, token: str) -> str:
    return (f"Dzień dobry,\n\nklient z miejscowości {lead['miejscowosc_nazwa']} szuka notariusza.\n\n"
            f"Sprawa: {SPRAWY[lead['sprawa']][0]}\n"
            + (f"Opis: {lead['opis']}\n" if lead["opis"] else "")
            + f"\nZapytanie dostały wszystkie kancelarie z miejscowości {lead['miejscowosc_nazwa']}, na tych samych zasadach. "
            f"Do {lead['okno_do'][11:16]} każda może odpowiedzieć klientowi – po odpowiedzi zobaczy jego dane kontaktowe:\n"
            f"{STRONA_ODPOWIEDZI}{token}\n\n"
            "Po tym czasie zapytanie trafia do archiwum, które widzą kancelarie korzystające z notarai.pl.\n\n"
            f"Zespół notarai, kontakt@notarai.pl\n"
            "Jeśli kancelaria nie chce dostawać takich zapytań, wystarczy odpowiedzieć na tę wiadomość.")


def nowy(*, klient: dict, sprawa: str, opis: str, miejscowosc: str, zrodlo: str,
         meta: dict | None = None, zapytanie: str = "") -> dict:
    """Tworzy lead i rozsyla zaproszenia. `miejscowosc` - slug albo nazwa."""
    import teczka
    m = teczka._miejsce(miejscowosc)
    slug = m["slug"] or (miejscowosc if miejscowosc in wizyty.baza()["miejscowosci"] else None)
    nazwa = wizyty.baza()["miejscowosci"][slug]["nazwa"] if slug else m["tekst"]
    teraz = _teraz()
    lead = {
        "id": uuid.uuid4().hex[:12], "utworzono": teraz.isoformat(timespec="seconds"),
        "okno_do": (teraz + timedelta(minutes=OKNO_MIN)).isoformat(timespec="seconds"),
        "zrodlo": zrodlo, "meta": meta or {},
        "klient": {k: _linia(klient.get(k), 120) for k in ("imie", "nazwisko", "telefon", "email")},
        "sprawa": rodzaj_sprawy(sprawa), "sprawa_tekst": _linia(sprawa, 200),
        "opis": str(opis or "").strip()[:2000], "zapytanie": zapytanie[:8000],
        "miejscowosc": slug, "miejscowosc_nazwa": nazwa,
        "zaproszenia": {}, "odpowiedzi": [], "wyslano": 0,
    }
    tokeny = {}
    for k in adresaci(slug) if slug else []:
        token = secrets.token_urlsafe(18)
        lead["zaproszenia"][_skrot(token)] = k["id"]
        tokeny[k["id"]] = (token, k["email"])
    _zmien(lambda d: d["leady"].append(lead))
    wyslano = 0
    for baza_id, (token, email) in tokeny.items():
        wyslano += wizyty._wyslij_email([email], f"Klient szuka notariusza: {SPRAWY[lead['sprawa']][0]}, "
                                                 f"{nazwa} (odpowiedź do {lead['okno_do'][11:16]})",
                                        _mail_do_kancelarii(lead, token))
    if wyslano:
        def odnotuj(d):
            for l in d["leady"]:
                if l["id"] == lead["id"]:
                    l["wyslano"] = wyslano
        _zmien(odnotuj)
    if wizyty.KOPIA:
        wizyty._wyslij_email([wizyty.KOPIA], f"[notarai] lead {lead['id']} ({zrodlo}): {nazwa or 'miejscowość nieznana'}",
                             f"Zaproszenia: {wyslano} z {len(tokeny)}."
                             + ("" if slug else " Miejscowość nie pasuje do wykazu - skieruj ręcznie w panelu /admin."))
    log.info("leady: nowy %s (%s), adresatow %d, wyslano %d", lead["id"], zrodlo, len(tokeny), wyslano)
    return {**lead, "wyslano": wyslano}


# ---------------------------------------------------------------- odpowiedz kancelarii


def _po_tokenie(d: dict, token: str) -> tuple[dict, int]:
    h = _skrot(token)
    for lead in d["leady"]:
        if h in lead["zaproszenia"]:
            return lead, lead["zaproszenia"][h]
    raise HTTPException(404, "Link jest nieważny. Zapytania starsze niż godzina są w archiwum w aplikacji notarai.")


def _odpowiedz(lead: dict, baza_id: int, tresc: str, termin: str, kontakt: str, kto: str) -> dict:
    """Wspolna dla linku z e-maila i dla aplikacji. Wywolywana pod blokada zapisu."""
    if any(o["baza_id"] == baza_id for o in lead["odpowiedzi"]):
        raise HTTPException(409, "Kancelaria już odpowiedziała na to zapytanie.")
    k = wizyty.baza()["kancelarie"].get(baza_id) or {}
    odp = {"baza_id": baza_id, "kancelaria": k.get("nazwa", ""), "czas": _teraz().isoformat(timespec="seconds"),
           "tresc": _linia(tresc, 1500), "termin": _linia(termin, 200),
           "kontakt": _linia(kontakt, 200) or " · ".join(k.get("telefony") or []) or k.get("email", ""),
           "adres": k.get("adres", ""), "kto": kto, "w_oknie": w_oknie(lead)}
    lead["odpowiedzi"].append(odp)
    return odp


def _powiadom_klienta(lead: dict, odp: dict) -> None:
    if not lead["klient"].get("email"):
        return
    wizyty._wyslij_email(
        [lead["klient"]["email"]], f"Notariusz odpowiedział: {odp['kancelaria']}",
        f"Dzień dobry,\n\nna Twoje zapytanie ({SPRAWY[lead['sprawa']][0]}, {lead['miejscowosc_nazwa']}) "
        f"odpowiedziała kancelaria:\n\n{odp['kancelaria']}\n{odp['adres']}\nKontakt: {odp['kontakt']}\n\n"
        + (f"Wiadomość: {odp['tresc']}\n" if odp["tresc"] else "")
        + (f"Proponowany termin: {odp['termin']}\n" if odp["termin"] else "")
        + "\nMożesz dostać odpowiedzi od kilku kancelarii – wybierz tę, która Ci odpowiada, i skontaktuj się z nią."
          "\n\nnotarai.pl")


router = APIRouter(prefix="/api/leady", tags=["leady"])


class Token(BaseModel):
    token: str = Field(min_length=16, max_length=100)


class Odpowiedz(Token):
    tresc: str = Field(default="", max_length=1500)
    termin: str = Field(default="", max_length=200)
    kontakt: str = Field(default="", max_length=200)


@router.post("/zaproszenie")
def zaproszenie(dane: Token):
    """Co widzi kancelaria po kliknieciu linku z e-maila."""
    lead, baza_id = _po_tokenie(_wczytaj(), dane.token)
    k = wizyty.baza()["kancelarie"].get(baza_id) or {}
    moja = next((o for o in lead["odpowiedzi"] if o["baza_id"] == baza_id), None)
    if moja:
        return {"lead": _pelny(lead), "kancelaria": k.get("nazwa", ""), "otwarte": False, "odpowiedz": moja}
    return {"lead": _anonim(lead), "kancelaria": k.get("nazwa", ""), "otwarte": w_oknie(lead), "odpowiedz": None}


@router.post("/odpowiedz")
def odpowiedz_z_linku(dane: Odpowiedz):
    wynik = {}

    def zmien(d):
        lead, baza_id = _po_tokenie(d, dane.token)
        if not w_oknie(lead):
            raise HTTPException(410, "Minęła godzina na odpowiedź. Zapytanie jest teraz w archiwum dla kancelarii "
                                     "korzystających z notarai.pl.")
        wynik["odp"] = _odpowiedz(lead, baza_id, dane.tresc, dane.termin, dane.kontakt, "link")
        wynik["lead"] = dict(lead)
    _zmien(zmien)
    _powiadom_klienta(wynik["lead"], wynik["odp"])
    log.info("leady: odpowiedz na %s z linku (kancelaria %s)", wynik["lead"]["id"], wynik["odp"]["baza_id"])
    return {"lead": _pelny(wynik["lead"]), "odpowiedz": wynik["odp"],
            "komunikat": "Odpowiedź wysłana do klienta. Niżej jego dane kontaktowe."}


# ---------------------------------------------------------------- aplikacja (kancelarie notarai)

router_kancelarii = APIRouter(prefix="/api/gielda", tags=["leady"])


def _moje_baza_id() -> list[int]:
    moja = magazyn.kancelaria()
    return [b for b, k in wizyty.kancelarie_notarai().items() if k == moja]


def _izby(baza_ids: list[int]) -> set[str]:
    b = wizyty.baza()
    return {b["miejscowosci"][b["kancelarie"][i]["slug"]]["izba"] for i in baza_ids
            if b["kancelarie"].get(i) and b["kancelarie"][i]["slug"] in b["miejscowosci"]}


def _moj_obszar(lead: dict, izby: set[str]) -> bool:
    m = wizyty.baza()["miejscowosci"].get(lead.get("miejscowosc") or "")
    return bool(m and m["izba"] in izby)


@router_kancelarii.get("")
def gielda():
    """Leady z izby kancelarii: otwarte (bez kontaktu, do odpowiedzi) i
    archiwum z kontaktem - archiwum tylko dla oplaconych."""
    moje = _moje_baza_id()
    if not moje:
        return {"oplacona": False, "otwarte": [], "archiwum": [], "powiazana": False}
    oplacona = autoryzacja._oplacona(magazyn.kancelaria())
    izby = _izby(moje)
    otwarte, archiwum = [], []
    for lead in sorted(_wczytaj()["leady"], key=lambda l: l["utworzono"], reverse=True):
        if not _moj_obszar(lead, izby):
            continue
        odpowiedziala = any(o["baza_id"] in moje for o in lead["odpowiedzi"])
        if w_oknie(lead):
            otwarte.append({**(_pelny(lead) if odpowiedziala else _anonim(lead)), "odpowiedziala": odpowiedziala})
        elif oplacona or odpowiedziala:
            archiwum.append({**_pelny(lead), "odpowiedziala": odpowiedziala})
    return {"oplacona": oplacona, "powiazana": True, "otwarte": otwarte, "archiwum": archiwum[:500]}


class OdpowiedzAplikacja(BaseModel):
    tresc: str = Field(default="", max_length=1500)
    termin: str = Field(default="", max_length=200)
    kontakt: str = Field(default="", max_length=200)


@router_kancelarii.post("/{lead_id}/odpowiedz")
def odpowiedz_w_aplikacji(lead_id: str, dane: OdpowiedzAplikacja):
    moje = _moje_baza_id()
    if not moje:
        raise HTTPException(409, "Kancelaria nie jest powiązana z wykazem notariuszy. Napisz do kontakt@notarai.pl.")
    oplacona = autoryzacja._oplacona(magazyn.kancelaria())
    izby = _izby(moje)
    wynik = {}

    def zmien(d):
        lead = next((l for l in d["leady"] if l["id"] == lead_id and _moj_obszar(l, izby)), None)
        if not lead:
            raise HTTPException(404, "Nie ma takiego zapytania.")
        if not w_oknie(lead) and not oplacona:
            raise HTTPException(402, "Archiwum zapytań jest dostępne w abonamencie notarai.")
        wynik["odp"] = _odpowiedz(lead, moje[0], dane.tresc, dane.termin, dane.kontakt, "aplikacja")
        wynik["lead"] = dict(lead)
    _zmien(zmien)
    _powiadom_klienta(wynik["lead"], wynik["odp"])
    log.info("leady: odpowiedz na %s w aplikacji", lead_id)
    return {"lead": _pelny(wynik["lead"]), "odpowiedz": wynik["odp"]}


# ---------------------------------------------------------------- admin

router_admina = APIRouter(prefix="/api/admin/leady", tags=["admin"])


@router_admina.get("")
def wszystkie(request: Request):
    autoryzacja._wymagaj_admina(request)
    leady = sorted(_wczytaj()["leady"], key=lambda l: l["utworzono"], reverse=True)
    for l in leady:
        l.pop("zaproszenia", None)
    return {"leady": leady, "okno_min": OKNO_MIN,
            "podsumowanie": {"leady": len(leady), "z_odpowiedzia": sum(1 for l in leady if l["odpowiedzi"]),
                             "bez_miejscowosci": sum(1 for l in leady if not l["miejscowosc"])}}


class LeadReczny(BaseModel):
    imie: str = ""
    nazwisko: str = ""
    telefon: str = ""
    email: str = ""
    sprawa: str
    opis: str = ""
    miejscowosc: str
    zrodlo: str = "reczny"


@router_admina.post("", status_code=201)
def dodaj(dane: LeadReczny, request: Request):
    """Lead wpisany recznie albo z importu (np. z Finance You)."""
    autoryzacja._wymagaj_admina(request)
    if not (dane.telefon or dane.email):
        raise HTTPException(400, "Lead bez telefonu i e-maila jest bezużyteczny.")
    lead = nowy(klient=dane.model_dump(include={"imie", "nazwisko", "telefon", "email"}), sprawa=dane.sprawa,
                opis=dane.opis, miejscowosc=dane.miejscowosc, zrodlo=_linia(dane.zrodlo, 40))
    return {"id": lead["id"], "wyslano": lead["wyslano"], "adresatow": len(lead["zaproszenia"])}
