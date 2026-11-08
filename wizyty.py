"""Umawianie wizyt: zgloszenia klientow ze strony notarai.pl do kancelarii.

Klient na stronie miejscowosci (notarai.pl/notariusz/<miasto>/) albo przy
wyniku kalkulatora wybiera kancelarie i zostawia kontakt. Zgloszenie trafia:
  - do kancelarii, ktora korzysta z notarai (dopasowanie po e-mailu z bazy
    albo powiazanie ustawione w panelu admina): widzi je w aplikacji w oknie
    "Zapytania klientow", dostaje e-mail, a po umowieniu terminu wpis laduje
    w jej kalendarzu,
  - do notarai (panel /admin), gdy kancelaria nie jest klientem: obsluga
    przekazuje je recznie e-mailem - to oferta "mamy klientow" dla kancelarii
    spoza notarai. Nic nie wysylamy do obcych kancelarii automatycznie.

Zgloszenia leza w jednym pliku w obszarze administracyjnym magazynu
(kancelarie/_administracja/wizyty.json; w S3 zaszyfrowane, w UE), bo
powstaja bez kontekstu kancelarii. Dane klienta (imie, telefon, e-mail) sa
danymi osobowymi: nie trafiaja do logow, a stare zgloszenia kasujemy po
RETENCJA_DNI. Adres IP sluzy tylko do limitu i nie jest zapisywany.
"""
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import autoryzacja
import dziennik
import kalendarz
import magazyn
import rekomendacje
import taksa
from kalkulator import Limit

log = logging.getLogger("pieczapp.wizyty")

PLIK = "wizyty"
OBSZAR = autoryzacja.KANCELARIA_ADMINOW
PLIK_BAZY = Path(__file__).resolve().parent / "seo" / "kancelarie.json"
STATUSY = ("nowa", "kontakt", "umowiona", "odrzucona", "zamknieta")
RETENCJA_DNI = int(os.getenv("PIECZAPP_WIZYTY_RETENCJA_DNI", "180"))
ADRES_APLIKACJI = os.getenv("PIECZAPP_ADRES", "https://app.notarai.pl").rstrip("/")
STRONA = "https://notarai.pl"

# E-mail przez Amazon SES (eu-central-1). Bez nadawcy zgloszenia dzialaja,
# tylko bez powiadomien - widac je w aplikacji i w panelu.
NADAWCA = os.getenv("PIECZAPP_EMAIL_NADAWCA", "").strip()
# Kopia kazdego zgloszenia dla obslugi notarai (np. zapytania@notarai.pl).
KOPIA = os.getenv("PIECZAPP_EMAIL_ZGLOSZEN", "").strip()

limit_zgloszen = Limit(int(os.getenv("PIECZAPP_WIZYTY_NA_IP", "5")), int(os.getenv("PIECZAPP_WIZYTY_NA_DOBE", "300")))

_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
_baza: dict | None = None
_blokada = threading.Lock()
_CACHE_NOTARAI: tuple[float, dict] = (0.0, {})


# --- baza kancelarii -------------------------------------------------------


def baza() -> dict:
    """seo/kancelarie.json w postaci slownikow: kancelarie po id, miejscowosci po slugu."""
    global _baza
    with _blokada:
        if _baza is None:
            dane = json.loads(PLIK_BAZY.read_text("utf-8")) if PLIK_BAZY.exists() else {"kancelarie": [], "miejscowosci": []}
            kancelarie = {k["id"]: k for k in dane["kancelarie"]}
            wg_miejscowosci: dict[str, list[int]] = {}
            for k in dane["kancelarie"]:
                wg_miejscowosci.setdefault(k["slug"], []).append(k["id"])
            _baza = {"kancelarie": kancelarie,
                     "miejscowosci": {m["slug"]: m for m in dane["miejscowosci"]},
                     "wg_miejscowosci": wg_miejscowosci}
        return _baza


def _ustaw_baze(dane: dict | None) -> None:
    """Dla testow."""
    global _baza, _CACHE_NOTARAI
    with _blokada:
        _baza = None if dane is None else {
            "kancelarie": {k["id"]: k for k in dane["kancelarie"]},
            "miejscowosci": {m["slug"]: m for m in dane["miejscowosci"]},
            "wg_miejscowosci": {}}
        if dane:
            for k in dane["kancelarie"]:
                _baza["wg_miejscowosci"].setdefault(k["slug"], []).append(k["id"])
    _CACHE_NOTARAI = (0.0, {})


