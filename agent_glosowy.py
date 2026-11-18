"""Narzedzia agenta glosowego NotarAI (ElevenLabs Agents) - webhooki serwer-serwer.

Agent rozmawia z dwiema grupami:
  - klienci kancelarii: koszt czynnosci (taksa), dokumenty do przyniesienia,
    kancelarie w miejscowosci, wolne godziny, rezerwacja albo prosba o kontakt,
  - kancelarie notarialne: pytania o notarai i prosba o kontakt handlowy.

Kazde narzedzie to jeden POST /api/agent-glosowy/<narzedzie>, ktory ElevenLabs
wola ze swoich serwerow. Odpowiedzi sa krotkie i gotowe do przeczytania na glos
(pole "do_powiedzenia"), bo model glosowy nie powinien sam przeliczac kwot ani
ukladac list kancelarii. Kwoty liczy taksa.py, kolejnosc kancelarii jest ta sama
neutralna kolejnosc co na stronie (rekomendacje.py) - agent nie promuje kancelarii
korzystajacych z notarai.

Dostep: naglowek X-Notarai-Agent porownywany z PIECZAPP_AGENT_GLOSOWY_TOKEN
(sekret notarai/agent-glosowy w Secrets Manager). Gdy tokenu nie ma, trasy sa
otwarte tak samo jak publiczne formularze strony (/api/taksa, /api/wizyty), ktore
robia dokladnie to samo - z wlasnymi limitami: na rozmowe (identyfikator rozmowy
ElevenLabs) i na dobe. Limit na adres IP nie ma tu sensu - wszystkie rozmowy
przychodza z tych samych adresow ElevenLabs.

RODO: do logow trafiaja tylko nazwy narzedzi, liczby i identyfikatory zgloszen.
Imion, telefonow, e-maili i opisow spraw nie logujemy.
"""
import difflib
import functools
import logging
import os
import re
import secrets
import unicodedata
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import autoryzacja
import kalkulator
import rekomendacje
import rezerwacje_klientow
import taksa
import wizyty

log = logging.getLogger("pieczapp.agent_glosowy")

NAGLOWEK = "x-notarai-agent"
TOKEN = os.getenv("PIECZAPP_AGENT_GLOSOWY_TOKEN", "").strip()
WLACZONY = os.getenv("PIECZAPP_AGENT_GLOSOWY", "true").lower() == "true"
KONTAKT = "kontakt@notarai.pl"

# Odczyty (taksa, kancelarie, terminy) i zapisy (zgloszenie, rezerwacja, kontakt).
# Klucz limitu to identyfikator rozmowy; "na godzine" = w praktyce na rozmowe.
limit_odczytow = kalkulator.Limit(int(os.getenv("PIECZAPP_AGENT_GLOSOWY_ODCZYTY", "60")),
                                  int(os.getenv("PIECZAPP_AGENT_GLOSOWY_ODCZYTY_NA_DOBE", "5000")))
limit_zapisow = kalkulator.Limit(int(os.getenv("PIECZAPP_AGENT_GLOSOWY_ZAPISY", "3")),
                                 int(os.getenv("PIECZAPP_AGENT_GLOSOWY_ZAPISY_NA_DOBE", "200")))

MAKS_KANCELARII = 5
MAKS_GODZIN_DNIA = 6
MAKS_DOKUMENTOW = 12

router = APIRouter(prefix="/api/agent-glosowy", tags=["agent glosowy"])


# --- wspolne -----------------------------------------------------------------


def _sprawdz_dostep(request: Request) -> None:
    if not WLACZONY:
        raise HTTPException(503, "Agent głosowy jest wyłączony.")
    if TOKEN and not secrets.compare_digest(request.headers.get(NAGLOWEK, "").encode(), TOKEN.encode()):
        raise HTTPException(401, "Brak dostępu.")


def _klucz(rozmowa: str, request: Request) -> str:
    """Limit liczony na rozmowe ElevenLabs; bez identyfikatora - na adres IP."""
    rozmowa = re.sub(r"[^A-Za-z0-9_-]", "", rozmowa or "")[:80]
    return f"rozmowa:{rozmowa}" if rozmowa else f"ip:{autoryzacja.adres_klienta(request)}"


def _odczyt(rozmowa: str, request: Request) -> None:
    _sprawdz_dostep(request)
    limit_odczytow.sprawdz(_klucz(rozmowa, request), "Za dużo zapytań w tej rozmowie. Zaproponuj kontakt "
                                                     "z kancelarią albo stronę notarai.pl.")


