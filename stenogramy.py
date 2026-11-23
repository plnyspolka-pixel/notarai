"""Stenogram odczytania aktu: telefon na stole nagrywa, przy sprawie zostaje
zanonimizowany tekst. Nagrania nie przechowujemy.

Przebieg:
  1. przeglądarka (static/stenogramy.html) nagrywa mowę (Opus ok. 24 kb/s)
     i co 15 s wysyła fragment: PUT /api/stenogramy/{id}/czesci/{nr}.
     Co 50 minut zaczyna nową „sesję” (samodzielny plik), bo jedno zadanie
     rozpoznawania mowy ma limit długości,
  2. POST .../koniec skleja fragmenty w pliki sesji (robocze, w buckecie
     kancelarii) i uruchamia przetwarzanie w tle,
  3. rozpoznawanie mowy: AWS Transcribe w eu-central-1 (tryb S3) albo
     faster-whisper na stanowisku lokalnym,
  4. anonimizacja (anonimizacja.py). Surowy tekst jest tylko w pamięci,
  5. zanonimizowany stenogram trafia do załączników sprawy
     (sprawy/{id}/zalaczniki/stenogram-....txt) i z nimi do S3,
  6. audio, wynik Transcribe i zadanie Transcribe są usuwane.

Transcribe ruszy dopiero, gdy właściciel potwierdzi, że na koncie AWS jest
polityka rezygnacji z używania treści do ulepszania usług AI
(PIECZAPP_TRANSCRIBE_OPTOUT=1). Bez niej AWS może przechowywać nagrania
stron do uczenia modeli.

W spisie jest, kto rozpoczął stenogram i kiedy.
RODO: w logach są tylko identyfikatory i liczby.
"""
import contextvars
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

import anonimizacja
import bedrock
import config
import magazyn
import transkrypcja

log = logging.getLogger("pieczapp.stenogramy")

router = APIRouter(prefix="/api/stenogramy", tags=["stenogramy"])

PLIK_SPISU = "stenogramy"
ZALACZNIKI = "zalaczniki"          # ten sam katalog co app.ZALACZNIKI
MAX_CZESC = 8 * 1024 * 1024
MAX_CZESCI = 3000                  # 3000 x 15 s = 12,5 h
MAX_SESJI = 15
TYPY = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a"}
FORMAT_TRANSCRIBE = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a"}
PORZUCONE_PO_S = 48 * 3600         # niedokończone nagranie: fragmenty kasujemy po 2 dobach
PRZEJECIE_PO_S = 30 * 60           # przetwarzanie, które utknęło (restart kontenera), podejmuje ktoś inny
CZEKAJ_S = 10                      # odpytywanie Transcribe
MAX_CZEKANIA_S = 3 * 3600
_ID = re.compile(r"[0-9a-f]{16}")
_STREFA = ZoneInfo("Europe/Warsaw")


class Start(BaseModel):
    sprawa: str
    sygnatura: str = ""
    typ: str = "audio/webm"


class Sesja(BaseModel):
    od: int
    do: int
    czas_s: float = 0


class Koniec(BaseModel):
    sesje: list[Sesja]


# --- silnik rozpoznawania mowy -----------------------------------------------

def silnik() -> str | None:
    """"transcribe", "whisper" albo None (nie ma czym rozpoznać mowy)."""
    wybor = os.getenv("PIECZAPP_STENOGRAM_SILNIK", "").strip().lower()
    if wybor in ("", "transcribe") and magazyn.TRYB == "s3":
        return "transcribe" if os.getenv("PIECZAPP_TRANSCRIBE_OPTOUT", "") == "1" else None
    if wybor in ("", "whisper") and transkrypcja.dostepna():
        return "whisper"
    return None


def _wymagaj_silnika() -> str:
    nazwa = silnik()
    if nazwa is None:
        raise HTTPException(503, "Stenogramy nie są jeszcze włączone w tej instalacji. "
                                 "Administrator znajdzie opis w SAAS.md (sekcja o stenogramach).")
    return nazwa


_transcribe = None   # klient boto3, podmienialny w testach