# --- plik zgloszen w obszarze administracyjnym ----------------------------


def _w_obszarze_admina(funkcja, *argumenty):
    """Plik zgloszen lezy poza kancelariami, wiec na czas operacji przelaczamy
    kontekst magazynu na obszar administracyjny (zapisywalny zawsze)."""
    z1 = magazyn.kancelaria_var.set(OBSZAR)
    z2 = magazyn.przechowywanie_var.set("chmura")
    try:
        return funkcja(*argumenty)
    finally:
        magazyn.przechowywanie_var.reset(z2)
        magazyn.kancelaria_var.reset(z1)


def _pusty() -> dict:
    return {"zgloszenia": [], "powiazania": {}}


def _wczytaj() -> dict:
    dane = _w_obszarze_admina(magazyn.wczytaj_plik_kancelarii, PLIK, _pusty())
    dane.setdefault("zgloszenia", [])
    dane.setdefault("powiazania", {})
    return dane


def _zmien(zmiana):
    def opakowana(dane):
        dane.setdefault("zgloszenia", [])
        dane.setdefault("powiazania", {})
        _usun_stare(dane)
        return zmiana(dane)
    try:
        return _w_obszarze_admina(magazyn.zmien_plik_kancelarii, PLIK, opakowana, _pusty())
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))


def _teraz() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _usun_stare(dane: dict) -> None:
    granica = (datetime.now() - timedelta(days=RETENCJA_DNI)).isoformat(timespec="seconds")
    dane["zgloszenia"] = [z for z in dane["zgloszenia"] if z.get("utworzono", "") >= granica]


# --- ktore kancelarie z bazy korzystaja z notarai ---------------------------


def kancelarie_notarai() -> dict[int, str]:
    """id z bazy -> id kancelarii w notarai. Powiazania z panelu admina maja
    pierwszenstwo; reszte dopasowujemy po e-mailu osoby z zespolu."""
    global _CACHE_NOTARAI
    if time.monotonic() - _CACHE_NOTARAI[0] < 60:
        return _CACHE_NOTARAI[1]
    wynik: dict[int, str] = {}
    try:
        rejestr = autoryzacja._wczytaj_rejestr()
    except Exception as blad:  # noqa: BLE001 - brak rejestru nie blokuje zgloszen
        log.warning("wizyty: rejestr kancelarii niedostepny (%s)", dziennik.opis_bledu(blad))
        rejestr = {}
    emaile = {}
    for wpis in rejestr.values():
        if not wpis.get("aktywna", True):
            continue
        for osoba in wpis.get("zespol", []):
            emaile[osoba["email"].lower()] = wpis["id"]
    for ident, k in baza()["kancelarie"].items():
        if k.get("email") and k["email"] in emaile:
            wynik[ident] = emaile[k["email"]]
    try:
        for klucz, id_k in _wczytaj()["powiazania"].items():
            if id_k:
                wynik[int(klucz)] = id_k
            else:
                wynik.pop(int(klucz), None)
    except Exception as blad:  # noqa: BLE001
        log.warning("wizyty: nie udalo sie odczytac powiazan (%s)", dziennik.opis_bledu(blad))
    _CACHE_NOTARAI = (time.monotonic(), wynik)
    return wynik


def _emaile_kancelarii(id_k: str) -> list[str]:
    try:
        rejestr = autoryzacja._wczytaj_rejestr()
    except Exception:  # noqa: BLE001
        return []
    for wpis in rejestr.values():
        if wpis["id"] == id_k:
            wlasciciele = autoryzacja._wlasciciele(wpis)
            return wlasciciele or [o["email"] for o in wpis.get("zespol", [])]
    return []


# --- e-mail ------------------------------------------------------------------


def _wyslij_email(do: list[str], temat: str, tresc: str) -> bool:
    """Amazon SES. Zwraca, czy wyszlo. Tresci nie logujemy - to dane klienta."""
    do = [a for a in do if a]
    if not NADAWCA or not do:
        return False
    try:
        import boto3
        import config
        boto3.client("ses", region_name=config.REGION).send_email(
            Source=NADAWCA, Destination={"ToAddresses": do},
            Message={"Subject": {"Data": temat, "Charset": "UTF-8"},
                     "Body": {"Text": {"Data": tresc, "Charset": "UTF-8"}}})
        return True
    except Exception as blad:  # noqa: BLE001
        log.warning("wizyty: e-mail nie wyszedl (%s)", dziennik.opis_bledu(blad))
        return False


