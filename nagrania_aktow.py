"""Nagrania odczytania aktu: telefon na stole, notariusz czyta akt, nagranie
trafia do kancelarii.

Przeglądarka (static/nagrania.html) nagrywa mowę kodekiem Opus, mono,
ok. 24 kb/s, czyli ok. 11 MB na godzinę. Co kilkanaście sekund wysyła
kolejny fragment: PUT /api/nagrania/{id}/czesci/{nr}. Padnięcie sieci
albo telefonu zabiera najwyżej ostatni fragment. Przeglądarka trzyma też
fragmenty u siebie, dopóki serwer ich nie przyjmie. Na końcu
POST /api/nagrania/{id}/koniec skleja fragmenty w jeden plik, liczy
SHA-256 (żeby dało się potem wykazać, że nagrania nikt nie zmienił)
i usuwa fragmenty.

Gdzie leżą pliki:
  chmura    - kancelarie/{kancelaria}/nagrania/{id}/nagranie.webm w buckecie
              spraw (Frankfurt, szyfrowany, wersjonowany), spis w pliku
              kancelarii "nagrania",
  urządzenie - serwer nic nie dostaje. Przeglądarka zapisuje plik na dysku
              notariusza (folder albo „Pobrane”). Kancelaria w trybie
              u-klienta ma tylko tę opcję, wtedy API odpowiada 409.

Bez potwierdzenia zgody na nagrywanie nagranie się nie zacznie, a zgoda
(kto potwierdził i kiedy) jest zapisana w spisie.

RODO: nagranie to treść aktu, w tym dane stron. W logach są tylko
identyfikator, liczba fragmentów, rozmiar i czas. Nigdy tytuł,
sygnatura ani nazwa sprawy, bo bywają nazwiskami.
"""
import hashlib
import logging
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

import magazyn

log = logging.getLogger("pieczapp.nagrania")

router = APIRouter(prefix="/api/nagrania", tags=["nagrania"])

PLIK_SPISU = "nagrania"
MAX_CZESC = 8 * 1024 * 1024          # 15 s Opusa to ok. 50 kB; zapas na inne kodeki
MAX_CZESCI = 3000                    # 3000 x 15 s = 12,5 h
MAX_TYTUL = 200
# Typy, które nagrywają przeglądarki: Chrome/Firefox/Android - WebM z Opusem,
# Safari na iPhonie - MP4 z AAC.
TYPY = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a"}
_ID = re.compile(r"[0-9a-f]{16}")


class Start(BaseModel):
    tytul: str = ""
    sygnatura: str = ""       # np. Rep. A nr 1234/2026
    sprawa: str = ""          # identyfikator sprawy w notarai, opcjonalny
    typ: str = "audio/webm"
    zgoda: bool = False


class Koniec(BaseModel):
    czesci: int
    czas_s: float = 0


def _teraz() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _typ(typ: str) -> str:
    podstawowy = (typ or "").split(";")[0].strip().lower()
    if podstawowy not in TYPY:
        raise HTTPException(415, "Ta przeglądarka nagrywa w formacie, którego nie przyjmujemy. "
                                 "Użyj Chrome, Edge, Firefoksa albo Safari.")
    return podstawowy


def _bez_chmury() -> None:
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie. Nagranie zapisuje się "
                                 "na urządzeniu, serwer niczego nie przechowuje.")


def _sprawdz_id(id_nagrania: str) -> str:
    if not _ID.fullmatch(id_nagrania):
        raise HTTPException(400, "Nieprawidłowy identyfikator nagrania.")
    return id_nagrania


def _spis() -> list[dict]:
    return magazyn.wczytaj_plik_kancelarii(PLIK_SPISU, [])


def _wpis(id_nagrania: str) -> dict:
    for wpis in _spis():
        if wpis["id"] == id_nagrania:
            return wpis
    raise HTTPException(404, "Nie ma takiego nagrania.")