def _klient_transcribe():
    global _transcribe
    if _transcribe is None:
        import boto3
        _transcribe = boto3.client("transcribe", region_name=os.getenv("AWS_REGION", "eu-central-1"))
    return _transcribe


def _nazwa_zadania(id_s: str, sesja: int, proba: int) -> str:
    return re.sub(r"[^0-9A-Za-z._-]", "-", f"notarai-{magazyn.kancelaria()}-{id_s}-{sesja}-{proba}")[:200]


def zadanie_transcribe(id_s: str, sesja: int, proba: int, wzgledna_audio: str, typ: str) -> dict:
    """Parametry StartTranscriptionJob (osobno, żeby test sprawdził je z botocore)."""
    wyjscie = f"{magazyn.PREFIKS}/{magazyn.kancelaria()}/{_robocze(id_s)}/transkrypcja-{sesja}-{proba}.json"
    zadanie = {
        "TranscriptionJobName": _nazwa_zadania(id_s, sesja, proba),
        "LanguageCode": "pl-PL",
        "MediaFormat": FORMAT_TRANSCRIBE[typ],
        "Media": {"MediaFileUri": f"s3://{magazyn.BUCKET}/{magazyn.PREFIKS}/{magazyn.kancelaria()}/{wzgledna_audio}"},
        # Wynik do NASZEGO bucketa, żeby dało się go na pewno skasować.
        "OutputBucketName": magazyn.BUCKET,
        "OutputKey": wyjscie,
    }
    if magazyn.KMS_KLUCZ:
        zadanie["OutputEncryptionKMSKeyId"] = magazyn.KMS_KLUCZ
    if proba == 0:
        # Rozróżnianie mówców. Gdyby dla polskiego zadanie z nim padło, druga próba idzie bez.
        zadanie["Settings"] = {"ShowSpeakerLabels": True, "MaxSpeakerLabels": 10}
    return zadanie


def _stan_zadania(klient, nazwa: str) -> dict | None:
    try:
        return klient.get_transcription_job(TranscriptionJobName=nazwa)["TranscriptionJob"]
    except Exception as blad:  # noqa: BLE001
        kod = str(getattr(blad, "response", {}).get("Error", {}).get("Code", ""))
        if kod in ("BadRequestException", "NotFoundException"):
            return None
        raise


def _transcribe_sesji(id_s: str, sesja: int, wzgledna_audio: str, typ: str) -> tuple[list[dict], list[str]]:
    """Segmenty jednej sesji i nazwy zadań do skasowania po zapisaniu stenogramu."""
    klient = _klient_transcribe()
    zadania = []
    for proba in (0, 1):
        parametry = zadanie_transcribe(id_s, sesja, proba, wzgledna_audio, typ)
        nazwa = parametry["TranscriptionJobName"]
        zadania.append(nazwa)
        stan = _stan_zadania(klient, nazwa)
        if stan is None:   # zadanie mogło już ruszyć przed restartem kontenera
            klient.start_transcription_job(**parametry)
        poczatek = time.monotonic()
        while True:
            stan = _stan_zadania(klient, nazwa) or {}
            status = stan.get("TranscriptionJobStatus")
            if status in ("COMPLETED", "FAILED"):
                break
            if time.monotonic() - poczatek > MAX_CZEKANIA_S:
                raise TimeoutError("Rozpoznawanie mowy trwa zbyt długo.")
            time.sleep(CZEKAJ_S)
        if status == "COMPLETED":
            surowe = magazyn.czytaj_obiekt(parametry["OutputKey"].split("/", 2)[2])
            if surowe is None:
                raise RuntimeError("Brak wyniku rozpoznawania mowy w buckecie.")
            return segmenty_transcribe(json.loads(surowe)), zadania
        # Powód porażki z AWS nie zawiera treści nagrania.
        log.warning("stenogram %s: zadanie Transcribe (proba %d) nieudane: %s",
                    id_s, proba, stan.get("FailureReason", "?"))
    raise RuntimeError("Rozpoznawanie mowy nie powiodło się.")


