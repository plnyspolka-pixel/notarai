"""Personalizacja projektow: API "Styl i zasady kancelarii" + kontrola projektu.

Trzy rzeczy, ktore notariusz robi w jednym miejscu aplikacji:
  - pisze nieprzekraczalne zasady kancelarii zwyklym zdaniem (zasady.py),
  - uczy notarai swojego stylu, wrzucajac stare akty (styl.py),
  - poprawia wyuczony styl: przypina wzorcowe sformulowania, ukrywa zle,
    przyjmuje albo odrzuca zasady podpowiedziane z jego aktow.

`przygotuj()` i `skontroluj()` wpinaja to w generowanie projektu: zasady
i styl ida do modelu, a gotowy projekt przechodzi przez zasady.egzekwuj(),
zanim zostanie pokazany.

Zero danych osobowych w logach: logujemy liczby, nigdy tresc aktow ani zasad.
"""
import json
import logging
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

import autoryzacja
import bedrock
import dziennik
import kategorie
import klauzule
import magazyn
import styl
import zasady

log = logging.getLogger("pieczapp.personalizacja")

router = APIRouter(prefix="/api/personalizacja", tags=["personalizacja"])

MAX_AKTOW = 30
MAX_ROZMIAR = 15 * 1024 * 1024


# ---------------------------------------------------------------------------
# Wpiecie w generowanie projektu
# ---------------------------------------------------------------------------
def rodzaje_sprawy(tekst_wzoru: str, polecenie: str = "") -> list[str]:
    """Rodzaj dokumentu ze wzoru i polecenia - wzor mowi, co piszemy."""
    return [r["rodzaj"] for r in kategorie.klasyfikuj_dokument(f"{tekst_wzoru}\n{polecenie}")]


def przygotuj(rodzaje: list[str]) -> tuple[dict | None, str]:
    """(zasady kancelarii albo None gdy nie udalo sie ich wczytac, blok dla modelu)."""
    try:
        ustawienia = zasady.wczytaj()
        profil = styl.wczytaj()
    except Exception as blad:  # noqa: BLE001 - projekt powstanie, ale z ostrzezeniem
        log.error("personalizacja: nie wczytano zasad ani stylu (%s)", dziennik.opis_bledu(blad))
        return None, ""
    bloki = [zasady.blok_do_polecenia(ustawienia, rodzaje), styl.blok_do_polecenia(profil, rodzaje)]
    return ustawienia, "\n\n".join(b for b in bloki if b)


def skontroluj(projekt: str, ustawienia: dict | None, rodzaje: list[str]) -> tuple[str, dict]:
    """Projekt po kontroli zasad kancelarii - zanim zobaczy go notariusz."""
    if ustawienia is None:
        return projekt, {
            "zgodny": False, "niesprawdzony": True, "sprawdzonych": 0, "blokujacych": 0, "ostrzezen": 0,
            "naruszenia": [], "poprawki": [], "rodzaje": [],
            "komunikat": "Nie udało się wczytać zasad kancelarii - projekt NIE został z nimi sprawdzony.",
        }
    projekt, raport = zasady.egzekwuj(projekt, ustawienia, popraw_modelem=bedrock.popraw_wg_zasad,
                                      sprawdz_modelem=bedrock.sprawdz_wytyczne, rodzaje=rodzaje)
    log.info("kontrola zasad: sprawdzonych=%d blokujacych=%d ostrzezen=%d poprawek=%d",
             raport["sprawdzonych"], raport["blokujacych"], raport["ostrzezen"], len(raport["poprawki"]))
    return projekt, raport


# ---------------------------------------------------------------------------
# Pomocnicze
# ---------------------------------------------------------------------------
MAX_PLIKOW_PRZEGLADARKI = 8 * 1024 * 1024


def stan_z_przegladarki(pliki) -> dict | None:
    """Zasady i styl przyslane przez przegladarke kancelarii "u siebie".

    Dla kancelarii w chmurze zwraca None - jej pliki sa na serwerze, a to,
    co przyslala przegladarka, pomijamy. Zawartosc normalizujemy: plik
    z dysku mogl zapisac starszy klient albo ktos go recznie zmienil.
    """
    if pliki is None or not magazyn.u_klienta():
        return None
    if isinstance(pliki, str):
        if not pliki.strip():
            return None
        if len(pliki) > MAX_PLIKOW_PRZEGLADARKI:
            raise HTTPException(413, "Pliki zasad i stylu są za duże.")
        try:
            pliki = json.loads(pliki)
        except json.JSONDecodeError:
            raise HTTPException(400, "Nieprawidłowy format plików zasad i stylu.")
    if not isinstance(pliki, dict):
        raise HTTPException(400, "Nieprawidłowy format plików zasad i stylu.")
    return {"zasady": zasady.normalizuj(pliki.get("zasady")), "styl": styl.normalizuj(pliki.get("styl"))}


