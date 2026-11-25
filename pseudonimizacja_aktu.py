"""Rdzeń pseudonimizacji tekstu na podstawie potwierdzonego rejestru osób.

Nie jest detektorem wszystkich danych osobowych ani automatycznym OCR.
Nie podłączać do Bedrock bez bramki kompletności i kontroli ścieżek.
Słownik wyłącznie w pamięci pojedynczej operacji sprawy; bez logowania,
globalnego cache, dostępu sieciowego ani identyfikatorów z PESEL.
"""
from dataclasses import dataclass, field
import re
import secrets
import unicodedata
from collections import defaultdict

import walidacja


class WymagaWeryfikacji(ValueError):
    """Wyłącznie kod błędu; bez danych źródłowych."""


def _norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFC", s).casefold().split())


def _cyfry(s: str) -> str:
    return re.sub(r"[\s-]", "", s)


@dataclass(frozen=True, repr=False)
class Osoba:
    id: str  # losowy identyfikator lokalnego, potwierdzonego rekordu
    imiona: tuple[str, ...]
    nazwisko: str
    pesel: str = ""
    aliasy: tuple[str, ...] = ()  # odmiany zatwierdzone, nie zgadywane
    role: tuple[str, ...] = ()

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.id):
            raise WymagaWeryfikacji("INVALID_PERSON_ID")
        if not self.imiona or not all(n.strip() for n in self.imiona) or not self.nazwisko.strip():
            raise WymagaWeryfikacji("MISSING_NAME")
        if self.pesel and (not re.fullmatch(r"[0-9]{11}", _cyfry(self.pesel))
                           or not walidacja.pesel(self.pesel)[0]):
            raise WymagaWeryfikacji("INVALID_PESEL")

    def nazwy(self):
        return { " ".join((*self.imiona, self.nazwisko)),
                 " ".join((self.imiona[0], self.nazwisko)), *self.aliasy }


@dataclass(frozen=True, repr=False)
class Wystapienie:
    poczatek: int
    koniec: int
    osoba_id: str
    typ: str = "NAZWA"


@dataclass(frozen=True, repr=False)
class DaneDodatkowe:
    poczatek: int
    koniec: int
    typ: str  # np. ADRES, KW, DOWOD, KONTO, DATA, FIRMA, PII
    osoba_id: str | None = None


