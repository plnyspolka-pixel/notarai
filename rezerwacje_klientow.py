"""Rezerwacja online dla klientow ze strony notarai.pl.

Zacheta dla kancelarii korzystajacych z notarai, ktora NIE zmienia ich miejsca
na liscie (docs/rekomendacje-notariuszy.md): klient, ktory juz wybral
kancelarie (sam albo przez kolejke "dowolna kancelaria"), moze od razu wybrac
wolna godzine zamiast czekac na telefon.

Godziny przyjec i czas wizyty to te same ustawienia co w rezerwacjach B2B
(rezerwacje_hurtowe.Polityka); kancelaria wlacza je dla klientow osobnym
przelacznikiem `klienci`. Rezerwacja wchodzi do tego samego kalendarza
kancelarii, przez ten sam atomowy zapis, wiec nie da sie zajac godziny dwa razy.

Klient dostaje e-mail z linkiem do odwolania (token jednorazowy; w pliku
zgloszen trzymamy tylko jego skrot SHA-256) i przypomnienie dzien przed wizyta
(przypomnienia.py). Dane klienta nie trafiaja do logow.
"""
import hashlib
import logging
import os
import secrets
import threading
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import autoryzacja
import kalendarz
import magazyn
import rezerwacje_hurtowe as hurt
import wizyty

log = logging.getLogger("pieczapp.rezerwacje_klientow")

MAKS_DNI_NARAZ = 14
GODZINY_ODWOLANIA = 2   # najpozniej tyle godzin przed wizyta klient odwoluje sam

router = APIRouter(prefix="/api/wizyty", tags=["rezerwacje klientow"])


