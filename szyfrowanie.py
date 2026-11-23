"""Przeszyfrowanie plikow juz lezacych w buckecie spraw kluczem KMS notarai.

Domyslne szyfrowanie bucketa dotyczy tylko nowych plikow. Pliki zapisane
wczesniej (kluczem S3, AES256) przepisujemy w miejscu: kopia obiektu na ten
sam klucz z SSE-KMS, potem usuniecie starej wersji - zeby po przebiegu w
buckecie nie zostal zaden biezacy plik pod kluczem S3. Starsze wersje z
historii (sprzed przebiegu) i tak wygasaja po 90 dniach (cykl zycia bucketa).

Uruchamia administrator: POST /api/admin/przeszyfruj (praca w tle),
GET /api/admin/przeszyfruj - postep. Przebieg mozna powtarzac: pliki juz
zaszyfrowane kluczem KMS sa pomijane. Robi to rola aplikacji, bo tylko ona
moze czytac tresc spraw (polityka bucketa).

Zero danych osobowych w logach: liczby, nigdy klucze obiektow (nazwy skanow
to nazwiska stron).
"""
import logging
import threading

from fastapi import APIRouter, Request

import magazyn

log = logging.getLogger("pieczapp.szyfrowanie")

MAKS_KOPII_B = 5 * 1024 ** 3   # copy_object w jednym kroku; wieksze pomijamy i liczymy
_stan: dict = {"trwa": False}
_blokada = threading.Lock()


def przeszyfruj(prefiks: str = "") -> dict:
    """Jeden przebieg po calym buckecie (albo prefiksie). Zwraca liczniki."""
    s3 = magazyn._klient_s3()
    licz = {"obiektow": 0, "przeszyfrowano": 0, "juz_kms": 0, "pominieto_duze": 0, "bledy": 0}
    for strona in s3.get_paginator("list_objects_v2").paginate(Bucket=magazyn.BUCKET, Prefix=prefiks):
        for obiekt in strona.get("Contents", []):
            licz["obiektow"] += 1
            klucz = obiekt["Key"]
            try:
                naglowek = s3.head_object(Bucket=magazyn.BUCKET, Key=klucz)
                if naglowek.get("ServerSideEncryption") == "aws:kms":
                    licz["juz_kms"] += 1
                    continue
                if obiekt.get("Size", 0) > MAKS_KOPII_B:
                    licz["pominieto_duze"] += 1
                    continue
                stara = naglowek.get("VersionId")
                szyfr = magazyn._szyfrowanie() or {"ServerSideEncryption": "aws:kms"}
                # Kopia tylko, gdy plik sie nie zmienil od odczytu naglowka - inaczej
                # nadpisalibysmy swiezy zapis aplikacji stara trescia (a swiezy zapis
                # i tak jest juz pod kluczem KMS).
                try:
                    s3.copy_object(Bucket=magazyn.BUCKET, Key=klucz,
                                   CopySource={"Bucket": magazyn.BUCKET, "Key": klucz},
                                   CopySourceIfMatch=naglowek["ETag"], MetadataDirective="COPY", **szyfr)
                except Exception as blad:  # noqa: BLE001
                    if magazyn._kod_bledu(blad) in ("PreconditionFailed", "412"):
                        licz["juz_kms"] += 1
                        continue
                    raise
                if stara and stara != "null":
                    s3.delete_object(Bucket=magazyn.BUCKET, Key=klucz, VersionId=stara)
                licz["przeszyfrowano"] += 1
            except Exception as blad:  # noqa: BLE001 - jeden plik nie zatrzymuje przebiegu
                licz["bledy"] += 1
                log.warning("przeszyfrowanie: plik pominiety (%s)", type(blad).__name__)
        _stan.update(licz)
    log.info("przeszyfrowanie: %s", licz)
    return licz


def _w_tle() -> None:
    try:
        _stan.update(przeszyfruj(magazyn.PREFIKS + "/"), koniec=True)
    except Exception as blad:  # noqa: BLE001
        _stan.update(blad=type(blad).__name__)
        log.error("przeszyfrowanie przerwane (%s)", type(blad).__name__)
    finally:
        _stan["trwa"] = False


router_admina = APIRouter(prefix="/api/admin/przeszyfruj", tags=["admin"])


@router_admina.post("")
def uruchom(request: Request):
    import autoryzacja
    autoryzacja._wymagaj_admina(request)
    if magazyn.TRYB != "s3":
        return {"trwa": False, "uwaga": "Tryb lokalny - w buckecie nie ma czego przeszyfrowac."}
    with _blokada:
        if _stan.get("trwa"):
            return dict(_stan)
        _stan.clear()
        _stan["trwa"] = True
    threading.Thread(target=_w_tle, daemon=True, name="przeszyfrowanie").start()
    return dict(_stan)


@router_admina.get("")
def postep(request: Request):
    import autoryzacja
    autoryzacja._wymagaj_admina(request)
    return dict(_stan)