def _zapis(rozmowa: str, request: Request) -> str:
    _sprawdz_dostep(request)
    klucz = _klucz(rozmowa, request)
    limit_zapisow.sprawdz(klucz, "W tej rozmowie wysłano już kilka zgłoszeń. Kolejne przez stronę notarai.pl.")
    return klucz


def lagodnie(funkcja):
    """Bledy, ktore rozmowca moze poprawic (brak wartosci, nieznana kancelaria,
    zajety termin), wracaja jako zwykla odpowiedz {"ok": false, "do_powiedzenia"}.
    ElevenLabs domyslnie ukrywa przed modelem tresc bledow HTTP, a agent musi
    wiedziec, o co dopytac. Brak dostepu (401), limity (429) i bledy serwera
    zostaja bledami HTTP."""
    @functools.wraps(funkcja)
    def opakowana(*args, **kwargs):
        try:
            return funkcja(*args, **kwargs)
        except HTTPException as blad:
            if blad.status_code in (400, 404, 409, 422):
                return {"ok": False, "do_powiedzenia": str(blad.detail)}
            raise
    return opakowana


def zl_na_glos(x) -> str:
    """12808.91 -> '12 808 zł 91 gr' (czytelne dla syntezy mowy)."""
    k = taksa.grosze(taksa.kwota(x))
    zlote, grosze = divmod(int(k * 100), 100)
    tekst = f"{zlote:,}".replace(",", " ") + " zł"
    return tekst + (f" {grosze:02d} gr" if grosze else "")


def _bez_ogonkow(tekst: str) -> str:
    tekst = (tekst or "").replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFKD", tekst) if not unicodedata.combining(c))


def _slug(tekst: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _bez_ogonkow(tekst).lower()).strip("-")


def znajdz_miejscowosc(nazwa: str) -> tuple[str | None, list[str]]:
    """Nazwa z rozmowy -> (slug z bazy albo None, podpowiedzi nazw).

    Dokladnie po slugu, potem po nazwie bez ogonkow, potem podobne nazwy
    (literowki rozpoznawania mowy: 'Krakow', 'Bielsko Biala')."""
    miejscowosci = wizyty.baza()["miejscowosci"]
    tekst = re.sub(r"^(w|we|z|ze|do|na)\s+", "", (nazwa or "").strip(), flags=re.I)
    slug = _slug(tekst)
    if not slug:
        return None, []
    if slug in miejscowosci:
        return slug, []
    po_nazwie = {_slug(m["nazwa"]): s for s, m in miejscowosci.items()}
    if slug in po_nazwie:
        return po_nazwie[slug], []
    podobne = difflib.get_close_matches(slug, list(po_nazwie), n=3, cutoff=0.75)
    if len(podobne) == 1 and difflib.SequenceMatcher(None, slug, podobne[0]).ratio() >= 0.88:
        return po_nazwie[podobne[0]], []
    return None, [miejscowosci[po_nazwie[p]]["nazwa"] for p in podobne]


def _kancelaria(baza_id: int) -> dict:
    k = wizyty.baza()["kancelarie"].get(int(baza_id))
    if not k:
        raise HTTPException(404, "Nie znamy kancelarii o tym numerze. Najpierw wyszukaj kancelarie w miejscowości.")
    return k


# --- koszt czynnosci i dokumenty ----------------------------------------------


CZYNNOSCI = [r["id"] for r in taksa.RODZAJE] + [c["id"] for c in taksa.CZYNNOSCI_STALE]


class Koszt(BaseModel):
    czynnosc: str
    wartosc: float | None = None
    grupa1: bool = False
    hipoteka_kwota: float | None = None
    ilosc: int = Field(1, ge=1, le=50)
    rozmowa: str = ""


def _parametry(d: Koszt) -> dict:
    if d.czynnosc in taksa.RODZAJE_WG_ID:
        if not d.wartosc or d.wartosc <= 0:
            raise HTTPException(422, "Ta czynność liczy się od wartości. Zapytaj o wartość (np. cenę nieruchomości).")
        parametry = {"czynnosci": [{"rodzaj": d.czynnosc, "wartosc": d.wartosc}], "grupa1": d.grupa1}
    elif d.czynnosc in taksa.STALE_WG_ID:
        parametry = {"stale": [{"id": d.czynnosc, "ilosc": d.ilosc}]}
    else:
        raise HTTPException(422, "Nieznana czynność. Wybierz identyfikator z listy narzędzia.")
    if d.hipoteka_kwota and d.hipoteka_kwota > 0:
        parametry["hipoteka"] = {"kwota": d.hipoteka_kwota}
    return parametry


