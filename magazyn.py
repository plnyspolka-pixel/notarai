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
import hashlib
import json
import logging
import os
import threading
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


# Znacznik wersji lokalnej kopii: odcisk calej sprawy w S3 (klucze plikow wraz
# z ich ETagami) z chwili ostatniego zapisu albo pobrania. Pozwala wykryc, ze
# inna kopia aplikacji zmienila sprawe, i odswiezyc cache. Sam nie jest
# wysylany do S3.
#
# Odcisk musi obejmowac wszystkie pliki sprawy, nie same metadane: sporzadzenie
# projektu dodaje projekt.docx i projekt.txt, nie ruszajac sprawa.json. Gdy
# znacznik patrzyl tylko na sprawa.json, druga kopia aplikacji uznawala swoja
# kopie za aktualna i notariusz nie mogl wrocic do wlasnego projektu.
_ZNACZNIK = ".s3-znacznik"


def _zapisz_znacznik(katalog: Path, sygnatura: str) -> None:
    if sygnatura:
        (katalog / _ZNACZNIK).write_text(sygnatura, encoding="utf-8")


def _znacznik(katalog: Path) -> str:
    plik = katalog / _ZNACZNIK
    return plik.read_text("utf-8").strip() if plik.exists() else ""


def _sygnatura(spis: list[tuple[str, str]]) -> str:
    """Odcisk sprawy. Zmiana dowolnego pliku zmienia wynik."""
    tresc = "\n".join(f"{klucz} {etag}" for klucz, etag in sorted(spis))
    return hashlib.sha256(tresc.encode("utf-8")).hexdigest()


def _spis_s3(id_sprawy: str) -> list[tuple[str, str]]:
    """Klucze i ETagi wszystkich plikow sprawy lezacych w S3."""
    prefiks = _klucz(id_sprawy, "")
    spis: list[tuple[str, str]] = []
    strony = _klient_s3().get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=prefiks
    )
    for strona in strony:
        for obiekt in strona.get("Contents", []):
            spis.append((obiekt["Key"], obiekt.get("ETag", "")))
    return spis


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
    wyslane: list[tuple[str, str]] = []
    for plik in sorted(katalog.rglob("*")):
        if not plik.is_file() or plik.name == _ZNACZNIK:
            continue
        klucz = _klucz(id_sprawy, plik.relative_to(katalog).as_posix())
        odpowiedz_put = _klient_s3().put_object(
            Bucket=BUCKET,
            Key=klucz,
            Body=plik.read_bytes(),
            **_szyfrowanie(),
        )
        wyslane.append((klucz, (odpowiedz_put or {}).get("ETag", "")))
    _zapisz_znacznik(katalog, _sygnatura(wyslane))
    log.info("sprawa %s: utrwalono %d plikow do S3", id_sprawy, len(wyslane))


def pobierz_sprawe(katalog: Path) -> bool:
    """Sciaga sprawe z S3 do lokalnego cache, jesli jej tam brakuje albo
    jest nieaktualna.

    Dysk kontenera to tylko pamiec podreczna. Gdy aplikacja dziala w kilku
    kopiach, sprawe mogla zmienic inna z nich - dlatego przed odczytem
    porownujemy odcisk lokalnej kopii z tym, co faktycznie lezy w S3.

    Zwraca True, gdy sprawa istnieje (lokalnie lub po pobraniu).
    No-op w trybie lokalnym (wtedy tylko sprawdza dysk).
    """
    if TRYB != "s3":
        return (katalog / "sprawa.json").exists() or katalog.is_dir()

    id_sprawy = katalog.name
    try:
        spis = _spis_s3(id_sprawy)
    except Exception:
        # S3 chwilowo nie odpowiada. Lepiej pokazac kopie lokalna niz przerwac
        # prace notariusza.
        log.warning("sprawa %s: S3 nie odpowiada, pracuje na kopii lokalnej", id_sprawy)
        return katalog.is_dir()

    if not spis:
        # Sprawy nie ma jeszcze w S3 - wlasnie powstaje na tym kontenerze.
        return katalog.is_dir()

    if (katalog / "sprawa.json").exists() and _sygnatura(spis) == _znacznik(katalog):
        return True

    prefiks = _klucz(id_sprawy, "")
    for klucz, _ in spis:
        wzgledna = klucz[len(prefiks):]
        if not wzgledna:
            continue
        cel = katalog / wzgledna
        cel.parent.mkdir(parents=True, exist_ok=True)
        cel.write_bytes(_klient_s3().get_object(Bucket=BUCKET, Key=klucz)["Body"].read())
    _zapisz_znacznik(katalog, _sygnatura(spis))
    log.info("sprawa %s: pobrano %d plikow z S3", id_sprawy, len(spis))
    return True


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
    usuniete = _usun_wszystkie_wersje(_klucz(id_sprawy, ""))
    log.info("sprawa %s: usunieto %d obiektow z S3", id_sprawy, usuniete)
    return usuniete