def _opis_zgloszenia(z: dict) -> str:
    klient = z["klient"]
    linie = [f"Kancelaria: {z.get('kancelaria_nazwa') or 'dowolna w miejscowości'} ({z.get('miejscowosc_nazwa', '')})",
             f"Czynność: {z['czynnosc']}"]
    if z.get("wartosc"):
        linie.append(f"Wartość: {taksa.zl(z['wartosc'])}")
    if z.get("termin"):
        linie.append(f"Preferowany termin: {z['termin']}")
    if z.get("wiadomosc"):
        linie.append(f"Wiadomość: {z['wiadomosc']}")
    linie += ["", f"Imię: {klient['imie']}", f"Telefon: {klient.get('telefon') or 'nie podano'}",
              f"E-mail: {klient.get('email') or 'nie podano'}"]
    if z.get("kalkulacja"):
        linie += ["", "Szacunek z kalkulatora notarai:", z["kalkulacja"]["tekst"]]
    if z.get("zapytanie"):
        linie += ["", z["zapytanie"]]
    linie += ["", f"Zgłoszenie {z['id']} z {z['utworzono'].replace('T', ' ')}, przez {STRONA}."]
    return "\n".join(linie)


def _powiadom(z: dict) -> dict:
    wynik = {"kancelaria": False, "notarai": False, "klient": False}
    opis = _opis_zgloszenia(z)
    if z.get("kancelaria_id"):
        wynik["kancelaria"] = _wyslij_email(
            _emaile_kancelarii(z["kancelaria_id"]),
            f"Nowe zapytanie klienta: {z['czynnosc'][:60]}",
            "Klient chce umówić wizytę w Twojej kancelarii.\n\n" + opis
            + f"\n\nOdpowiedz w aplikacji: {ADRES_APLIKACJI} (pasek boczny, Zapytania klientów).")
    if KOPIA:
        wynik["notarai"] = _wyslij_email(
            [KOPIA], f"[notarai] zgłoszenie {z['id']}: {z.get('kancelaria_nazwa') or z.get('miejscowosc_nazwa', '')}",
            ("Kancelaria korzysta z notarai, dostała zgłoszenie sama.\n\n" if z.get("kancelaria_id")
             else "Kancelaria NIE korzysta z notarai. Przekaż zgłoszenie z panelu /admin.\n\n") + opis)
    if z["klient"].get("email"):
        wynik["klient"] = _wyslij_email(
            [z["klient"]["email"]], "Twoje zgłoszenie do notariusza",
            f"Dzień dobry,\n\nprzyjęliśmy zgłoszenie wizyty u notariusza"
            + (f" w kancelarii {z['kancelaria_nazwa']}" if z.get("kancelaria_nazwa") else "")
            + f" ({z.get('miejscowosc_nazwa', '')}).\n\n"
            + ("Kancelaria korzysta z notarai i skontaktuje się z Tobą bezpośrednio.\n"
               if z.get("kancelaria_id") else
               "Przekażemy je kancelarii i potwierdzimy kontakt.\n")
            + "\nTwoje zgłoszenie:\n" + opis
            + "\n\nJeśli to nie Ty wysłałeś zgłoszenie, odpowiedz na tę wiadomość.\n\nnotarai.pl")
    return wynik


# --- API publiczne -----------------------------------------------------------

router = APIRouter(prefix="/api/wizyty", tags=["wizyty"])


class Zgloszenie(BaseModel):
    imie: str
    telefon: str = ""
    email: str = ""
    czynnosc: str
    wartosc: float | str | None = None
    termin: str = ""
    wiadomosc: str = ""
    zgoda: bool = False
    kancelaria: int | str | None = None
    miejscowosc: str = ""
    parametry: dict | None = None     # z kalkulatora - liczymy na nowo, nie bierzemy kwot od klienta
    zrodlo: str = "strona"
    strona: str = ""                  # pulapka na automaty


def _linia(tekst, limit: int) -> str:
    return " ".join(str(tekst or "").split())[:limit]