def _dokumenty(wynik: dict) -> list[str]:
    lista = []
    for grupa in wynik.get("dokumenty") or []:
        for pozycja in grupa["pozycje"]:
            lista.append(f"{pozycja} ({grupa['grupa']})")
    return lista[:MAKS_DOKUMENTOW]


@router.post("/koszt")
@lagodnie
def koszt(d: Koszt, request: Request):
    """Szacunek kosztow: taksa, wypisy, PCC, oplaty sadowe - i lista dokumentow."""
    _odczyt(d.rozmowa, request)
    wynik = taksa.oblicz(_parametry(d))
    if not wynik["pozycje"]:
        raise HTTPException(422, "Nie udało się policzyć kosztu dla tych danych.")
    pozycje = [f"{p['etykieta']}: {zl_na_glos(p['brutto'])}" for p in wynik["pozycje"]]
    log.info("agent_glosowy: koszt (%s), pozycji %d", d.czynnosc, len(pozycje))
    return {
        "ok": True,
        "razem": zl_na_glos(wynik["razem"]),
        "pozycje": pozycje,
        "dokumenty": _dokumenty(wynik),
        "uwagi": wynik.get("uwagi") or [],
        "do_powiedzenia": (f"Szacunkowo razem około {zl_na_glos(wynik['razem'])} brutto. "
                           "To kwoty według maksymalnych stawek z rozporządzenia; notariusz może "
                           "przyjąć niższą taksę, a dokładną kwotę potwierdza kancelaria."),
    }


class Dokumenty(BaseModel):
    czynnosc: str
    rozmowa: str = ""


@router.post("/dokumenty")
@lagodnie
def dokumenty(d: Dokumenty, request: Request):
    """Co przyniesc do kancelarii. Bez wartosci: lista zalezy tylko od rodzaju czynnosci."""
    _odczyt(d.rozmowa, request)
    if d.czynnosc not in CZYNNOSCI:
        raise HTTPException(422, "Nieznana czynność. Wybierz identyfikator z listy narzędzia.")
    wartosc = 100000 if d.czynnosc in taksa.RODZAJE_WG_ID else None
    wynik = taksa.oblicz(_parametry(Koszt(czynnosc=d.czynnosc, wartosc=wartosc)))
    lista = _dokumenty(wynik)
    return {"ok": True, "dokumenty": lista,
            "do_powiedzenia": ("Zwykle potrzebne są: " + "; ".join(lista) + ". Kancelaria może poprosić o więcej."
                               if lista else "Wystarczy dowód osobisty lub paszport. Kancelaria potwierdzi szczegóły.")}


# --- kancelarie, terminy, rezerwacja, zgloszenie ------------------------------


class Szukaj(BaseModel):
    miejscowosc: str
    tylko_rezerwacja_online: bool = False
    rozmowa: str = ""


@router.post("/kancelarie")
@lagodnie
def kancelarie(d: Szukaj, request: Request):
    """Kancelarie w miejscowosci w tej samej neutralnej kolejnosci co na stronie."""
    _odczyt(d.rozmowa, request)
    slug, podpowiedzi = znajdz_miejscowosc(d.miejscowosc)
    if not slug:
        return {"znaleziono": False, "podpowiedzi": podpowiedzi,
                "do_powiedzenia": ("Nie znalazłam tej miejscowości w wykazie. "
                                   + (f"Czy chodzi o: {', '.join(podpowiedzi)}?" if podpowiedzi
                                      else "Poproś o nazwę miejscowości albo najbliższego miasta."))}
    b = wizyty.baza()
    identyfikatory = b["wg_miejscowosci"].get(slug, [])
    online = [i for i in identyfikatory if i in wizyty.kancelarie_notarai()]
    rezerwacja = set(rezerwacje_klientow.online(online))
    kolejnosc = rekomendacje.kolejnosc([b["kancelarie"][i] for i in identyfikatory], kontekst=slug)
    kolejnosc = [k for k in kolejnosc if not k.get("brak_kontaktu")]
    if d.tylko_rezerwacja_online:
        kolejnosc = [k for k in kolejnosc if k["id"] in rezerwacja]
    lista = [{"kancelaria_id": k["id"], "nazwa": k["nazwa"], "adres": k.get("adres", ""),
              "telefon": (k.get("telefony") or [""])[0], "rezerwacja_online": k["id"] in rezerwacja,
              "zgloszenie_w_aplikacji": k["id"] in online}
             for k in kolejnosc[:MAKS_KANCELARII]]
    nazwa = b["miejscowosci"][slug]["nazwa"]
    return {"znaleziono": True, "miejscowosc": nazwa, "miejscowosc_id": slug, "liczba": len(kolejnosc),
            "kancelarie": lista, "kolejnosc": "neutralna (codzienna rotacja, jak na notarai.pl)",
            "do_powiedzenia": (f"W miejscowości {nazwa} mam {len(kolejnosc)} kancelarii. "
                               + ("Kilka pierwszych z dzisiejszej kolejności: "
                                  + "; ".join(k["nazwa"] for k in lista) + "."
                                  if lista else "Żadna nie przyjmuje teraz rezerwacji online."))}


