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
        return SesjaPseudonimizacji(tuple(w.osoba for w in self.wpisy.values()))

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