@contextmanager
def pliki_przegladarki(stan: dict | None):
    """Na czas bloku zasady i styl czytamy i zmieniamy w `stan`, nie na serwerze."""
    if stan is None:
        yield None
        return
    znacznik = magazyn.pliki_przegladarki_var.set(stan)
    try:
        yield stan
    finally:
        magazyn.pliki_przegladarki_var.reset(znacznik)


def _z_plikami(pliki, praca, zapis: bool = True):
    """Wykonanie pracy z plikami kancelarii tam, gdzie kancelaria je trzyma.

    Chmura: zwykly odczyt i zapis w magazynie. "U siebie": na plikach
    przyslanych przez przegladarke; odpowiedz niesie ich nowa wersje
    (`pliki_kancelarii`), ktora przegladarka zapisuje w folderze kancelarii.
    """
    stan = stan_z_przegladarki(pliki)
    if stan is None and zapis and magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie. Wskaż folder na sprawy - "
                                 "tam zapiszę zasady i styl kancelarii.")
    with pliki_przegladarki(stan):
        wynik = _wykonaj(praca)
    if stan is not None and isinstance(wynik, dict):
        wynik = {**wynik, "pliki_kancelarii": stan}
    return wynik


def _wykonaj(funkcja, *argumenty, **nazwane):
    try:
        return funkcja(*argumenty, **nazwane)
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))
    except KeyError:
        raise HTTPException(404, "Nie ma takiej pozycji - odśwież stronę.")
    except ValueError as blad:
        raise HTTPException(400, str(blad))
    except RuntimeError as blad:
        raise HTTPException(409, str(blad))


def _moge_zmieniac_zasady(request: Request) -> bool:
    """Nieprzekraczalne zasady zmienia notariusz (wlasciciel kancelarii).
    Bez logowania osoby (tryb lokalny, token kancelarii) - kazdy."""
    if not getattr(request.state, "email", ""):
        return True
    try:
        _, _, wpis, email = autoryzacja._moja_kancelaria(request)
    except HTTPException:
        return True
    return email in autoryzacja._wlasciciele(wpis)


def _wymagaj_notariusza(request: Request) -> None:
    if not _moge_zmieniac_zasady(request):
        raise HTTPException(403, "Nieprzekraczalne zasady zmienia notariusz - właściciel kancelarii. "
                                 "Możesz je przeglądać i sprawdzać nimi tekst.")


def _stan(request: Request) -> dict:
    ustawienia = zasady.wczytaj()
    profil = styl.wczytaj()
    lista = ustawienia.get("zasady", [])
    wylaczone = set(ustawienia.get("wbudowane_wylaczone", []))
    return {
        "zasady": lista,
        "wbudowane": [{"kod": k, "opis": v, "wlaczona": k not in wylaczone} for k, v in
                      klauzule.KONSTRUKCJA.items()],
        "liczby": {
            "zasad": len(lista),
            "wlaczonych": sum(1 for z in lista if z.get("wlaczona", True)),
            "automatycznie": sum(1 for z in lista if z.get("wlaczona", True) and z["sprawdzanie"] != "ai"),
            "naprawianych": sum(1 for z in lista if z.get("wlaczona", True) and z.get("naprawa")),
        },
        "styl": styl.podsumowanie(profil),
        "sugestie": styl.sugestie(profil, ustawienia),
        "kategorie": kategorie.slownik_dla_ui(),
        "przyklady": zasady.PRZYKLADY,
        "moge_zmieniac": _moge_zmieniac_zasady(request),
        "u_klienta": magazyn.u_klienta(),
    }


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
class ZPlikami(BaseModel):
    """Kancelaria "u siebie" dolacza do kazdego zadania swoje zasady i styl."""
    pliki_kancelarii: dict | None = None


class TekstZasady(ZPlikami):
    tekst: str


class NowaZasada(ZPlikami):
    tekst: str
    poziom: str | None = None
    zakres: dict | None = None


class ZmianaZasady(ZPlikami):
    tekst: str | None = None
    wlaczona: bool | None = None
    poziom: str | None = None
    zakres: dict | None = None


