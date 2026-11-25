"""Potwierdzona tożsamość uczestników pojedynczej sprawy.

Nie jest globalnym CRM osób. Źródła i rozstrzygnięcia pochodzą od
uprawnionego notariusza, nie z podobieństwa nazwiska ani kolejności pól.
Rejestr można serializować do istniejącego magazynu sprawy; pseudonimy
operacyjne i ich słownik nie są serializowane.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import re
import uuid

import magazyn
from pseudonimizacja_aktu import Osoba, SesjaPseudonimizacji, WymagaWeryfikacji


@dataclass(frozen=True, repr=False)
class Zrodlo:
    dokument_id: str
    strona: int
    od: int
    do: int
    sha256: str

    def __post_init__(self):
        if (not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", self.dokument_id)
                or self.strona < 1 or not 0 <= self.od < self.do
                or not re.fullmatch(r"[0-9a-f]{64}", self.sha256)):
            raise WymagaWeryfikacji("INVALID_IDENTITY_SOURCE")


@dataclass(frozen=True, repr=False)
class PotwierdzonaOsoba:
    osoba: Osoba
    zrodla: tuple[Zrodlo, ...]

    def __post_init__(self):
        if not self.zrodla:
            raise WymagaWeryfikacji("MISSING_IDENTITY_SOURCE")


@dataclass(repr=False)
class RejestrSprawy:
    tenant: str
    sprawa: str
    wersja: int = 0
    wpisy: dict[str, PotwierdzonaOsoba] = field(default_factory=dict)
    zdarzenia: list[dict] = field(default_factory=list)

    def _sprawdz_zakres(self):
        if self.tenant != magazyn.kancelaria() or not re.fullmatch(r"[A-Za-z0-9]{1,128}", self.sprawa):
            raise WymagaWeryfikacji("IDENTITY_SCOPE_MISMATCH")

    def dodaj(self, *, imiona, nazwisko, pesel="", aliasy=(), role=(),
              zrodla, aktor, oczekiwana_wersja):
        """Nowa osoba wymaga jawnej decyzji; nigdy nie wyszukujemy po nazwisku."""
        self._sprawdz_zakres()
        oid = uuid.uuid4().hex
        osoba = Osoba(oid, tuple(imiona), nazwisko, pesel, tuple(aliasy), tuple(role))
        self._zmien(PotwierdzonaOsoba(osoba, tuple(zrodla)), aktor, oczekiwana_wersja, "dodanie")
        return oid

    def popraw(self, osoba, zrodla, *, aktor, oczekiwana_wersja):
        self._sprawdz_zakres()
        if osoba.id not in self.wpisy:
            raise WymagaWeryfikacji("UNKNOWN_PERSON")
        self._zmien(PotwierdzonaOsoba(osoba, tuple(zrodla)), aktor, oczekiwana_wersja, "korekta")

    def _zmien(self, wpis, aktor, oczekiwana_wersja, akcja):
        if oczekiwana_wersja != self.wersja:
            raise WymagaWeryfikacji("IDENTITY_VERSION_CONFLICT")
        if not aktor or len(aktor) > 256:
            raise WymagaWeryfikacji("MISSING_REVIEWER")
        nowe = dict(self.wpisy)
        nowe[wpis.osoba.id] = wpis
        # Walidacja unikalności PESEL; konflikt trafia do człowieka.
        kontrola = SesjaPseudonimizacji(tuple(w.osoba for w in nowe.values()))
        kontrola.zamknij()
        self.wpisy = nowe
        self.wersja += 1
        self.zdarzenia.append({"wersja": self.wersja, "akcja": akcja,
                              "osoba_id": wpis.osoba.id, "aktor": aktor,
                              "czas": datetime.now(timezone.utc).isoformat()})

    def sesja(self):
        self._sprawdz_zakres()
        return SesjaPseudonimizacji(tuple(w.osoba for w in self.wpisy.values()), sprawa=self.sprawa)

    def do_zapisu(self):
        self._sprawdz_zakres()
        return {"tenant": self.tenant, "sprawa": self.sprawa, "wersja": self.wersja,
                "wpisy": [asdict(w) for w in self.wpisy.values()],
                "zdarzenia": [dict(z) for z in self.zdarzenia]}

    @classmethod
    def odczytaj(cls, dane, sprawa):
        r = cls(dane["tenant"], dane["sprawa"], dane["wersja"])
        r._sprawdz_zakres()
        if r.sprawa != sprawa:
            raise WymagaWeryfikacji("IDENTITY_CASE_MISMATCH")
        for w in dane["wpisy"]:
            o = dict(w["osoba"])
            for pole in ("imiona", "aliasy", "role"):
                o[pole] = tuple(o[pole])
            osoba = Osoba(**o)
            if osoba.id in r.wpisy:
                raise WymagaWeryfikacji("DUPLICATE_PERSON_ID")
            r.wpisy[osoba.id] = PotwierdzonaOsoba(osoba, tuple(Zrodlo(**z) for z in w["zrodla"]))
        r.zdarzenia = [dict(z) for z in dane["zdarzenia"]]
        s = r.sesja()
        s.zamknij()
        return r


# W tej samej przestrzeni sprawy co odczyt i projekt. Nie ma osobnego zasobu
# AWS ani globalnej bazy PII. S3 ma warunkowy zapis i szyfrowanie jak sprawa.
PLIK = "rejestr-tozsamosci.json"

import hashlib
import json
import os
import threading
from pathlib import Path

import szyfrowanie_kancelarii as szyfr

_blokada = threading.RLock()


def _katalog(katalog):
    import config
    katalog = Path(katalog)
    if (katalog.parent.resolve() != config.SPRAWY.resolve()
            or not (katalog / "sprawa.json").is_file()
            or not re.fullmatch(r"[A-Za-z0-9]{1,128}", katalog.name)
            or magazyn.u_klienta()):
        raise WymagaWeryfikacji("IDENTITY_CASE_UNAVAILABLE")
    return katalog


def _wczytaj(katalog):
    katalog = _katalog(katalog)
    plik = katalog / PLIK
    etag = ""
    if magazyn.TRYB == "s3":
        klucz = magazyn._klucz(katalog.name, PLIK)
        try:
            odp = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=klucz)
        except Exception as blad:
            if magazyn._kod_bledu(blad) not in ("NoSuchKey", "404") and type(blad).__name__ != "NoSuchKey":
                raise WymagaWeryfikacji("IDENTITY_STORAGE_READ_FAILED") from None
            dane = None
        else:
            etag = odp.get("ETag", "")
            if not etag:
                raise WymagaWeryfikacji("IDENTITY_STORAGE_ETAG_MISSING")
            surowe = odp["Body"].read()
            if szyfr.aktywne():
                surowe = szyfr.odszyfruj(surowe, klucz)
            dane = json.loads(surowe)
    else:
        dane = json.loads(plik.read_text("utf-8")) if plik.exists() else None
    return (RejestrSprawy.odczytaj(dane, katalog.name) if dane is not None
            else RejestrSprawy(magazyn.kancelaria(), katalog.name)), etag


def wczytaj(katalog):
    with _blokada:
        return _wczytaj(katalog)[0]


def zmien(katalog, akcja):
    """Akcja modyfikuje rejestr, a zapis CAS nie gubi równoległych decyzji."""
    with _blokada:
        katalog = _katalog(katalog)
        rejestr, etag = _wczytaj(katalog)
        wynik = akcja(rejestr)
        surowe = json.dumps(rejestr.do_zapisu(), ensure_ascii=False).encode("utf-8")
        if magazyn.TRYB == "s3":
            klucz = magazyn._klucz(katalog.name, PLIK)
            warunek = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
            if szyfr.aktywne():
                surowe = szyfr.szyfruj(surowe, klucz)
            try:
                magazyn._klient_s3().put_object(
                    Bucket=magazyn.BUCKET, Key=klucz, Body=surowe,
                    **warunek, **magazyn._szyfrowanie())
            except Exception:
                raise WymagaWeryfikacji("IDENTITY_STORAGE_WRITE_OR_CONFLICT") from None
        else:
            tmp = katalog / (PLIK + ".tmp")
            try:
                fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "wb") as out:
                    out.write(surowe)
                tmp.replace(katalog / PLIK)
            finally:
                tmp.unlink(missing_ok=True)
        return wynik, rejestr.wersja


def zrodla_sprawy(katalog):
    """Teksty źródłowe z już zapisanej sprawy. Id źródła nie zawiera nazwiska."""
    katalog = _katalog(katalog)
    plik = katalog / "transkrypcje.json"
    strony = json.loads(plik.read_text("utf-8")) if plik.exists() else []
    wynik = {}
    for indeks, s in enumerate(strony):
        for typ in ("tresc", "tekst_pdf"):
            tekst = s.get(typ, "")
            if not isinstance(tekst, str) or not tekst.strip():
                continue
            oid = hashlib.sha256(f"{indeks}:{typ}:{s.get('dokument','')}:{s.get('strona',1)}".encode()).hexdigest()
            wynik[oid] = {"strona": int(s.get("strona", 1)), "typ": typ,
                          "tekst": tekst, "sha256": hashlib.sha256(tekst.encode()).hexdigest()}
    return wynik


def sprawdz_zrodla(katalog, zrodla, osoba):
    """Potwierdzone zakresy muszą wskazywać aktualne źródło w tej sprawie."""
    dostepne = zrodla_sprawy(katalog)
    fragmenty = []
    for z in zrodla:
        s = dostepne.get(z.dokument_id)
        if (s is None or s["strona"] != z.strona or s["sha256"] != z.sha256
                or z.do > len(s["tekst"])):
            raise WymagaWeryfikacji("IDENTITY_SOURCE_STALE")
        fragmenty.append(s["tekst"][z.od:z.do])
    calosc = " ".join(fragmenty)
    from pseudonimizacja_aktu import _norm, _cyfry
    if not any(_norm(n) in _norm(calosc) for n in osoba.nazwy()):
        raise WymagaWeryfikacji("NAME_NOT_IN_EVIDENCE")
    if osoba.pesel and _cyfry(osoba.pesel) not in _cyfry(calosc):
        raise WymagaWeryfikacji("PESEL_NOT_IN_EVIDENCE")