def segmenty_transcribe(dane: dict) -> list[dict]:
    """Wynik Transcribe -> [{start, mowca, tekst}], kolejne słowa tego samego mówcy razem."""
    wyniki = dane.get("results", {})
    segmenty: list[dict] = []
    for item in wyniki.get("items", []):
        slowo = ((item.get("alternatives") or [{}])[0].get("content") or "").strip()
        if not slowo:
            continue
        if item.get("type") == "punctuation":
            if segmenty:
                segmenty[-1]["tekst"] += slowo
            continue
        mowca = item.get("speaker_label") or ""
        if segmenty and segmenty[-1]["mowca"] == mowca:
            segmenty[-1]["tekst"] += " " + slowo
        else:
            segmenty.append({"start": float(item.get("start_time") or 0), "mowca": mowca, "tekst": slowo})
    if not segmenty:
        tekst = " ".join(t.get("transcript", "") for t in wyniki.get("transcripts", [])).strip()
        if tekst:
            segmenty.append({"start": 0.0, "mowca": "", "tekst": tekst})
    for s in segmenty:   # "spk_0" -> "Mówca 1"
        m = re.fullmatch(r"spk_(\d+)", s["mowca"])
        s["mowca"] = f"Mówca {int(m.group(1)) + 1}" if m else s["mowca"]
    return segmenty


def _whisper_sesji(wzgledna_audio: str) -> list[dict]:
    sciezka = magazyn.pobierz_plik(wzgledna_audio)
    if sciezka is None:
        raise RuntimeError("Brak pliku sesji nagrania.")
    return transkrypcja.segmenty_pliku(sciezka)


# --- spis --------------------------------------------------------------------

def _teraz() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bez_chmury() -> None:
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie, a stenogram zapisuje się "
                                 "przy sprawie na serwerze. Ta funkcja jest dla niej wyłączona.")


def _sprawdz_id(id_s: str) -> str:
    if not _ID.fullmatch(id_s):
        raise HTTPException(400, "Nieprawidłowy identyfikator stenogramu.")
    return id_s


def _spis() -> list[dict]:
    return magazyn.wczytaj_plik_kancelarii(PLIK_SPISU, [])


def _wpis(id_s: str) -> dict:
    for wpis in _spis():
        if wpis["id"] == id_s:
            return wpis
    raise HTTPException(404, "Nie ma takiego stenogramu.")


def _zmien_wpis(id_s: str, zmiana) -> dict:
    def _zmien(spis):
        for wpis in spis:
            if wpis["id"] == id_s:
                wynik = zmiana(wpis)
                return dict(wpis) if wynik is None else wynik
        raise HTTPException(404, "Nie ma takiego stenogramu.")
    return magazyn.zmien_plik_kancelarii(PLIK_SPISU, _zmien, [])


def _robocze(id_s: str) -> str:
    return f"stenogramy-robocze/{id_s}"


def _czesc(id_s: str, nr: int) -> str:
    return f"{_robocze(id_s)}/czesci/{nr:05d}"


def _katalog_sprawy(sprawa: str):
    if not sprawa or not sprawa.isalnum():
        raise HTTPException(400, "Nieprawidłowy identyfikator sprawy.")
    katalog = config.SPRAWY / sprawa
    if not magazyn.pobierz_sprawe(katalog):
        raise HTTPException(404, "Nie ma takiej sprawy.")
    return katalog


# --- przetwarzanie -------------------------------------------------------------

def _czas(s: float) -> str:
    s = int(max(0, s))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}"


def tresc_stenogramu(wpis: dict, segmenty: list[dict]) -> str:
    kiedy = datetime.fromisoformat(wpis["utworzono"]).astimezone(_STREFA)
    naglowek = ["STENOGRAM ODCZYTANIA AKTU"]
    if wpis.get("sygnatura"):
        naglowek.append(f"Repertorium A nr {wpis['sygnatura']}")
    naglowek += [
        f"Odczytanie: {kiedy:%d.%m.%Y}, godz. {kiedy:%H:%M}",
        f"Czas odczytania: {_czas(wpis.get('czas_s', 0))}",
        "",
        "Dane osobowe zamaskowano: w słowach zostaje pierwsza i ostatnia litera (np. J*n S*****k),",
        "w numerach dwie pierwsze i dwie ostatnie cyfry (np. PESEL 80*******45).",
        "Tekst powstał z automatycznego rozpoznawania mowy i może zawierać błędy.",
        "Nie jest protokołem ani częścią aktu. Dźwięk usunięto po spisaniu.",
        "",
    ]
    linie = [f"[{_czas(s['start'])}] " + (f"{s['mowca']}: " if s["mowca"] else "") + s["tekst"]
             for s in segmenty]
    return "\n".join(naglowek + linie) + "\n"


