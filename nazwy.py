"""Nazwa sprawy z nazwisk stron, np. "Sobczak – Pawlak".

Kolejnosc zrodel:
  1. pole "STALE: nazwiska stron" odczytane przez model,
  2. pola rol (zbywca/sprzedajacy, nabywca/kupujacy, darczynca, spadkodawca...),
     najpierw strona zbywajaca, potem nabywajaca,
  3. nazwy plikow skanow w konwencji kancelarii "Nazwisko Imie - Nazwisko Imie - ...".
Brak wyniku -> None (interfejs pokaze numer sprawy).
"""
import re

LITERY = "A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż"
SLOWO = re.compile(rf"^[{LITERY}]+(?:-[{LITERY}]+)*$")
NIE_NAZWISKA = {
    "małżonkowie", "malzonkowie", "małżonków", "małżonkom", "syn", "córka", "corka", "pesel",
    "brak", "null", "nieznane", "nie", "dotyczy", "wariant", "i", "oraz", "pan", "pani",
}
ROLE = [  # (wzorzec nazwy pola, priorytet: mniejszy = wczesniej w nazwie)
    (re.compile(r"zbyw|sprzedaj|darczy|spadkodaw|aaa:", re.I), 0),
    (re.compile(r"nabyw|kupuj|obdarow|spadkobierc|bbb:", re.I), 1),
    (re.compile(r"stawaj|strona czynno", re.I), 2),
]
MAX_NAZWISK = 3


def _ladnie(slowo: str) -> str:
    return "-".join(cz[:1].upper() + cz[1:].lower() for cz in slowo.split("-"))


def _pole_z_osoba(nazwa: str) -> bool:
    """Czy pole zawiera samo imie i nazwisko strony (a nie np. jej PESEL, KW czy adres)."""
    if re.match(r"^[a-z]{2}[a-z0-9]:\s*\S+(\s+\S+)?\s*$", nazwa):   # kod legendy: "aaa: zbywca"
        return True
    if re.search(r"nazwisk", nazwa, re.I):                        # "+ Nazwisko nabywcy", "zbywca - imię i nazwisko"
        return not re.search(r"rodzic|ojc|matk|panie[ńn]sk", nazwa, re.I)
    rdzen = re.sub(r"^\+\s*", "", nazwa).strip().lower()
    return rdzen in {"zbywca", "nabywca", "nabywcy", "sprzedający", "sprzedajacy", "kupujący", "kupujacy",
                     "darczyńca", "obdarowany", "obdarowana", "spadkodawca", "spadkobierca"}


def _bez_form_odmienionych(nazwiska) -> list[str]:
    """Sobczak/Sobczaka/Sobczakowi to ta sama osoba - zostaje pierwsza forma."""
    wynik: list[str] = []
    for n in nazwiska:
        if any(_ten_sam_rdzen(n, w) for w in wynik):
            continue
        wynik.append(n)
    return wynik


def _ten_sam_rdzen(a: str, b: str) -> bool:
    a, b = a.lower(), b.lower()
    if a == b:
        return True
    krotsze, dluzsze = sorted((a, b), key=len)
    if len(krotsze) >= 4 and dluzsze.startswith(krotsze) and len(dluzsze) - len(krotsze) <= 3:
        return True
    rdzen = min(len(a), len(b)) - 1        # Kowalska / Kowalskiej, Nowak / Nowaka
    return rdzen >= 4 and a[:rdzen] == b[:rdzen] and abs(len(a) - len(b)) <= 3


def nazwiska_z_wartosci(wartosc: str, tylko_nazwisko: bool = False) -> list[str]:
    """'TOMASZ PIOTR SOBCZAK, STANISŁAW, HALINA, 85031512337' -> ['Sobczak'];
    'Marian i Anna małżonkowie Nowak' -> ['Nowak']."""
    if not wartosc:
        return []
    tekst = re.sub(r"\d+", " ", str(wartosc))
    osoby = re.split(r"\s+(?:i|oraz)\s+|;", tekst)
    wynik: list[str] = []
    for osoba in osoby:
        osoba = osoba.split(",")[0]          # po przecinku: imiona rodzicow, adres
        osoba = re.split(r"\(|\s[-–]\s", osoba)[0]
        slowa = [s for s in osoba.split() if SLOWO.match(s) and s.lower() not in NIE_NAZWISKA]
        if not slowa:
            continue
        if not tylko_nazwisko and len(slowa) == 1 and len(osoby) > 1:
            continue                          # samo imie ("Marian" w "Marian i Anna ... Nowak")
        kandydat = slowa[-1]
        if len(kandydat) < 2:
            continue
        wynik.append(_ladnie(kandydat))
    return wynik


def nazwiska_z_plikow(nazwy_plikow: list[str]) -> list[str]:
    """'Sobczak Tomasz - Pawlak Grzegorz - sprzedaż RI - Zalesie.pdf' -> ['Sobczak', 'Pawlak']."""
    for nazwa in nazwy_plikow:
        rdzen = re.sub(r"\.[a-z0-9]+$", "", nazwa, flags=re.I)
        czesci = [c.strip() for c in re.split(r"\s+[-–]\s+", rdzen)]
        if len(czesci) < 2:
            continue
        wynik = []
        for czesc in czesci:
            slowa = czesc.split()
            if 2 <= len(slowa) <= 3 and all(SLOWO.match(s) and s[0].isupper() for s in slowa):
                wynik.append(_ladnie(slowa[0]))   # konwencja: Nazwisko Imie
            else:
                break
        if wynik:
            return wynik
    return []


def nazwa_sprawy(pola: list[dict] | None, pliki: list[str] | None = None) -> str | None:
    pola = pola or []
    znalezione: list[tuple[int, int, int, str]] = []

    for pole in pola:
        nazwa = str(pole.get("nazwa", ""))
        if nazwa.startswith("STALE: nazwiska stron") and pole.get("wartosc"):
            gotowe = [_ladnie(s) for s in re.split(r"\s*[-–,;/]\s*|\s+i\s+", str(pole["wartosc"]))
                      if SLOWO.match(s.strip()) and s.strip().lower() not in NIE_NAZWISKA]
            if gotowe:
                return " – ".join(dict.fromkeys(gotowe[:MAX_NAZWISK]))

    for kolejnosc, pole in enumerate(pola):
        nazwa = str(pole.get("nazwa", ""))
        wartosc = pole.get("wartosc")
        if not wartosc or nazwa.startswith("??") or not _pole_z_osoba(nazwa):
            continue
        for wzorzec, priorytet in ROLE:
            if wzorzec.search(nazwa):
                tylko = bool(re.search(r"nazwisk", nazwa, re.I)) and not re.search(r"imi", nazwa, re.I)
                for i, n in enumerate(nazwiska_z_wartosci(str(wartosc), tylko_nazwisko=tylko)):
                    znalezione.append((priorytet, kolejnosc, i, n))
                break

    nazwiska = _bez_form_odmienionych(n for *_, n in sorted(znalezione))
    if not nazwiska:
        nazwiska = nazwiska_z_plikow(pliki or [])
    return " – ".join(nazwiska[:MAX_NAZWISK]) if nazwiska else None
