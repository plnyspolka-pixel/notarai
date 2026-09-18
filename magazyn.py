"""Magazyn plikow spraw - dysk lokalny albo S3 (tryb SaaS).

Zasada: caly istniejacy kod dalej pracuje na sciezkach lokalnych (Path).
Dysk lokalny jest pamiecia podreczna; w trybie S3 kazda sprawa jest
utrwalana do S3 po zapisie i pobierana z S3 przed odczytem.

Uklad kluczy w S3 (izolacja per kancelaria):
  kancelarie/{kancelaria}/sprawy/{id_sprawy}/{sciezka względna}

Tryby (PIECZAPP_MAGAZYN):
  lokalny  - jak dotychczas, wszystko na dysku (domyslnie)
  s3       - dysk jako cache + utrwalanie do S3 (wymaga PIECZAPP_S3_BUCKET)

Zero danych osobowych w logach: logujemy identyfikatory i liczby plikow,
nigdy tresc.
"""
import logging
import os
from contextvars import ContextVar
from pathlib import Path

log = logging.getLogger("pieczapp.magazyn")

TRYB = os.getenv("PIECZAPP_MAGAZYN", "lokalny")
BUCKET = os.getenv("PIECZAPP_S3_BUCKET", "")
PREFIKS = os.getenv("PIECZAPP_S3_PREFIKS", "kancelarie")
KMS_KLUCZ = os.getenv("PIECZAPP_KMS_KEY_ID", "")  # opcjonalny CMK dla SSE-KMS

if TRYB == "s3" and not BUCKET:
    raise RuntimeError(
        "PIECZAPP_MAGAZYN=s3 wymaga PIECZAPP_S3_BUCKET. "
        "Ustaw nazwe bucketa albo wroc do PIECZAPP_MAGAZYN=lokalny."
    )

# Kancelaria biezacego zadania. Ustawiana przez autoryzacje (tryb SaaS);
# w trybie lokalnym zawsze "lokalna" i sciezki sa identyczne jak dotychczas.
kancelaria_var: ContextVar[str] = ContextVar("kancelaria", default="lokalna")

# Gdzie leza pliki tej kancelarii: "chmura" (domyslnie) albo "u-klienta".
# Przy "u-klienta" serwer niczego nie zapisuje - pliki trzyma przegladarka
# notariusza na jego dysku, a my tylko przetwarzamy je w locie.
przechowywanie_var: ContextVar[str] = ContextVar("przechowywanie", default="chmura")


def u_klienta() -> bool:
    return przechowywanie_var.get() == "u-klienta"

_s3 = None  # leniwie tworzony klient boto3; podmienialny w testach


def _klient_s3():
    global _s3
    if _s3 is None:
        import boto3
        _s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "eu-central-1"))
    return _s3