def _przejmij(id_s: str) -> dict | None:
    """Rezerwuje przetwarzanie dla tej kopii aplikacji; None = ktoś już to robi."""
    def _zmiana(w):
        if w["stan"] != "przetwarzanie":
            return {}
        od = w.get("przetwarza_od")
        if od and (datetime.now(timezone.utc) - datetime.fromisoformat(od)).total_seconds() < PRZEJECIE_PO_S:
            return {}
        w["przetwarza_od"] = _teraz()
        return dict(w)
    wynik = _zmien_wpis(id_s, _zmiana)
    return wynik or None


def przetworz(id_s: str) -> None:
    """Nagranie -> zanonimizowany stenogram przy sprawie. Wolno wołać wielokrotnie."""
    wpis = _przejmij(id_s)
    if wpis is None:
        return
    try:
        nazwa_silnika = silnik()
        if nazwa_silnika is None:
            raise RuntimeError("Brak silnika rozpoznawania mowy.")
        segmenty, zadania, przesuniecie = [], [], 0.0
        for nr, sesja in enumerate(wpis["sesje"]):
            audio = f"{_robocze(id_s)}/sesja-{nr}{TYPY[wpis['typ']]}"
            if nazwa_silnika == "transcribe":
                czesc, nazwy = _transcribe_sesji(id_s, nr, audio, wpis["typ"])
                zadania += nazwy
            else:
                czesc = _whisper_sesji(audio)
            segmenty += [{**s, "start": s["start"] + przesuniecie} for s in czesc]
            przesuniecie += sesja.get("czas_s", 0)

        katalog = _katalog_sprawy(wpis["sprawa"])
        anonimowe = anonimizacja.anonimizuj(segmenty, anonimizacja.znane_z_sprawy(katalog))
        del segmenty   # surowy tekst nie wychodzi poza pamięć
        kiedy = datetime.fromisoformat(wpis["utworzono"]).astimezone(_STREFA)
        nazwa = f"stenogram-{kiedy:%Y-%m-%d-%H%M}-{id_s[:6]}.txt"
        folder = katalog / ZALACZNIKI
        folder.mkdir(exist_ok=True)
        (folder / nazwa).write_text(tresc_stenogramu(wpis, anonimowe), encoding="utf-8")
        magazyn.utrwal_sprawe(katalog)

        def _gotowe(w):
            w.update(stan="gotowe", plik=f"{ZALACZNIKI}/{nazwa}", wypowiedzi=len(anonimowe),
                     zakonczono=_teraz())
            w.pop("przetwarza_od", None)
            w.pop("komunikat", None)
        _zmien_wpis(id_s, _gotowe)
        _sprzataj(id_s, zadania)
        log.info("stenogram %s: gotowy, %d wypowiedzi", id_s, len(anonimowe))
    except Exception as blad:  # noqa: BLE001 - stan błędu zamiast wiszącego przetwarzania
        log.error("stenogram %s: blad %s", id_s, type(blad).__name__)
        komunikat = (str(blad) if isinstance(blad, bedrock.Przeciazenie)
                     else "Nie udało się przygotować stenogramu. Spróbuj ponownie za chwilę.")

        def _blad(w):
            w.update(stan="blad", komunikat=komunikat)
            w.pop("przetwarza_od", None)
        try:
            _zmien_wpis(id_s, _blad)
        except Exception:  # noqa: BLE001
            log.error("stenogram %s: nie zapisano stanu bledu", id_s)


def _sprzataj(id_s: str, zadania: list[str]) -> None:
    """Audio i surowy wynik Transcribe znikają razem ze wszystkimi wersjami."""
    magazyn.usun_pliki(_robocze(id_s))
    if zadania:
        klient = _klient_transcribe()
        for nazwa in zadania:
            try:
                klient.delete_transcription_job(TranscriptionJobName=nazwa)
            except Exception:  # noqa: BLE001 - zadania mogło nie być (druga próba)
                pass