class Wbudowana(ZPlikami):
    wlaczona: bool


class Fragment(ZPlikami):
    tekst: str


class ZmianaSformulowania(ZPlikami):
    przypiete: bool | None = None
    ukryte: bool | None = None
    czesc: str | None = None
    szkielet: str | None = None


class TekstDoSprawdzenia(ZPlikami):
    tekst: str


def _pliki(dane: ZPlikami | None):
    return dane.pliki_kancelarii if dane is not None else None


@router.get("")
def stan(request: Request):
    return _z_plikami(None, lambda: _stan(request), zapis=False)


@router.post("/stan")
def stan_z_plikami(request: Request, dane: ZPlikami = Body(default=None)):
    """To samo co GET, ale z plikami kancelarii "u siebie" w tresci zadania."""
    return _z_plikami(_pliki(dane), lambda: _stan(request), zapis=False)


@router.post("/zasady/interpretuj")
def interpretuj(dane: TekstZasady):
    """Podglad "Tak to rozumiem" w trakcie pisania - niczego nie zapisuje."""
    return _wykonaj(zasady.interpretuj, dane.tekst)


@router.post("/zasady", status_code=201)
def dodaj_zasade(request: Request, dane: NowaZasada):
    _wymagaj_notariusza(request)
    nadpisania = {k: v for k, v in (("poziom", dane.poziom), ("zakres", dane.zakres)) if v is not None}
    return _z_plikami(dane.pliki_kancelarii, lambda: zasady.dodaj(dane.tekst, nadpisania))


@router.put("/zasady/{identyfikator}")
def zmien_zasade(request: Request, identyfikator: str, dane: ZmianaZasady):
    _wymagaj_notariusza(request)
    zmiany = {k: v for k, v in dane.model_dump(exclude={"pliki_kancelarii"}).items() if v is not None}
    return _z_plikami(dane.pliki_kancelarii, lambda: zasady.zmien(identyfikator, zmiany))


@router.delete("/zasady/{identyfikator}")
def usun_zasade(request: Request, identyfikator: str, dane: ZPlikami = Body(default=None)):
    _wymagaj_notariusza(request)

    def praca():
        zasady.usun(identyfikator)
        return {"usunieto": identyfikator}
    return _z_plikami(_pliki(dane), praca)


@router.put("/wbudowane/{kod}")
def ustaw_wbudowana(request: Request, kod: str, dane: Wbudowana):
    _wymagaj_notariusza(request)

    def praca():
        zasady.ustaw_wbudowana(kod, dane.wlaczona)
        return {"kod": kod, "wlaczona": dane.wlaczona}
    return _z_plikami(dane.pliki_kancelarii, praca)


@router.post("/sprawdz")
def sprawdz_tekst(dane: TekstDoSprawdzenia):
    """Sprawdzenie dowolnego tekstu zasadami kancelarii (bez modelu, bez zapisu)."""
    if not dane.tekst.strip():
        raise HTTPException(400, "Wklej tekst do sprawdzenia.")
    if len(dane.tekst) > 400_000:
        raise HTTPException(413, "Tekst jest za długi.")

    def praca() -> dict:
        ustawienia = zasady.wczytaj()
        poprawiony, poprawki = zasady.napraw(dane.tekst, ustawienia)
        raport = zasady.sprawdz(dane.tekst, ustawienia)
        raport["do_sprawdzenia_ai"] = len(raport["do_sprawdzenia_ai"])
        raport["poprawiony"] = poprawiony if poprawki else None
        raport["poprawki"] = poprawki
        return raport

    wynik = _z_plikami(dane.pliki_kancelarii, praca, zapis=False)
    wynik.pop("pliki_kancelarii", None)     # niczego nie zmienilismy
    return wynik


