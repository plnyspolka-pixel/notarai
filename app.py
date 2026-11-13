"""pieczapp - lokalny asystent kancelarii notarialnej.

Uruchomienie:  python app.py
Adres:         http://127.0.0.1:8000
"""
import asyncio
import base64
import contextvars
import json
import logging
import os
import queue
import re
import shutil
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import aml
import aml_listy
import bedrock
import config
import crbr
import dziennik
import dokumenty
import dokumenty_prawne
import ekw
import giif
import ksiegi_notarialne
import formularze
import kalendarz
import kalkulator
import krz
import urzadzenia
import zlecenia
import magazyn
import notariusze
import autoryzacja
import nazwy
import osoby
import poczta_polska
import personalizacja
import przesylki
import sledzenie
import poswiadczenia
import prompty
import rejestracja
import rejestry
import rezerwacje_hurtowe
import tokenomia
import rezerwacje_klientow
import teczka
import leady
import meta_leady
import wizyty
import transkrypcja
import walidacja
import dowody_ethereum
import sealed_vault

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
dziennik.wlacz_maskowanie()
log = logging.getLogger("pieczapp")

app = FastAPI(title="pieczapp", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

# Tryb SaaS: token logowania na /api/* + panel admina. W trybie lokalnym
# middleware przepuszcza wszystko, a panel admina wymaga PIECZAPP_ADMIN_TOKEN.
app.middleware("http")(autoryzacja.middleware)
app.include_router(autoryzacja.router)
app.include_router(autoryzacja.router_logowania)
app.include_router(autoryzacja.router_zespolu)
app.include_router(autoryzacja.router_serwisu)
app.include_router(autoryzacja.router_abonamentu)
app.include_router(autoryzacja.router_stripe)
app.include_router(rejestracja.router)
app.include_router(rejestracja.router_dokumentow)
app.include_router(rezerwacje_hurtowe.router_biuro)
app.include_router(rezerwacje_hurtowe.router_partner)
app.include_router(rezerwacje_hurtowe.router_admin)
app.include_router(rezerwacje_hurtowe.router_mcp)
# Narzędzia klientów — publiczny kalkulator i składanie zgłoszeń,
# autoryzacja kancelarii obowiązuje wyłącznie na trasach prywatnych.
app.include_router(kalkulator.router)
app.include_router(przesylki.router)
app.include_router(personalizacja.router)
app.include_router(poczta_polska.router)
app.include_router(sledzenie.router)
app.include_router(wizyty.router)
app.include_router(rezerwacje_klientow.router)
app.include_router(teczka.router)
app.include_router(leady.router)
app.include_router(leady.router_kancelarii)
app.include_router(leady.router_admina)
app.include_router(meta_leady.router)
app.include_router(rezerwacje_klientow.router_admina)
rezerwacje_klientow.uruchom_przypomnienia()
app.include_router(wizyty.router_zapytan)
app.include_router(wizyty.router_admina)
app.include_router(notariusze.router)
app.include_router(notariusze.router_kancelarii)
app.include_router(notariusze.router_admina)
# Poswiadczenie kopii -> opis do repertorium A (trasa prywatna kancelarii).
app.include_router(poswiadczenia.router)
app.include_router(dowody_ethereum.router)
app.include_router(sealed_vault.router)
app.include_router(tokenomia.router)
app.include_router(tokenomia.router_admina)
app.middleware("http")(kalkulator.cors)


@app.exception_handler(Exception)
async def _nieobsluzony(request: Request, blad: Exception):
    """Blad, ktorego nie zlapal endpoint: do dziennika, bez tresci wyjatku."""
    log.error("%s %s: nieobsluzony blad (%s)", request.method, request.url.path,
              dziennik.opis_bledu(blad))
    return JSONResponse({"detail": "Blad serwera."}, status_code=500)


@app.get("/zdrowie")
def zdrowie(request: Request):
    """Sonda dla App Runner/ECS. Zadnych danych, sam status.

    Sciezka jest otwarta (sonda nie ma tokenu), wiec publicznie zwraca tylko
    "ok". Konfiguracja - tryb magazynu, model, region - to informacje o
    wnetrzu uslugi i widzi je wylacznie administrator.
    """
    if not autoryzacja.czy_admin(request):
        return {"status": "ok"}
    return {
        "status": "ok",
        "magazyn": magazyn.TRYB,
        "multi": autoryzacja.MULTI,
        "model": config.MODEL,
        "region": config.REGION,
    }


@app.get("/admin", response_class=HTMLResponse)
def panel_admina():
    """Zakladanie kancelarii bez curl. Strona jest jawna; dane za nia chroni
    token administratora, ktory przegladarka wysyla z kazdym zadaniem."""
    autoryzacja.zaloz_stalych_adminow()
    return (Path(__file__).parent / "static" / "admin.html").read_text("utf-8")


@app.get("/hurtowe", response_class=HTMLResponse)
def portal_hurtowy():
    """Portal rezerwacyjny partnerow B2B, bez danych przed podaniem klucza."""
    return (Path(__file__).parent / "static" / "hurtowe.html").read_text("utf-8")


@app.get("/rejestracja", response_class=HTMLResponse)
def strona_rejestracji():
    """Notariusz zaklada konto kancelarii sam, bez nas i bez papieru."""
    return (Path(__file__).parent / "static" / "rejestracja.html").read_text("utf-8")


@app.get("/dokumenty/{nazwa}", response_class=HTMLResponse)
def dokument_publiczny(nazwa: str):
    """Dokumenty do przeczytania przed rejestracja - w tej samej wersji,
    ktora formularz zapisuje jako zaakceptowana."""
    if nazwa not in ("regulamin", "umowa", "prywatnosc", "instrukcja"):
        raise HTTPException(404, "Nie ma takiego dokumentu.")
    return dokumenty_prawne.strona(nazwa)



@app.get("/notariusze", response_class=HTMLResponse)
def strona_mapy_kancelarii():
    """Publiczna mapa kancelarii, ktore wlaczyly publikacje adresu."""
    return (Path(__file__).parent / "static" / "notariusze.html").read_text("utf-8")


@app.get("/poswiadczenia", response_class=HTMLResponse)
def strona_poswiadczen():
    """Zdjecie albo skan dokumentu -> opis do repertorium A. Strona jest
    jawna (jak /admin); odczyt za nia wymaga tokenu logowania kancelarii."""
    return (Path(__file__).parent / "static" / "poswiadczenia.html").read_text("utf-8")


@app.get("/kalkulator", response_class=HTMLResponse)
def strona_kalkulatora():
    """Kalkulator taksy bez koniecznosci logowania."""
    strona = (Path(__file__).parent / "strona" / "kalkulator" / "index.html").read_text("utf-8")
    return strona.replace('"../logo-mark.svg"', '"/static/notarai-symbol.svg"')


@app.get("/", response_class=HTMLResponse)
def strona_glowna():
    """Strona z informacja o tym, gdzie naprawde leza dane.

    Ta sama aplikacja dziala na stanowisku notariusza i w chmurze, a rozni je
    miejsce przechowywania skanow i projektow. Zapewnienie w stopce musi
    odpowiadac rzeczywistosci, wiec wstawiamy je przy wydaniu strony.
    """
    strona = (Path(__file__).parent / "static" / "index.html").read_text("utf-8")
    if magazyn.TRYB == "s3":
        gdzie = (
            f"Model przez Bedrock w regionie {config.REGION}. Skany i projekty "
            f"zapisujemy zaszyfrowane w chmurze AWS w tym samym regionie, "
            f"nie na tym komputerze."
        )
    else:
        gdzie = (
            f"Model przez Bedrock w regionie {config.REGION}. Skany i projekty "
            f"zostaja na tym komputerze."
        )
    return strona.replace("Sprawdzam, gdzie zapisywane są dane…", gdzie)


# Przelacznik "Dokladnosc odczytu"; nieznana wartosc = ustawienie domyslne.
WYSILKI = {"max", "high", "medium"}


def _przetworz(sciezka_wzoru: Path, sciezki_skanow: list[Path], polecenie: str,
               etykieta: str, postep=None, wysilek: str = "") -> dict:
    """Wspolna czesc: analiza wzoru, odczyt skanow, pierwsza tura rozmowy.

    Nie zapisuje niczego trwale - zapis (albo jego brak) nalezy do funkcji
    wywolujacej. `etykieta` trafia tylko do logow, nigdy dane osobowe.
    `postep(etap, gotowe, wszystkie)` dostaje kolejne kroki odczytu.
    """
    tekst_wzoru = dokumenty.wzor_na_tekst(sciezka_wzoru)
    analiza = dokumenty.analizuj_wzor(tekst_wzoru)
    pola_wzoru = analiza["pola"]
    strony = dokumenty.opisz_strony(sciezki_skanow)
    wysilek = wysilek if wysilek in WYSILKI else config.WYSILEK

    log.info("%s: wzor=%s pol=%d legenda=%d warianty=%d stron=%d wysilek=%s",
             etykieta, sciezka_wzoru.name, len(pola_wzoru),
             len(analiza["legenda"]), analiza["warianty"], len(strony), wysilek)

    # Tokenomia: strony (cena zalezna od dokladnosci) + zestawienie z pytaniami.
    # Saldo sprawdzamy przed pierwszym wywolaniem, pobieramy po udanym odczycie.
    platna = tokenomia.akcja(tokenomia.akcja_odczytu(wysilek), len(strony), etykieta)
    platna.dodaj("zalozenie_sprawy", 1)
    with platna:
        odczyt, transkrypcje, pytania = _odczytaj_i_zapytaj(
            strony, pola_wzoru, polecenie, analiza, postep, wysilek, etykieta)
    pola = _zwaliduj(odczyt.get("pola", []))
    kontekst = prompty.kontekst_rozmowy(
        pola, odczyt.get("braki", []), odczyt.get("rozbieznosci", []), polecenie
    )
    if pytania is None:
        pytania = ("Nie udalo sie przygotowac pytan. Mozesz pisac do mnie ponizej "
                   "albo od razu sporzadzic projekt.")

    return {
        "analiza": analiza,
        "pola_wzoru": pola_wzoru,
        "pola": pola,
        "braki": odczyt.get("braki", []),
        "rozbieznosci": odczyt.get("rozbieznosci", []),
        "stron": len(strony),
        "wysilek": wysilek,
        "transkrypcje": transkrypcje,
        "kontekst": kontekst,
        "rozmowa": [{"rola": "asystent", "tresc": pytania,
                     "czas": datetime.now().isoformat(timespec="seconds")}],
    }


def _odczytaj_i_zapytaj(strony, pola_wzoru, polecenie, analiza, postep, wysilek, etykieta):
    """Odczyt sprawy i pytania wstepne (None, gdy pytan nie udalo sie przygotowac)."""
    try:
        odczyt, transkrypcje = bedrock.odczytaj_sprawe(
            strony, pola_wzoru, polecenie, analiza["legenda"], postep, wysilek)
    except bedrock.Przeciazenie as blad:
        log.error("%s: odczyt przerwany, limit zapytan Bedrock", etykieta)
        raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("%s: blad odczytu (%s)", etykieta, dziennik.opis_bledu(blad))
        raise HTTPException(502, f"Bedrock: {blad}")

    pola = _zwaliduj(odczyt.get("pola", []))
    kontekst = prompty.kontekst_rozmowy(
        pola, odczyt.get("braki", []), odczyt.get("rozbieznosci", []), polecenie
    )
    try:
        pytania = bedrock.rozmawiaj(kontekst, [], None)
    except Exception as blad:
        log.error("%s: blad pytan wstepnych (%s)", etykieta, dziennik.opis_bledu(blad))
        pytania = None
    return odczyt, transkrypcje, pytania


def _chce_strumienia(request: Request) -> bool:
    return "application/x-ndjson" in request.headers.get("accept", "")


async def _wykonaj(request: Request, praca, nazwa: str = "odczyt") -> Response:
    """Uruchamia dluga prace (odczyt, projekt) poza petla zdarzen.

    Przegladarka, ktora prosi o application/x-ndjson, dostaje strumien linii
    JSON: postep ({"postep": ...}), co kilkanascie sekund znak zycia, na koncu
    {"wynik": ...} albo {"blad": ..., "kod": ...}. Bez tego ALB (idle 900 s)
    zerwalby polaczenie przy duzej sprawie, ktora czyta sie dluzej niz kwadrans
    - 24.10.2026 tak urwal sie projekt aktu pisany 21 minut.
    Bez naglowka - zwykla odpowiedz JSON jak dawniej.

    Kontekst kancelarii (contextvars) przechodzi do watku razem z praca.
    """
    if not _chce_strumienia(request):
        return JSONResponse(await asyncio.to_thread(contextvars.copy_context().run, praca, None))

    kolejka: queue.Queue = queue.Queue()
    kontekst = contextvars.copy_context()

    def postep(etap: str, gotowe: int, wszystkie: int) -> None:
        kolejka.put({"postep": {"etap": etap, "gotowe": gotowe, "wszystkie": wszystkie}})

    def watek():
        try:
            kolejka.put({"wynik": praca(postep)})
        except HTTPException as blad:
            kolejka.put({"blad": blad.detail, "kod": blad.status_code})
        except Exception as blad:  # noqa: BLE001 - tresc bledu nie trafia do logu
            log.error("%s w tle: %s", nazwa, dziennik.opis_bledu(blad))
            kolejka.put({"blad": f"Blad serwera ({nazwa}).", "kod": 500})
        finally:
            kolejka.put(None)

    threading.Thread(target=kontekst.run, args=(watek,), daemon=True).start()

    async def linie():
        while True:
            try:
                wpis = await asyncio.to_thread(kolejka.get, True, 15)
            except queue.Empty:
                yield b'{"zyje":1}\n'
                continue
            if wpis is None:
                return
            yield (json.dumps(wpis, ensure_ascii=False) + "\n").encode("utf-8")

    return StreamingResponse(linie(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/sprawy")
async def nowa_sprawa(
    request: Request,
    skany: list[UploadFile] = File(...),
    wzor: UploadFile | None = File(None),
    # Kancelaria zwykle pracuje na kilku tych samych wzorach. Zamiast wgrywac
    # plik przy kazdej sprawie, mozna wskazac sprawe, z ktorej go wziac.
    wzor_ze_sprawy: str = Form(""),
    polecenie: str = Form(""),
    sygnatura: str = Form(""),
    wysilek: str = Form(""),
):
    """Wgranie wzoru i skanow, odczyt danych. Sprawa zostaje w magazynie."""
    if magazyn.u_klienta():
        raise HTTPException(409, (
            "Ta kancelaria trzyma pliki u siebie. Uzyj /api/odczyt, ktore niczego "
            "nie zapisuje."
        ))
    wzor_zrodlowy = None
    if wzor is None:
        if not wzor_ze_sprawy:
            raise HTTPException(400, "Dodaj wzor aktu.")
        wzor_zrodlowy = next(_katalog_sprawy(wzor_ze_sprawy).glob("wzor.*"), None)
        if wzor_zrodlowy is None:
            raise HTTPException(404, "W tamtej sprawie nie ma wzoru.")

    identyfikator = uuid.uuid4().hex[:12]
    katalog = config.SPRAWY / identyfikator
    (katalog / "skany").mkdir(parents=True)

    if wzor_zrodlowy is not None:
        sciezka_wzoru = katalog / wzor_zrodlowy.name
        shutil.copyfile(wzor_zrodlowy, sciezka_wzoru)
    else:
        sciezka_wzoru = katalog / f"wzor{Path(wzor.filename).suffix.lower()}"
        _zapisz(wzor, sciezka_wzoru)

    sciezki_skanow = []
    for skan in skany:
        cel = katalog / "skany" / Path(skan.filename).name
        _zapisz(skan, cel)
        sciezki_skanow.append(cel)

    def praca(postep) -> dict:
        try:
            wynik = _przetworz(sciezka_wzoru, sciezki_skanow, polecenie,
                               f"sprawa {identyfikator}", postep, wysilek)
        except ValueError as blad:
            log.warning("sprawa %s: odrzucona (%s)", identyfikator, dziennik.opis_bledu(blad))
            shutil.rmtree(katalog, ignore_errors=True)
            raise HTTPException(400, str(blad))
        except BaseException:
            shutil.rmtree(katalog, ignore_errors=True)
            raise
        return _zapisz_nowa_sprawe(katalog, identyfikator, sciezka_wzoru, sciezki_skanow,
                                   polecenie, sygnatura, wynik)

    return await _wykonaj(request, praca)


def _zapisz_nowa_sprawe(katalog: Path, identyfikator: str, sciezka_wzoru: Path,
                        sciezki_skanow: list[Path], polecenie: str, sygnatura: str,
                        wynik: dict) -> dict:
    analiza, pola = wynik["analiza"], wynik["pola"]
    rozmowa = wynik["rozmowa"]
    _zapisz_rozmowe(katalog, rozmowa)
    (katalog / "kontekst.txt").write_text(wynik["kontekst"], encoding="utf-8")

    _zapisz_json(katalog / "sprawa.json", {
        "id": identyfikator,
        "nazwa": nazwy.nazwa_sprawy(pola, [p.name for p in sciezki_skanow]),
        "sygnatura": sygnatura,
        "utworzono": datetime.now().isoformat(timespec="seconds"),
        "polecenie": polecenie,
        "wzor": sciezka_wzoru.name,
        "skany": [p.name for p in sciezki_skanow],
        "stron": wynik["stron"],
        "wysilek": wynik["wysilek"],
        "pola_wzoru": wynik["pola_wzoru"],
        "legenda": analiza["legenda"],
        "warianty": analiza["warianty"],
    })
    # Transkrypcje zostaja przy sprawie: do wgladu, gdy odczyt budzi watpliwosci.
    _zapisz_json(katalog / "transkrypcje.json", wynik["transkrypcje"])
    _zapisz_json(katalog / "odczyt.json", {
        "pola": pola,
        "braki": wynik["braki"],
        "rozbieznosci": wynik["rozbieznosci"],
    })
    magazyn.utrwal_sprawe(katalog)

    return {
        "id": identyfikator,
        "nazwa": nazwy.nazwa_sprawy(pola, [p.name for p in sciezki_skanow]),
        "sygnatura": sygnatura,
        "pola": pola,
        "braki": wynik["braki"],
        "rozbieznosci": wynik["rozbieznosci"],
        "stron": wynik["stron"],
        "warianty": analiza["warianty"],
        "rozmowa": rozmowa,
    }


@app.get("/api/ustawienia")
def ustawienia_kancelarii():
    """Co przegladarka musi wiedziec o tej kancelarii, zeby wybrac tryb pracy."""
    return {
        "przechowywanie": magazyn.przechowywanie_var.get(),
        "kancelaria": magazyn.kancelaria(),
        # Czy ta instalacja moze sama wpisywac do rejestrow. W chmurze nie -
        # tam robi to pomocnik na komputerze notariusza.
        "sterowanie_przegladarka": formularze.silnik.czy_mozna_sterowac(),
        # Czy pomocnik tej kancelarii jest teraz pod reka. Bez niego przycisk
        # sprawdzenia w rejestrze ma byc nieczynny, zamiast skladac zlecenia,
        # ktorych nikt nie odbierze.
        "pomocnik_polaczony": _pomocnik_pod_reka(),
        # Mikrofon pokazujemy tylko tam, gdzie nagranie da sie przepisac.
        # W kontenerze nie ma modelu mowy, wiec przycisk konczylby sie bledem.
        "transkrypcja": transkrypcja.dostepna(),
        # Pobranie tresci ksiegi wieczystej z EKW (ekw.py). Bez tokenu dostawcy
        # przycisk nie ma sensu, wiec interfejs go nie pokazuje.
        "ekw": ekw.dostepne(),
        # Saldo kredytow, gdy kancelaria placi za akcje (tokenomia); inaczej None.
        "kredyty": tokenomia.saldo_kancelarii(),
    }


# --- praca bez zapisu: pliki zostaja u kancelarii --------------------------
# Te punkty nie tworza sprawy i nic nie zapisuja. Pliki przychodza z dysku
# notariusza przy kazdym zadaniu, a wyniki wracaja do przegladarki, ktora
# zapisuje je z powrotem u niego. Serwer pracuje w katalogu tymczasowym,
# kasowanym zawsze, takze po bledzie.


@app.post("/api/odczyt")
async def odczyt_bez_zapisu(
    request: Request,
    wzor: UploadFile = File(...),
    skany: list[UploadFile] = File(...),
    polecenie: str = Form(""),
    wysilek: str = Form(""),
):
    """Odczyt skanow bez tworzenia sprawy. Nic nie zostaje na serwerze.

    Katalog tymczasowy zyje tyle, co sam odczyt (takze odczyt w tle przy
    odpowiedzi strumieniowej) i jest kasowany zawsze, takze po bledzie.
    """
    katalog = Path(tempfile.mkdtemp(prefix="notarai-"))
    try:
        (katalog / "skany").mkdir()
        sciezka_wzoru = katalog / f"wzor{Path(wzor.filename).suffix.lower()}"
        _zapisz(wzor, sciezka_wzoru)
        sciezki_skanow = []
        for skan in skany:
            cel = katalog / "skany" / Path(skan.filename).name
            _zapisz(skan, cel)
            sciezki_skanow.append(cel)
    except BaseException:
        shutil.rmtree(katalog, ignore_errors=True)
        raise

    def praca(postep) -> dict:
        try:
            try:
                wynik = _przetworz(sciezka_wzoru, sciezki_skanow, polecenie,
                                   "odczyt bez zapisu", postep, wysilek)
            except ValueError as blad:
                log.warning("odczyt bez zapisu: odrzucony (%s)", dziennik.opis_bledu(blad))
                raise HTTPException(400, str(blad))
        finally:
            shutil.rmtree(katalog, ignore_errors=True)

        analiza = wynik["analiza"]
        return {
            "nazwa": nazwy.nazwa_sprawy(wynik["pola"], [p.name for p in sciezki_skanow]),
            "pola": wynik["pola"],
            "braki": wynik["braki"],
            "rozbieznosci": wynik["rozbieznosci"],
            "stron": wynik["stron"],
            "warianty": analiza["warianty"],
            "legenda": analiza["legenda"],
            "pola_wzoru": wynik["pola_wzoru"],
            "kontekst": wynik["kontekst"],
            "rozmowa": wynik["rozmowa"],
        }

    return await _wykonaj(request, praca)


@app.post("/api/projekt")
async def projekt_bez_zapisu(
    request: Request,
    wzor: UploadFile = File(...),
    pola: str = Form("[]"),
    polecenie: str = Form(""),
    rozmowa: str = Form("[]"),
):
    """Projekt dokumentu bez tworzenia sprawy. Zwraca plik do zapisania u siebie."""
    try:
        lista_pol = json.loads(pola)
        historia = json.loads(rozmowa)
    except json.JSONDecodeError:
        raise HTTPException(400, "Nieprawidlowy format pol albo rozmowy")

    # Wzor zapisujemy od razu: przy odpowiedzi strumieniem przesylany plik
    # zostalby zamkniety, zanim praca w tle zdazy go przeczytac.
    katalog = Path(tempfile.mkdtemp(prefix="notarai-"))
    try:
        sciezka_wzoru = katalog / f"wzor{Path(wzor.filename).suffix.lower()}"
        _zapisz(wzor, sciezka_wzoru)
    except BaseException:
        shutil.rmtree(katalog, ignore_errors=True)
        raise

    def praca(postep) -> dict:
        try:
            analiza = dokumenty.analizuj_wzor(dokumenty.wzor_na_tekst(sciezka_wzoru))
            projekt, zgodnosc = _sporzadz(analiza, lista_pol, polecenie, historia, "projekt bez zapisu")
            cel = katalog / "projekt.docx"
            dokumenty.tekst_na_docx(projekt, cel)
            dane = cel.read_bytes()
        finally:
            shutil.rmtree(katalog, ignore_errors=True)

        log.info("projekt bez zapisu: znakow=%d", len(projekt))
        # Tekst do podgladu w przegladarce, plik do zapisania na dysku notariusza.
        return {
            "tekst": projekt,
            "brakujace": projekt.count("<<BRAK:"),
            "do_wyboru": projekt.count("<<WYBOR:"),
            "docx": base64.b64encode(dane).decode("ascii"),
            "zgodnosc": zgodnosc,
        }

    return await _wykonaj(request, praca, "projekt")


def _sporzadz(analiza: dict, pola: list[dict], polecenie: str, rozmowa: list[dict],
              etykieta: str) -> tuple[str, dict]:
    """Projekt z modelu po kontroli zasad kancelarii: (tekst, raport zgodnosci).
    Tokenomia: projekt w cenie do 40 tys. znakow wzoru, dalej doplata."""
    platna = tokenomia.akcja("projekt", 1, etykieta)
    platna.dodaj("projekt_dodatek", tokenomia.jednostki_projektu(len(analiza["tresc"])))
    with platna:
        return _sporzadz_bez_oplaty(analiza, pola, polecenie, rozmowa, etykieta)


def _sporzadz_bez_oplaty(analiza: dict, pola: list[dict], polecenie: str, rozmowa: list[dict],
                         etykieta: str) -> tuple[str, dict]:
    """Zasady i styl kancelarii ida do modelu razem ze wzorem, a gotowy projekt
    przechodzi przez personalizacja.skontroluj() ZANIM trafi do notariusza.
    Bledy modelu zamieniamy na odpowiedzi HTTP.
    """
    rodzaje = personalizacja.rodzaje_sprawy(analiza["tresc"], polecenie)
    ustawienia, blok = personalizacja.przygotuj(rodzaje)
    try:
        projekt = bedrock.sporzadz_projekt(
            analiza["tresc"], pola, polecenie, analiza["legenda"], rozmowa, personalizacja=blok
        )
    except bedrock.Przeciazenie as blad:
        log.error("%s: projekt przerwany, limit zapytan Bedrock", etykieta)
        raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("%s: blad generowania (%s)", etykieta, dziennik.opis_bledu(blad))
        raise HTTPException(502, f"Bedrock: {blad}")
    return personalizacja.skontroluj(projekt, ustawienia, rodzaje)


class ZadanieRozmowy(BaseModel):
    kontekst: str
    historia: list[dict] = []
    tresc: str


@app.post("/api/rozmowa")
def rozmowa_bez_zapisu(zadanie: ZadanieRozmowy):
    """Kolejna tura rozmowy bez sprawy na serwerze. Historie trzyma przegladarka."""
    tresc = zadanie.tresc.strip()
    if not tresc:
        raise HTTPException(400, "Pusta wiadomosc")
    try:
        with tokenomia.akcja("rozmowa_tura", _tury_rozmowy(zadanie.kontekst, zadanie.historia, tresc),
                             "rozmowa bez zapisu"):
            odpowiedz = bedrock.rozmawiaj(zadanie.kontekst, zadanie.historia, tresc)
    except HTTPException:
        raise
    except bedrock.Przeciazenie as blad:
        raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("rozmowa bez zapisu: blad (%s)", dziennik.opis_bledu(blad))
        raise HTTPException(502, f"Bedrock: {type(blad).__name__}")
    return {"odpowiedz": odpowiedz}


def _tury_rozmowy(kontekst: str, historia: list[dict], tresc: str) -> int:
    """Ile tur rozmowy policzyc: kontekst sprawy i cala historia ida do modelu
    przy kazdej wiadomosci, wiec dluga rozmowa kosztuje wiecej."""
    znakow = len(kontekst or "") + len(tresc or "") + sum(len(str(w.get("tresc", ""))) for w in historia or [])
    return tokenomia.jednostki_rozmowy(znakow)


class ZadanieGenerowania(BaseModel):
    pola: list[dict]
    polecenie: str = ""
    z_rozmowa: bool = True


# Stan sporzadzania projektu lezy przy sprawie (i w S3), nie w przegladarce:
# duzy akt pisze sie kilkanascie minut, a w tym czasie notariusz przechodzi do
# kalendarza, odswieza strone albo otwiera sprawe na drugim urzadzeniu. Serwer
# konczy prace takze wtedy, gdy przegladarka sie rozlaczy.
PROJEKT_STAN = "projekt-stan.json"
# "w toku" starsze niz to (np. po restarcie kontenera) nie blokuje nowego projektu.
PROJEKT_MAKS_S = 2 * 3600


def _teraz_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stan_projektu(katalog: Path) -> dict:
    plik = katalog / PROJEKT_STAN
    try:
        stan = json.loads(plik.read_text("utf-8")) if plik.exists() else {}
    except ValueError:
        stan = {}
    if stan.get("stan") == "w_toku":
        try:
            trwa = (datetime.now() - datetime.fromisoformat(stan["od"])).total_seconds()
        except (KeyError, ValueError):
            trwa = PROJEKT_MAKS_S + 1
        if trwa > PROJEKT_MAKS_S:
            stan = {"stan": "przerwany", "od": stan.get("od", "")}
        else:
            stan["sekund"] = int(trwa)
    return stan or {"stan": "brak"}


def _zapisz_stan_projektu(katalog: Path, stan: dict) -> None:
    _zapisz_json(katalog / PROJEKT_STAN, stan)
    magazyn.utrwal_sprawe(katalog)


@app.get("/api/sprawy/{identyfikator}/projekt/stan")
def stan_projektu(identyfikator: str):
    """Czy projekt tej sprawy sie sporzadza, od kiedy i czym sie skonczyl."""
    return _stan_projektu(_katalog_sprawy(identyfikator))


@app.post("/api/sprawy/{identyfikator}/projekt")
async def generuj_projekt(request: Request, identyfikator: str, zadanie: ZadanieGenerowania):
    """Wypelnienie wzoru zatwierdzonymi danymi. Duzy akt pisze sie ponad kwadrans,
    wiec przegladarka dostaje strumien ze znakami zycia (jak przy odczycie),
    a stan pracy zapisujemy przy sprawie (GET .../projekt/stan)."""
    katalog = _katalog_sprawy(identyfikator)
    stan = _stan_projektu(katalog)
    if stan.get("stan") == "w_toku":
        raise HTTPException(409, "Projekt tej sprawy już się sporządza (od "
                                 + stan.get("od", "")[11:16] + "). Wynik pojawi się sam.")
    poczatek = _teraz_iso()
    _zapisz_stan_projektu(katalog, {"stan": "w_toku", "od": poczatek})

    def praca(postep) -> dict:
        start = datetime.now()
        if postep:
            postep("projekt", 0, 1)
        try:
            wynik = _generuj_projekt(identyfikator, zadanie)
        except HTTPException as blad:
            _zapisz_stan_projektu(katalog, {"stan": "blad", "od": poczatek, "do": _teraz_iso(),
                                            "komunikat": str(blad.detail)[:300], "kod": blad.status_code})
            raise
        except BaseException:
            _zapisz_stan_projektu(katalog, {"stan": "blad", "od": poczatek, "do": _teraz_iso(),
                                            "komunikat": "Blad serwera (projekt).", "kod": 500})
            raise
        sekund = int((datetime.now() - start).total_seconds())
        _zapisz_stan_projektu(katalog, {"stan": "gotowy", "od": poczatek, "do": _teraz_iso(),
                                        "sekund": sekund})
        log.info("sprawa %s: projekt sporzadzony w %d s", identyfikator, sekund)
        return {**wynik, "sekund": sekund}

    return await _wykonaj(request, praca, "projekt")


def _generuj_projekt(identyfikator: str, zadanie: ZadanieGenerowania) -> dict:
    katalog = _katalog_sprawy(identyfikator)
    sciezka_wzoru = next(katalog.glob("wzor.*"), None)
    if sciezka_wzoru is None:
        raise HTTPException(404, "Brak wzoru w tej sprawie")

    analiza = dokumenty.analizuj_wzor(dokumenty.wzor_na_tekst(sciezka_wzoru))
    rozmowa = _wczytaj_rozmowe(katalog) if zadanie.z_rozmowa else []
    projekt, zgodnosc = _sporzadz(analiza, zadanie.pola, zadanie.polecenie, rozmowa,
                                  f"sprawa {identyfikator}")

    cel = katalog / "projekt.docx"
    dokumenty.tekst_na_docx(projekt, cel)
    (katalog / "projekt.txt").write_text(projekt, encoding="utf-8")
    odczyt_plik = katalog / "odczyt.json"
    stary = json.loads(odczyt_plik.read_text("utf-8")) if odczyt_plik.exists() else {}
    stary["pola"] = zadanie.pola  # wersja po poprawkach notariusza
    _zapisz_json(odczyt_plik, stary)
    meta_plik = katalog / "sprawa.json"
    if meta_plik.exists():
        meta = json.loads(meta_plik.read_text("utf-8"))
        if not meta.get("nazwa_reczna"):
            nowa = nazwy.nazwa_sprawy(zadanie.pola, meta.get("skany") or [])
            if nowa:
                meta["nazwa"] = nowa
                _zapisz_json(meta_plik, meta)
    _zapisz_json(katalog / "zgodnosc.json", zgodnosc)
    magazyn.utrwal_sprawe(katalog)
    log.info("sprawa %s: projekt zapisany", identyfikator)

    return {
        "tekst": projekt,
        "brakujace": projekt.count("<<BRAK:"),
        "do_wyboru": projekt.count("<<WYBOR:"),
        "plik": f"/api/sprawy/{identyfikator}/plik",
        "zgodnosc": zgodnosc,
    }


@app.get("/api/sprawy/{identyfikator}/plik")
def pobierz(identyfikator: str):
    plik = _katalog_sprawy(identyfikator) / "projekt.docx"
    if not plik.exists():
        raise HTTPException(404, "Projekt nie zostal jeszcze wygenerowany")
    return FileResponse(
        plik,
        filename=f"projekt-{identyfikator}.docx",
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    )


# --- Lista spraw i powrot do sprawy -----------------------------------------


class Sygnatura(BaseModel):
    sygnatura: str = ""


class NazwaSprawy(BaseModel):
    nazwa: str = ""


def _nazwa(katalog: Path, meta: dict) -> str:
    """Nazwa z metadanych; dla starych spraw wyliczana raz i zapisywana."""
    if "nazwa" in meta and (meta["nazwa"] or meta.get("nazwa_reczna")):
        return meta["nazwa"] or ""
    odczyt_plik = katalog / "odczyt.json"
    pola = []
    if odczyt_plik.exists():
        try:
            pola = json.loads(odczyt_plik.read_text("utf-8")).get("pola", [])
        except ValueError:
            pola = []
    pliki = meta.get("skany") or sorted(p.name for p in (katalog / "skany").glob("*") if p.is_file())
    meta["nazwa"] = nazwy.nazwa_sprawy(pola, pliki)
    _zapisz_json(katalog / "sprawa.json", meta)
    return meta["nazwa"] or ""


@app.get("/api/sprawy")
def lista_spraw():
    """Wszystkie sprawy z dane/sprawy, najnowsze pierwsze. Bez danych osobowych."""
    wynik = []
    baza = config.SPRAWY
    for identyfikator in magazyn.identyfikatory_spraw(baza):
        katalog = baza / identyfikator
        plik = katalog / "sprawa.json"
        if not katalog.is_dir() or not plik.exists():
            continue
        try:
            meta = json.loads(plik.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        etap = 3 if (katalog / "projekt.txt").exists() or (katalog / "projekt.docx").exists() else 2
        skany = meta.get("skany") or sorted(p.name for p in (katalog / "skany").glob("*") if p.is_file())
        wynik.append({
            "id": meta.get("id", katalog.name),
            "nazwa": _nazwa(katalog, meta),
            "sygnatura": meta.get("sygnatura", ""),
            "utworzono": meta.get("utworzono", ""),
            "wzor": meta.get("wzor") or next((p.name for p in katalog.glob("wzor.*")), ""),
            "skany": len(skany),
            "stron": meta.get("stron", 0),
            "etap": etap,
            "sprawdzenia": len(rejestry.wczytaj_sprawdzenia(katalog.name)),
        })
    wynik.sort(key=lambda w: w["utworzono"], reverse=True)
    return wynik


@app.get("/api/sprawy/{identyfikator}")
def wczytaj_sprawe(identyfikator: str):
    """Pelny stan sprawy do odtworzenia w interfejsie."""
    katalog = _katalog_sprawy(identyfikator)
    meta = json.loads((katalog / "sprawa.json").read_text("utf-8"))
    odczyt_plik = katalog / "odczyt.json"
    odczyt = json.loads(odczyt_plik.read_text("utf-8")) if odczyt_plik.exists() else {"pola": [], "braki": [], "rozbieznosci": []}
    projekt_plik = katalog / "projekt.txt"
    projekt = projekt_plik.read_text("utf-8") if projekt_plik.exists() else None
    zgodnosc_plik = katalog / "zgodnosc.json"
    zgodnosc = json.loads(zgodnosc_plik.read_text("utf-8")) if projekt and zgodnosc_plik.exists() else None
    return {
        "id": meta.get("id", identyfikator),
        "nazwa": _nazwa(katalog, meta),
        "sygnatura": meta.get("sygnatura", ""),
        "utworzono": meta.get("utworzono", ""),
        "polecenie": meta.get("polecenie", ""),
        "wzor": meta.get("wzor", ""),
        "skany": meta.get("skany") or sorted(p.name for p in (katalog / "skany").glob("*") if p.is_file()),
        "stron": meta.get("stron", 0),
        "warianty": meta.get("warianty", 0),
        "pola": odczyt.get("pola", []),
        "braki": odczyt.get("braki", []),
        "rozbieznosci": odczyt.get("rozbieznosci", []),
        "rozmowa": _wczytaj_rozmowe(katalog),
        "projekt": projekt,
        "brakujace": projekt.count("<<BRAK:") if projekt else 0,
        "do_wyboru": projekt.count("<<WYBOR:") if projekt else 0,
        "plik": f"/api/sprawy/{identyfikator}/plik" if (katalog / "projekt.docx").exists() else None,
        "sprawdzenia": rejestry.wczytaj_sprawdzenia(identyfikator),
        "zgodnosc": zgodnosc,
        "projekt_stan": _stan_projektu(katalog),
    }


@app.delete("/api/sprawy/{identyfikator}")
def usun_sprawe(identyfikator: str, potwierdzam: bool = False):
    """Kasuje sprawe razem ze skanami, odczytem, rozmowa i projektem.

    Nieodwracalne i takie ma byc: to realizacja prawa do usuniecia danych.
    Kasujemy tez starsze wersje plikow w S3, zeby nie zostawaly przez 90 dni.
    """
    katalog = _katalog_sprawy(identyfikator)
    if not potwierdzam:
        raise HTTPException(400, "Usuniecie sprawy wymaga jawnego potwierdzenia")
    usuniete = magazyn.usun_sprawe(katalog)
    kalendarz.usun_sprawe(identyfikator)
    przesylki.usun_sprawe(identyfikator)
    log.info("sprawa %s: usunieta, obiektow w S3: %d", identyfikator, usuniete)
    return {"usunieto": identyfikator, "obiektow": usuniete}


@app.put("/api/sprawy/{identyfikator}/sygnatura")
def zmien_sygnature(identyfikator: str, dane: Sygnatura):
    katalog = _katalog_sprawy(identyfikator)
    plik = katalog / "sprawa.json"
    meta = json.loads(plik.read_text("utf-8"))
    meta["sygnatura"] = dane.sygnatura.strip()[:120]
    _zapisz_json(plik, meta)
    magazyn.utrwal_sprawe(katalog)
    return {"sygnatura": meta["sygnatura"]}


@app.put("/api/sprawy/{identyfikator}/nazwa")
def zmien_nazwe(identyfikator: str, dane: NazwaSprawy):
    """Reczna nazwa sprawy. Pusta = wroc do nazwy z nazwisk stron."""
    katalog = _katalog_sprawy(identyfikator)
    plik = katalog / "sprawa.json"
    meta = json.loads(plik.read_text("utf-8"))
    nowa = dane.nazwa.strip()[:120]
    if nowa:
        meta["nazwa"], meta["nazwa_reczna"] = nowa, True
    else:
        meta.pop("nazwa", None)
        meta.pop("nazwa_reczna", None)
    _zapisz_json(plik, meta)
    magazyn.utrwal_sprawe(katalog)
    return {"nazwa": _nazwa(katalog, meta)}


def _zapisz_json(plik: Path, dane) -> None:
    plik.write_text(json.dumps(dane, ensure_ascii=False, indent=2), encoding="utf-8")


# --- Pliki sprawy (dokumenty dodane przez kancelarie) ------------------------


# Dowolne dokumenty do sprawy: zaswiadczenia, wypisy, korespondencja. Leza
# w {sprawa}/zalaczniki/ i ida do S3 razem z reszta sprawy, wiec znikaja
# przy jej usunieciu. Nazwy plikow bywaja nazwiskami - nie trafiaja do logow.
ZALACZNIKI = "zalaczniki"
MAKS_ZALACZNIK = 25 * 1024 * 1024


def _nazwa_zalacznika(nazwa: str) -> str:
    czysta = re.sub(r"[^\w .()\-]", "_", Path(nazwa or "").name).strip(" .")[:120]
    if not czysta:
        raise HTTPException(400, "Nieprawidlowa nazwa pliku")
    return czysta


def _spis_zalacznikow(katalog: Path) -> list[dict]:
    folder = katalog / ZALACZNIKI
    if not folder.is_dir():
        return []
    return [{"nazwa": p.name, "rozmiar": p.stat().st_size,
             "dodano": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")}
            for p in sorted(folder.iterdir(), key=lambda p: p.name.lower()) if p.is_file()]


@app.get("/api/sprawy/{identyfikator}/pliki")
def pliki_sprawy(identyfikator: str):
    return _spis_zalacznikow(_katalog_sprawy(identyfikator))


@app.post("/api/sprawy/{identyfikator}/pliki")
def dodaj_pliki_sprawy(identyfikator: str, pliki: list[UploadFile] = File(...)):
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie.")
    katalog = _katalog_sprawy(identyfikator)
    folder = katalog / ZALACZNIKI
    folder.mkdir(exist_ok=True)
    for plik in pliki:
        rozmiar = plik.size if plik.size is not None else len(plik.file.read())
        plik.file.seek(0)
        if rozmiar > MAKS_ZALACZNIK:
            raise HTTPException(413, f"Plik jest większy niż {MAKS_ZALACZNIK // 1024 // 1024} MB")
    for plik in pliki:
        nazwa = _nazwa_zalacznika(plik.filename)
        cel, numer = folder / nazwa, 2
        # Ten sam plik dodany drugi raz nie nadpisuje pierwszego.
        while cel.exists():
            cel = folder / f"{Path(nazwa).stem} ({numer}){Path(nazwa).suffix}"
            numer += 1
        _zapisz(plik, cel)
    magazyn.utrwal_sprawe(katalog)
    log.info("sprawa %s: dodano plikow %d", identyfikator, len(pliki))
    return _spis_zalacznikow(katalog)


@app.get("/api/sprawy/{identyfikator}/pliki/{nazwa}")
def pobierz_plik_sprawy(identyfikator: str, nazwa: str):
    plik = _katalog_sprawy(identyfikator) / ZALACZNIKI / _nazwa_zalacznika(nazwa)
    if not plik.is_file():
        raise HTTPException(404, "Nie ma takiego pliku")
    return FileResponse(plik, filename=plik.name)


@app.delete("/api/sprawy/{identyfikator}/pliki/{nazwa}")
def usun_plik_sprawy(identyfikator: str, nazwa: str):
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie.")
    katalog = _katalog_sprawy(identyfikator)
    wzgledna = f"{ZALACZNIKI}/{_nazwa_zalacznika(nazwa)}"
    if not (katalog / wzgledna).is_file():
        raise HTTPException(404, "Nie ma takiego pliku")
    magazyn.usun_plik_sprawy(katalog, wzgledna)
    log.info("sprawa %s: usunieto plik", identyfikator)
    return _spis_zalacznikow(katalog)


# --- Osoby i telefony --------------------------------------------------------


# Telefony i kalendarz leza na serwerze. Kancelaria, ktora trzyma pliki
# u siebie, zadeklarowala, ze serwer niczego nie przechowuje - wiec tu nic.
def _tylko_w_chmurze() -> None:
    if magazyn.u_klienta():
        raise HTTPException(409, (
            "Ta kancelaria trzyma pliki u siebie, a kalendarz i telefony "
            "bylyby zapisane na serwerze."
        ))


def _zapis_kancelarii(funkcja, *argumenty):
    try:
        return funkcja(*argumenty)
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))
    except ValueError as blad:
        raise HTTPException(400, str(blad))


class Telefon(BaseModel):
    telefon: str = ""


class NowaOsoba(BaseModel):
    imie_nazwisko: str
    telefon: str = ""


@app.get("/api/osoby")
def lista_osob():
    """Strony czynnosci ze wszystkich spraw z telefonami. PESEL tylko zamaskowany."""
    _tylko_w_chmurze()
    wynik = osoby.wszystkie(lista_spraw())
    return {"osoby": wynik, "bez_telefonu": sum(1 for o in wynik if not o["telefon"])}


@app.put("/api/osoby/{identyfikator}/telefon")
def zmien_telefon(identyfikator: str, dane: Telefon):
    _tylko_w_chmurze()
    numer = _zapis_kancelarii(osoby.ustaw_telefon, identyfikator, dane.telefon)
    log.info("osoba %s: telefon %s", identyfikator, "zapisany" if numer else "usuniety")
    return {"telefon": numer}


@app.post("/api/osoby")
def dodaj_osobe(dane: NowaOsoba):
    _tylko_w_chmurze()
    identyfikator = _zapis_kancelarii(osoby.dodaj_reczna, dane.imie_nazwisko, dane.telefon)
    log.info("osoba %s: dodana recznie", identyfikator)
    return {"id": identyfikator}


@app.delete("/api/osoby/{identyfikator}")
def usun_osobe(identyfikator: str):
    _tylko_w_chmurze()
    if not _zapis_kancelarii(osoby.usun_reczna, identyfikator):
        raise HTTPException(404, "Usunąć można tylko osobę dodaną ręcznie")
    log.info("osoba %s: usunieta", identyfikator)
    return {"ok": True}


# --- Kalendarz ---------------------------------------------------------------


class WpisKalendarza(BaseModel):
    data: str
    godzina: str = ""
    koniec: str = ""
    tytul: str = ""
    rodzaj: str = ""
    rodzaj_inny: str = ""
    uczestnicy: str = ""
    telefon: str = ""  # dawne pojedyncze pole; nowy interfejs wysyla `telefony`
    telefony: list[dict] | None = None
    sprawa: str = ""
    uwagi: str = ""


@app.get("/api/kalendarz")
def lista_kalendarza():
    _tylko_w_chmurze()
    return kalendarz.lista()


@app.post("/api/kalendarz")
def dodaj_do_kalendarza(dane: WpisKalendarza):
    _tylko_w_chmurze()
    wpis = _zapis_kancelarii(kalendarz.dodaj, dane.model_dump())
    log.info("kalendarz %s: dodany", wpis["id"])
    return wpis


class OpisDnia(BaseModel):
    tytul: str = ""
    nieczynne: bool = False


@app.get("/api/kalendarz/dni")
def dni_kalendarza():
    _tylko_w_chmurze()
    return kalendarz.dni()


@app.put("/api/kalendarz/dni/{dzien}")
def ustaw_dzien_kalendarza(dzien: str, dane: OpisDnia):
    _tylko_w_chmurze()
    opis = _zapis_kancelarii(kalendarz.ustaw_dzien, dzien, dane.model_dump())
    log.info("kalendarz: opis dnia %s %s", dzien, "zapisany" if opis["tytul"] or opis["nieczynne"] else "usuniety")
    return opis


@app.put("/api/kalendarz/{identyfikator}")
def zmien_w_kalendarzu(identyfikator: str, dane: WpisKalendarza):
    _tylko_w_chmurze()
    wpis = _zapis_kancelarii(kalendarz.zmien, identyfikator, dane.model_dump())
    if wpis is None:
        raise HTTPException(404, "Nie ma takiego terminu")
    log.info("kalendarz %s: zmieniony", identyfikator)
    return wpis


@app.delete("/api/kalendarz/{identyfikator}")
def usun_z_kalendarza(identyfikator: str):
    _tylko_w_chmurze()
    if not _zapis_kancelarii(kalendarz.usun, identyfikator):
        raise HTTPException(404, "Nie ma takiego terminu")
    log.info("kalendarz %s: usuniety", identyfikator)
    return {"ok": True}


# --- Rozmowa o sprawie -------------------------------------------------------


class Wiadomosc(BaseModel):
    tresc: str


@app.get("/api/sprawy/{identyfikator}/rozmowa")
def rozmowa_sprawy(identyfikator: str):
    return _wczytaj_rozmowe(_katalog_sprawy(identyfikator))


@app.post("/api/sprawy/{identyfikator}/rozmowa")
def wyslij_wiadomosc(identyfikator: str, wiadomosc: Wiadomosc):
    katalog = _katalog_sprawy(identyfikator)
    tresc = wiadomosc.tresc.strip()
    if not tresc:
        raise HTTPException(400, "Pusta wiadomosc")
    kontekst_plik = katalog / "kontekst.txt"
    kontekst = kontekst_plik.read_text("utf-8") if kontekst_plik.exists() else "(brak danych)"
    rozmowa = _wczytaj_rozmowe(katalog)
    teraz = datetime.now().isoformat(timespec="seconds")
    try:
        with tokenomia.akcja("rozmowa_tura", _tury_rozmowy(kontekst, rozmowa, tresc),
                             f"sprawa {identyfikator}"):
            odpowiedz = bedrock.rozmawiaj(kontekst, rozmowa, tresc)
    except HTTPException:
        raise
    except bedrock.Przeciazenie as blad:
        raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("sprawa %s: blad rozmowy (%s)", identyfikator, dziennik.opis_bledu(blad))
        raise HTTPException(502, f"Bedrock: {type(blad).__name__}")
    rozmowa.append({"rola": "uzytkownik", "tresc": tresc, "czas": teraz})
    rozmowa.append({"rola": "asystent", "tresc": odpowiedz, "czas": datetime.now().isoformat(timespec="seconds")})
    _zapisz_rozmowe(katalog, rozmowa)
    magazyn.utrwal_sprawe(katalog)
    log.info("sprawa %s: rozmowa, tur=%d", identyfikator, len(rozmowa))
    return {"odpowiedz": odpowiedz, "rozmowa": rozmowa}


@app.post("/api/transkrypcja")
async def transkrybuj_audio(audio: UploadFile = File(...)):
    """Nagranie z przegladarki -> tekst. Lokalnie, plik usuwany po transkrypcji."""
    if not transkrypcja.dostepna():
        raise HTTPException(503, "Transkrypcja niedostepna: zainstaluj faster-whisper (uruchom.bat robi to sam).")
    dane = await audio.read()
    if len(dane) > 25 * 1024 * 1024:
        raise HTTPException(413, "Nagranie za dlugie (limit 25 MB)")
    rozszerzenie = Path(audio.filename or "nagranie.webm").suffix.lower() or ".webm"
    try:
        tekst = transkrypcja.transkrybuj(dane, rozszerzenie)
    except Exception as blad:
        log.error("transkrypcja: blad (%s)", dziennik.opis_bledu(blad))
        raise HTTPException(500, f"Transkrypcja nie powiodla sie: {type(blad).__name__}")
    return {"tekst": tekst}


def _wczytaj_rozmowe(katalog: Path) -> list[dict]:
    plik = katalog / "rozmowa.json"
    return json.loads(plik.read_text("utf-8")) if plik.exists() else []


def _zapisz_rozmowe(katalog: Path, rozmowa: list[dict]) -> None:
    (katalog / "rozmowa.json").write_text(
        json.dumps(rozmowa, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# --- Asysta formularzy i sprawdzenia (SPEC A3, B) -------------------------

# Jedna odpowiedz na "wpisz to w rejestrze" tam, gdzie serwer nie ma
# przegladarki. Mowi, gdzie ta czynnosc nalezy, zamiast kazac notariuszowi
# instalowac Chrome, ktorego przeciez ma.
BRAK_POMOCNIKA = (
    "Pomocnik notarai nie jest teraz uruchomiony na Twoim komputerze. "
    "Sprawdzenie w rejestrze dzieje sie w Twojej przegladarce, wiec bez niego "
    "nie ma kto go wykonac. Uruchom pomocnika i sprobuj ponownie."
)

BRAK_PRZEGLADARKI = (
    "Wpisywanie do rejestru dzieje sie w przegladarce na Twoim komputerze, "
    "a ta notarai pracuje w chmurze. Zrobi to pomocnik notarai, ktory "
    "instaluje sie na komputerze - jest w przygotowaniu. Na razie skorzystaj "
    "z podgladu wypelnienia i zatwierdz wynik odczytany z ekranu."
)
# Skutek zewnetrzny (wyslanie, zlozenie) NIGDY nie nastepuje tutaj. Silnik
# wypelnia pola w przegladarce notariusza i zatrzymuje sie przed wysylka.


@app.get("/api/formularze")
def lista_formularzy():
    return formularze.dostepne_systemy()


class ZadanieDopasowania(BaseModel):
    tekst_aktu: str = ""
    pola: list[dict] = []


@app.post("/api/formularze/{system}/dopasuj")
def dopasuj_formularz(system: str, zadanie: ZadanieDopasowania):
    """Proponuje, co wpisac w kazde pole formularza, na podstawie tresci aktu.

    Niczego nie wpisuje i nie dotyka przegladarki - to material do sprawdzenia
    przez notariusza. Kazda wartosc ma zrodlo: pole sprawy albo cytat z aktu.
    """
    try:
        mapowanie = formularze.wczytaj_mapowanie(system)
    except formularze.BladMapowania as blad:
        raise HTTPException(404, str(blad))

    pola_sprawy = {str(p.get("nazwa", "")): p.get("wartosc") for p in zadanie.pola}
    try:
        with tokenomia.akcja("formularz", 1, f"formularz {system}"):
            wynik = formularze.dopasuj(
                mapowanie, zadanie.tekst_aktu, pola_sprawy,
                model=bedrock.wyciagnij_do_formularza,
            )
    except HTTPException:
        raise
    except bedrock.Przeciazenie as blad:
        raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("formularz %s: blad dopasowania (%s)", system, dziennik.opis_bledu(blad))
        raise HTTPException(502, f"Bedrock: {type(blad).__name__}")

    return {
        "system": mapowanie.system,
        "opis": mapowanie.opis,
        "status": mapowanie.status,
        "wpisy": wynik["wpisy"],
        "gotowych": sum(1 for w in wynik["wpisy"] if w["wartosc"]),
        "brakujacych": sum(1 for w in wynik["wpisy"] if not w["wartosc"]),
        "ostrzezen": sum(1 for w in wynik["wpisy"] if w["ostrzezenie"]),
    }


class ZadanieFormularza(BaseModel):
    pola: list[dict]
    tryb: str = "podglad"          # podglad | faktyczny
    potwierdzam: bool = False      # jawne potwierdzenie z interfejsu dla trybu faktycznego


@app.post("/api/sprawy/{identyfikator}/formularze/{system}")
def wypelnij_formularz(identyfikator: str, system: str, zadanie: ZadanieFormularza):
    _katalog_sprawy(identyfikator)
    try:
        mapowanie = formularze.wczytaj_mapowanie(system)
    except formularze.BladMapowania as blad:
        raise HTTPException(404, str(blad))
    dane = {str(p.get("nazwa", "")): p.get("wartosc") for p in zadanie.pola}

    if zadanie.tryb != "faktyczny":
        raport = formularze.zaplanuj(mapowanie, dane)
    else:
        if not zadanie.potwierdzam:
            raise HTTPException(400, "Tryb faktyczny wymaga jawnego potwierdzenia")
        if not formularze.silnik.czy_mozna_sterowac():
            raise HTTPException(409, BRAK_PRZEGLADARKI)
        try:
            pw, strona = formularze.silnik.aktywna_strona()
        except RuntimeError as blad:
            raise HTTPException(409, str(blad))
        try:
            raport = formularze.wypelnij(mapowanie, dane, strona, tryb="faktyczny")
        finally:
            pw.stop()
    log.info("sprawa %s: formularz %s tryb=%s pol=%d bledy=%d",
             identyfikator, system, raport.tryb, len(raport.kroki), len(raport.bledy))
    return {
        "system": raport.system,
        "tryb": raport.tryb,
        "status_mapowania": mapowanie.status,
        "kroki": [
            {"pole": k.pole, "wartosc": k.wartosc, "wykonano": k.wykonano, "uwaga": k.uwaga}
            for k in raport.kroki
        ],
        "brakujace": raport.brakujace,
        "zatrzymano_przed": "przyciskiem wysylki - wysyla czlowiek",
        "bledy": raport.bledy,
    }


class ZadanieSprawdzenia(BaseModel):
    rejestr: str
    pesel: str
    status: str
    szczegoly: str = ""
    zrodlo: str = "Rejestry Notarialne KRN"
    etykieta: str = ""        # ktorej strony czynnosci dotyczy wpis


@app.post("/api/sprawy/{identyfikator}/sprawdzenia")
def zapisz_sprawdzenie(identyfikator: str, zadanie: ZadanieSprawdzenia):
    """Notariusz odczytal wynik z ekranu rejestru i zatwierdza go w pieczapp."""
    _katalog_sprawy(identyfikator)
    try:
        wynik = rejestry.WynikSprawdzenia(
            rejestr=zadanie.rejestr,
            zapytanie=rejestry.maskuj_pesel(zadanie.pesel),
            status=zadanie.status,
            szczegoly=zadanie.szczegoly,
            zrodlo=zadanie.zrodlo,
            etykieta=zadanie.etykieta,
        )
    except ValueError as blad:
        raise HTTPException(400, str(blad))
    rejestry.zapisz_sprawdzenie(identyfikator, wynik)
    magazyn.utrwal_sprawe(config.SPRAWY / identyfikator)
    log.info("sprawa %s: sprawdzenie %s status=%s", identyfikator, wynik.rejestr, wynik.status)
    return rejestry.wczytaj_sprawdzenia(identyfikator)


@app.get("/api/sprawy/{identyfikator}/sprawdzenia")
def lista_sprawdzen(identyfikator: str):
    _katalog_sprawy(identyfikator)
    return rejestry.wczytaj_sprawdzenia(identyfikator)


class OsobaKRZ(BaseModel):
    pesel: str
    etykieta: str = ""


class ZadanieKRZ(BaseModel):
    osoby: list[OsobaKRZ]
    potwierdzam: bool = False


@app.post("/api/sprawy/{identyfikator}/krz")
def sprawdz_krz(identyfikator: str, zadanie: ZadanieKRZ):
    """Jeden przycisk: uruchamia przegladarke (jesli trzeba), dla kazdej osoby
    dwa wyszukiwania w KRZ, zrzuty + wpisy audytowe."""
    _katalog_sprawy(identyfikator)
    if not zadanie.potwierdzam:
        raise HTTPException(400, "Sprawdzenie w KRZ wymaga jawnego potwierdzenia")
    if not zadanie.osoby:
        raise HTTPException(400, "Brak osob do sprawdzenia")
    if not formularze.silnik.czy_mozna_sterowac():
        # Serwer nie ma przegladarki. Zlecamy to pomocnikowi przy komputerze
        # notariusza - zapytanie ma wychodzic z lacza kancelarii, nie z chmury.
        if not zlecenia.dostepne():
            raise HTTPException(409, BRAK_PRZEGLADARKI)
        if not _pomocnik_pod_reka():
            raise HTTPException(409, BRAK_POMOCNIKA)
        zlecenie = zlecenia.zloz("krz", identyfikator, {
            "osoby": [{"pesel": o.pesel, "etykieta": o.etykieta} for o in zadanie.osoby],
        })
        return JSONResponse({"zlecenie": zlecenie["id"], "stan": "czeka"}, status_code=202)
    try:
        pw, strona = formularze.silnik.aktywna_strona()
    except RuntimeError as blad:
        raise HTTPException(409, str(blad))
    try:
        for osoba in zadanie.osoby:
            try:
                wynik = krz.sprawdz_osobe(krz.StronaPlaywright(strona._p), osoba.pesel, identyfikator, osoba.etykieta)
            except ValueError as blad:
                wynik = rejestry.WynikSprawdzenia(
                    rejestr="KRZ", zapytanie=rejestry.maskuj_pesel(osoba.pesel), status="blad",
                    szczegoly=f"{osoba.etykieta} - {blad}", zrodlo=krz.ADRES,
                    etykieta=osoba.etykieta,
                )
            except Exception as blad:  # noqa: BLE001
                log.error("sprawa %s: KRZ blad (%s)", identyfikator, dziennik.opis_bledu(blad))
                wynik = rejestry.WynikSprawdzenia(
                    rejestr="KRZ", zapytanie=rejestry.maskuj_pesel(osoba.pesel), status="niedostepny",
                    szczegoly=f"{osoba.etykieta} - portal niedostepny albo zmienil uklad ({type(blad).__name__})",
                    zrodlo=krz.ADRES, etykieta=osoba.etykieta,
                )
            rejestry.zapisz_sprawdzenie(identyfikator, wynik)
    finally:
        pw.stop()
    magazyn.utrwal_sprawe(config.SPRAWY / identyfikator)
    return rejestry.wczytaj_sprawdzenia(identyfikator)


# --- Ksiega wieczysta z EKW ------------------------------------------------
# Portal EKW odrzuca ruch z serwerow, wiec tresc ksiegi pobiera dostawca
# (aktor Apify) - jedna ksiega na zadanie notariusza, z jawnym potwierdzeniem.
# Tresc zostaje w sprawie (katalog ksiegi/), pobranie w sladzie audytowym.

BRAK_EKW = (
    "Pobieranie ksiag z EKW nie jest wlaczone w tej instalacji. Administrator "
    "musi skonfigurowac dostawce: Finance You (PIECZAPP_FINYOU_URL i "
    "PIECZAPP_FINYOU_TOKEN) albo Apify (PIECZAPP_APIFY_TOKEN). Do tego czasu "
    "wklej wydruk ksiegi jako dokument sprawy."
)


class ZadanieEKW(BaseModel):
    numer_kw: str
    potwierdzam: bool = False


@app.post("/api/sprawy/{identyfikator}/ekw")
def pobierz_ksiege(identyfikator: str, zadanie: ZadanieEKW):
    """Jedna ksiega: pobranie przez dostawce, zapis do sprawy, wpis audytowy."""
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie.")
    _katalog_sprawy(identyfikator)
    if not ekw.dostepne():
        raise HTTPException(409, BRAK_EKW)
    if not zadanie.potwierdzam:
        raise HTTPException(400, "Pobranie ksiegi z EKW wymaga jawnego potwierdzenia")
    try:
        numer = ekw.normalizuj_numer(zadanie.numer_kw)
    except ValueError as blad:
        raise HTTPException(400, str(blad))
    start = datetime.now()
    try:
        # Platny wynik u dostawcy: kredyty tylko za pobrana ksiege.
        with tokenomia.akcja("ekw_ksiega", 1, f"sprawa {identyfikator}"):
            ksiega = ekw.pobierz(numer)
    except ekw.BladEKW as blad:
        # Nieudana proba tez jest sladem starannosci - bez numeru KW w logach.
        rejestry.zapisz_sprawdzenie(identyfikator, ekw.wynik_bledu(numer, blad))
        magazyn.utrwal_sprawe(config.SPRAWY / identyfikator)
        log.warning("sprawa %s: EKW nie pobrano (%s)", identyfikator, blad.kod)
        kod = {"nie_znaleziono": 404, "brak_tokenu": 409, "blad_tokenu": 409, "limit": 429}.get(blad.kod, 502)
        raise HTTPException(kod, str(blad))
    ekw.zapisz(identyfikator, ksiega)
    magazyn.utrwal_sprawe(config.SPRAWY / identyfikator)
    log.info("sprawa %s: EKW pobrano ksiege, dzialow z wpisami=%d, czas=%.0fs",
             identyfikator, sum(1 for d in ksiega["dzialy"] if not d["pusty"]),
             (datetime.now() - start).total_seconds())
    return {"ksiega": ksiega, "sprawdzenia": rejestry.wczytaj_sprawdzenia(identyfikator)}


@app.get("/api/sprawy/{identyfikator}/ksiegi")
def ksiegi_sprawy(identyfikator: str):
    _katalog_sprawy(identyfikator)
    return ekw.wczytaj(identyfikator)
# --- AML: listy sankcyjne, PEP i CRBR (ustawa z 1.03.2018) -------------------
# Notariusz jest instytucja obowiazana (art. 2 ust. 1 pkt 13). Listy przychodza
# do nas (aml_listy), dopasowanie liczymy u siebie (aml_dopasowanie) - dane
# stron czynnosci nie wychodza na zewnatrz. Wyjatek: CRBR, gdzie pytamy
# oficjalna bramke MF o spolke (NIP/KRS), nie o osobe.


class StronaAML(BaseModel):
    imie_nazwisko: str = ""
    pesel: str = ""
    etykieta: str = ""


class ZadanieAML(BaseModel):
    strony: list[StronaAML] = []          # puste = wszystkie strony z odczytu sprawy
    rejestry: list[str] = ["SANKCJE", "PEP"]
    potwierdzam: bool = False


def _strony_sprawy(katalog: Path) -> list[dict]:
    plik = katalog / "odczyt.json"
    pola = json.loads(plik.read_text("utf-8")).get("pola", []) if plik.exists() else []
    return [{"imie_nazwisko": s["imie_nazwisko"], "pesel": s.get("pesel", ""), "etykieta": s.get("rola", "")}
            for s in osoby.osoby_ze_sprawy(pola) if s.get("imie_nazwisko")]


@app.post("/api/sprawy/{identyfikator}/aml")
def sprawdz_aml(identyfikator: str, zadanie: ZadanieAML):
    """Strony czynnosci na listach sankcyjnych i PEP. Jeden wpis sladu na
    strone i liste; trafienia czekaja na decyzje notariusza."""
    katalog = _katalog_sprawy(identyfikator)
    if not zadanie.potwierdzam:
        raise HTTPException(400, "Sprawdzenie na listach wymaga jawnego potwierdzenia")
    for r in zadanie.rejestry:
        if r not in aml.KATEGORIA_REJESTRU:
            raise HTTPException(400, f"Nieznana lista: {r}")
    strony = [s.model_dump() for s in zadanie.strony if s.imie_nazwisko.strip()] or _strony_sprawy(katalog)
    if not strony:
        raise HTTPException(400, "Brak stron czynnosci do sprawdzenia - odczytaj sprawe albo podaj osoby")
    wyniki = aml.sprawdz_strony(strony, tuple(zadanie.rejestry))
    for wynik in wyniki:
        rejestry.zapisz_sprawdzenie(identyfikator, wynik)
    magazyn.utrwal_sprawe(katalog)
    log.info("sprawa %s: AML stron=%d wpisow=%d trafien=%d", identyfikator, len(strony), len(wyniki),
             sum(1 for w in wyniki if w.status == "wpis"))
    return rejestry.wczytaj_sprawdzenia(identyfikator)


class ZadanieCRBR(BaseModel):
    nip: str = ""
    krs: str = ""
    nazwa: str = ""
    etykieta: str = ""
    potwierdzam: bool = False


@app.post("/api/sprawy/{identyfikator}/crbr")
def sprawdz_crbr(identyfikator: str, zadanie: ZadanieCRBR):
    """Beneficjenci rzeczywisci spolki z oficjalnej bramki CRBR. W sladzie
    PESEL-e beneficjentow sa zamaskowane; strony czynnosci porownujemy
    z beneficjentami po imieniu i nazwisku."""
    katalog = _katalog_sprawy(identyfikator)
    if not zadanie.potwierdzam:
        raise HTTPException(400, "Zapytanie do CRBR wymaga jawnego potwierdzenia")
    wynik = crbr.sprawdz(zadanie.nip, zadanie.krs, zadanie.nazwa)
    if wynik.status == "bledne_dane":
        raise HTTPException(400, wynik.komunikat)
    zapytanie = (f"NIP {crbr.normalizuj_nip(zadanie.nip)}" if crbr.normalizuj_nip(zadanie.nip)
                 else f"KRS {crbr.normalizuj_krs(zadanie.krs)}" if crbr.normalizuj_krs(zadanie.krs)
                 else zadanie.nazwa.strip())
    status = {"ok": "wpis", "brak": "brak_wpisu", "wiele": "blad", "blad": "niedostepny"}[wynik.status]
    szczegoly = crbr.opis_dla_sladu(wynik)
    trafienia = []
    if wynik.status == "ok":
        strony = [s["imie_nazwisko"] for s in _strony_sprawy(katalog)]
        dopasowania = crbr.dopasuj_osoby(strony, wynik.beneficjenci)
        if strony:
            sa = [n for n, ok in dopasowania.items() if ok]
            nie = [n for n, ok in dopasowania.items() if not ok]
            szczegoly += " | Strony czynnosci wsrod beneficjentow: " + (", ".join(sa) or "zadna")
            if nie:
                szczegoly += "; poza CRBR: " + ", ".join(nie)
        trafienia = [{"nazwa_na_liscie": o.imie_nazwisko, "rola": "beneficjent", "uprawnienia": o.uprawnienia,
                      "data_urodzenia": o.data_urodzenia, "pesel": o.pesel_maska,
                      "strona_czynnosci": any(dopasowania.get(n) and crbr._norm(n) in crbr._norm(o.imie_nazwisko)
                                              or crbr._norm(o.imie_nazwisko) in crbr._norm(n) for n in strony)}
                     for o in wynik.beneficjenci] + [
                     {"nazwa_na_liscie": o.imie_nazwisko, "rola": "zglaszajacy", "funkcja": o.funkcja}
                     for o in wynik.zglaszajacy]
    elif wynik.status == "wiele":
        trafienia = [{"nazwa_na_liscie": k.nazwa, "rola": "spolka", "nip": k.nip, "krs": k.krs} for k in wynik.kandydaci]
    wpis = rejestry.WynikSprawdzenia(rejestr="CRBR", zapytanie=zapytanie, status=status, szczegoly=szczegoly,
                                     zrodlo=wynik.zrodlo, etykieta=zadanie.etykieta, trafienia=trafienia)
    rejestry.zapisz_sprawdzenie(identyfikator, wpis)
    magazyn.utrwal_sprawe(katalog)
    log.info("sprawa %s: CRBR status=%s", identyfikator, wynik.status)
    return rejestry.wczytaj_sprawdzenia(identyfikator)


class DecyzjaSprawdzenia(BaseModel):
    indeks: int
    decyzja: str                       # falszywe_trafienie | potwierdzone
    uzasadnienie: str


@app.post("/api/sprawy/{identyfikator}/sprawdzenia/decyzja")
def decyzja_sprawdzenia(identyfikator: str, dane: DecyzjaSprawdzenia, request: Request):
    """Notariusz rozstrzyga trafienie z list. Stary wpis zostaje, dochodzi nowy."""
    katalog = _katalog_sprawy(identyfikator)
    wpisy = rejestry.wczytaj_sprawdzenia(identyfikator)
    try:
        wynik = aml.decyzja(wpisy, dane.indeks, dane.decyzja, dane.uzasadnienie,
                            kto=getattr(request.state, "email", "") or "")
    except ValueError as blad:
        raise HTTPException(400, str(blad))
    rejestry.zapisz_sprawdzenie(identyfikator, wynik)
    magazyn.utrwal_sprawe(katalog)
    log.info("sprawa %s: decyzja %s o wpisie %d (%s)", identyfikator, dane.decyzja, dane.indeks, wynik.rejestr)
    return rejestry.wczytaj_sprawdzenia(identyfikator)


@app.get("/api/aml/listy")
def listy_aml():
    """Z kiedy sa listy i ile maja wpisow - interfejs pokazuje to przy przycisku."""
    return aml_listy.stan()


@app.post("/api/admin/aml/listy/odswiez")
def odswiez_listy_aml(request: Request):
    """Pobiera listy na nowo (w tle - Wikidata trwa kilka minut)."""
    autoryzacja._wymagaj_admina(request)
    threading.Thread(target=aml_listy.odswiez, kwargs={"wymus": True}, daemon=True, name="listy-aml-admin").start()
    return {"stan": "uruchomiono", "zrodla": aml_listy.zrodla_wlaczone()}


# --- Ksiegi notarialne i zgloszenia do GIIF ------------------------------------
# Repertorium A/P, ksiega depozytowa, dzienniki (ksiegi_notarialne.py) oraz
# obieg zgloszen do GIIF / Szefa KAS (giif.py). Numery nadaje serwer,
# poprawki zostaja w historii. Wysylka do SI*GIIF i do systemu KW MS odbywa
# sie podpisem kwalifikowanym notariusza - tu rejestrujemy jej wynik.


def _kto(request: Request) -> str:
    return getattr(request.state, "email", "") or ""


def _ksiegi(funkcja, *argumenty, **nazwane):
    _tylko_w_chmurze()
    try:
        return funkcja(*argumenty, **nazwane)
    except ksiegi_notarialne.BrakWpisu as blad:
        raise HTTPException(404, str(blad))
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))
    except ValueError as blad:
        raise HTTPException(400, str(blad))
    except (TypeError, ArithmeticError, KeyError, IndexError, AttributeError) as blad:
        # Dane z przegladarki w nieoczekiwanym ksztalcie - to blad danych, nie serwera.
        log.info("ksiegi/giif: niepoprawne dane (%s)", type(blad).__name__)
        raise HTTPException(400, "Niepoprawne dane - sprawdź typy pól")


class Poprawka(BaseModel):
    zmiany: dict
    powod: str


class Uwaga(BaseModel):
    tresc: str


@app.get("/api/ksiegi-kancelarii")
def definicje_ksiag():
    return ksiegi_notarialne.definicje()


@app.get("/api/ksiegi-kancelarii/repertorium_a/sumy")
def sumy_repertorium(rok: int, miesiac: int | None = None):
    return _ksiegi(ksiegi_notarialne.sumy, rok, miesiac)


@app.get("/api/ksiegi-kancelarii/repertorium_a/skorowidz")
def skorowidz_repertorium(rok: int):
    return _ksiegi(ksiegi_notarialne.skorowidz, rok)


@app.get("/api/ksiegi-kancelarii/{ksiega}/wydruk")
def wydruk_ksiegi(ksiega: str, rok: int | None = None, format: str = "html"):
    """Wydruk do oprawienia (HTML, A4 poziomo) albo CSV do arkusza."""
    if format == "csv":
        tresc = _ksiegi(ksiegi_notarialne.csv_ksiegi, ksiega, rok)
        return Response(tresc, media_type="text/csv; charset=utf-8", headers={
            "Content-Disposition": f'attachment; filename="{ksiega}-{rok or "wszystkie"}.csv"'})
    return HTMLResponse(_ksiegi(ksiegi_notarialne.wydruk_html, ksiega, rok))


@app.get("/api/ksiegi-kancelarii/{ksiega}")
def lista_ksiegi(ksiega: str, rok: int | None = None):
    return _ksiegi(ksiegi_notarialne.lista, ksiega, rok)


@app.post("/api/ksiegi-kancelarii/{ksiega}")
def wpis_do_ksiegi(ksiega: str, dane: dict, request: Request):
    wpis = _ksiegi(ksiegi_notarialne.dodaj, ksiega, dane, _kto(request))
    log.info("ksiega %s: nowy wpis %s", ksiega, wpis["id"])
    return wpis


@app.post("/api/ksiegi-kancelarii/{ksiega}/{wpis}/poprawka")
def poprawka_w_ksiedze(ksiega: str, wpis: str, dane: Poprawka, request: Request):
    wynik = _ksiegi(ksiegi_notarialne.popraw, ksiega, wpis, dane.zmiany, dane.powod, _kto(request))
    log.info("ksiega %s: poprawka wpisu %s", ksiega, wpis)
    return wynik


@app.post("/api/ksiegi-kancelarii/{ksiega}/{wpis}/uwagi")
def uwaga_w_ksiedze(ksiega: str, wpis: str, dane: Uwaga, request: Request):
    return _ksiegi(ksiegi_notarialne.dodaj_uwage, ksiega, wpis, dane.tresc, _kto(request))


@app.post("/api/ksiegi-kancelarii/repertorium_a/{wpis}/wnioski-kw")
def wniosek_kw(wpis: str, dane: dict, request: Request):
    return _ksiegi(ksiegi_notarialne.zarejestruj_wniosek_kw, wpis, dane, _kto(request))


@app.post("/api/ksiegi-kancelarii/repertorium_a/{wpis}/wnioski-kw/{wniosek}")
def zmiana_wniosku_kw(wpis: str, wniosek: str, dane: dict, request: Request):
    return _ksiegi(ksiegi_notarialne.zmien_wniosek_kw, wpis, wniosek, dane, _kto(request))


@app.get("/api/ksiegi-kancelarii/repertorium_a/{wpis}/wnioski-kw/{wniosek}/pakiet")
def pakiet_wniosku_kw(wpis: str, wniosek: str):
    """Kroki do portalu MS w kolejnosci formularza - do skopiowania albo dla pomocnika."""
    return _ksiegi(ksiegi_notarialne.pakiet_wniosku_kw, wpis, wniosek)


@app.post("/api/ksiegi-kancelarii/repertorium_a/{wpis}/wnioski-kw/{wniosek}/status")
def status_wniosku_kw(wpis: str, wniosek: str, dane: dict, request: Request):
    """Zlozony (z numerem REP.C -> repertorium C), w sadzie, wpis dokonany, zwrot..."""
    wynik = _ksiegi(ksiegi_notarialne.zmien_status_wniosku_kw, wpis, wniosek, dane, _kto(request))
    log.info("wniosek KW %s: status %s", wniosek, dane.get("status"))
    return wynik


@app.get("/api/ksiegi-kancelarii/repertorium_a/{wpis}/giif")
def kwalifikacja_giif(wpis: str, kurs_eur: str = ""):
    rep = _ksiegi(ksiegi_notarialne.wpis, "repertorium_a", wpis)
    if rep is None:
        raise HTTPException(404, "Nie ma takiego wpisu")
    return _ksiegi(giif.kwalifikuj, rep, kurs_eur or None)


class NoweZgloszenie(BaseModel):
    rodzaj: str | None = None
    rep_a_id: str = ""
    kurs_eur: str = ""
    dane: dict = {}


class Wysylka(BaseModel):
    identyfikator_si_giif: str
    data_wysylki: str


@app.get("/api/giif")
def lista_zgloszen(status: str | None = None):
    return {"definicje": giif.definicje(), "zgloszenia": _ksiegi(giif.lista, status),
            "zalegle": _ksiegi(giif.zalegle)}


@app.post("/api/giif")
def nowe_zgloszenie(dane: NoweZgloszenie, request: Request):
    if dane.rep_a_id:
        z = _ksiegi(giif.z_repertorium, dane.rep_a_id, dane.rodzaj, dane.kurs_eur or None, _kto(request))
    else:
        z = _ksiegi(giif.utworz, dane.rodzaj or "", dane.dane, _kto(request))
    log.info("giif: nowe zgloszenie %s rodzaj=%s", z["id"], z["rodzaj"])
    return z


@app.get("/api/giif/ustawienia")
def ustawienia_giif():
    return _ksiegi(giif.ustawienia)


@app.post("/api/giif/ustawienia")
def zapis_ustawien_giif(dane: dict):
    return _ksiegi(giif.zapisz_ustawienia, dane)


@app.post("/api/giif/{zgloszenie}/karta")
def karta_zgloszenia(zgloszenie: str, karta: dict, request: Request):
    return _ksiegi(giif.zapisz_karte, zgloszenie, karta, _kto(request))


@app.get("/api/giif/{zgloszenie}/xml")
def xml_zgloszenia(zgloszenie: str, pobierz: bool = False):
    """Plik XML wg XSD CRWDE 14250 + bledy. pobierz=1 - sam plik, tylko gdy bez bledow."""
    wynik = _ksiegi(giif.plik_xml, zgloszenie)
    if not pobierz:
        return wynik
    if wynik["bledy"]:
        raise HTTPException(400, "Plik ma bledy: " + "; ".join(wynik["bledy"][:5]))
    return Response(wynik["xml"], media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{wynik["nazwa_pliku"]}"'})


@app.post("/api/giif/{zgloszenie}")
def zmiana_zgloszenia(zgloszenie: str, dane: dict, request: Request):
    return _ksiegi(giif.zmien, zgloszenie, dane, _kto(request))


@app.post("/api/giif/{zgloszenie}/zatwierdz")
def zatwierdz_zgloszenie(zgloszenie: str, request: Request):
    return _ksiegi(giif.zatwierdz, zgloszenie, _kto(request))


@app.post("/api/giif/{zgloszenie}/wysylka")
def wysylka_zgloszenia(zgloszenie: str, dane: Wysylka, request: Request):
    z = _ksiegi(giif.zarejestruj_wysylke, zgloszenie, dane.model_dump(), _kto(request))
    log.info("giif: zgloszenie %s wyslane", zgloszenie)
    return z


@app.post("/api/giif/{zgloszenie}/upo")
async def upo_zgloszenia(zgloszenie: str, request: Request, plik: UploadFile = File(...)):
    tresc = await plik.read()
    return _ksiegi(giif.zarejestruj_upo, zgloszenie, tresc, _kto(request))


# --- Pomocnik notariusza ----------------------------------------------------
# Czynnosci, ktore musza sie wydarzyc w przegladarce notariusza, serwer zleca
# pomocnikowi na jego komputerze. Tu jest oba konce tej rozmowy: interfejs pyta
# o stan zlecenia, pomocnik odbiera robote i odsyla raport.


@app.get("/api/sprawy/{identyfikator}/zlecenia/{zlecenie}")
def stan_zlecenia(identyfikator: str, zlecenie: str):
    _katalog_sprawy(identyfikator)
    if not zlecenia.dostepne():
        raise HTTPException(404, "Ta instalacja nie sklada zlecen")
    stan = zlecenia.wynik(zlecenie)
    if not stan:
        raise HTTPException(404, "Nie ma takiego zlecenia albo stracilo waznosc")
    return {"stan": stan["stan"], "raport": stan.get("raport")}


class RaportPomocnika(BaseModel):
    sprawdzenia: list[ZadanieSprawdzenia] = []
    bledy: list[str] = []


# --- Klikamy: model prowadzi przegladarke notariusza ------------------------
# Notariusz pisze, co ma sie stac; model decyduje o kolejnym kroku, a pomocnik
# go wykonuje. Model stoi tutaj, bo tu jest dostep do Bedrocka - komputer
# notariusza dostaje gotowa czynnosc, a nie klucze do modelu.


class ZadanieKlikania(BaseModel):
    cel: str
    dozwolone_hosty: list[str] = []


@app.post("/api/sprawy/{identyfikator}/klikamy", status_code=202)
def zlec_klikanie(identyfikator: str, zadanie: ZadanieKlikania):
    _katalog_sprawy(identyfikator)
    cel = zadanie.cel.strip()
    if not cel:
        raise HTTPException(400, "Napisz, co pomocnik ma zrobic w przegladarce")
    if not zlecenia.dostepne():
        raise HTTPException(409, BRAK_PRZEGLADARKI)
    if not _pomocnik_pod_reka():
        raise HTTPException(409, BRAK_POMOCNIKA)
    zlecenie = zlecenia.zloz("klikamy", identyfikator, {
        "cel": cel[:1000],
        "dozwolone_hosty": [h.strip() for h in zadanie.dozwolone_hosty if h.strip()][:20],
    })
    log.info("sprawa %s: zlecono klikanie, zlecenie %s", identyfikator, zlecenie["id"])
    return {"zlecenie": zlecenie["id"], "stan": "czeka"}


class WidokStrony(BaseModel):
    cel: str
    stan: dict
    kroki: list[dict] = []


@app.post("/api/pomocnik/klikamy/{zlecenie}/krok")
def krok_klikania(request: Request, zlecenie: str, widok: WidokStrony):
    """Pomocnik pokazuje, co widzi na stronie; model mowi, co zrobic dalej."""
    if not zlecenia.dostepne():
        raise HTTPException(404, "Ta instalacja nie sklada zlecen")
    _odnotuj_pomocnika(request)
    if not zlecenia.wynik(zlecenie):
        raise HTTPException(404, "Nie ma takiego zlecenia albo stracilo waznosc")
    try:
        with tokenomia.akcja("asystent_krok", 1, f"zlecenie {zlecenie}"):
            krok = bedrock.nastepny_krok(widok.cel, widok.stan, widok.kroki)
    except bedrock.Przeciazenie as blad:
        raise HTTPException(503, str(blad), headers={"Retry-After": "30"})
    # W logach rodzaj czynnosci, nigdy tresc strony - ta niesie dane stron.
    log.info("zlecenie %s: krok %s", zlecenie, krok.get("akcja") or "brak")
    return krok


def _odnotuj_pomocnika(request: Request, wersja: str = "") -> None:
    """Obecnosc komputera z wlasnym tokenem albo - dawniej - calej kancelarii."""
    komputer = getattr(request.state, "komputer", None)
    if komputer:
        urzadzenia.odnotuj(magazyn.kancelaria(), komputer, wersja)
    else:
        zlecenia.odnotuj_pomocnika(wersja)


def _pomocnik_pod_reka() -> bool:
    if not zlecenia.dostepne():
        return False
    return zlecenia.pomocnik_aktywny() or urzadzenia.aktywny(magazyn.kancelaria())


@app.get("/api/pomocnik/zlecenia")
def zlecenia_dla_pomocnika(request: Request, wersja: str = ""):
    """Pomocnik pyta o robote.

    Samo zapytanie jest znakiem, ze jest pod reka - dlatego odnotowujemy je
    jako obecnosc. Gdy pomocnik zamilknie, przycisk sprawdzenia gasnie sam.
    """
    if not zlecenia.dostepne():
        raise HTTPException(404, "Ta instalacja nie sklada zlecen")
    _odnotuj_pomocnika(request, wersja)
    return zlecenia.czekajace()


# --- laczenie pomocnika z kancelaria ---------------------------------------
# Pomocnik prosi o kod, notariusz klika "Polacz" w zalogowanej notarai,
# pomocnik odbiera wlasny token. Nikt niczego nie przepisuje. Szczegoly i
# zabezpieczenia w urzadzenia.py.


class NazwaKomputera(BaseModel):
    nazwa: str = ""


class OdbiorTokenu(BaseModel):
    sekret: str


class KodPolaczenia(BaseModel):
    kod: str


def _wymagaj_urzadzen() -> None:
    if not urzadzenia.dostepne():
        raise HTTPException(404, "Pomocnik działa tylko z notarai w chmurze.")


@app.post("/api/pomocnik/parowanie", status_code=201)
def parowanie_start(request: Request, dane: NazwaKomputera):
    _wymagaj_urzadzen()
    ip = autoryzacja.adres_klienta(request)
    if not urzadzenia.wolno(ip):
        raise HTTPException(429, "Za dużo prób łączenia. Spróbuj za kilka minut.")
    return urzadzenia.rozpocznij(dane.nazwa, ip)


@app.post("/api/pomocnik/parowanie/{kod}")
def parowanie_odbior(kod: str, dane: OdbiorTokenu):
    """Pomocnik dopytuje. 202 - czekamy na notariusza, 200 - jest token."""
    _wymagaj_urzadzen()
    try:
        wynik = urzadzenia.odbierz(kod, dane.sekret)
    except urzadzenia.BladParowania as blad:
        raise HTTPException(410, str(blad))
    if wynik is None:
        return JSONResponse({"stan": "czeka"}, status_code=202)
    return wynik


@app.post("/api/pomocnik/odlacz")
def pomocnik_odlacza_sie(request: Request):
    """Pomocnik odlacza swoj komputer (np. przed oddaniem laptopa)."""
    _wymagaj_urzadzen()
    komputer = getattr(request.state, "komputer", None)
    if komputer:
        urzadzenia.odlacz(magazyn.kancelaria(), komputer)
    return {"odlaczono": bool(komputer)}


@app.get("/api/urzadzenia/kod/{kod}")
def parowanie_opis(kod: str):
    """Co zobaczy notariusz przed kliknieciem Polacz."""
    _wymagaj_urzadzen()
    try:
        return urzadzenia.opis(kod, magazyn.kancelaria())
    except urzadzenia.BladParowania as blad:
        raise HTTPException(410, str(blad))


@app.get("/api/urzadzenia/oczekujace")
def oczekujace_urzadzenia(request: Request):
    """Pomocnicy z tej sieci, ktorzy czekaja na Polacz. Kreator pyta o to sam."""
    _wymagaj_urzadzen()
    return urzadzenia.oczekujace(autoryzacja.adres_klienta(request))


_POBIERZ = Path(__file__).parent / "static" / "pobierz"


def _pomocnik_do_pobrania() -> dict | None:
    """Plik buduje infra/zbuduj-pomocnika.ps1. Bez niego kreator mowi, ze
    pomocnik jest w przygotowaniu, zamiast podsuwac zepsuty odnosnik."""
    plik = _POBIERZ / "notarai-pomocnik.exe"
    if not plik.exists():
        return None
    try:
        opis = json.loads((_POBIERZ / "notarai-pomocnik.json").read_text("utf-8-sig"))
    except (OSError, ValueError):
        opis = {}
    return {"adres": "/static/pobierz/notarai-pomocnik.exe",
            "wersja": opis.get("wersja", ""), "sha256": opis.get("sha256", ""),
            "rozmiar_mb": round(plik.stat().st_size / 1024 / 1024, 1)}


@app.post("/api/urzadzenia/polacz")
def parowanie_potwierdz(request: Request, dane: KodPolaczenia):
    _wymagaj_urzadzen()
    try:
        return urzadzenia.potwierdz(dane.kod, magazyn.kancelaria(),
                                    autoryzacja.adres_klienta(request))
    except urzadzenia.BladParowania as blad:
        raise HTTPException(409, str(blad))


@app.get("/api/urzadzenia")
def lista_urzadzen():
    """Komputery z pomocnikiem i to, czy ktorys jest teraz pod reka.

    Interfejs pyta o to co kilkanascie sekund, wiec przycisk sprawdzenia w
    rejestrze i znaczek pomocnika zmieniaja sie same, bez odswiezania strony.
    """
    if not urzadzenia.dostepne():
        return {"dostepne": False, "polaczony": False, "urzadzenia": [], "pobierz": None}
    lista = urzadzenia.lista(magazyn.kancelaria())
    return {
        "dostepne": True,
        "polaczony": any(u["polaczony"] for u in lista) or zlecenia.pomocnik_aktywny(),
        "urzadzenia": lista,
        "pobierz": _pomocnik_do_pobrania(),
    }


@app.delete("/api/urzadzenia/{identyfikator}")
def odlacz_urzadzenie(identyfikator: str):
    _wymagaj_urzadzen()
    if not urzadzenia.odlacz(magazyn.kancelaria(), identyfikator):
        raise HTTPException(404, "Nie ma takiego komputera")
    return {"odlaczono": True}


@app.post("/api/pomocnik/zlecenia/{zlecenie}/wynik")
def wynik_od_pomocnika(request: Request, zlecenie: str, raport: RaportPomocnika):
    """Pomocnik skonczyl. Jego wpisy trafiaja do sladu audytowego sprawy."""
    if not zlecenia.dostepne():
        raise HTTPException(404, "Ta instalacja nie sklada zlecen")
    _odnotuj_pomocnika(request)
    stan = zlecenia.wynik(zlecenie)
    if not stan:
        raise HTTPException(404, "Nie ma takiego zlecenia albo stracilo waznosc")

    identyfikator = stan["sprawa"]
    katalog = _katalog_sprawy(identyfikator)
    zapisane = 0
    for wpis in raport.sprawdzenia:
        try:
            wynik = rejestry.WynikSprawdzenia(
                rejestr=wpis.rejestr,
                zapytanie=rejestry.maskuj_pesel(wpis.pesel),
                status=wpis.status,
                szczegoly=wpis.szczegoly,
                zrodlo=wpis.zrodlo,
                etykieta=wpis.etykieta,
            )
        except ValueError as blad:
            raise HTTPException(400, str(blad))
        rejestry.zapisz_sprawdzenie(identyfikator, wynik)
        zapisane += 1
    if zapisane:
        magazyn.utrwal_sprawe(katalog)
    zlecenia.zapisz_wynik(zlecenie, {"zapisano": zapisane, "bledy": raport.bledy})
    log.info("zlecenie %s: raport przyjety, wpisow=%d bledow=%d",
             zlecenie, zapisane, len(raport.bledy))
    return {"stan": "wykonane", "zapisano": zapisane}


@app.get("/api/sprawy/{identyfikator}/sprawdzenia/pliki/{nazwa}")
def plik_sprawdzenia(identyfikator: str, nazwa: str):
    katalog = _katalog_sprawy(identyfikator) / "sprawdzenia"
    if not re.fullmatch(r"[a-z0-9_\-]+\.png", nazwa):
        raise HTTPException(400, "Nieprawidlowa nazwa pliku")
    plik = katalog / nazwa
    if not plik.exists():
        raise HTTPException(404, "Brak pliku")
    return FileResponse(plik, media_type="image/png")


def _katalog_sprawy(identyfikator: str) -> Path:
    if not identyfikator.isalnum():
        raise HTTPException(400, "Nieprawidlowy identyfikator sprawy")
    katalog = config.SPRAWY / identyfikator
    if not magazyn.pobierz_sprawe(katalog):
        raise HTTPException(404, "Nie znaleziono sprawy")
    return katalog


def _zapisz(plik: UploadFile, cel: Path) -> None:
    with cel.open("wb") as wyjscie:
        shutil.copyfileobj(plik.file, wyjscie)


def _zwaliduj(pola: list[dict]) -> list[dict]:
    wynik = []
    for pole in pola:
        nazwa = str(pole.get("nazwa", "")).strip()
        wartosc = pole.get("wartosc")
        poprawne, komentarz = walidacja.sprawdz_pole(nazwa, wartosc or "")
        wymaga_uwagi = (
            poprawne is False
            or wartosc in (None, "")
            or pole.get("pewnosc") == "niska"
        )
        wynik.append(
            {
                "nazwa": nazwa,
                "wartosc": wartosc,
                "zrodlo": pole.get("zrodlo", ""),
                "pewnosc": pole.get("pewnosc", "wysoka"),
                "uwaga": pole.get("uwaga", ""),
                "walidacja": komentarz,
                "walidacja_ok": poprawne,
                "wymaga_uwagi": wymaga_uwagi,
            }
        )
    return wynik


if __name__ == "__main__":
    import uvicorn

    print(f"\n  pieczapp  ->  http://{config.HOST}:{config.PORT}")
    print(f"  model: {config.MODEL}")
    print(f"  region: {config.REGION}\n")
    if os.getenv("PIECZAPP_AML_LISTY", "1") != "0":
        aml_listy.odswiezaj_w_tle()   # listy sankcyjne i PEP, co 6 h
    uvicorn.run(app, host=config.HOST, port=config.PORT, access_log=False)