def _sprawdz_zgloszenie(dane: Zgloszenie) -> dict:
    imie = _linia(dane.imie, 80)
    if len(imie) < 2:
        raise HTTPException(400, "Podaj imię, żeby kancelaria wiedziała, do kogo dzwonić.")
    telefon = _linia(dane.telefon, 40)
    if telefon and len(re.sub(r"\D", "", telefon)) < 7:
        raise HTTPException(400, "Numer telefonu wygląda na niepełny.")
    email = _linia(dane.email, 120).lower()
    if email and not _EMAIL.match(email):
        raise HTTPException(400, "To nie wygląda na adres e-mail.")
    if not telefon and not email:
        raise HTTPException(400, "Podaj telefon albo e-mail, żeby kancelaria mogła odpowiedzieć.")
    czynnosc = _linia(dane.czynnosc, 200)
    if len(czynnosc) < 2:
        raise HTTPException(400, "Napisz, jakiej czynności dotyczy wizyta.")
    if not dane.zgoda:
        raise HTTPException(400, "Potrzebna jest zgoda na przekazanie danych kancelarii.")
    b = baza()
    kancelaria = None
    if dane.kancelaria not in (None, ""):
        try:
            kancelaria = b["kancelarie"][int(dane.kancelaria)]
        except (ValueError, KeyError):
            raise HTTPException(400, "Nie znamy takiej kancelarii.")
    slug = kancelaria["slug"] if kancelaria else _linia(dane.miejscowosc, 80).lower()
    miejscowosc = b["miejscowosci"].get(slug)
    if not kancelaria and not miejscowosc:
        raise HTTPException(400, "Wybierz kancelarię albo miejscowość.")
    wartosc = taksa.kwota(dane.wartosc)
    kalkulacja = None
    if isinstance(dane.parametry, dict) and len(json.dumps(dane.parametry)) < 20000:
        wynik = taksa.oblicz(dane.parametry)
        if wynik["pozycje"]:
            kalkulacja = {"razem": wynik["razem"], "tekst": wynik["tekst"], "parametry": dane.parametry}
            wartosc = wartosc or taksa.kwota(wynik.get("wartosc"))
    return {
        "id": uuid.uuid4().hex[:12],
        "utworzono": _teraz(),
        "zrodlo": dane.zrodlo if dane.zrodlo in ("strona", "kalkulator", "inne") else "inne",
        "miejscowosc": slug,
        "miejscowosc_nazwa": miejscowosc["nazwa"] if miejscowosc else (kancelaria or {}).get("miejscowosc", ""),
        "baza_id": kancelaria["id"] if kancelaria else None,
        "kancelaria_nazwa": kancelaria["nazwa"] if kancelaria else "",
        "kancelaria_id": None,
        "klient": {"imie": imie, "telefon": telefon, "email": email},
        "czynnosc": czynnosc,
        "wartosc": float(wartosc) if wartosc else None,
        "termin": _linia(dane.termin, 200),
        "wiadomosc": str(dane.wiadomosc or "").strip()[:2000],
        "kalkulacja": kalkulacja,
        "zgoda": _teraz(),
        "status": "nowa",
        "historia": [],
        "przekazano": None,
    }


@router.post("/zgloszenie", status_code=201)
def zgloszenie(dane: Zgloszenie, request: Request):
    return przyjmij(dane, request)