@router.post("/akty")
def naucz_z_aktow(pliki: list[UploadFile] = File(...), pliki_kancelarii: str = Form("")):
    """Nauka stylu z wczesniejszych aktow. Pliki czytamy w pamieci tymczasowej
    i od razu usuwamy - zapisujemy tylko szkielety klauzul bez danych osobowych
    (w chmurze albo, u kancelarii "u siebie", w jej folderze)."""
    stan_plikow = stan_z_przegladarki(pliki_kancelarii)
    if stan_plikow is None and magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie. Wskaż folder na sprawy - "
                                 "tam zapiszę styl kancelarii.")
    if len(pliki) > MAX_AKTOW:
        raise HTTPException(400, f"Naraz najwyżej {MAX_AKTOW} aktów.")
    katalog = Path(tempfile.mkdtemp(prefix="notarai-styl-"))
    analizy, pominiete = [], []
    try:
        for numer, plik in enumerate(pliki, start=1):
            rozszerzenie = Path(plik.filename or "").suffix.lower()
            sciezka = katalog / f"akt{numer}{rozszerzenie}"
            dane = plik.file.read(MAX_ROZMIAR + 1)
            if len(dane) > MAX_ROZMIAR:
                pominiete.append({"plik": numer, "powod": "Plik większy niż 15 MB."})
                continue
            sciezka.write_bytes(dane)
            try:
                tekst = styl.tekst_z_pliku(sciezka)
            except styl.NieobslugiwanyPlik as blad:
                pominiete.append({"plik": numer, "nazwa": plik.filename, "powod": str(blad)})
                continue
            except Exception as blad:  # noqa: BLE001
                log.warning("styl: nie odczytano pliku nr %d (%s)", numer, type(blad).__name__)
                pominiete.append({"plik": numer, "nazwa": plik.filename, "powod": "Nie udało się odczytać pliku."})
                continue
            analiza = styl.analizuj(tekst)
            if not analiza["klauzule"]:
                pominiete.append({"plik": numer, "nazwa": plik.filename,
                                  "powod": "Nie znalazłem w pliku klauzul aktu."})
                continue
            analiza["nazwa"] = plik.filename
            analizy.append(analiza)
    finally:
        shutil.rmtree(katalog, ignore_errors=True)
    if not analizy:
        return {"dodane": [], "pominiete": pominiete, "aktow": None}
    with pliki_przegladarki(stan_plikow):
        wynik = _wykonaj(styl.naucz, analizy)
    log.info("styl: dodano aktow=%d pominieto=%d sformulowan=%d", len(wynik["dodane"]),
             len(pominiete), wynik["sformulowan"])
    # nazwa pliku wraca tylko do przegladarki, ktora ja wyslala - nie zapisujemy jej
    odpowiedz = {**wynik, "pominiete": pominiete,
                 "dodane": [{**d, "nazwa": a["nazwa"], "czesci": [kategorie.nazwa_czesci(c) for c in a["czesci"]]}
                            for d, a in zip(wynik["dodane"], analizy)]}
    if stan_plikow is not None:
        odpowiedz["pliki_kancelarii"] = stan_plikow
    return odpowiedz


@router.delete("/styl")
def zapomnij_styl(request: Request, dane: ZPlikami = Body(default=None)):
    _wymagaj_notariusza(request)

    def praca():
        styl.zapomnij()
        return {"zapomniano": True}
    return _z_plikami(_pliki(dane), praca)


@router.post("/sformulowania", status_code=201)
def zapamietaj_sformulowanie(dane: Fragment):
    """Zaznaczony w projekcie fragment -> wzorcowe sformulowanie kancelarii."""
    return _z_plikami(dane.pliki_kancelarii, lambda: styl.zapamietaj_sformulowanie(dane.tekst))


@router.put("/sformulowania/{identyfikator}")
def zmien_sformulowanie(identyfikator: str, dane: ZmianaSformulowania):
    zmiany = {k: v for k, v in dane.model_dump(exclude={"pliki_kancelarii"}).items() if v is not None}
    return _z_plikami(dane.pliki_kancelarii, lambda: styl.zmien_sformulowanie(identyfikator, zmiany))


@router.delete("/sformulowania/{identyfikator}")
def usun_sformulowanie(identyfikator: str, dane: ZPlikami = Body(default=None)):
    def praca():
        styl.usun_sformulowanie(identyfikator)
        return {"usunieto": identyfikator}
    return _z_plikami(_pliki(dane), praca)


@router.post("/sugestie/{klucz:path}/przyjmij", status_code=201)
def przyjmij_sugestie(request: Request, klucz: str, dane: ZPlikami = Body(default=None)):
    _wymagaj_notariusza(request)

    def praca():
        for s in styl.sugestie(styl.wczytaj(), zasady.wczytaj()):
            if s["klucz"] == klucz:
                return zasady.dodaj(s["tekst"], None, "z_aktow")
        raise KeyError(klucz)
    return _z_plikami(_pliki(dane), praca)


@router.post("/sugestie/{klucz:path}/odrzuc")
def odrzuc_sugestie(klucz: str, dane: ZPlikami = Body(default=None)):
    def praca():
        styl.odrzuc_sugestie(klucz)
        return {"odrzucono": klucz}
    return _z_plikami(_pliki(dane), praca)
