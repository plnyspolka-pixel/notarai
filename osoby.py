"""Baza osob bioracych udzial w aktach - z numerami telefonu.

Osoby nie sa przepisywane do osobnej bazy. Lista powstaje na biezaco z pol
odczytanych w sprawach (sprawy/<id>/odczyt.json), a w osoby.json kancelarii
(kancelarie/{kancelaria}/osoby.json w S3) leza tylko rzeczy dopisane recznie:
telefony i osoby spoza odczytu.

Ta sama osoba w kilku sprawach to jeden wpis - kluczem jest PESEL, a gdy go
brak, imie i nazwisko. Identyfikator osoby to skrot klucza, wiec ani w
adresach API, ani w osoby.json nie ma numeru PESEL.
"""
import hashlib
import json
import re
import uuid
from pathlib import Path

import config
import magazyn
import nazwy
import rejestry
import walidacja

PLIK = "osoby"

ROLE = [  # (wzorzec nazwy pola, rola w akcie)
    (re.compile(r"zbyw|sprzedaj|^aa[a-z0-9]:", re.I), "zbywca"),
    (re.compile(r"nabyw|kupuj|^bb[a-z0-9]:", re.I), "nabywca"),
    (re.compile(r"darczy", re.I), "darczyńca"),
    (re.compile(r"obdarow", re.I), "obdarowany"),
    (re.compile(r"spadkodaw", re.I), "spadkodawca"),
    (re.compile(r"spadkobierc", re.I), "spadkobierca"),
    (re.compile(r"pe[lł]nomocni", re.I), "pełnomocnik"),
    (re.compile(r"stawaj|strona czynno", re.I), "stawający"),
]
PESEL = re.compile(r"(?<!\d)\d{11}(?!\d)")


# --- osoby z pol sprawy ------------------------------------------------------


def _rola(nazwa_pola: str) -> str | None:
    for wzorzec, rola in ROLE:
        if wzorzec.search(nazwa_pola):
            return rola
    return None


def _mianownik(nazwa_pola: str) -> bool:
    """'aaa: zbywca' i 'imie i nazwisko' maja forme podstawowa; 'aa2: zbywcy' to odmiana."""
    return bool(re.match(r"^([a-z])\1\1:", nazwa_pola) or re.search(r"imi", nazwa_pola, re.I))


def _ladnie(slowo: str) -> str:
    return "-".join(cz[:1].upper() + cz[1:].lower() for cz in slowo.split("-"))


def osoby_z_wartosci(wartosc: str) -> list[str]:
    """'TOMASZ PIOTR SOBCZAK, STANISŁAW, HALINA, 85031512337' -> ['Tomasz Piotr Sobczak'];
    'Grzegorz i Ewa małżonkowie Pawlak' -> ['Grzegorz Pawlak', 'Ewa Pawlak']."""
    tekst = re.sub(r"\d+", " ", str(wartosc or ""))
    czesci = []
    for osoba in re.split(r"\s+(?:i|oraz)\s+|;", tekst):
        osoba = re.split(r"\(|\s[-–]\s", osoba.split(",")[0])[0]
        slowa = [s for s in osoba.split() if nazwy.SLOWO.match(s) and s.lower() not in nazwy.NIE_NAZWISKA]
        if slowa:
            czesci.append([_ladnie(s) for s in slowa])
    nazwisko = next((c[-1] for c in reversed(czesci) if len(c) > 1), None)
    wynik = []
    for slowa in czesci:
        if len(slowa) == 1:
            if not nazwisko or len(czesci) == 1:
                continue                     # samo imie albo samo nazwisko - za malo
            slowa = slowa + [nazwisko]       # "Grzegorz i Ewa ... Pawlak"
        wynik.append(" ".join(slowa))
    return wynik


def _pole_imion(nazwa_pola: str) -> bool:
    """Pole z pelnym imieniem i nazwiskiem; samo nazwisko ('+ Nazwisko nabywcy') za malo."""
    if re.search(r"imi\S* i nazwisk", nazwa_pola, re.I):
        return True
    return nazwy._pole_z_osoba(nazwa_pola) and not re.search(r"nazwisk", nazwa_pola, re.I)


def _poprawne_pesele(wartosc: str) -> list[str]:
    return [p for p in PESEL.findall(re.sub(r"[\s-]", "", str(wartosc or ""))) if walidacja.pesel(p)[0]]