def przyjmij(dane: Zgloszenie, request: Request, dodatki: dict | None = None) -> dict:
    """Walidacja, przydzial, zapis i powiadomienia. `dodatki` dopisuje do
    zgloszenia np. pelne zapytanie z teczki klienta (teczka.py)."""
    if dane.strona:
        return {"id": "", "notarai": False, "komunikat": "Dziękujemy."}
    z = _sprawdz_zgloszenie(dane)
    z.update(dodatki or {})
    limit_zgloszen.sprawdz(autoryzacja.adres_klienta(request),
                           "Za dużo zgłoszeń naraz. Spróbuj za godzinę albo zadzwoń do kancelarii.")
    klienci = kancelarie_notarai()

    def dodaj(d):
        if z["baza_id"] is None:
            _przydziel(z, d["zgloszenia"])
        if z["baza_id"] is not None:
            z["kancelaria_id"] = klienci.get(z["baza_id"])
        d["zgloszenia"].append(z)
        return z
    _zmien(dodaj)
    powiadomienia = _powiadom(z)
    if any(powiadomienia.values()):
        def odnotuj(d):
            for w in d["zgloszenia"]:
                if w["id"] == z["id"]:
                    w["powiadomiono"] = powiadomienia
        _zmien(odnotuj)
    log.info("wizyty: zgloszenie %s (%s), kancelaria notarai=%s, e-maile=%s",
             z["id"], z["zrodlo"], "tak" if z["kancelaria_id"] else "nie",
             ",".join(k for k, v in powiadomienia.items() if v) or "brak")
    if z["kancelaria_id"]:
        komunikat = (f"Zgłoszenie dotarło do kancelarii {z['kancelaria_nazwa']}. Kancelaria korzysta z notarai "
                     "i skontaktuje się z Tobą, żeby potwierdzić termin.")
    elif z["kancelaria_nazwa"]:
        komunikat = (f"Zgłoszenie przyjęte. Przekażemy je kancelarii {z['kancelaria_nazwa']} i potwierdzimy "
                     "kontakt. Jeśli sprawa jest pilna, zadzwoń do kancelarii bezpośrednio.")
    else:
        komunikat = (f"Zgłoszenie przyjęte. Dobierzemy kancelarię w miejscowości {z['miejscowosc_nazwa']} "
                     "i potwierdzimy kontakt.")
    if z.get("przydzial"):
        komunikat = (f"Kancelarię w miejscowości {z['miejscowosc_nazwa']} dobraliśmy z kolejki, po równo dla "
                     f"wszystkich kancelarii: {z['kancelaria_nazwa']}. "
                     + ("Kancelaria korzysta z notarai i skontaktuje się z Tobą, żeby potwierdzić termin."
                        if z["kancelaria_id"] else "Przekażemy jej zgłoszenie i potwierdzimy kontakt."))
    return {"id": z["id"], "notarai": bool(z["kancelaria_id"]), "komunikat": komunikat}


def _przydziel(z: dict, wczesniejsze: list[dict]) -> None:
    """Klient nie wybral kancelarii: kolejka po rowno dla wszystkich kancelarii
    w miejscowosci, bez wzgledu na to, czy korzystaja z notarai
    (rekomendacje.przydziel). Wywolywane pod blokada zapisu pliku zgloszen."""
    b = baza()
    kandydaci = [i for i in b["wg_miejscowosci"].get(z["miejscowosc"], [])
                 if not b["kancelarie"][i].get("brak_kontaktu")]
    wybrana = rekomendacje.przydziel(kandydaci, wczesniejsze, z["miejscowosc"])
    if wybrana is None:
        return
    z["baza_id"] = wybrana
    z["kancelaria_nazwa"] = b["kancelarie"][wybrana]["nazwa"]
    z["przydzial"] = {"sposob": "kolejka", "wersja": rekomendacje.WERSJA, "kandydaci": len(kandydaci)}


@router.get("/kancelarie")
def kancelarie_w_miejscowosci(miejscowosc: str = "", tylko_online: bool = False):
    """Kolejnosc kancelarii na stronie miejscowosci na dzis (neutralna,
    rekomendacje.kolejnosc) i jak kazda przyjmie klienta:
      online      - zgloszenie trafia od razu do aplikacji kancelarii,
      rezerwacja  - klient od razu wybiera wolna godzine.
    To informacja o sposobie obslugi; nie zmienia miejsca na liscie.
    tylko_online=1 to filtr, ktory klient wlacza sam (domyslnie wylaczony):
    zaweza liste, kolejnosc pozostalych zostaje ta sama."""
    import rezerwacje_klientow
    b = baza()
    slug = _linia(miejscowosc, 80).lower()
    identyfikatory = b["wg_miejscowosci"].get(slug, [])
    klienci = kancelarie_notarai()
    online = [i for i in identyfikatory if i in klienci]
    rezerwacja = rezerwacje_klientow.online(online)
    lista = [k["id"] for k in rekomendacje.kolejnosc([b["kancelarie"][i] for i in identyfikatory], kontekst=slug)]
    if tylko_online:
        lista = [i for i in lista if i in rezerwacja]
    return {"miejscowosc": slug, "kolejnosc": lista, "online": online, "rezerwacja": rezerwacja,
            "notarai": online, "zasady": rekomendacje.WERSJA, "filtr": "tylko_online" if tylko_online else ""}


