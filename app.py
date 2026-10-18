"""pieczapp - lokalny asystent kancelarii notarialnej.

Uruchomienie:  python app.py
Adres:         http://127.0.0.1:8000
"""
import base64
import json
import logging
import re
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import bedrock
import config
import dokumenty
import formularze
import krz
import urzadzenia
import zlecenia
import magazyn
import autoryzacja
import nazwy
import prompty
import rejestry
import transkrypcja
import walidacja

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("pieczapp")

app = FastAPI(title="pieczapp", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

# Tryb SaaS: token kancelarii na /api/* + panel admina. W trybie lokalnym
# middleware przepuszcza wszystko, a panel admina wymaga PIECZAPP_ADMIN_TOKEN.
app.middleware("http")(autoryzacja.middleware)
app.include_router(autoryzacja.router)
app.include_router(autoryzacja.router_logowania)


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


def _przetworz(sciezka_wzoru: Path, sciezki_skanow: list[Path], polecenie: str,
               etykieta: str) -> dict:
    """Wspolna czesc: analiza wzoru, odczyt skanow, pierwsza tura rozmowy.

    Nie zapisuje niczego trwale - zapis (albo jego brak) nalezy do funkcji
    wywolujacej. `etykieta` trafia tylko do logow, nigdy dane osobowe.
    """
    tekst_wzoru = dokumenty.wzor_na_tekst(sciezka_wzoru)
    analiza = dokumenty.analizuj_wzor(tekst_wzoru)
    pola_wzoru = analiza["pola"]
    strony = dokumenty.strony_ze_skanow(sciezki_skanow)

    log.info("%s: wzor=%s pol=%d legenda=%d warianty=%d stron=%d",
             etykieta, sciezka_wzoru.name, len(pola_wzoru),
             len(analiza["legenda"]), analiza["warianty"], len(strony))

    try:
        odczyt = bedrock.odczytaj_dane(strony, pola_wzoru, polecenie, analiza["legenda"])
    except bedrock.Przeciazenie as blad:
        raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("%s: blad odczytu (%s)", etykieta, type(blad).__name__)
        raise HTTPException(502, f"Bedrock: {blad}")

    pola = _zwaliduj(odczyt.get("pola", []))
    kontekst = prompty.kontekst_rozmowy(
        pola, odczyt.get("braki", []), odczyt.get("rozbieznosci", []), polecenie
    )
    try:
        pytania = bedrock.rozmawiaj(kontekst, [], None)
    except Exception as blad:
        log.error("%s: blad pytan wstepnych (%s)", etykieta, type(blad).__name__)
        pytania = ("Nie udalo sie przygotowac pytan. Mozesz pisac do mnie ponizej "
                   "albo od razu sporzadzic projekt.")

    return {
        "analiza": analiza,
        "pola_wzoru": pola_wzoru,
        "pola": pola,
        "braki": odczyt.get("braki", []),
        "rozbieznosci": odczyt.get("rozbieznosci", []),
        "stron": len(strony),
        "kontekst": kontekst,
        "rozmowa": [{"rola": "asystent", "tresc": pytania,
                     "czas": datetime.now().isoformat(timespec="seconds")}],
    }


@app.post("/api/sprawy")
async def nowa_sprawa(
    wzor: UploadFile = File(...),
    skany: list[UploadFile] = File(...),
    polecenie: str = Form(""),
    sygnatura: str = Form(""),
):
    """Wgranie wzoru i skanow, odczyt danych. Sprawa zostaje w magazynie."""
    if magazyn.u_klienta():
        raise HTTPException(409, (
            "Ta kancelaria trzyma pliki u siebie. Uzyj /api/odczyt, ktore niczego "
            "nie zapisuje."
        ))
    identyfikator = uuid.uuid4().hex[:12]
    katalog = config.SPRAWY / identyfikator
    (katalog / "skany").mkdir(parents=True)

    sciezka_wzoru = katalog / f"wzor{Path(wzor.filename).suffix.lower()}"
    _zapisz(wzor, sciezka_wzoru)

    sciezki_skanow = []
    for skan in skany:
        cel = katalog / "skany" / Path(skan.filename).name
        _zapisz(skan, cel)
        sciezki_skanow.append(cel)

    try:
        wynik = _przetworz(sciezka_wzoru, sciezki_skanow, polecenie,
                           f"sprawa {identyfikator}")
    except ValueError as blad:
        shutil.rmtree(katalog, ignore_errors=True)
        raise HTTPException(400, str(blad))
    except HTTPException:
        shutil.rmtree(katalog, ignore_errors=True)
        raise

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
        "pola_wzoru": wynik["pola_wzoru"],
        "legenda": analiza["legenda"],
        "warianty": analiza["warianty"],
    })
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
    }


# --- praca bez zapisu: pliki zostaja u kancelarii --------------------------
# Te punkty nie tworza sprawy i nic nie zapisuja. Pliki przychodza z dysku
# notariusza przy kazdym zadaniu, a wyniki wracaja do przegladarki, ktora
# zapisuje je z powrotem u niego. Serwer pracuje w katalogu tymczasowym,
# kasowanym zawsze, takze po bledzie.