def osoby_ze_sprawy(pola: list[dict]) -> list[dict]:
    """Strony czynnosci odczytane z pol sprawy: [{imie_nazwisko, pesel, rola}].

    Imiona i numery PESEL tej samej roli lacza sie w kolejnosci wystapienia.
    Niczego nie dopowiadamy - osoba bez PESEL zostaje bez PESEL.
    """
    imiona: dict[str, list[tuple[int, str]]] = {}
    pesele: dict[str, list[str]] = {}
    for pole in pola or []:
        nazwa = str(pole.get("nazwa", ""))
        wartosc = pole.get("wartosc")
        if not wartosc or nazwa.startswith("??"):
            continue
        rola = _rola(nazwa)
        if not rola:
            continue
        if re.search(r"pesel", nazwa, re.I):
            pesele.setdefault(rola, []).extend(_poprawne_pesele(wartosc))
        elif _pole_imion(nazwa):
            priorytet = 0 if _mianownik(nazwa) else 1
            imiona.setdefault(rola, []).extend((priorytet, o) for o in osoby_z_wartosci(wartosc))
            pesele.setdefault(rola, []).extend(_poprawne_pesele(wartosc))

    wynik = []
    for rola in dict.fromkeys([*imiona, *pesele]):
        ludzie: list[str] = []
        for _, osoba in sorted(imiona.get(rola, []), key=lambda x: x[0]):
            if not any(nazwy._ten_sam_rdzen(osoba.split()[-1], o.split()[-1])
                       and nazwy._ten_sam_rdzen(osoba.split()[0], o.split()[0]) for o in ludzie):
                ludzie.append(osoba)
        numery = list(dict.fromkeys(pesele.get(rola, [])))
        for i in range(max(len(ludzie), len(numery))):
            wynik.append({
                "imie_nazwisko": ludzie[i] if i < len(ludzie) else "",
                "pesel": numery[i] if i < len(numery) else "",
                "rola": rola,
            })
    return wynik


# --- baza --------------------------------------------------------------------


def _klucz(osoba: dict) -> str:
    if osoba.get("pesel"):
        return "p:" + osoba["pesel"]
    return "n:" + " ".join(osoba.get("imie_nazwisko", "").lower().split())


def _ta_sama_osoba(a: str, b: str) -> bool:
    """To samo pierwsze imie i nazwisko, a drugie imie najwyzej w jednym z zapisow:
    'Artur Makuch' i 'Artur Roman Makuch' tak; 'Artur Makuch' i 'Anna Makuch' nie."""
    a, b = a.lower().split(), b.lower().split()
    if len(a) < 2 or len(b) < 2 or a[0] != b[0] or a[-1] != b[-1]:
        return False
    krotsze, dluzsze = sorted((a, b), key=len)
    return set(krotsze) <= set(dluzsze)


def _identyfikator(klucz: str) -> str:
    return hashlib.sha256(klucz.encode("utf-8")).hexdigest()[:16]


def _pusty() -> dict:
    return {"telefony": {}, "reczne": {}}


def _wczytaj_zapis() -> dict:
    dane = magazyn.wczytaj_plik_kancelarii(PLIK, _pusty())
    dane.setdefault("telefony", {})
    dane.setdefault("reczne", {})
    return dane


def _zmien_zapis(zmiana):
    def calosc(dane):
        dane.setdefault("telefony", {})
        dane.setdefault("reczne", {})
        return zmiana(dane)
    return magazyn.zmien_plik_kancelarii(PLIK, calosc, _pusty())


_PAMIEC: dict[Path, tuple[float, list[dict]]] = {}


def _osoby_sprawy_z_dysku(plik: Path) -> list[dict]:
    """Odczyt sprawy z pamieci, dopoki plik sie nie zmienil."""
    czas = plik.stat().st_mtime
    zapamietane = _PAMIEC.get(plik)
    if zapamietane and zapamietane[0] == czas:
        return zapamietane[1]
    try:
        pola = json.loads(plik.read_text("utf-8")).get("pola", [])
    except (OSError, ValueError):
        pola = []
    osoby = osoby_ze_sprawy(pola)
    _PAMIEC[plik] = (czas, osoby)
    return osoby