def _przydzialy(d: dict, slug: str | None = None) -> dict:
    granica = (datetime.now() - timedelta(days=rekomendacje.OKNO_DNI)).isoformat(timespec="seconds")
    wynik: dict[str, dict[int, int]] = {}
    for z in d["zgloszenia"]:
        if (z.get("przydzial") or {}).get("sposob") == "kolejka" and z.get("utworzono", "") >= granica \
                and (slug is None or z.get("miejscowosc") == slug):
            miasto = wynik.setdefault(z["miejscowosc"], {})
            miasto[z["baza_id"]] = miasto.get(z["baza_id"], 0) + 1
    return wynik


@router.get("/przejrzystosc")
def przejrzystosc(miejscowosc: str, data: str = ""):
    """Publiczny wglad w algorytm: regula, kolejnosc na wskazany dzien (do
    sprawdzenia przez kazdego) i liczba przydzialow z kolejki "dowolna
    kancelaria" w oknie 90 dni. Same liczby, zadnych danych klientow."""
    from datetime import date
    b = baza()
    slug = _linia(miejscowosc, 80).lower()
    if slug not in b["miejscowosci"]:
        raise HTTPException(404, "Nie znamy takiej miejscowości.")
    try:
        dzien = date.fromisoformat(data) if data else date.today()
    except ValueError:
        raise HTTPException(400, "Data w formacie RRRR-MM-DD.")
    kancelarie = [b["kancelarie"][i] for i in b["wg_miejscowosci"].get(slug, [])]
    przydzialy = _przydzialy(_wczytaj(), slug).get(slug, {})
    return {
        "wersja": rekomendacje.WERSJA, "data": dzien.isoformat(), "miejscowosc": slug,
        "regula": {"pasmo_km": rekomendacje.PASMO_KM, "okno_dni": rekomendacje.OKNO_DNI,
                   "rotacja": f"sha256('notarai|{rekomendacje.WERSJA}|<data>|<miejscowosc>|<id>'), rosnaco",
                   "pomijane": "abonament, płatności, konto w notarai, terminy z kalendarza notarai"},
        "kolejnosc": [{"id": k["id"], "nazwa": k["nazwa"], "brak_kontaktu": bool(k.get("brak_kontaktu")),
                       "los": str(rekomendacje.los(dzien, slug, k["id"]))}
                      for k in rekomendacje.kolejnosc(kancelarie, kontekst=slug, dzien=dzien)],
        "przydzialy": [{"id": k["id"], "nazwa": k["nazwa"], "liczba": przydzialy.get(k["id"], 0)}
                       for k in kancelarie if not k.get("brak_kontaktu")],
    }


# --- API kancelarii ----------------------------------------------------------

router_zapytan = APIRouter(prefix="/api/zapytania", tags=["zapytania"])


def _moje(d: dict) -> list[dict]:
    moja = magazyn.kancelaria()
    return [z for z in d["zgloszenia"] if z.get("kancelaria_id") == moja]


@router_zapytan.get("")
def lista_zapytan():
    zgloszenia = _moje(_wczytaj())
    return sorted(zgloszenia, key=lambda z: z["utworzono"], reverse=True)


class ZmianaZapytania(BaseModel):
    status: str
    uwagi: str = ""
    data: str = ""        # termin wizyty (RRRR-MM-DD) przy statusie "umowiona"
    godzina: str = ""
    koniec: str = ""


# Slowa z opisu czynnosci -> rodzaj z kalendarza kancelarii.
_RODZAJE_SLOWA = [
    ("sprzedaż", ("sprzeda", "zakup", "kupn", "kupuj", "nabyci")),
    ("darowizna", ("darow",)),
    ("dział spadku", ("dział spadku", "dzial spadku", "zniesienie wsp")),
    ("testament", ("testament",)),
    ("pełnomocnictwo notarialne", ("pełnomoc", "pelnomoc")),
    ("poświadczenie podpisów", ("poświadczenie podpis", "poswiadczenie podpis", "podpis")),
]


def _rodzaj_kalendarza(czynnosc: str) -> str:
    tekst = czynnosc.lower()
    for rodzaj, slowa in _RODZAJE_SLOWA:
        if rodzaj in kalendarz.RODZAJE and any(slowo in tekst for slowo in slowa):
            return rodzaj
    return "inne"