@app.post("/api/odczyt")
async def odczyt_bez_zapisu(
    wzor: UploadFile = File(...),
    skany: list[UploadFile] = File(...),
    polecenie: str = Form(""),
):
    """Odczyt skanow bez tworzenia sprawy. Nic nie zostaje na serwerze."""
    with tempfile.TemporaryDirectory(prefix="notarai-") as tymczasowy:
        katalog = Path(tymczasowy)
        (katalog / "skany").mkdir()
        sciezka_wzoru = katalog / f"wzor{Path(wzor.filename).suffix.lower()}"
        _zapisz(wzor, sciezka_wzoru)
        sciezki_skanow = []
        for skan in skany:
            cel = katalog / "skany" / Path(skan.filename).name
            _zapisz(skan, cel)
            sciezki_skanow.append(cel)

        try:
            wynik = _przetworz(sciezka_wzoru, sciezki_skanow, polecenie, "odczyt bez zapisu")
        except ValueError as blad:
            raise HTTPException(400, str(blad))

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


@app.post("/api/projekt")
async def projekt_bez_zapisu(
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

    with tempfile.TemporaryDirectory(prefix="notarai-") as tymczasowy:
        katalog = Path(tymczasowy)
        sciezka_wzoru = katalog / f"wzor{Path(wzor.filename).suffix.lower()}"
        _zapisz(wzor, sciezka_wzoru)
        analiza = dokumenty.analizuj_wzor(dokumenty.wzor_na_tekst(sciezka_wzoru))
        try:
            projekt = bedrock.sporzadz_projekt(
                analiza["tresc"], lista_pol, polecenie, analiza["legenda"], historia
            )
        except bedrock.Przeciazenie as blad:
            raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
        except Exception as blad:
            log.error("projekt bez zapisu: blad generowania (%s)", type(blad).__name__)
            raise HTTPException(502, f"Bedrock: {blad}")

        cel = katalog / "projekt.docx"
        dokumenty.tekst_na_docx(projekt, cel)
        dane = cel.read_bytes()

    log.info("projekt bez zapisu: znakow=%d", len(projekt))
    # Tekst do podgladu w przegladarce, plik do zapisania na dysku notariusza.
    return {
        "tekst": projekt,
        "brakujace": projekt.count("<<BRAK:"),
        "do_wyboru": projekt.count("<<WYBOR:"),
        "docx": base64.b64encode(dane).decode("ascii"),
    }


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
        odpowiedz = bedrock.rozmawiaj(zadanie.kontekst, zadanie.historia, tresc)
    except bedrock.Przeciazenie as blad:
        raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("rozmowa bez zapisu: blad (%s)", type(blad).__name__)
        raise HTTPException(502, f"Bedrock: {type(blad).__name__}")
    return {"odpowiedz": odpowiedz}


class ZadanieGenerowania(BaseModel):
    pola: list[dict]
    polecenie: str = ""
    z_rozmowa: bool = True


@app.post("/api/sprawy/{identyfikator}/projekt")
def generuj_projekt(identyfikator: str, zadanie: ZadanieGenerowania):
    """Wypelnienie wzoru zatwierdzonymi danymi."""
    katalog = _katalog_sprawy(identyfikator)
    sciezka_wzoru = next(katalog.glob("wzor.*"), None)
    if sciezka_wzoru is None:
        raise HTTPException(404, "Brak wzoru w tej sprawie")

    analiza = dokumenty.analizuj_wzor(dokumenty.wzor_na_tekst(sciezka_wzoru))
    rozmowa = _wczytaj_rozmowe(katalog) if zadanie.z_rozmowa else []
    try:
        projekt = bedrock.sporzadz_projekt(
            analiza["tresc"], zadanie.pola, zadanie.polecenie, analiza["legenda"], rozmowa
        )
    except bedrock.Przeciazenie as blad:
        raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("sprawa %s: blad generowania (%s)", identyfikator, type(blad).__name__)
        raise HTTPException(502, f"Bedrock: {blad}")

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
    magazyn.utrwal_sprawe(katalog)
    log.info("sprawa %s: projekt zapisany", identyfikator)

    return {
        "tekst": projekt,
        "brakujace": projekt.count("<<BRAK:"),
        "do_wyboru": projekt.count("<<WYBOR:"),
        "plik": f"/api/sprawy/{identyfikator}/plik",
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
        odpowiedz = bedrock.rozmawiaj(kontekst, rozmowa, tresc)
    except bedrock.Przeciazenie as blad:
        raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("sprawa %s: blad rozmowy (%s)", identyfikator, type(blad).__name__)
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
        log.error("transkrypcja: blad (%s)", type(blad).__name__)
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
        wynik = formularze.dopasuj(
            mapowanie, zadanie.tekst_aktu, pola_sprawy,
            model=bedrock.wyciagnij_do_formularza,
        )
    except bedrock.Przeciazenie as blad:
        raise HTTPException(503, str(blad), headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("formularz %s: blad dopasowania (%s)", system, type(blad).__name__)
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
                log.error("sprawa %s: KRZ blad (%s)", identyfikator, type(blad).__name__)
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
    uvicorn.run(app, host=config.HOST, port=config.PORT, access_log=False)