@dataclass(repr=False)
class SesjaPseudonimizacji:
    """Jednorazowy kontekst jednej sprawy i jednego uprawnionego tenant-a.

    Wywołujący odpowiada za potwierdzenie listy osób i zakresu tekstu.
    Przekazywać do modelu tylko wynik pseudonimizuj(), nigdy obiekt sesji.
    """
    osoby: tuple[Osoba, ...]
    _nonce: str = field(default_factory=lambda: secrets.token_hex(8), init=False)
    _osoby: dict = field(default_factory=dict, init=False)
    _aliasy: dict = field(default_factory=dict, init=False)
    _tokeny: dict = field(default_factory=dict, init=False)
    _odwrotne: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        aliasy = defaultdict(set)
        pesele = set()
        for o in self.osoby:
            if o.id in self._osoby:
                raise WymagaWeryfikacji("DUPLICATE_PERSON_ID")
            p = _cyfry(o.pesel)
            if p and p in pesele:
                raise WymagaWeryfikacji("DUPLICATE_PESEL_REVIEW")
            if p:
                pesele.add(p)
            self._osoby[o.id] = f"P{len(self._osoby)+1:03d}"
            for n in o.nazwy():
                if n.strip():
                    aliasy[_norm(n)].add(o.id)
            if p:
                aliasy[p].add(o.id)
        self._aliasy = dict(aliasy)

    def kandydaci(self, nazwa: str) -> tuple[str, ...]:
        """Propozycja dopasowania, nigdy scalenie dwóch rekordów."""
        k = _norm(nazwa)
        if re.fullmatch(r"[0-9\s-]+", k):
            k = _cyfry(k)
        return tuple(sorted(self._aliasy.get(k, ())))

    def kandydaci_roli(self, rola: str) -> tuple[str, ...]:
        """Rola nie jest tozsamoscia. Wynik wymaga oceny kontekstu wzmianki."""
        return tuple(sorted(o.id for o in self.osoby
                            if _norm(rola) in {_norm(r) for r in o.role}))

    def _token(self, wartosc: str, osoba_id: str | None, typ: str) -> str:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,23}", typ):
            raise WymagaWeryfikacji("INVALID_FIELD_TYPE")
        if osoba_id is not None and osoba_id not in self._osoby:
            raise WymagaWeryfikacji("UNKNOWN_PERSON")
        klucz = (osoba_id, typ, wartosc)
        if klucz not in self._odwrotne:
            osoba = self._osoby.get(osoba_id, "D000")
            t = f"[[NA_{self._nonce}_{osoba}_{typ}_{len(self._tokeny)+1:04d}]]"
            self._tokeny[t] = wartosc
            self._odwrotne[klucz] = t
        return self._odwrotne[klucz]

    def pseudonimizuj(self, tekst: str, *,
                      potwierdzone: tuple[Wystapienie, ...] = (),
                      dodatkowe: tuple[DaneDodatkowe, ...] = ()) -> str:
        """Zastąp znane nazwy, PESEL i zatwierdzone zakresy innych danych.

        Krótszy zapis imienia ma ten sam Pxxx co pełny, ale odrębny token
        powierzchniowy; zachowujemy dokładną pisownię i odmianę po odtworzeniu.
        Niejednoznaczny alias zatrzymuje operację, chyba że dany zakres
        rozstrzygnął uprawniony użytkownik. Nie wykrywa nieznanych nazw.
        """
        if re.search(r"\[\[\s*NA(?:_|[\s-])", tekst, re.I) or self._nonce in tekst:
            raise WymagaWeryfikacji("TOKEN_IN_SOURCE")
        miejsca = []
        for w in potwierdzone:
            if w.osoba_id not in self._osoby:
                raise WymagaWeryfikacji("UNKNOWN_PERSON")
            if not 0 <= w.poczatek < w.koniec <= len(tekst):
                raise WymagaWeryfikacji("INVALID_PERSON_SPAN")
            fragment = tekst[w.poczatek:w.koniec]
            if w.typ == "PESEL" and w.osoba_id not in self.kandydaci(fragment):
                raise WymagaWeryfikacji("PESEL_PERSON_CONFLICT")
            if w.typ == "ROLA" and w.osoba_id not in self.kandydaci_roli(fragment):
                raise WymagaWeryfikacji("ROLE_PERSON_CONFLICT")
            if w.typ == "NAZWA":
                kandydaci = self.kandydaci(fragment)
                if kandydaci and w.osoba_id not in kandydaci:
                    raise WymagaWeryfikacji("NAME_PERSON_CONFLICT")
            miejsca.append((w.poczatek, w.koniec, w.osoba_id, w.typ))
        for d in dodatkowe:
            miejsca.append((d.poczatek, d.koniec, d.osoba_id, d.typ))
        miejsca.sort()
        koniec = 0
        for a, b, _, _ in miejsca:
            if a < koniec or a < 0 or b <= a or b > len(tekst):
                raise WymagaWeryfikacji("INVALID_OR_OVERLAPPING_SPANS")
            koniec = b

        # Dłuższe nazwy wygrywają z krótszymi. Bez fuzzy match i bez
        # usuwania polskich znaków, które mogłoby zlać różne nazwiska.
        propozycje = []
        for nazwa, ids in self._aliasy.items():
            if re.fullmatch(r"[0-9]{11}", nazwa):
                wzor = r"[\s-]*".join(map(re.escape, nazwa))
                typ = "PESEL"
            else:
                wzor = r"\s+".join(map(re.escape, nazwa.split()))
                typ = "NAZWA"
            for m in re.finditer(r"(?<!\w)" + wzor + r"(?!\w)", tekst, re.I):
                propozycje.append((m.start(), m.end(), ids, typ))
        for a, b, ids, typ in sorted(propozycje, key=lambda x: (-(x[1]-x[0]), x[0])):
            nakladajace = [(x, y) for x,y,_,_ in miejsca if a < y and x < b]
            if nakladajace:
                if any(x <= a and b <= y for x,y in nakladajace):
                    continue
                raise WymagaWeryfikacji("PARTIAL_SPAN_OVERLAP")
            if len(ids) != 1:
                raise WymagaWeryfikacji("AMBIGUOUS_PERSON_MENTION")
            miejsca.append((a,b,next(iter(ids)),typ))

        # Nieznany ciąg 11 cyfr traktujemy zachowawczo: także z błędną sumą
        # kontrolną może być PESEL-em po błędzie OCR. Nie przypisujemy osobie.
        for m in re.finditer(r"(?<!\d)[0-9](?:[\s-]*[0-9]){10}(?!\d)", tekst):
            a,b = m.span()
            overlaps = [(x,y) for x,y,_,_ in miejsca if a < y and x < b]
            if overlaps:
                if any(x <= a and b <= y for x,y in overlaps):
                    continue
                raise WymagaWeryfikacji("PARTIAL_IDENTIFIER_OVERLAP")
            miejsca.append((a,b,None,"NUMER11"))
        fragmenty = []
        k = 0
        for a,b,oid,typ in sorted(miejsca):
            fragmenty.extend((tekst[k:a], self._token(tekst[a:b],oid,typ)))
            k = b
        fragmenty.append(tekst[k:])
        return "".join(fragmenty)

    def przywroc(self, tekst: str) -> str:
        """Odtwarza tylko dokładne tokeny tej sesji. Nie ufa nowym tokenom."""
        wzor = re.compile(r"\[\[NA_[^\[\]\n]*\]\]")
        def zamien(m):
            if m.group() not in self._tokeny:
                raise WymagaWeryfikacji("UNKNOWN_TOKEN")
            return self._tokeny[m.group()]
        # Sprawdź resztę przed odtworzeniem, nie po wstawieniu oryginalnych danych.
        reszta = wzor.sub("", tekst)
        if (re.search(r"\[\[\s*NA(?:_|[\s-])", reszta, re.I)
                or self._nonce.casefold() in reszta.casefold()):
            raise WymagaWeryfikacji("MALFORMED_TOKEN")
        return wzor.sub(zamien, tekst)

    def zamknij(self):
        """Usuń mapy; Python nie daje gwarancji fizycznego wyzerowania pamięci."""
        self._tokeny.clear()
        self._odwrotne.clear()
        self._aliasy.clear()
        self._osoby.clear()
        self.osoby = ()