def _wpis_kalendarza(z: dict, zmiana: ZmianaZapytania) -> dict:
    rodzaj = _rodzaj_kalendarza(z["czynnosc"])
    return {
        "data": zmiana.data, "godzina": zmiana.godzina, "koniec": zmiana.koniec,
        "tytul": f"Wizyta: {z['czynnosc'][:120]} ({z['klient']['imie']})",
        "rodzaj": rodzaj, "rodzaj_inny": z["czynnosc"][:200] if rodzaj == "inne" else "",
        "uczestnicy": z["klient"]["imie"],
        "telefony": [{"imie": z["klient"]["imie"], "numer": z["klient"]["telefon"]}] if z["klient"].get("telefon") else [],
        "uwagi": "Zgłoszenie ze strony notarai.pl.\n" + _opis_zgloszenia(z),
    }


@router_zapytan.put("/{identyfikator}")
def zmien_zapytanie(identyfikator: str, zmiana: ZmianaZapytania):
    if zmiana.status not in STATUSY:
        raise HTTPException(400, "Nieznany status.")
    moja = magazyn.kancelaria()
    wpis_kalendarza = None

    def zmien(d):
        for z in d["zgloszenia"]:
            if z["id"] == identyfikator and z.get("kancelaria_id") == moja:
                z["status"] = zmiana.status
                z["historia"].append({"czas": _teraz(), "kto": "kancelaria", "status": zmiana.status,
                                      "uwagi": _linia(zmiana.uwagi, 500)})
                if zmiana.status == "umowiona" and zmiana.data:
                    z["wizyta"] = {"data": zmiana.data, "godzina": zmiana.godzina}
                return z
        return None
    z = _zmien(zmien)
    if not z:
        raise HTTPException(404, "Nie ma takiego zapytania.")
    if zmiana.status == "umowiona" and zmiana.data and not magazyn.u_klienta():
        try:
            wpis_kalendarza = kalendarz.dodaj(_wpis_kalendarza(z, zmiana))
        except (ValueError, magazyn.KonfliktZapisu) as blad:
            raise HTTPException(400, f"Status zapisany, ale termin nie trafił do kalendarza: {blad}")
    log.info("wizyty: zapytanie %s -> %s%s", identyfikator, zmiana.status,
             " (kalendarz)" if wpis_kalendarza else "")
    return {**z, "kalendarz": wpis_kalendarza}


# --- API administratora notarai ---------------------------------------------

router_admina = APIRouter(prefix="/api/admin/wizyty", tags=["admin"])


@router_admina.get("")
def wszystkie(request: Request):
    autoryzacja._wymagaj_admina(request)
    d = _wczytaj()
    klienci = {v: k for k, v in kancelarie_notarai().items()}
    zgloszenia = sorted(d["zgloszenia"], key=lambda z: z["utworzono"], reverse=True)
    for z in zgloszenia:
        k = baza()["kancelarie"].get(z.get("baza_id") or -1)
        z["kancelaria_email"] = k["email"] if k else ""
        z["kancelaria_telefony"] = k["telefony"] if k else []
    return {"zgloszenia": zgloszenia, "powiazania": d["powiazania"],
            "kancelarie_notarai": klienci}


@router_admina.get("/rownosc")
def rownosc(request: Request):
    """Audyt kolejki: w kazdej miejscowosci roznica miedzy najczesciej
    i najrzadziej wybierana kancelaria (z kontaktem). Kolejka gwarantuje
    roznice najwyzej 1 w oknie; wieksza oznacza blad albo reczna ingerencje."""
    autoryzacja._wymagaj_admina(request)
    b = baza()
    wynik = []
    for slug, liczby in _przydzialy(_wczytaj()).items():
        kandydaci = [i for i in b["wg_miejscowosci"].get(slug, []) if not b["kancelarie"][i].get("brak_kontaktu")]
        wartosci = [liczby.get(i, 0) for i in kandydaci] or [0]
        wynik.append({"miejscowosc": slug, "kancelarie": len(kandydaci), "przydzialy": sum(wartosci),
                      "roznica": max(wartosci) - min(wartosci)})
    wynik.sort(key=lambda w: -w["roznica"])
    return {"wersja": rekomendacje.WERSJA, "okno_dni": rekomendacje.OKNO_DNI,
            "miejscowosci": wynik, "naruszenia": [w for w in wynik if w["roznica"] > 1]}


class ZmianaAdmina(BaseModel):
    status: str = ""
    uwagi: str = ""
    kancelaria_id: str | None = None   # reczne skierowanie do kancelarii notarai