def _zmien_wpis(id_nagrania: str, zmiana) -> dict:
    def _zmien(spis):
        for wpis in spis:
            if wpis["id"] == id_nagrania:
                zmiana(wpis)
                return dict(wpis)
        raise HTTPException(404, "Nie ma takiego nagrania.")
    return magazyn.zmien_plik_kancelarii(PLIK_SPISU, _zmien, [])


def _katalog(id_nagrania: str) -> str:
    return f"nagrania/{id_nagrania}"


def _czesc(id_nagrania: str, nr: int) -> str:
    return f"{_katalog(id_nagrania)}/czesci/{nr:05d}"


def _uporzadkuj(plik, typ: str) -> bool:
    """Plik z MediaRecorder nie ma długości ani indeksu, więc przewijanie
    w odtwarzaczu kuleje. Gdy jest ffmpeg, przepisujemy kontener bez zmiany
    dźwięku (-c copy). Bez ffmpeg plik zostaje taki, jak przyszedł."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    wynik = plik.with_name("uporzadkowane" + plik.suffix)
    try:
        subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(plik), "-c", "copy",
                        *(["-movflags", "+faststart"] if typ == "audio/mp4" else []), str(wynik)],
                       check=True, capture_output=True, timeout=600)
    except (subprocess.SubprocessError, OSError):
        wynik.unlink(missing_ok=True)
        log.warning("nagranie: ffmpeg nie uporzadkowal pliku, zostaje oryginal")
        return False
    wynik.replace(plik)
    return True


# --- API ---------------------------------------------------------------------

@router.get("")
def lista():
    if magazyn.u_klienta():
        return {"przechowywanie": "u-klienta", "nagrania": []}
    spis = sorted(_spis(), key=lambda w: w.get("utworzono", ""), reverse=True)
    return {"przechowywanie": "chmura", "nagrania": spis}


@router.post("")
def rozpocznij(dane: Start, request: Request):
    _bez_chmury()
    if not dane.zgoda:
        raise HTTPException(400, "Potwierdź, że osoby obecne przy akcie zgodziły się na nagrywanie.")
    typ = _typ(dane.typ)
    if dane.sprawa and not dane.sprawa.isalnum():
        raise HTTPException(400, "Nieprawidłowy identyfikator sprawy.")
    teraz = _teraz()
    wpis = {
        "id": uuid.uuid4().hex[:16],
        "tytul": dane.tytul.strip()[:MAX_TYTUL] or f"Nagranie z {teraz[:10]}",
        "sygnatura": dane.sygnatura.strip()[:MAX_TYTUL],
        "sprawa": dane.sprawa,
        "typ": typ,
        "stan": "nagrywanie",
        "utworzono": teraz,
        "zgoda": {"potwierdzil": getattr(request.state, "email", None) or "stanowisko lokalne",
                  "kiedy": teraz},
    }
    magazyn.zmien_plik_kancelarii(PLIK_SPISU, lambda spis: spis.append(wpis), [])
    log.info("nagranie %s: start", wpis["id"])
    return wpis


@router.put("/{id_nagrania}/czesci/{nr}")
async def czesc(id_nagrania: str, nr: int, request: Request):
    """Jeden fragment nagrania. Powtórne wysłanie tego samego numeru nadpisuje
    fragment, więc przeglądarka może bezpiecznie ponawiać."""
    _bez_chmury()
    _sprawdz_id(id_nagrania)
    if not 0 <= nr < MAX_CZESCI:
        raise HTTPException(400, "Nagranie jest za długie.")
    if _wpis(id_nagrania)["stan"] != "nagrywanie":
        raise HTTPException(409, "To nagranie jest już zakończone.")
    dane = await request.body()
    if not dane:
        raise HTTPException(400, "Pusty fragment.")
    if len(dane) > MAX_CZESC:
        raise HTTPException(413, "Fragment nagrania jest za duży.")
    wzgledna = _czesc(id_nagrania, nr)
    plik = magazyn.katalog_kancelarii() / wzgledna
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_bytes(dane)
    magazyn.utrwal_plik(wzgledna)
    return {"nr": nr, "rozmiar": len(dane)}


@router.post("/{id_nagrania}/koniec")
def zakoncz(id_nagrania: str, dane: Koniec):
    """Sklejenie fragmentów 0..czesci-1 w jeden plik. Brakujące fragmenty
    (np. z innej kopii aplikacji, której nie ma już w S3) = 409 z listą,
    żeby przeglądarka dosłała je ze swojej pamięci."""
    _bez_chmury()
    _sprawdz_id(id_nagrania)
    wpis = _wpis(id_nagrania)
    if wpis["stan"] == "gotowe":
        return wpis
    if not 0 < dane.czesci <= MAX_CZESCI:
        raise HTTPException(400, "Nagranie nie ma żadnego fragmentu.")
    sciezki, brakujace = [], []
    for nr in range(dane.czesci):
        sciezka = magazyn.pobierz_plik(_czesc(id_nagrania, nr))
        (sciezki if sciezka else brakujace).append(sciezka or nr)
    if brakujace:
        raise HTTPException(409, {"komunikat": "Brakuje fragmentów nagrania.", "brakujace": brakujace})

    rozszerzenie = TYPY[wpis["typ"]]
    wzgledna = f"{_katalog(id_nagrania)}/nagranie{rozszerzenie}"
    cel = magazyn.katalog_kancelarii() / wzgledna
    with cel.open("wb") as wyjscie:
        for sciezka in sciezki:
            with sciezka.open("rb") as wejscie:
                shutil.copyfileobj(wejscie, wyjscie)
    _uporzadkuj(cel, wpis["typ"])
    skrot = hashlib.sha256()
    with cel.open("rb") as plik:
        for kawalek in iter(lambda: plik.read(1024 * 1024), b""):
            skrot.update(kawalek)
    rozmiar = cel.stat().st_size
    magazyn.utrwal_plik(wzgledna)

    def _gotowe(w):
        w.update(stan="gotowe", plik=wzgledna, rozmiar=rozmiar, sha256=skrot.hexdigest(),
                 czas_s=round(max(dane.czas_s, 0), 1), zakonczono=_teraz())
    wynik = _zmien_wpis(id_nagrania, _gotowe)
    # Fragmenty są już w pliku. Kasujemy je dopiero po zapisaniu spisu.
    magazyn.usun_pliki(f"{_katalog(id_nagrania)}/czesci")
    log.info("nagranie %s: gotowe, %d fragmentow, %d kB", id_nagrania, dane.czesci, rozmiar // 1024)
    return wynik


@router.get("/{id_nagrania}/plik")
def plik(id_nagrania: str):
    _bez_chmury()
    _sprawdz_id(id_nagrania)
    wpis = _wpis(id_nagrania)
    if wpis["stan"] != "gotowe":
        raise HTTPException(409, "Nagranie jeszcze trwa albo nie zostało zakończone.")
    sciezka = magazyn.pobierz_plik(wpis["plik"])
    if sciezka is None:
        raise HTTPException(404, "Nie ma pliku nagrania.")
    # Nazwa pliku bez tytułu, bo tytuł bywa nazwiskiem i trafia do historii pobrań.
    return FileResponse(sciezka, media_type=wpis["typ"],
                        filename=f"nagranie-{wpis['utworzono'][:10]}-{id_nagrania[:6]}{sciezka.suffix}",
                        content_disposition_type="inline")


@router.delete("/{id_nagrania}")
def usun(id_nagrania: str):
    _bez_chmury()
    _sprawdz_id(id_nagrania)
    _wpis(id_nagrania)
    magazyn.usun_pliki(_katalog(id_nagrania))

    def _usun(spis):
        spis[:] = [w for w in spis if w["id"] != id_nagrania]
    magazyn.zmien_plik_kancelarii(PLIK_SPISU, _usun, [])
    log.info("nagranie %s: usuniete", id_nagrania)
    return {"usunieto": id_nagrania}