def usun_plik_sprawy(katalog: Path, wzgledna: str) -> None:
    """Kasuje jeden plik sprawy z dysku i z S3, razem ze starszymi wersjami."""
    (katalog / wzgledna).unlink(missing_ok=True)
    if TRYB != "s3":
        return
    klucz = _klucz(katalog.name, wzgledna)
    # Prefiks lapie tez "plik.pdf.bak" - zostawiamy tylko dokladny klucz.
    klient = _klient_s3()
    for strona in klient.get_paginator("list_object_versions").paginate(Bucket=BUCKET, Prefix=klucz):
        wersje = [{"Key": o["Key"], "VersionId": o["VersionId"]}
                  for rodzaj in ("Versions", "DeleteMarkers")
                  for o in strona.get(rodzaj, []) if o["Key"] == klucz]
        if wersje:
            klient.delete_objects(Bucket=BUCKET, Delete={"Objects": wersje, "Quiet": True})
    _zapisz_znacznik(katalog, _sygnatura(_spis_s3(katalog.name)))


def _usun_wszystkie_wersje(prefiks: str) -> int:
    """Kasuje z S3 kazda wersje i kazdy znacznik usuniecia pod prefiksem."""
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
    return usuniete


# Identyfikatory, ktore nie sa kancelariami: "admin" to rejestr i tokeny
# urzadzen, "lokalna" to tryb jednego stanowiska.
ZASTRZEZONE = ("admin", "lokalna")


def usun_kancelarie(id_kancelarii: str, baza: Path) -> int:
    """Kasuje wszystkie dane kancelarii: sprawy, zlecenia, wpisy pomocnikow,
    z dysku i z S3, razem ze starszymi wersjami. Zwraca liczbe obiektow S3.

    To realizacja obowiazku z umowy powierzenia (usuniecie danych po
    zakonczeniu uslugi), wiec nie zostawiamy niczego "na 90 dni".
    """
    import shutil

    if (not id_kancelarii or id_kancelarii in ZASTRZEZONE
            or "/" in id_kancelarii or "\\" in id_kancelarii or ".." in id_kancelarii):
        raise ValueError("Nieprawidlowy identyfikator kancelarii")

    katalog = baza / "kancelarie" / id_kancelarii
    if katalog.exists():
        shutil.rmtree(katalog)
    if TRYB != "s3":
        return 0
    # Ukosnik na koncu: "kancelaria-a/" nie moze trafic w "kancelaria-ab/".
    usuniete = _usun_wszystkie_wersje(f"{PREFIKS}/{id_kancelarii}/")
    log.info("kancelaria %s: usunieto %d obiektow z S3", id_kancelarii, usuniete)
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


# --- Pliki calej kancelarii (kalendarz, telefony) ---------------------------


# Rejestry wspolne dla calej kancelarii, nie dla jednej sprawy:
#   kancelarie/{kancelaria}/{nazwa}.json
# Leza pod prefiksem kancelarii, wiec usun_kancelarie() kasuje je razem
# ze sprawami. W trybie S3 czytamy je zawsze z S3 - sa male, a dwie kopie
# aplikacji nie moga miec dwoch roznych wersji kalendarza.
PLIKI_KANCELARII = ("kalendarz", "dni", "osoby", "wizyty")   # wizyty: tylko obszar _administracja
_PROB_ZAPISU = 5
_BLOKADA_PLIKOW = threading.Lock()