@router_admina.put("/{identyfikator}")
def zmien_jako_admin(identyfikator: str, zmiana: ZmianaAdmina, request: Request):
    autoryzacja._wymagaj_admina(request)
    if zmiana.status and zmiana.status not in STATUSY:
        raise HTTPException(400, "Nieznany status.")

    def zmien(d):
        for z in d["zgloszenia"]:
            if z["id"] == identyfikator:
                if zmiana.status:
                    z["status"] = zmiana.status
                if zmiana.kancelaria_id is not None:
                    z["kancelaria_id"] = zmiana.kancelaria_id or None
                z["historia"].append({"czas": _teraz(), "kto": "notarai", "status": z["status"],
                                      "uwagi": _linia(zmiana.uwagi, 500)})
                return z
        return None
    z = _zmien(zmien)
    if not z:
        raise HTTPException(404, "Nie ma takiego zgłoszenia.")
    if zmiana.kancelaria_id:
        _powiadom(z)
    return z


@router_admina.post("/{identyfikator}/przekaz")
def przekaz(identyfikator: str, request: Request):
    """Reczne przekazanie zgloszenia kancelarii spoza notarai - na jej adres
    z bazy. Jedna decyzja czlowieka na jedno zgloszenie."""
    autoryzacja._wymagaj_admina(request)
    d = _wczytaj()
    z = next((w for w in d["zgloszenia"] if w["id"] == identyfikator), None)
    if not z:
        raise HTTPException(404, "Nie ma takiego zgłoszenia.")
    k = baza()["kancelarie"].get(z.get("baza_id") or -1)
    if not k or not k.get("email"):
        raise HTTPException(409, "Nie znamy adresu e-mail tej kancelarii. Zadzwoń do niej.")
    if not NADAWCA:
        raise HTTPException(503, "Wysyłka e-mail jest wyłączona (PIECZAPP_EMAIL_NADAWCA).")
    wyszlo = _wyslij_email(
        [k["email"]], f"Klient chce umówić wizytę: {z['czynnosc'][:60]}",
        "Dzień dobry,\n\nklient zostawił na notarai.pl prośbę o wizytę w Państwa kancelarii. "
        "Przekazujemy ją w jego imieniu - prosimy o kontakt z klientem.\n\n" + _opis_zgloszenia(z)
        + "\n\nnotarai.pl to asystent kancelarii notarialnej: projekty aktów ze skanów, kalendarz, "
        "sprawdzenia w rejestrach i takie zapytania od klientów wprost w aplikacji. "
        f"Więcej: {STRONA}\n\nZespół notarai, kontakt@notarai.pl")
    if not wyszlo:
        raise HTTPException(502, "E-mail nie wyszedł. Spróbuj ponownie albo zadzwoń do kancelarii.")

    def odnotuj(dane):
        for w in dane["zgloszenia"]:
            if w["id"] == identyfikator:
                w["przekazano"] = _teraz()
                w["status"] = "kontakt" if w["status"] == "nowa" else w["status"]
                w["historia"].append({"czas": _teraz(), "kto": "notarai", "status": w["status"],
                                      "uwagi": "przekazano kancelarii e-mailem"})
                return w
    z = _zmien(odnotuj)
    log.info("wizyty: zgloszenie %s przekazane kancelarii spoza notarai", identyfikator)
    return z


class Powiazanie(BaseModel):
    kancelaria_id: str = ""   # pusto = usun powiazanie


@router_admina.put("/powiazania/{baza_id}")
def powiaz(baza_id: int, dane: Powiazanie, request: Request):
    """Kancelaria z bazy korzysta z notarai pod innym e-mailem niz w wykazie:
    administrator laczy ja recznie, zeby zgloszenia trafialy do aplikacji."""
    autoryzacja._wymagaj_admina(request)
    if baza_id not in baza()["kancelarie"]:
        raise HTTPException(404, "Nie ma takiej kancelarii w bazie.")

    def zmien(d):
        if dane.kancelaria_id:
            d["powiazania"][str(baza_id)] = dane.kancelaria_id
        else:
            d["powiazania"].pop(str(baza_id), None)
        return dict(d["powiazania"])
    wynik = _zmien(zmien)
    global _CACHE_NOTARAI
    _CACHE_NOTARAI = (0.0, {})
    return {"powiazania": wynik}