def _w_tle(id_s: str) -> None:
    kontekst = contextvars.copy_context()   # kancelaria bieżącego zapytania
    threading.Thread(target=kontekst.run, args=(przetworz, id_s), daemon=True,
                     name=f"stenogram-{id_s[:6]}").start()


def _porzadki(spis: list[dict]) -> None:
    """Porzucone nagrania (nikt ich nie zakończył przez 2 doby) i utknięte przetwarzanie."""
    teraz = datetime.now(timezone.utc)
    for w in spis:
        wiek = (teraz - datetime.fromisoformat(w["utworzono"])).total_seconds()
        if w["stan"] == "nagrywanie" and wiek > PORZUCONE_PO_S:
            magazyn.usun_pliki(_robocze(w["id"]))

            def _usun(s, id_s=w["id"]):
                s[:] = [x for x in s if x["id"] != id_s]
            magazyn.zmien_plik_kancelarii(PLIK_SPISU, _usun, [])
            log.info("stenogram %s: porzucone nagranie usuniete", w["id"])
        elif w["stan"] == "przetwarzanie":
            od = w.get("przetwarza_od")
            if not od or (teraz - datetime.fromisoformat(od)).total_seconds() >= PRZEJECIE_PO_S:
                _w_tle(w["id"])


# --- API ---------------------------------------------------------------------

@router.get("")
def lista(sprawa: str = ""):
    if magazyn.u_klienta():
        return {"wlaczone": False, "stenogramy": []}
    spis = _spis()
    _porzadki(spis)
    spis = [w for w in _spis() if not sprawa or w["sprawa"] == sprawa]
    spis.sort(key=lambda w: w.get("utworzono", ""), reverse=True)
    return {"wlaczone": silnik() is not None, "stenogramy": spis}


@router.post("")
def rozpocznij(dane: Start, request: Request):
    _bez_chmury()
    _wymagaj_silnika()
    typ = (dane.typ or "").split(";")[0].strip().lower()
    if typ not in TYPY:
        raise HTTPException(415, "Ta przeglądarka przesyła dźwięk w formacie, którego nie przyjmujemy. "
                                 "Użyj Chrome, Edge, Firefoksa albo Safari.")
    _katalog_sprawy(dane.sprawa)
    teraz = _teraz()
    wpis = {
        "id": uuid.uuid4().hex[:16],
        "sprawa": dane.sprawa,
        "sygnatura": dane.sygnatura.strip()[:60],
        "typ": typ,
        "stan": "nagrywanie",
        "utworzono": teraz,
        "rozpoczal": getattr(request.state, "email", None) or "stanowisko lokalne",
    }
    magazyn.zmien_plik_kancelarii(PLIK_SPISU, lambda spis: spis.append(wpis), [])
    log.info("stenogram %s: start nagrania", wpis["id"])
    return wpis


@router.put("/{id_s}/czesci/{nr}")
async def czesc(id_s: str, nr: int, request: Request):
    """Fragment nagrania. Ponowne wysłanie tego samego numeru nadpisuje fragment."""
    _bez_chmury()
    _sprawdz_id(id_s)
    if not 0 <= nr < MAX_CZESCI:
        raise HTTPException(400, "Odczytanie jest za długie.")
    if _wpis(id_s)["stan"] != "nagrywanie":
        raise HTTPException(409, "To odczytanie jest już zakończone.")
    dane = await request.body()
    if not dane:
        raise HTTPException(400, "Pusty fragment.")
    if len(dane) > MAX_CZESC:
        raise HTTPException(413, "Fragment dźwięku jest za duży.")
    wzgledna = _czesc(id_s, nr)
    plik = magazyn.katalog_kancelarii() / wzgledna
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_bytes(dane)
    magazyn.utrwal_plik(wzgledna)
    return {"nr": nr, "rozmiar": len(dane)}