class Terminy(BaseModel):
    kancelaria_id: int
    od: str = ""
    dni: int = Field(7, ge=1, le=14)
    rozmowa: str = ""


@router.post("/terminy")
@lagodnie
def terminy(d: Terminy, request: Request):
    _odczyt(d.rozmowa, request)
    k = _kancelaria(d.kancelaria_id)
    if d.od:
        try:
            date.fromisoformat(d.od)
        except ValueError:
            raise HTTPException(422, "Data w formacie RRRR-MM-DD.")
    wynik = rezerwacje_klientow.terminy(d.kancelaria_id, d.od, d.dni)
    if not wynik["online"]:
        return {"rezerwacja_online": False, "kancelaria": k["nazwa"],
                "do_powiedzenia": ("Ta kancelaria nie przyjmuje rezerwacji online. Mogę przekazać prośbę "
                                   "o kontakt - kancelaria oddzwoni i ustali termin.")}
    dni: dict[str, list[str]] = {}
    for s in wynik["terminy"]:
        dni.setdefault(s["data"], []).append(s["godzina"])
    wolne = [{"data": dzien, "godziny": godziny[:MAKS_GODZIN_DNIA], "wiecej": max(0, len(godziny) - MAKS_GODZIN_DNIA)}
             for dzien, godziny in dni.items()]
    return {"rezerwacja_online": True, "kancelaria": k["nazwa"], "adres": wynik.get("adres", ""),
            "czas_wizyty_minut": wynik["czas_minut"], "wolne": wolne,
            "do_powiedzenia": ("Brak wolnych godzin w tym okresie. Zapytaj o późniejszy termin."
                               if not wolne else "Podaj klientowi dwa, trzy najbliższe terminy i zapytaj, który pasuje.")}


class DaneKlienta(BaseModel):
    imie: str
    telefon: str = ""
    email: str = ""
    czynnosc: str
    zgoda: bool = False
    rozmowa: str = ""


class Rezerwacja(DaneKlienta):
    kancelaria_id: int
    data: str
    godzina: str
    wartosc: float | None = None
    uwagi: str = ""


@router.post("/rezerwacja")
@lagodnie
def rezerwacja(d: Rezerwacja, request: Request):
    klucz = _zapis(d.rozmowa, request)
    _kancelaria(d.kancelaria_id)
    dane = rezerwacje_klientow.Rezerwacja(
        imie=d.imie, telefon=d.telefon, email=d.email, czynnosc=d.czynnosc, wartosc=d.wartosc,
        wiadomosc=_wiadomosc(d.uwagi), zgoda=d.zgoda, kancelaria=d.kancelaria_id, data=d.data,
        godzina=d.godzina, zrodlo="agent_glosowy")
    wynik = rezerwacje_klientow.zarezerwuj(dane, klucz)
    log.info("agent_glosowy: rezerwacja %s", wynik["id"])
    return {"ok": True, "id": wynik["id"], "do_powiedzenia": wynik["komunikat"]}


class Zgloszenie(DaneKlienta):
    kancelaria_id: int | None = None
    miejscowosc: str = ""
    termin: str = ""
    wartosc: float | None = None
    uwagi: str = ""


def _wiadomosc(uwagi: str) -> str:
    return ("Zgłoszenie przyjęte przez asystenta głosowego notarai.\n" + (uwagi or "").strip())[:2000]