def wszystkie(sprawy: list[dict]) -> list[dict]:
    """Osoby ze wszystkich spraw plus dopisane recznie.

    `sprawy` to lista z /api/sprawy (id, nazwa, sygnatura) - z niej nazwy spraw.
    Wynik bez pelnego PESEL: tylko zamaskowany.
    """
    po_kluczu: dict[str, dict] = {}
    for sprawa in sprawy:
        plik = config.SPRAWY / sprawa["id"] / "odczyt.json"
        if not plik.exists():
            continue
        for o in _osoby_sprawy_z_dysku(plik):
            klucz = _klucz(o)
            if klucz in ("n:", "p:"):
                continue
            wpis = po_kluczu.setdefault(klucz, {"klucze": {klucz}, "imie_nazwisko": "", "pesel": o["pesel"], "sprawy": []})
            if not wpis["imie_nazwisko"] and o["imie_nazwisko"]:
                wpis["imie_nazwisko"] = o["imie_nazwisko"]
            if not any(s["id"] == sprawa["id"] and s["rola"] == o["rola"] for s in wpis["sprawy"]):
                wpis["sprawy"].append({"id": sprawa["id"], "nazwa": sprawa.get("nazwa") or sprawa.get("sygnatura") or "",
                                       "rola": o["rola"]})

    # Osoba bez PESEL w jednej sprawie i z PESEL w innej - to ta sama osoba,
    # jesli imie i nazwisko pasuje do dokladnie jednej osoby z numerem.
    # Gdy zadna z numerem nie pasuje - do dokladnie jednej bez numeru o pelniejszym
    # imieniu ('Artur Makuch' -> 'Artur Roman Makuch').
    for klucz in sorted((k for k in po_kluczu if k.startswith("n:")), key=len):
        bez = po_kluczu[klucz]
        pasujace = [w for k, w in po_kluczu.items()
                    if k.startswith("p:") and _ta_sama_osoba(bez["imie_nazwisko"], w["imie_nazwisko"])]
        if not pasujace:
            pasujace = [w for k, w in po_kluczu.items()
                        if k.startswith("n:") and len(k) > len(klucz)
                        and _ta_sama_osoba(bez["imie_nazwisko"], w["imie_nazwisko"])]
        if len(pasujace) == 1:
            cel = pasujace[0]
            del po_kluczu[klucz]
            cel["klucze"] |= bez["klucze"]
            cel["sprawy"].extend(s for s in bez["sprawy"] if s not in cel["sprawy"])
            if len(bez["imie_nazwisko"].split()) > len(cel["imie_nazwisko"].split()):
                cel["imie_nazwisko"] = bez["imie_nazwisko"]

    zapis = _wczytaj_zapis()
    telefony = zapis["telefony"]
    wynik = []
    for klucz, w in po_kluczu.items():
        identyfikatory = [_identyfikator(k) for k in sorted(w["klucze"], key=lambda k: k != klucz)]
        telefon = next((telefony[i] for i in identyfikatory if telefony.get(i)), "")
        wynik.append({
            "id": identyfikatory[0],
            "imie_nazwisko": w["imie_nazwisko"],
            "pesel": rejestry.maskuj_pesel(w["pesel"]) if w["pesel"] else "",
            "telefon": telefon,
            "sprawy": w["sprawy"],
            "reczna": False,
        })
    for identyfikator, r in zapis["reczne"].items():
        wynik.append({
            "id": identyfikator,
            "imie_nazwisko": r.get("imie_nazwisko", ""),
            "pesel": "",
            "telefon": telefony.get(identyfikator, ""),
            "sprawy": [],
            "reczna": True,
        })
    wynik.sort(key=lambda o: (_sortowanie(o["imie_nazwisko"]), o["id"]))
    return wynik


def _sortowanie(imie_nazwisko: str) -> str:
    slowa = imie_nazwisko.split()
    return (" ".join(slowa[-1:] + slowa[:-1]) if slowa else "￿").lower()


def telefon(wartosc: str) -> str:
    """Numer w postaci '+48 600 100 200'. Pusty -> ''. Bledny -> ValueError."""
    cyfry = re.sub(r"[\s\-().]", "", wartosc or "")
    if not cyfry:
        return ""
    if cyfry.startswith("00"):
        cyfry = "+" + cyfry[2:]
    if re.fullmatch(r"\d{9}", cyfry):
        cyfry = "+48" + cyfry
    if re.fullmatch(r"\+48\d{9}", cyfry):
        n = cyfry[3:]
        return f"+48 {n[:3]} {n[3:6]} {n[6:]}"
    if re.fullmatch(r"\+\d{7,15}", cyfry):
        return cyfry
    raise ValueError("Nieprawidłowy numer telefonu - podaj 9 cyfr albo numer z prefiksem kraju (+...)")


def ustaw_telefon(identyfikator: str, numer: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{16}", identyfikator):
        raise ValueError("Nieprawidłowy identyfikator osoby")
    gotowy = telefon(numer)

    def zmiana(zapis):
        if gotowy:
            zapis["telefony"][identyfikator] = gotowy
        else:
            zapis["telefony"].pop(identyfikator, None)
    _zmien_zapis(zmiana)
    return gotowy


def dodaj_reczna(imie_nazwisko: str, numer: str = "") -> str:
    imie_nazwisko = " ".join(imie_nazwisko.split())[:120]
    if not imie_nazwisko:
        raise ValueError("Podaj imię i nazwisko")
    gotowy = telefon(numer)
    identyfikator = uuid.uuid4().hex[:16]

    def zmiana(zapis):
        zapis["reczne"][identyfikator] = {"imie_nazwisko": imie_nazwisko}
        if gotowy:
            zapis["telefony"][identyfikator] = gotowy
    _zmien_zapis(zmiana)
    return identyfikator


def usun_reczna(identyfikator: str) -> bool:
    def zmiana(zapis):
        if identyfikator not in zapis["reczne"]:
            return False
        del zapis["reczne"][identyfikator]
        zapis["telefony"].pop(identyfikator, None)
        return True
    return _zmien_zapis(zmiana)