@router.post("/{id_s}/koniec")
def zakoncz(id_s: str, dane: Koniec):
    """Sklejenie fragmentów w pliki sesji i start przetwarzania. Brakujące
    fragmenty = 409 z listą, żeby przeglądarka dosłała je ze swojej pamięci."""
    _bez_chmury()
    _sprawdz_id(id_s)
    wpis = _wpis(id_s)
    if wpis["stan"] != "nagrywanie":
        return wpis
    sesje = dane.sesje
    if not 0 < len(sesje) <= MAX_SESJI or sesje[0].od != 0 or any(
            s.do <= s.od or s.do > MAX_CZESCI for s in sesje) or any(
            a.do != b.od for a, b in zip(sesje, sesje[1:])):
        raise HTTPException(400, "Nieprawidłowy podział na fragmenty.")

    pliki, brakujace = {}, []
    for nr in range(sesje[-1].do):
        sciezka = magazyn.pobierz_plik(_czesc(id_s, nr))
        if sciezka is None:
            brakujace.append(nr)
        pliki[nr] = sciezka
    if brakujace:
        raise HTTPException(409, {"komunikat": "Brakuje fragmentów odczytania.", "brakujace": brakujace})

    rozmiar = 0
    for i, sesja in enumerate(sesje):
        wzgledna = f"{_robocze(id_s)}/sesja-{i}{TYPY[wpis['typ']]}"
        cel = magazyn.katalog_kancelarii() / wzgledna
        with cel.open("wb") as wyjscie:
            for nr in range(sesja.od, sesja.do):
                with pliki[nr].open("rb") as wejscie:
                    shutil.copyfileobj(wejscie, wyjscie)
        rozmiar += cel.stat().st_size
        magazyn.utrwal_plik(wzgledna)

    def _przetwarzaj(w):
        w.update(stan="przetwarzanie", sesje=[s.model_dump() for s in sesje],
                 czas_s=round(sum(max(s.czas_s, 0) for s in sesje), 1))
    wynik = _zmien_wpis(id_s, _przetwarzaj)
    # Sesje są już sklejone, fragmenty niepotrzebne.
    magazyn.usun_pliki(f"{_robocze(id_s)}/czesci")
    log.info("stenogram %s: nagranie zakonczone, %d sesji, %d kB", id_s, len(sesje), rozmiar // 1024)
    _w_tle(id_s)
    return wynik


@router.get("/{id_s}")
def stan(id_s: str):
    _bez_chmury()
    return _wpis(_sprawdz_id(id_s))


@router.post("/{id_s}/ponow")
def ponow(id_s: str):
    _bez_chmury()
    _sprawdz_id(id_s)
    _wymagaj_silnika()

    def _zmiana(w):
        if w["stan"] != "blad":
            raise HTTPException(409, "Ten stenogram nie czeka na ponowienie.")
        w.update(stan="przetwarzanie")
        w.pop("komunikat", None)
    wynik = _zmien_wpis(id_s, _zmiana)
    _w_tle(id_s)
    return wynik


@router.get("/{id_s}/tekst", response_class=PlainTextResponse)
def tekst(id_s: str):
    _bez_chmury()
    wpis = _wpis(_sprawdz_id(id_s))
    if wpis["stan"] != "gotowe":
        raise HTTPException(409, "Stenogram jeszcze się przygotowuje.")
    plik = _katalog_sprawy(wpis["sprawa"]) / wpis["plik"]
    if not plik.is_file():
        raise HTTPException(404, "Stenogram usunięto z plików sprawy.")
    return plik.read_text("utf-8")


@router.delete("/{id_s}")
def usun(id_s: str):
    _bez_chmury()
    wpis = _wpis(_sprawdz_id(id_s))
    magazyn.usun_pliki(_robocze(id_s))
    if wpis.get("plik"):
        try:
            katalog = _katalog_sprawy(wpis["sprawa"])
            if (katalog / wpis["plik"]).is_file():
                magazyn.usun_plik_sprawy(katalog, wpis["plik"])
        except HTTPException:
            pass   # sprawy już nie ma

    def _usun(spis):
        spis[:] = [w for w in spis if w["id"] != id_s]
    magazyn.zmien_plik_kancelarii(PLIK_SPISU, _usun, [])
    log.info("stenogram %s: usuniety", id_s)
    return {"usunieto": id_s}