def _szyfrowanie() -> dict:
    if KMS_KLUCZ:
        return {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": KMS_KLUCZ}
    return {"ServerSideEncryption": "AES256"}


# --- Sciezki ---------------------------------------------------------------


def kancelaria() -> str:
    return kancelaria_var.get()


def sprawy_dir(baza: Path) -> Path:
    """Katalog spraw biezacej kancelarii. Tworzy go, jesli nie istnieje.

    Kancelaria "lokalna" -> dotychczasowe dane/sprawy (pelna zgodnosc wstecz).
    Inna kancelaria      -> dane/kancelarie/{nazwa}/sprawy.
    """
    k = kancelaria()
    if k == "lokalna":
        katalog = baza / "sprawy"
    else:
        katalog = baza / "kancelarie" / k / "sprawy"
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog


def _klucz(id_sprawy: str, wzgledna: str) -> str:
    return f"{PREFIKS}/{kancelaria()}/sprawy/{id_sprawy}/{wzgledna}"


# --- Synchronizacja z S3 ----------------------------------------------------


# Znacznik wersji lokalnej kopii: ETag pliku sprawa.json z S3 w chwili
# ostatniego zapisu albo pobrania. Pozwala wykryc, ze inna kopia aplikacji
# zmienila sprawe, i odswiezyc cache. Sam nie jest wysylany do S3.
_ZNACZNIK = ".s3-znacznik"


def _zapisz_znacznik(katalog: Path, etag: str) -> None:
    if etag:
        (katalog / _ZNACZNIK).write_text(etag.strip(), encoding="utf-8")


def _aktualna_kopia(katalog: Path) -> bool:
    """Czy lokalna kopia sprawy odpowiada temu, co jest w S3."""
    znacznik = katalog / _ZNACZNIK
    if not znacznik.exists():
        return False
    try:
        odp = _klient_s3().head_object(
            Bucket=BUCKET, Key=_klucz(katalog.name, "sprawa.json")
        )
    except Exception:
        # Sprawy nie ma jeszcze w S3 (wlasnie powstaje) albo S3 chwilowo nie
        # odpowiada. Lepiej pokazac kopie lokalna niz przerwac prace.
        return True
    return odp.get("ETag", "") == znacznik.read_text("utf-8").strip()


def utrwal_sprawe(katalog: Path) -> None:
    """Wysyla wszystkie pliki sprawy do S3. No-op w trybie lokalnym."""
    if u_klienta():
        # Zabezpieczenie na poziomie magazynu, nie tylko sciezek w API:
        # kancelarii, ktora trzyma pliki u siebie, nie wolno nic zapisac.
        raise RuntimeError(
            "Ta kancelaria trzyma pliki u siebie - zapis w chmurze jest wylaczony."
        )
    if TRYB != "s3":
        return
    id_sprawy = katalog.name
    ile = 0
    etag = ""
    for plik in sorted(katalog.rglob("*")):
        if not plik.is_file() or plik.name == _ZNACZNIK:
            continue
        wzgledna = plik.relative_to(katalog).as_posix()
        odpowiedz_put = _klient_s3().put_object(
            Bucket=BUCKET,
            Key=_klucz(id_sprawy, wzgledna),
            Body=plik.read_bytes(),
            **_szyfrowanie(),
        )
        if wzgledna == "sprawa.json":
            etag = (odpowiedz_put or {}).get("ETag", "")
        ile += 1
    _zapisz_znacznik(katalog, etag)
    log.info("sprawa %s: utrwalono %d plikow do S3", id_sprawy, ile)


def pobierz_sprawe(katalog: Path) -> bool:
    """Sciaga sprawe z S3 do lokalnego cache, jesli jej tam brakuje albo
    jest nieaktualna.

    Dysk kontenera to tylko pamiec podreczna. Gdy aplikacja dziala w kilku
    kopiach, sprawe mogla zmienic inna z nich - dlatego przed odczytem
    porownujemy znacznik wersji z ETagiem w S3.

    Zwraca True, gdy sprawa istnieje (lokalnie lub po pobraniu).
    No-op w trybie lokalnym (wtedy tylko sprawdza dysk).
    """
    if (katalog / "sprawa.json").exists():
        if TRYB != "s3" or _aktualna_kopia(katalog):
            return True
        log.info("sprawa %s: lokalna kopia nieaktualna, odswiezam z S3", katalog.name)
    elif TRYB != "s3":
        return katalog.is_dir()

    id_sprawy = katalog.name
    prefiks = _klucz(id_sprawy, "")
    strony = _klient_s3().get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=prefiks
    )
    ile = 0
    etag = ""
    for strona in strony:
        for obiekt in strona.get("Contents", []):
            wzgledna = obiekt["Key"][len(prefiks):]
            if not wzgledna:
                continue
            cel = katalog / wzgledna
            cel.parent.mkdir(parents=True, exist_ok=True)
            odpowiedz = _klient_s3().get_object(Bucket=BUCKET, Key=obiekt["Key"])
            cel.write_bytes(odpowiedz["Body"].read())
            if wzgledna == "sprawa.json":
                etag = obiekt.get("ETag", "")
            ile += 1
    if ile:
        _zapisz_znacznik(katalog, etag)
        log.info("sprawa %s: pobrano %d plikow z S3", id_sprawy, ile)
    return ile > 0 or katalog.is_dir()


def usun_sprawe(katalog: Path) -> int:
    """Kasuje sprawe z dysku i z S3. Zwraca liczbe usunietych obiektow.

    Usuwamy takze starsze wersje plikow. Bucket ma wersjonowanie, wiec samo
    skasowanie zostawiloby poprzednie wersje na kolejne 90 dni - a "usunieta"
    sprawa ma znaczyc usunieta, nie ukryta.
    """
    import shutil

    if katalog.exists():
        shutil.rmtree(katalog)
    if TRYB != "s3":
        return 0

    id_sprawy = katalog.name
    prefiks = _klucz(id_sprawy, "")
    klient = _klient_s3()
    usuniete = 0
    strony = klient.get_paginator("list_object_versions").paginate(
        Bucket=BUCKET, Prefix=prefiks
    )
    for strona in strony:
        do_usuniecia = [
            {"Key": o["Key"], "VersionId": o["VersionId"]}
            for klucz in ("Versions", "DeleteMarkers")
            for o in strona.get(klucz, [])
        ]
        for poczatek in range(0, len(do_usuniecia), 1000):  # limit jednego zadania
            paczka = do_usuniecia[poczatek:poczatek + 1000]
            klient.delete_objects(Bucket=BUCKET, Delete={"Objects": paczka, "Quiet": True})
            usuniete += len(paczka)
    log.info("sprawa %s: usunieto %d obiektow z S3", id_sprawy, usuniete)
    return usuniete


def identyfikatory_spraw(baza_spraw: Path) -> list[str]:
    """Lista identyfikatorow spraw biezacej kancelarii.

    Tryb lokalny: katalogi na dysku. Tryb S3: unia dysku i S3, a brakujace
    lokalnie sprawa.json sa dociagane, zeby lista dzialala po restarcie
    kontenera (dysk App Runner/ECS jest ulotny).
    """
    lokalne = {k.name for k in baza_spraw.iterdir() if k.is_dir()} if baza_spraw.is_dir() else set()
    if TRYB != "s3":
        return sorted(lokalne)

    prefiks = f"{PREFIKS}/{kancelaria()}/sprawy/"
    zdalne: set[str] = set()
    strony = _klient_s3().get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=prefiks, Delimiter="/"
    )
    for strona in strony:
        for wspolny in strona.get("CommonPrefixes", []):
            zdalne.add(wspolny["Prefix"][len(prefiks):].strip("/"))

    for id_sprawy in zdalne - lokalne:
        pobierz_sprawe(baza_spraw / id_sprawy)
    return sorted(lokalne | zdalne)