@router.post("/zgloszenie")
@lagodnie
def zgloszenie(d: Zgloszenie, request: Request):
    """Prosba o kontakt do wybranej kancelarii albo do kancelarii w miejscowosci."""
    klucz = _zapis(d.rozmowa, request)
    miejscowosc = ""
    if d.kancelaria_id is None:
        slug, podpowiedzi = znajdz_miejscowosc(d.miejscowosc)
        if not slug:
            return {"ok": False, "podpowiedzi": podpowiedzi,
                    "do_powiedzenia": "Nie rozpoznałam miejscowości. Poproś o nią jeszcze raz."}
        miejscowosc = slug
    else:
        _kancelaria(d.kancelaria_id)
    dane = wizyty.Zgloszenie(
        imie=d.imie, telefon=d.telefon, email=d.email, czynnosc=d.czynnosc, wartosc=d.wartosc,
        termin=d.termin, wiadomosc=_wiadomosc(d.uwagi), zgoda=d.zgoda, kancelaria=d.kancelaria_id,
        miejscowosc=miejscowosc, zrodlo="agent_glosowy")
    wynik = wizyty.przyjmij(dane, request, klucz_limitu=klucz)
    log.info("agent_glosowy: zgloszenie %s (gielda=%s)", wynik["id"], bool(wynik.get("gielda")))
    return {"ok": True, "id": wynik["id"], "do_powiedzenia": wynik["komunikat"]}


# --- kancelarie zainteresowane notarai ----------------------------------------


class KontaktKancelarii(BaseModel):
    imie: str
    kancelaria: str = ""
    miejscowosc: str = ""
    telefon: str = ""
    email: str = ""
    temat: str = ""
    zgoda: bool = False
    rozmowa: str = ""


@router.post("/kontakt-notarai")
@lagodnie
def kontakt_notarai(d: KontaktKancelarii, request: Request):
    """Notariusz albo pracownik kancelarii chce rozmowy o notarai (demo, wdrozenie, cena)."""
    _zapis(d.rozmowa, request)
    imie = " ".join(d.imie.split())[:80]
    telefon = " ".join(d.telefon.split())[:40]
    email = d.email.strip().lower()[:120]
    if len(imie) < 2:
        return {"ok": False, "do_powiedzenia": "Zapytaj, jak się nazywa rozmówca."}
    if not telefon and not email:
        return {"ok": False, "do_powiedzenia": "Potrzebny jest telefon albo e-mail do kontaktu."}
    if telefon and len(re.sub(r"\D", "", telefon)) < 7:
        return {"ok": False, "do_powiedzenia": "Numer telefonu wygląda na niepełny. Poproś o niego jeszcze raz."}
    if not d.zgoda:
        return {"ok": False, "do_powiedzenia": "Zapytaj o zgodę na kontakt w sprawie notarai."}
    adresy = [a for a in [wizyty.KOPIA, *autoryzacja.STALI_ADMINI] if a]
    tresc = (f"Prośba o kontakt w sprawie notarai (asystent głosowy).\n\nImię i nazwisko: {imie}\n"
             f"Kancelaria: {d.kancelaria[:200]}\nMiejscowość: {d.miejscowosc[:80]}\nTelefon: {telefon}\n"
             f"E-mail: {email}\nTemat: {d.temat[:1000]}\nZgoda na kontakt: tak\n")
    if not wizyty._wyslij_email(adresy, "[notarai] kancelaria prosi o kontakt (asystent głosowy)", tresc):
        log.error("agent_glosowy: kontakt-notarai nie wyslany (brak poczty)")
        return {"ok": False, "do_powiedzenia": f"Nie udało się teraz przekazać prośby. Zaproponuj e-mail na {KONTAKT} "
                                               "albo samodzielną rejestrację na notarai.pl - 14 dni za darmo."}
    log.info("agent_glosowy: kontakt-notarai wyslany")
    return {"ok": True, "do_powiedzenia": "Przekazałam prośbę. Zespół notarai odezwie się zwykle w ciągu jednego "
                                          "dnia roboczego."}


@router.get("")
def stan():
    """Sonda dla testow po wdrozeniu: czy trasy dzialaja i czy wymagany jest token."""
    return {"wlaczony": WLACZONY, "token_wymagany": bool(TOKEN), "czynnosci": len(CZYNNOSCI),
            "narzedzia": ["koszt", "dokumenty", "kancelarie", "terminy", "rezerwacja", "zgloszenie",
                          "kontakt-notarai"]}
