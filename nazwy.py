"""Nazwa sprawy z nazwisk stron, np. "Sobczak – Pawlak".

Kolejnosc zrodel:
  1. pole "STALE: nazwiska stron" odczytane przez model,
  2. pola rol (zbywca/sprzedajacy, nabywca/kupujacy, darczynca, spadkodawca...),
     najpierw strona zbywajaca, potem nabywajaca,
  3. nazwy plikow skanow w konwencji kancelarii "Nazwisko Imie - Nazwisko Imie - ...".
Brak wyniku -> None (interfejs pokaze numer sprawy).

Nazwa pliku Word (nazwa_pliku): wg wzoru kancelarii z polami w klamrach, np.
"{zbywca} - {nabywca} - {czynnosc} - {miejscowosc}" -> "Sobczak - Pawlak - sprzedaż - Zalesie".
Puste pola znikaja razem ze swoim separatorem, znaki niedozwolone w nazwach
plikow sa usuwane. Nic tu nie trafia do logow.
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

    for pole in pola:
        nazwa = str(pole.get("nazwa", ""))
        if nazwa.startswith("STALE: nazwiska stron") and pole.get("wartosc"):
            gotowe = [_ladnie(s) for s in re.split(r"\s*[-–,;/]\s*|\s+i\s+", str(pole["wartosc"]))
                      if SLOWO.match(s.strip()) and s.strip().lower() not in NIE_NAZWISKA]
            if gotowe:
                return " – ".join(dict.fromkeys(gotowe[:MAX_NAZWISK]))

    znalezione = _nazwiska_wg_rol(pola)
    nazwiska = _bez_form_odmienionych(n for *_, n in sorted(znalezione))
    if not nazwiska:
        nazwiska = nazwiska_z_plikow(pliki or [])
    return " – ".join(nazwiska[:MAX_NAZWISK]) if nazwiska else None


def _nazwiska_wg_rol(pola: list[dict]) -> list[tuple[int, int, int, str]]:
    """[(priorytet roli, kolejnosc pola, kolejnosc w polu, nazwisko)] z pol rol."""
    znalezione: list[tuple[int, int, int, str]] = []
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
    return znalezione


def nazwiska_stron(pola: list[dict] | None, pliki: list[str] | None = None) -> dict[str, list[str]]:
    """{"zbywcy": [...], "nabywcy": [...], "inni": [...]} - nazwiska stron wg roli.

    Pole "STALE: nazwiska stron" (zbywajacy, potem nabywajacy, oddzielone " - ")
    ma pierwszenstwo: pierwsze nazwisko to zbywca, reszta to nabywcy. Bez pol -
    nazwy plikow skanow w konwencji kancelarii (tak samo: pierwszy zbywa).
    """
    pola = pola or []
    for pole in pola:
        nazwa = str(pole.get("nazwa", ""))
        if nazwa.startswith("STALE: nazwiska stron") and pole.get("wartosc"):
            gotowe = list(dict.fromkeys(
                _ladnie(s) for s in re.split(r"\s*[-–,;/]\s*|\s+i\s+", str(pole["wartosc"]))
                if SLOWO.match(s.strip()) and s.strip().lower() not in NIE_NAZWISKA))
            if gotowe:
                return {"zbywcy": gotowe[:1], "nabywcy": gotowe[1:MAX_NAZWISK + 1], "inni": []}

    wg_rol: dict[int, list[str]] = {0: [], 1: [], 2: []}
    for priorytet, _, _, nazwisko in sorted(_nazwiska_wg_rol(pola)):
        wg_rol[priorytet].append(nazwisko)
    wynik = {klucz: _bez_form_odmienionych(wg_rol[p])[:MAX_NAZWISK]
             for klucz, p in (("zbywcy", 0), ("nabywcy", 1), ("inni", 2))}
    if not any(wynik.values()):
        z_plikow = nazwiska_z_plikow(pliki or [])
        wynik = {"zbywcy": z_plikow[:1], "nabywcy": z_plikow[1:MAX_NAZWISK + 1], "inni": []}
    return wynik


# ---------------------------------------------------------------------------
# Nazwa pliku Word wg wzoru kancelarii
# ---------------------------------------------------------------------------
DOMYSLNY_WZOR_NAZWY = "{zbywca} - {nabywca} - {czynnosc} - {miejscowosc}"

# Pola do wstawienia we wzorze nazwy (klucz -> opis dla interfejsu).
POLA_NAZWY = {
    "zbywca": "nazwisko zbywcy (sprzedającego, darczyńcy, spadkodawcy)",
    "nabywca": "nazwisko nabywcy (kupującego, obdarowanego, spadkobiercy)",
    "strony": "wszystkie nazwiska stron",
    "czynnosc": "rodzaj czynności (sprzedaż, darowizna, pełnomocnictwo…)",
    "miejscowosc": "miejscowość położenia nieruchomości",
    "sygnatura": "sygnatura sprawy",
    "data": "data założenia sprawy (RRRR-MM-DD)",
    "nazwa": "nazwa sprawy z listy spraw",
}

# Rodzaj czynnosci (kategorie.RODZAJE) -> krotkie slowo do nazwy pliku.
ETYKIETY_CZYNNOSCI = {
    "sprzedaz": "sprzedaż", "sprzedaz_rolna": "sprzedaż", "darowizna": "darowizna",
    "zamiana": "zamiana", "przedwstepna": "umowa przedwstępna", "deweloperska": "umowa deweloperska",
    "odrebna_wlasnosc": "odrębna własność lokalu", "sluzebnosc": "służebność", "hipoteka": "hipoteka",
    "poddanie_egzekucji": "poddanie się egzekucji", "pelnomocnictwo": "pełnomocnictwo",
    "testament": "testament", "poswiadczenie_dziedziczenia": "poświadczenie dziedziczenia",
    "dzial_spadku": "dział spadku", "zniesienie_wspolwlasnosci": "zniesienie współwłasności",
    "podzial_majatku": "podział majątku", "intercyza": "umowa majątkowa", "dozywocie": "dożywocie",
    "spolka": "spółka", "protokol": "protokół", "oswiadczenie": "oświadczenie",
}

_POLE_WZORU = re.compile(r"\{\s*([a-zA-Z_]+)\s*\}")
_NIEDOZWOLONE_W_NAZWIE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SEPARATOR = r"[\s]*[-–—_|,;·.]+[\s]*"
_PUSTE = "\x00"
MAX_DLUGOSC_NAZWY = 120
_PRZYKLAD = {
    "zbywca": "Sobczak", "nabywca": "Pawlak", "strony": "Sobczak - Pawlak", "czynnosc": "sprzedaż",
    "miejscowosc": "Zalesie", "sygnatura": "A 123/2026", "data": "2026-11-13", "nazwa": "Sobczak – Pawlak",
}


def nieznane_pola_wzoru(wzor: str) -> list[str]:
    return sorted({p for p in _POLE_WZORU.findall(wzor or "") if p not in POLA_NAZWY})


def czynnosc_z_rodzajow(rodzaje: list[str] | None) -> str:
    """Pierwszy rozpoznany rodzaj czynnosci jako slowo do nazwy ("inny" -> pusto)."""
    for rodzaj in rodzaje or []:
        if rodzaj in ETYKIETY_CZYNNOSCI:
            return ETYKIETY_CZYNNOSCI[rodzaj]
    return ""


def miejscowosc_z_pol(pola: list[dict] | None) -> str:
    """Miejscowosc polozenia nieruchomosci: pole STALE, a gdy go nie ma - inne
    pole o miejscowosci/obrebie (nie adres ani zamieszkanie strony)."""
    kandydaci: list[tuple[int, str]] = []
    for pole in pola or []:
        nazwa = str(pole.get("nazwa", ""))
        wartosc = str(pole.get("wartosc") or "").strip()
        if not wartosc or nazwa.startswith("??"):
            continue
        plaska = nazwa.lower()
        if plaska.startswith("stale: miejscowosc polozenia"):
            kandydaci.append((0, wartosc))
        elif re.search(r"miejscowo|obr[eę]b", plaska) and not re.search(r"zamieszk|adres|siedzib|urodz|strony|zbywc|nabywc", plaska):
            kandydaci.append((1, wartosc))
    for _, wartosc in sorted(kandydaci, key=lambda k: k[0]):
        pierwsza = wartosc.splitlines()[0]
        pierwsza = re.split(r"[:(,;|]|\s[-–]\s|\s+dz\.|\s+dzia[łl]", pierwsza)[0]
        pierwsza = re.sub(r"^(w|we|obr[eę]b|miejscowo[śs][ćc])\s+", "", pierwsza.strip(), flags=re.I)
        slowa = [s for s in re.findall(rf"[{LITERY}]+(?:-[{LITERY}]+)*", pierwsza) if s.lower() not in NIE_NAZWISKA]
        if slowa:
            return " ".join(_ladnie(s) if s.islower() or s.isupper() else s for s in slowa[:3])
    return ""


def bezpieczna_nazwa_pliku(tekst: str) -> str:
    """Bez znakow niedozwolonych w Windows/macOS, bez kropek i spacji na koncach."""
    tekst = re.sub(r"\s*[/\\:]\s*", "-", tekst or "")   # A 123/2026 -> A 123-2026
    tekst = _NIEDOZWOLONE_W_NAZWIE.sub("", tekst)
    tekst = re.sub(r"\s+", " ", tekst).strip(" .-–—_")
    return tekst[:MAX_DLUGOSC_NAZWY].rstrip(" .-–—_")


def _polacz_nazwiska(nazwiska: list[str]) -> str:
    if len(nazwiska) <= 1:
        return "".join(nazwiska)
    return ", ".join(nazwiska[:-1]) + " i " + nazwiska[-1]


def wartosci_nazwy(pola: list[dict] | None, pliki: list[str] | None = None, rodzaje: list[str] | None = None,
                   sygnatura: str = "", utworzono: str = "", nazwa: str = "") -> dict[str, str]:
    """Wartosci wszystkich pol wzoru nazwy dla jednej sprawy (puste = brak danych)."""
    strony = nazwiska_stron(pola, pliki)
    wszystkie = list(dict.fromkeys(strony["zbywcy"] + strony["nabywcy"] + strony["inni"]))
    return {
        "zbywca": _polacz_nazwiska(strony["zbywcy"]),
        "nabywca": _polacz_nazwiska(strony["nabywcy"]),
        "strony": " - ".join(wszystkie[:MAX_NAZWISK]),
        "czynnosc": czynnosc_z_rodzajow(rodzaje),
        "miejscowosc": miejscowosc_z_pol(pola),
        "sygnatura": (sygnatura or "").strip(),
        "data": (utworzono or "")[:10],
        "nazwa": (nazwa or "").strip(),
    }


def wypelnij_wzor_nazwy(wzor: str, wartosci: dict[str, str]) -> str:
    """Wzor z polami -> nazwa (bez rozszerzenia). Puste pole znika razem
    z separatorem obok; nieznane pole liczy sie jak puste."""
    tekst = _POLE_WZORU.sub(lambda m: bezpieczna_nazwa_pliku(wartosci.get(m.group(1), "")) or _PUSTE,
                            wzor or DOMYSLNY_WZOR_NAZWY)
    # Puste pole zabiera separator PRZED soba ("A - <puste> - B" -> "A - B"),
    # a na poczatku wzoru - separator za soba ("<puste> - B" -> "B").
    for _ in range(len(tekst)):   # az nic sie nie zmienia
        nowy = re.sub(_SEPARATOR + _PUSTE, "", tekst)
        nowy = re.sub("^" + _PUSTE + _SEPARATOR, "", nowy)
        if nowy == tekst:
            break
        tekst = nowy
    return bezpieczna_nazwa_pliku(tekst.replace(_PUSTE, ""))


def nazwa_pliku(wzor: str, pola: list[dict] | None, pliki: list[str] | None = None,
                rodzaje: list[str] | None = None, sygnatura: str = "", utworzono: str = "",
                nazwa: str = "", identyfikator: str = "") -> str:
    """Nazwa pliku Word z projektem (bez rozszerzenia). Gdy ze wzoru nic nie
    wychodzi (sprawa bez odczytanych stron) - "projekt-<id>"."""
    wynik = wypelnij_wzor_nazwy(wzor, wartosci_nazwy(pola, pliki, rodzaje, sygnatura, utworzono, nazwa))
    if not wynik:
        wynik = bezpieczna_nazwa_pliku(f"projekt-{identyfikator}") if identyfikator else "projekt"
    return wynik


def przyklad_nazwy(wzor: str) -> str:
    """Podglad wzoru na przykladowych danych (dla okna ustawien)."""
    return (wypelnij_wzor_nazwy(wzor, _PRZYKLAD) or "projekt") + ".docx"
