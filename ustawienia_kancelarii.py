"""Ustawienia ogolne kancelarii: to, co notariusz ustawia raz, zamiast klikac
przy kazdej sprawie.

  - domyslna dokladnosc odczytu (auto / max / high / medium) - od niej zaczyna
    przelacznik "Dokladnosc odczytu" przy kazdej nowej sprawie, na kazdym
    urzadzeniu; "auto" dobiera dokladnosc do dokumentow (dokladnosc_odczytu),
  - wzor nazwy pliku Word z projektem (nazwy.nazwa_pliku), np.
    "{zbywca} - {nabywca} - {czynnosc} - {miejscowosc}",
  - jak dlugo trwa zalogowanie (wylogowanie) i czy wylogowac po bezczynnosci
    (bezczynnosc) - pilnuje tego autoryzacja.odnow i przegladarka,
  - jak dlugo kopie spraw leza na serwerze (przechowywanie_spraw) i czy po
    tym czasie usuwac je samemu (usuwanie_spraw) - retencja_spraw.py.

Plik kancelarii "ustawienia" (magazyn.PLIKI_KANCELARII): w chmurze lezy w S3
razem z kalendarzem i zasadami, lokalnie w dane/. Same preferencje, zero
danych osobowych. Zmienia je notariusz (wlasciciel kancelarii), tak jak
nieprzekraczalne zasady; w trybie lokalnym - kazdy.
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import dokumenty
import magazyn
import nazwy

log = logging.getLogger("pieczapp.ustawienia")

router = APIRouter(prefix="/api/ustawienia/ogolne", tags=["ustawienia"])

PLIK = "ustawienia"

# Wartosci przelacznika. "auto" nie trafia do modelu - dokladnosc_odczytu()
# zamienia je na konkretny wysilek po obejrzeniu dokumentow sprawy.
DOKLADNOSCI = ("auto", "max", "high", "medium")
OPISY_DOKLADNOSCI = {
    "auto": "Automatyczna: dokumenty elektroniczne (PDF z tekstem) czytam szybko, "
            "skany i zdjecia - z wysoka dokladnoscia.",
    "max": "Maksymalna: model najdluzej analizuje kazda strone. Najwolniej i najdrozej.",
    "high": "Wysoka: zwykle wystarcza przy czytelnych skanach.",
    "medium": "Szybka: najszybciej i najtaniej, do prostych spraw z wyraznymi dokumentami.",
}
MAX_DLUGOSC_WZORU = 200
# Jak w pliku Word wyglada brakujaca dana: "opis" = <<BRAK: numer dowodu>>,
# "pytajnik" = sam "?" (podswietlony). W aplikacji znacznik zostaje zawsze -
# na nim dzialaja licznik brakow, podswietlenie i korespondencja.
BRAKI = ("opis", "pytajnik")
# Profil interfejsu kancelarii: kazdy notariusz ustawia aplikacje pod siebie
# (zwykle zdaniem, przez asystenta kancelarii). Przegladarka stosuje go przy starcie.
ROZMIARY_TEKSTU = ("normalny", "duzy", "bardzo_duzy")
WIDOKI_STARTOWE = ("panel", "nowa_sprawa", "kalendarz", "osoby", "przesylki", "poczta", "ksiegi")
NARZEDZIA_MENU = ("sprawdzenia", "klikamy", "kalendarz", "osoby", "przesylki", "poczta",
                  "poswiadczenia", "stenogramy", "styl", "ksiegi", "giif")

# Bezpieczenstwo i przechowywanie - wybiera notariusz. Domyslne zachowuja to,
# co bylo przed wprowadzeniem ustawien: logowanie raz na 30 dni, bez
# wylogowania po bezczynnosci, sprawy leza do recznego usuniecia.
WYLOGOWANIE_S = {"8_godzin": 8 * 3600, "1_dzien": 86400, "7_dni": 7 * 86400,
                 "30_dni": 30 * 86400, "nigdy": None}
BEZCZYNNOSC_S = {"wylaczone": None, "15_minut": 15 * 60, "30_minut": 30 * 60,
                 "1_godzina": 3600, "4_godziny": 4 * 3600}
PRZECHOWYWANIE_DNI = {"bez_limitu": None, "30_dni": 30, "90_dni": 90, "180_dni": 180,
                      "1_rok": 365, "2_lata": 730, "5_lat": 1825}
USUWANIE = ("przypominaj", "automatycznie")
# Po wlaczeniu automatycznego usuwania (albo skroceniu czasu) pierwsze sprawy
# znikaja dopiero po tylu dniach. Notariusz widzi je na liscie spraw i moze
# zmienic zdanie - pomylka w jednym zdaniu do asystenta nie kasuje archiwum.
KARENCJA_DNI = 7
# Pozostale ustawienia z zamknieta lista wartosci: klucz -> dozwolone.
WYBORY = {
    "dokladnosc": DOKLADNOSCI, "braki": BRAKI, "rozmiar_tekstu": ROZMIARY_TEKSTU,
    "widok_startowy": WIDOKI_STARTOWE, "wylogowanie": tuple(WYLOGOWANIE_S),
    "bezczynnosc": tuple(BEZCZYNNOSC_S), "przechowywanie_spraw": tuple(PRZECHOWYWANIE_DNI),
    "usuwanie_spraw": USUWANIE,
}
_BLEDY_WYBORU = {
    "dokladnosc": "Nieznana dokladnosc odczytu. Dozwolone: ",
    "braki": "Nieznany sposob oznaczania brakow. Dozwolone: ",
    "rozmiar_tekstu": "Wielkosc tekstu: ",
    "widok_startowy": "Ekran startowy: ",
    "wylogowanie": "Wylogowanie: ",
    "bezczynnosc": "Wylogowanie po bezczynnosci: ",
    "przechowywanie_spraw": "Przechowywanie spraw: ",
    "usuwanie_spraw": "Usuwanie spraw: ",
}


def _lista_narzedzi(wartosc) -> list[str] | None:
    """"kalendarz, giif" -> ["giif", "kalendarz"]; None gdy jest nieznana nazwa."""
    if isinstance(wartosc, (list, tuple)):
        nazwy = [str(n).strip().lower() for n in wartosc]
    else:
        nazwy = [n.strip().lower() for n in str(wartosc or "").replace(";", ",").split(",")]
    nazwy = [n for n in nazwy if n]
    if any(n not in NARZEDZIA_MENU for n in nazwy):
        return None
    return sorted(set(nazwy))


# Opisy dla asystenta kancelarii (asystent_kancelarii.py) - kazde ustawienie
# z domyslne() MUSI miec tu opis z dozwolonymi wartosciami.
OPISY_USTAWIEN = {
    "dokladnosc": "domyślna dokładność odczytu skanów: auto | max | high | medium",
    "nazwa_pliku": "wzór nazwy pliku Word z projektem, pola: {zbywca} {nabywca} {strony} {czynnosc} "
                   "{miejscowosc} {sygnatura} {nazwa} (np. \"{zbywca} - {nabywca} - {czynnosc}\")",
    "braki": "jak oznaczać w pliku Word brakujące dane: opis (<<BRAK: numer dowodu>>) | pytajnik (?)",
    "rozmiar_tekstu": "wielkość tekstu w aplikacji: normalny | duzy | bardzo_duzy",
    "widok_startowy": "ekran po zalogowaniu: panel | nowa_sprawa | kalendarz | osoby | przesylki | poczta | ksiegi",
    "ukryte_narzedzia": "narzędzia schowane z menu, po przecinku (pusto = wszystkie widoczne): "
                        + ", ".join(NARZEDZIA_MENU),
    "wylogowanie": "po jakim czasie od zalogowania hasłem aplikacja wyloguje (nigdy = zalogowany non-stop, "
                   "do ręcznego wylogowania): " + " | ".join(WYLOGOWANIE_S),
    "bezczynnosc": "wylogowanie po czasie bez pracy przy komputerze: " + " | ".join(BEZCZYNNOSC_S),
    "przechowywanie_spraw": "jak długo kopie spraw leżą na serwerze notarai, liczone od ostatniej zmiany "
                            "w sprawie: " + " | ".join(PRZECHOWYWANIE_DNI),
    "usuwanie_spraw": "co po tym czasie: przypominaj (sprawa oznaczona na liście, usuwa notariusz) | "
                      "automatycznie (serwer sam usuwa sprawę na zawsze, pierwsze usunięcia "
                      f"najwcześniej {KARENCJA_DNI} dni po włączeniu)",
}


def domyslne() -> dict:
    return {"dokladnosc": "auto", "nazwa_pliku": nazwy.DOMYSLNY_WZOR_NAZWY, "braki": "opis",
            "rozmiar_tekstu": "normalny", "widok_startowy": "panel", "ukryte_narzedzia": "",
            "wylogowanie": "30_dni", "bezczynnosc": "wylaczone",
            "przechowywanie_spraw": "bez_limitu", "usuwanie_spraw": "przypominaj"}


def _oczysc(dane: dict) -> dict:
    """Tylko znane klucze i poprawne wartosci; reszta wraca do domyslnych."""
    wynik = domyslne()
    for klucz, dozwolone in WYBORY.items():
        if dane.get(klucz) in dozwolone:
            wynik[klucz] = dane[klucz]
    # Znacznik techniczny (nie ustawienie): od kiedy dziala automatyczne usuwanie
    # w obecnym ksztalcie. Liczy sie od niego karencja.
    if wynik["usuwanie_spraw"] == "automatycznie" and _data(dane.get("automatyczne_od")):
        wynik["automatyczne_od"] = dane["automatyczne_od"]
    ukryte = _lista_narzedzi(dane.get("ukryte_narzedzia", ""))
    if ukryte is not None:
        wynik["ukryte_narzedzia"] = ", ".join(ukryte)
    wzor = dane.get("nazwa_pliku")
    if isinstance(wzor, str) and wzor.strip():
        wynik["nazwa_pliku"] = wzor.strip()[:MAX_DLUGOSC_WZORU]
    return wynik


def wczytaj() -> dict:
    """Ustawienia kancelarii; przy bledzie odczytu - domyslne (odczyt sprawy
    nie moze sie wywrocic przez plik ustawien)."""
    try:
        dane = magazyn.wczytaj_plik_kancelarii(PLIK, {})
    except Exception as blad:  # noqa: BLE001
        log.warning("ustawienia kancelarii nieodczytane (%s), biore domyslne", type(blad).__name__)
        dane = {}
    return _oczysc(dane if isinstance(dane, dict) else {})


def _data(wartosc) -> datetime | None:
    try:
        return datetime.fromisoformat(str(wartosc)) if wartosc else None
    except ValueError:
        return None


def sekundy_sesji(ustawienia: dict) -> int | None:
    """Najdluzszy czas od zalogowania haslem; None = bez limitu."""
    return WYLOGOWANIE_S.get(ustawienia.get("wylogowanie"), WYLOGOWANIE_S["30_dni"])


def dni_przechowania(ustawienia: dict) -> int | None:
    """Ile dni od ostatniej zmiany sprawa lezy na serwerze; None = bez limitu."""
    return PRZECHOWYWANIE_DNI.get(ustawienia.get("przechowywanie_spraw"))


def usuwanie_od(ustawienia: dict) -> datetime | None:
    """Od kiedy wolno usuwac automatycznie (koniec karencji); None = nie wolno."""
    if ustawienia.get("usuwanie_spraw") != "automatycznie" or dni_przechowania(ustawienia) is None:
        return None
    poczatek = _data(ustawienia.get("automatyczne_od"))
    return (poczatek + timedelta(days=KARENCJA_DNI)) if poczatek else None


def zapisz(zmiany: dict) -> dict:
    """Zapis tylko podanych kluczy; nieznane wartosci sa odrzucane (400)."""
    for klucz, dozwolone in WYBORY.items():
        if klucz in zmiany and zmiany[klucz] not in dozwolone:
            raise ValueError(_BLEDY_WYBORU[klucz] + ", ".join(dozwolone) + ".")
    if "ukryte_narzedzia" in zmiany:
        ukryte = _lista_narzedzi(zmiany["ukryte_narzedzia"])
        if ukryte is None:
            raise ValueError("Nieznane narzedzie. Dostepne: " + ", ".join(NARZEDZIA_MENU) + ".")
        zmiany["ukryte_narzedzia"] = ", ".join(ukryte)
    if "nazwa_pliku" in zmiany:
        wzor = str(zmiany["nazwa_pliku"] or "").strip()
        if not wzor:
            zmiany["nazwa_pliku"] = nazwy.DOMYSLNY_WZOR_NAZWY
        elif len(wzor) > MAX_DLUGOSC_WZORU:
            raise ValueError(f"Wzor nazwy pliku jest za dlugi (najwyzej {MAX_DLUGOSC_WZORU} znakow).")
        else:
            nieznane = nazwy.nieznane_pola_wzoru(wzor)
            if nieznane:
                raise ValueError("Nieznane pola we wzorze nazwy: " + ", ".join("{" + p + "}" for p in nieznane)
                                 + ". Dostepne: " + ", ".join("{" + p + "}" for p in nazwy.POLA_NAZWY) + ".")
            zmiany["nazwa_pliku"] = wzor

    def zmiana(dane: dict) -> dict:
        przed = _oczysc(dane)
        for klucz in domyslne():
            if klucz in zmiany:
                dane[klucz] = zmiany[klucz]
        po = _oczysc(dane)
        # Karencja liczy sie od nowa przy kazdym zaostrzeniu: wlaczeniu
        # automatycznego usuwania albo skroceniu czasu przechowania.
        if po["usuwanie_spraw"] == "automatycznie" and dni_przechowania(po) is not None:
            dni_przed = dni_przechowania(przed)
            zaostrzenie = (przed["usuwanie_spraw"] != "automatycznie" or dni_przed is None
                           or dni_przechowania(po) < dni_przed or not przed.get("automatyczne_od"))
            if zaostrzenie:
                dane["automatyczne_od"] = datetime.now().isoformat(timespec="seconds")
        else:
            dane.pop("automatyczne_od", None)
        return _oczysc(dane)

    wynik = magazyn.zmien_plik_kancelarii(PLIK, zmiana, {})
    log.info("ustawienia kancelarii zapisane: dokladnosc=%s wylogowanie=%s przechowywanie=%s/%s",
             wynik["dokladnosc"], wynik["wylogowanie"], wynik["przechowywanie_spraw"], wynik["usuwanie_spraw"])
    return wynik


# ---------------------------------------------------------------------------
# Dokladnosc odczytu dla konkretnej sprawy
# ---------------------------------------------------------------------------
def dokladnosc_odczytu(zadana: str, strony: list[dict]) -> tuple[str, str]:
    """(wysilek dla modelu, powod wyboru).

    `zadana` to wartosc z przelacznika przy sprawie; pusta albo nieznana
    oznacza domyslna kancelarii. "auto" rozstrzygamy po dokumentach: gdy kazda
    strona ma warstwe tekstowa PDF (wydruki z EKW, rejestru gruntow, pisma
    z systemow), model dostaje dokladne znaki i wystarczy odczyt szybki;
    skany i zdjecia czytamy z wysoka dokladnoscia. Maksymalna zostaje do
    wyboru recznego - trudne sprawy notariusz poznaje sam.

    Powod: "wybrana" (przelacznik), "domyslna" (ustawienie kancelarii),
    "auto_elektroniczne" albo "auto_skany".
    """
    if zadana in DOKLADNOSCI:
        wybor, powod = zadana, "wybrana"
    else:
        wybor, powod = wczytaj()["dokladnosc"], "domyslna"
    if wybor != "auto":
        return wybor, powod
    try:
        udzial = dokumenty.udzial_warstwy_tekstowej(strony)
    except Exception as blad:  # noqa: BLE001 - uszkodzony plik wyjdzie przy odczycie
        log.warning("auto-dokladnosc: nie sprawdzono warstwy tekstowej (%s)", type(blad).__name__)
        udzial = 0.0
    if strony and udzial >= 1.0:
        return "medium", "auto_elektroniczne"
    return "high", "auto_skany"


def opis_wyboru(wysilek: str, powod: str) -> str:
    """Zdanie dla notariusza po odczycie - skad sie wziela ta dokladnosc."""
    nazwa = {"max": "maksymalna", "high": "wysoka", "medium": "szybka"}.get(wysilek, wysilek)
    if powod == "auto_elektroniczne":
        return f"Dokładność {nazwa}: wszystkie strony to dokumenty elektroniczne z tekstem."
    if powod == "auto_skany":
        return f"Dokładność {nazwa}: w sprawie są skany lub zdjęcia bez warstwy tekstowej."
    if powod == "domyslna":
        return f"Dokładność {nazwa} (ustawienie kancelarii)."
    return f"Dokładność {nazwa}."


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
class Zmiany(BaseModel):
    dokladnosc: str | None = None
    nazwa_pliku: str | None = None
    braki: str | None = None
    rozmiar_tekstu: str | None = None
    widok_startowy: str | None = None
    ukryte_narzedzia: str | None = None
    wylogowanie: str | None = None
    bezczynnosc: str | None = None
    przechowywanie_spraw: str | None = None
    usuwanie_spraw: str | None = None


def _moge_zmieniac(request: Request) -> bool:
    # Te same reguly co dla zasad kancelarii: wlasciciel; bez logowania - kazdy.
    import personalizacja
    return personalizacja._moge_zmieniac_zasady(request)


@router.get("")
def pobierz(request: Request):
    return {
        **wczytaj(),
        "moge_zmieniac": _moge_zmieniac(request),
        "u_klienta": magazyn.u_klienta(),
        "pola_nazwy": nazwy.POLA_NAZWY,
        "domyslny_wzor_nazwy": nazwy.DOMYSLNY_WZOR_NAZWY,
        "przyklad_nazwy": nazwy.przyklad_nazwy(wczytaj()["nazwa_pliku"]),
    }


@router.put("")
def zmien(request: Request, dane: Zmiany):
    if not _moge_zmieniac(request):
        raise HTTPException(403, "Ustawienia kancelarii zmienia notariusz - właściciel kancelarii.")
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie - ustawienia zostają w tej przeglądarce.")
    zmiany = {k: v for k, v in dane.model_dump().items() if v is not None}
    if not zmiany:
        raise HTTPException(400, "Nic do zapisania.")
    try:
        wynik = zapisz(zmiany)
    except ValueError as blad:
        raise HTTPException(400, str(blad))
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))
    return {**wynik, "przyklad_nazwy": nazwy.przyklad_nazwy(wynik["nazwa_pliku"])}