def skrot(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def biuro_online(baza_id: int) -> tuple[str, dict] | None:
    """(id kancelarii w notarai, polityka) albo None, gdy kancelaria nie
    przyjmuje rezerwacji online. Te same warunki co dla partnerow B2B:
    aktywna, dane w chmurze, oplacona, umowa powierzenia zawarta."""
    id_k = wizyty.kancelarie_notarai().get(baza_id)
    if not id_k:
        return None
    _, biuro = autoryzacja._znajdz(autoryzacja._wczytaj_rejestr(), id_k)
    if (not biuro or not biuro.get("aktywna", True) or biuro.get("przechowywanie", "chmura") == "u-klienta"
            or not autoryzacja._oplacona(id_k) or not autoryzacja.umowa_zawarta(id_k)):
        return None
    with hurt._WBiurze(id_k):
        p = hurt._polityka()
    if not p.get("klienci") or not p.get("godziny"):
        return None
    return id_k, p


def online(identyfikatory: list[int]) -> list[int]:
    """Ktore z kancelarii z bazy przyjmuja rezerwacje online."""
    wynik = []
    for i in identyfikatory:
        try:
            if biuro_online(i):
                wynik.append(i)
        except Exception:  # noqa: BLE001 - awaria jednej kancelarii nie psuje listy
            continue
    return wynik


def _wolne_dnia(wpisy: list[dict], p: dict, dzien: str, dni_opisane: dict) -> list[dict]:
    if dni_opisane.get(dzien, {}).get("nieczynne"):
        return []
    return hurt._dostepne(wpisy, p, dzien)


@router.get("/terminy")
def terminy(kancelaria: int, od: str = "", dni: int = 7):
    """Wolne godziny kancelarii na kolejne dni. Publiczne: zwraca tylko
    godziny, nigdy tresc kalendarza."""
    wynik = biuro_online(kancelaria)
    if not wynik:
        return {"online": False, "terminy": []}
    id_k, p = wynik
    start = hurt._data(od) if od else hurt._teraz().date()
    dni = max(1, min(dni, MAKS_DNI_NARAZ))
    with hurt._WBiurze(id_k):
        wpisy, opisy = kalendarz.lista(), kalendarz.dni()
        sloty = []
        for n in range(dni):
            sloty += _wolne_dnia(wpisy, p, (start + timedelta(days=n)).isoformat(), opisy)
    return {"online": True, "czas_minut": p["czas_minut"], "adres": p.get("adres", ""), "terminy": sloty}


class Rezerwacja(wizyty.Zgloszenie):
    data: str
    godzina: str = Field(min_length=5, max_length=5)


@router.post("/rezerwacja", status_code=201)
def rezerwuj(dane: Rezerwacja, request: Request):
    if dane.strona:
        return {"id": "", "komunikat": "Dziękujemy."}
    if dane.kancelaria in (None, ""):
        raise HTTPException(400, "Rezerwacja online wymaga wybrania kancelarii.")
    z = wizyty._sprawdz_zgloszenie(dane)
    if not z["klient"]["email"]:
        raise HTTPException(400, "Podaj e-mail: wyślemy potwierdzenie i link do odwołania wizyty.")
    wizyty.limit_zgloszen.sprawdz(autoryzacja.adres_klienta(request),
                                  "Za dużo zgłoszeń naraz. Spróbuj za godzinę albo zadzwoń do kancelarii.")
    wynik = biuro_online(z["baza_id"])
    if not wynik:
        raise HTTPException(409, "Ta kancelaria nie przyjmuje rezerwacji online. Wyślij zwykłe zgłoszenie.")
    id_k, p = wynik
    z["kancelaria_id"] = id_k
    token = secrets.token_urlsafe(24)
    m = hurt._minuty(dane.godzina)
    rodzaj = wizyty._rodzaj_kalendarza(z["czynnosc"])
    with hurt._WBiurze(id_k):
        if kalendarz.dni().get(dane.data, {}).get("nieczynne"):
            raise HTTPException(409, "Kancelaria jest tego dnia nieczynna.")

        def zmiana(wpisy):
            if dane.godzina not in {s["godzina"] for s in hurt._dostepne(wpisy, p, dane.data)}:
                raise HTTPException(409, "Ten termin właśnie się zajął. Wybierz inny.")
            nowy = kalendarz._sprawdz({
                "data": dane.data, "godzina": dane.godzina, "koniec": hurt._hhmm(m + p["czas_minut"]),
                "tytul": f"Wizyta: {z['czynnosc'][:120]} ({z['klient']['imie']})",
                "rodzaj": rodzaj, "rodzaj_inny": z["czynnosc"][:200] if rodzaj == "inne" else "",
                "uczestnicy": z["klient"]["imie"],
                "telefony": [{"imie": z["klient"]["imie"], "numer": z["klient"]["telefon"]}]
                if z["klient"]["telefon"] else [],
                "uwagi": "Rezerwacja online ze strony notarai.pl.\n" + wizyty._opis_zgloszenia(z),
            })
            wpis = {"id": uuid.uuid4().hex[:12], **nowy, "zrodlo": "klient", "zgloszenie": z["id"],
                    "status": "potwierdzona", "utworzono": datetime.now(timezone.utc).isoformat()}
            kalendarz._sprawdz_kolizje(wpisy, wpis)
            wpisy.append(wpis)
            return wpis
        wpis = hurt._zapisz_kalendarz(zmiana)
    z.update({"status": "umowiona", "zrodlo": "rezerwacja",
              "wizyta": {"data": dane.data, "godzina": dane.godzina, "koniec": wpis["koniec"],
                         "kalendarz": wpis["id"], "adres": p.get("adres", "")},
              "token": skrot(token), "przypomniano": None})
    z["historia"].append({"czas": wizyty._teraz(), "kto": "klient", "status": "umowiona",
                          "uwagi": "rezerwacja online"})
    wizyty._zmien(lambda d: d["zgloszenia"].append(z))
    _powiadom(z, token)
    log.info("rezerwacje_klientow: rezerwacja %s w kancelarii %s", z["id"], id_k)
    return {"id": z["id"], "data": dane.data, "godzina": dane.godzina, "koniec": wpis["koniec"],
            "komunikat": f"Wizyta zarezerwowana: {dane.data} o {dane.godzina}, {z['kancelaria_nazwa']}. "
                         "Potwierdzenie i link do odwołania wysłaliśmy e-mailem."}


def link_odwolania(token: str) -> str:
    return f"{wizyty.STRONA}/wizyta/odwolaj/#{token}"


def _powiadom(z: dict, token: str) -> None:
    w = z["wizyta"]
    opis = wizyty._opis_zgloszenia(z)
    wizyty._wyslij_email(
        wizyty._emaile_kancelarii(z["kancelaria_id"]),
        f"Rezerwacja online: {w['data']} {w['godzina']}, {z['czynnosc'][:50]}",
        f"Klient zarezerwował wizytę online na {w['data']} o {w['godzina']}-{w['koniec']}. "
        "Termin jest już w kalendarzu kancelarii.\n\n" + opis
        + f"\n\nAplikacja: {wizyty.ADRES_APLIKACJI} (Kalendarz, Zapytania klientów).")
    wizyty._wyslij_email(
        [z["klient"]["email"]], f"Potwierdzenie wizyty u notariusza: {w['data']} {w['godzina']}",
        f"Dzień dobry,\n\npotwierdzamy wizytę w kancelarii {z['kancelaria_nazwa']}"
        + (f", {w['adres']}" if w.get("adres") else "") + f":\n{w['data']} o {w['godzina']}.\n\n"
        "Dzień przed wizytą przypomnimy o niej e-mailem.\n"
        f"Jeśli nie możesz przyjść, odwołaj wizytę tutaj: {link_odwolania(token)}\n\n"
        "Twoje zgłoszenie:\n" + opis + "\n\nnotarai.pl")


class Odwolanie(BaseModel):
    token: str = Field(min_length=16, max_length=100)


@router.post("/rezerwacja/odwolaj")
def odwolaj(dane: Odwolanie):
    h = skrot(dane.token)
    teraz = datetime.now(hurt.STREFA).replace(tzinfo=None)

    def zmien(d):
        for z in d["zgloszenia"]:
            if z.get("token") and secrets.compare_digest(z["token"], h):
                w = z["wizyta"]
                poczatek = datetime.fromisoformat(f"{w['data']}T{w['godzina']}")
                if z["status"] != "umowiona":
                    raise HTTPException(409, "Ta wizyta jest już odwołana albo zamknięta.")
                if poczatek - teraz < timedelta(hours=GODZINY_ODWOLANIA):
                    raise HTTPException(409, "Do wizyty zostało mniej niż 2 godziny. Zadzwoń do kancelarii.")
                z["status"] = "odrzucona"
                z["historia"].append({"czas": wizyty._teraz(), "kto": "klient", "status": "odrzucona",
                                      "uwagi": "klient odwołał rezerwację online"})
                return dict(z)
        return None
    z = wizyty._zmien(zmien)
    if not z:
        raise HTTPException(404, "Nie znamy takiej rezerwacji.")
    with hurt._WBiurze(z["kancelaria_id"]):
        def anuluj(wpisy):
            for w in wpisy:
                if w["id"] == z["wizyta"]["kalendarz"]:
                    w["status"] = "anulowana"
        hurt._zapisz_kalendarz(anuluj)
    wizyty._wyslij_email(wizyty._emaile_kancelarii(z["kancelaria_id"]),
                         f"Klient odwołał wizytę {z['wizyta']['data']} {z['wizyta']['godzina']}",
                         "Termin zwolnił się w kalendarzu i znów jest widoczny dla klientów.\n\n"
                         + wizyty._opis_zgloszenia(z))
    log.info("rezerwacje_klientow: odwolano %s", z["id"])
    return {"komunikat": f"Wizyta {z['wizyta']['data']} o {z['wizyta']['godzina']} odwołana. Termin wrócił do kalendarza kancelarii."}


# --- przypomnienia -----------------------------------------------------------


def przypomnij(teraz: datetime | None = None) -> dict:
    """Wysyla przypomnienia o wizytach jutro. Bezpieczne do wywolywania
    wielokrotnie i z kilku kontenerow: znacznik `przypomniano` jest zapisywany
    atomowo przed wysylka (raczej zero niz dwa e-maile)."""
    teraz = teraz or datetime.now(hurt.STREFA).replace(tzinfo=None)
    jutro = (teraz.date() + timedelta(days=1)).isoformat()
    do_wyslania: list[dict] = []

    def zaznacz(d):
        for z in d["zgloszenia"]:
            if (z.get("status") == "umowiona" and z.get("zrodlo") == "rezerwacja" and not z.get("przypomniano")
                    and (z.get("wizyta") or {}).get("data") == jutro and z["klient"].get("email")):
                z["przypomniano"] = teraz.isoformat(timespec="seconds")
                do_wyslania.append(dict(z))
    wizyty._zmien(zaznacz)
    wyslane = 0
    for z in do_wyslania:
        w = z["wizyta"]
        wyslane += wizyty._wyslij_email(
            [z["klient"]["email"]], f"Jutro wizyta u notariusza o {w['godzina']}",
            f"Dzień dobry,\n\nprzypominamy o wizycie jutro, {w['data']} o {w['godzina']}, "
            f"w kancelarii {z['kancelaria_nazwa']}" + (f", {w['adres']}" if w.get("adres") else "") + ".\n\n"
            "Zabierz dowód osobisty i dokumenty dotyczące sprawy. Jeśli nie możesz przyjść, "
            "zadzwoń do kancelarii albo odwołaj wizytę linkiem z e-maila z potwierdzeniem.\n\nnotarai.pl")
    log.info("rezerwacje_klientow: przypomnienia na %s: %d z %d", jutro, wyslane, len(do_wyslania))
    return {"dzien": jutro, "do_wyslania": len(do_wyslania), "wyslane": wyslane}


router_admina = APIRouter(prefix="/api/admin/wizyty", tags=["admin"])


@router_admina.post("/przypomnienia")
def przypomnienia(request: Request):
    """Wywolywane raz dziennie (harmonogram) albo recznie z panelu."""
    autoryzacja._wymagaj_admina(request)
    return przypomnij()


GODZINA_PRZYPOMNIEN = int(os.getenv("PIECZAPP_PRZYPOMNIENIA_GODZINA", "17"))


def _petla_przypomnien(stop: threading.Event) -> None:
    """Raz na godzine sprawdza, czy po GODZINA_PRZYPOMNIEN czasu polskiego
    przypomnienia na jutro juz wyszly. Kilka kontenerow naraz nie szkodzi:
    znacznik `przypomniano` zapisuje sie atomowo (warunkowy zapis S3)."""
    while not stop.wait(3600):
        try:
            if datetime.now(hurt.STREFA).hour >= GODZINA_PRZYPOMNIEN:
                przypomnij()
        except Exception as blad:  # noqa: BLE001 - nastepna proba za godzine
            log.warning("rezerwacje_klientow: przypomnienia nie wyszly (%s)", type(blad).__name__)


def uruchom_przypomnienia() -> threading.Event | None:
    """Wlacza petle, gdy PIECZAPP_PRZYPOMNIENIA=true (w chmurze; testy i
    stanowisko lokalne jej nie uruchamiaja)."""
    if os.getenv("PIECZAPP_PRZYPOMNIENIA", "").lower() != "true":
        return None
    stop = threading.Event()
    threading.Thread(target=_petla_przypomnien, args=(stop,), daemon=True, name="przypomnienia").start()
    return stop
