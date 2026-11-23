"""Przeniesienie spraw z komputera kancelarii do chmury notarai.

Do 23.11.2026 kancelaria mogla wybrac tryb "u-klienta": sprawy w folderze na
komputerze notariusza, serwer niczego nie zapisywal. Tryb wycofano - nie
dzialal na telefonie ani na drugim komputerze. Teraz wszystkie sprawy leza
w chmurze (S3 we Frankfurcie, szyfrowane kluczem KMS notarai).

Kancelaria w dawnym trybie po zalogowaniu widzi przycisk "Przenies sprawy do
chmury". Przegladarka czyta jej folder i wysyla sprawe po sprawie (ten sam
uklad plikow co w chmurze: sprawa.json, odczyt.json, skany/, projekt.docx...),
a na koniec kancelaria przechodzi na "chmura". Do tego czasu serwer niczego
innego dla niej nie zapisuje (magazyn.u_klienta() dalej pilnuje).

Ponowne wyslanie tej samej sprawy niczego nie dubluje: pliki ida pod te same
klucze, a niezmienione nie sa wysylane do S3 drugi raz.

Zero danych osobowych w logach: identyfikatory spraw i liczby plikow.
"""
import logging
from pathlib import PurePosixPath

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

import autoryzacja
import config
import magazyn

log = logging.getLogger("pieczapp.przeniesienie")

router = APIRouter(prefix="/api/przeniesienie", tags=["przeniesienie"])

MAKS_PLIKOW = 2000
MAKS_BAJTOW = 500 * 1024 * 1024   # jedna sprawa; najwieksze sprawy maja kilkaset stron skanow


def _sciezka(nazwa: str) -> str:
    """Bezpieczna sciezka wzgledna wewnatrz sprawy albo 400."""
    czesci = PurePosixPath((nazwa or "").replace("\\", "/")).parts
    if (not czesci or czesci[0] in ("/", "") or any(c in ("..", ".") or c.startswith(".") for c in czesci)
            or len(czesci) > 4):
        raise HTTPException(400, "Nieprawidlowa sciezka pliku w sprawie.")
    return "/".join(czesci)


def _w_dawnym_trybie(request: Request) -> bool:
    return autoryzacja._przechowywanie(getattr(request.state, "kancelaria", "") or magazyn.kancelaria()) == "u-klienta"


@router.post("/sprawy/{identyfikator}")
async def przenies_sprawe(identyfikator: str, request: Request, pliki: list[UploadFile] = File(...)):
    """Jedna sprawa z folderu kancelarii -> katalog spraw i S3."""
    if not identyfikator.isalnum() or len(identyfikator) > 64:
        raise HTTPException(400, "Nieprawidlowy identyfikator sprawy.")
    if not _w_dawnym_trybie(request):
        raise HTTPException(409, "Ta kancelaria pracuje juz w chmurze - nie ma czego przenosic.")
    if len(pliki) > MAKS_PLIKOW:
        raise HTTPException(413, f"Sprawa ma wiecej niz {MAKS_PLIKOW} plikow.")
    sciezki = [_sciezka(p.filename) for p in pliki]
    if "sprawa.json" not in sciezki:
        raise HTTPException(400, "W folderze sprawy brakuje pliku sprawa.json.")

    # Zapis jak w zwyklej kancelarii chmurowej - tylko na czas tego zadania.
    znacznik = magazyn.przechowywanie_var.set("chmura")
    try:
        katalog = config.SPRAWY / identyfikator
        razem = 0
        for plik, wzgledna in zip(pliki, sciezki):
            if PurePosixPath(wzgledna).name in magazyn._POMIJANE:
                continue   # znaczniki synchronizacji powstana same
            dane = await plik.read()
            razem += len(dane)
            if razem > MAKS_BAJTOW:
                raise HTTPException(413, "Sprawa jest wieksza niz 500 MB - napisz do nas, przeniesiemy ja recznie.")
            cel = katalog / wzgledna
            cel.parent.mkdir(parents=True, exist_ok=True)
            cel.write_bytes(dane)
        magazyn.utrwal_sprawe(katalog)
    finally:
        magazyn.przechowywanie_var.reset(znacznik)
    log.info("przeniesienie: sprawa %s w chmurze, plikow: %d", identyfikator, len(pliki))
    return {"sprawa": identyfikator, "plikow": len(pliki)}


@router.post("/zakoncz")
def zakoncz(request: Request):
    """Kancelaria przechodzi na chmure. Od teraz pracuje jak kazda inna."""
    kancelaria = getattr(request.state, "kancelaria", "") or magazyn.kancelaria()
    autoryzacja._uniewaznij_rejestr()
    rejestr = autoryzacja._wczytaj_rejestr()
    _, wpis = autoryzacja._znajdz(rejestr, kancelaria)
    if not wpis:
        raise HTTPException(404, "Nie znaleziono kancelarii.")
    if wpis.get("przechowywanie", "chmura") != "chmura":
        wpis["przechowywanie"] = "chmura"
        wpis["przeniesiono_do_chmury"] = autoryzacja._teraz()
        autoryzacja._zapisz_rejestr(rejestr)
        log.info("przeniesienie: kancelaria %s pracuje w chmurze", kancelaria)
    return {"przechowywanie": "chmura"}