class KonfliktZapisu(RuntimeError):
    """Plik zmienial sie rownoczesnie tyle razy, ze nie udalo sie go zapisac."""


def _plik_kancelarii(nazwa: str) -> Path:
    import config
    return sprawy_dir(config.DANE).parent / f"{nazwa}.json"


def _klucz_kancelarii(nazwa: str) -> str:
    return f"{PREFIKS}/{kancelaria()}/{nazwa}.json"


def _czytaj_s3(nazwa: str) -> tuple[object | None, str]:
    """(dane albo None, ETag albo "")."""
    try:
        odp = _klient_s3().get_object(Bucket=BUCKET, Key=_klucz_kancelarii(nazwa))
    except Exception as blad:  # noqa: BLE001
        if type(blad).__name__ == "NoSuchKey" or _kod_bledu(blad) in ("NoSuchKey", "404"):
            return None, ""
        raise
    return json.loads(odp["Body"].read().decode("utf-8")), odp.get("ETag", "")


def _kod_bledu(blad: Exception) -> str:
    return str(getattr(blad, "response", {}).get("Error", {}).get("Code", ""))


def wczytaj_plik_kancelarii(nazwa: str, domyslne):
    if nazwa not in PLIKI_KANCELARII:
        raise ValueError(f"Nieznany plik kancelarii: {nazwa}")
    if TRYB == "s3":
        dane, _ = _czytaj_s3(nazwa)
        return domyslne if dane is None else dane
    plik = _plik_kancelarii(nazwa)
    with _BLOKADA_PLIKOW:
        return json.loads(plik.read_text("utf-8")) if plik.exists() else domyslne


def zmien_plik_kancelarii(nazwa: str, zmiana, domyslne):
    """Odczyt - zmiana - zapis bez gubienia cudzych zmian.

    `zmiana(dane)` zmienia dane w miejscu i zwraca wynik dla wywolujacego.
    W S3 zapis jest warunkowy (If-Match / If-None-Match): gdy druga kopia
    aplikacji zdazyla zapisac plik w miedzyczasie, czytamy go jeszcze raz
    i powtarzamy zmiane na nowszej wersji.
    """
    if nazwa not in PLIKI_KANCELARII:
        raise ValueError(f"Nieznany plik kancelarii: {nazwa}")
    if u_klienta():
        raise RuntimeError("Kancelaria trzyma pliki u siebie - serwer nie zapisuje jej danych.")
    if TRYB != "s3":
        plik = _plik_kancelarii(nazwa)
        with _BLOKADA_PLIKOW:
            dane = json.loads(plik.read_text("utf-8")) if plik.exists() else domyslne
            wynik = zmiana(dane)
            tymczasowy = plik.with_suffix(".tmp")
            tymczasowy.write_text(json.dumps(dane, ensure_ascii=False, indent=2), encoding="utf-8")
            tymczasowy.replace(plik)
        return wynik

    for _ in range(_PROB_ZAPISU):
        dane, etag = _czytaj_s3(nazwa)
        if dane is None:
            dane = domyslne
        wynik = zmiana(dane)
        warunek = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
        try:
            _klient_s3().put_object(
                Bucket=BUCKET, Key=_klucz_kancelarii(nazwa),
                Body=json.dumps(dane, ensure_ascii=False).encode("utf-8"),
                **warunek, **_szyfrowanie(),
            )
        except Exception as blad:  # noqa: BLE001
            if _kod_bledu(blad) in ("PreconditionFailed", "ConditionalRequestConflict", "412", "409"):
                log.info("plik kancelarii %s: rownoczesna zmiana, ponawiam", nazwa)
                continue
            raise
        return wynik
    raise KonfliktZapisu("Ktos rownoczesnie zmienia te dane. Sprobuj za chwile.")
