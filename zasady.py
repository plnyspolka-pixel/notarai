"""Nieprzekraczalne zasady kancelarii: od zdania notariusza do kontroli projektu.

Notariusz pisze zasade po swojemu, tak jak powiedzialby aplikantowi:

    "Zamiast „w/w” pisz „wyżej wymieniony”"
    "Kwoty zawsze cyframi i słownie"
    "W umowach sprzedaży zawsze wnioski wieczystoksięgowe"

`interpretuj()` bez udzialu modelu rozpoznaje, co to za zasada (typ),
czego dotyczy (obszar), w jakich dokumentach obowiazuje (zakres:
rodzaje czynnosci i czesci aktu) i jak bedzie pilnowana. Notariusz nic
nie wybiera z list - widzi tylko zdanie "Tak to rozumiem: ..." i moze je
poprawic.

Kazdy projekt dokumentu przechodzi przez `egzekwuj()` ZANIM trafi do
notariusza:
  1. sprawdzenie zasad i konstrukcji aktu (klauzule.sprawdz_konstrukcje),
  2. autonaprawa tego, co da sie poprawic deterministycznie (zamiany slow,
     kwoty slownie, format dat, spacje po §, cudzyslowy, numeracja §),
  3. gdy zostaly naruszenia blokujace - jedna tura poprawki przez model
     (tylko wskazane miejsca) i ponowne sprawdzenie,
  4. wytyczne, ktorych nie da sie sprawdzic regula, sprawdza model.
Wynik: tekst projektu + raport zgodnosci, ktory UI pokazuje nad projektem.
"""
import re
import uuid
from datetime import datetime

import kategorie
import klauzule
import slownie

POZIOMY = ("blokuje", "ostrzega")
PLIK = "zasady"

# typ -> (obszar, sposob pilnowania, czy autonaprawa)
TYPY = {
    "zamiana": ("slownictwo", "automatycznie", True),
    "zakaz_frazy": ("slownictwo", "automatycznie", False),
    "wymagana_fraza": ("tresc", "automatycznie", False),
    "wymagana_czesc": ("struktura", "automatycznie", False),
    "kwoty_slownie": ("kwoty", "automatycznie", True),
    "separator_tysiecy": ("kwoty", "automatycznie", True),
    "format_daty": ("daty", "automatycznie", True),
    "spacja_paragraf": ("typografia", "automatycznie", True),
    "cudzyslowy": ("typografia", "automatycznie", True),
    "wytyczna": ("inne", "ai", False),
}
# Zasady, ktore moga byc tylko jedne (nowa zastepuje poprzednia).
JEDYNE = {"kwoty_slownie", "separator_tysiecy", "format_daty", "spacja_paragraf", "cudzyslowy"}

_CUDZYSLOW = re.compile(r"[„\"“”«»']([^„\"“”«»'\n]{1,120})[”\"“«»']")
_MIESIACE = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
             "września", "października", "listopada", "grudnia"]
_MIESIACE_PLASKIE = [kategorie.bez_ogonkow(m) for m in _MIESIACE]


# ---------------------------------------------------------------------------
# Interpretacja zdania notariusza
# ---------------------------------------------------------------------------
def _cytaty(tekst: str) -> list[str]:
    return [c.strip() for c in _CUDZYSLOW.findall(tekst) if c.strip()]


def _poziom(plaski: str) -> str:
    if re.search(r"\b(staraj sie|raczej|najlepiej|preferuj|preferujemy|lepiej|w miare mozliwosci|"
                 r"unikaj|unikamy|wskazane|zalecane|jesli to mozliwe)\b", plaski):
        return "ostrzega"
    return "blokuje"


def _tekst_zakresu(tekst: str) -> str:
    """Zakres czytamy z poczatku zdania, bez cytatow i bez nazw ustaw
    ("pouczenie o art. 2 ustawy o ksztaltowaniu ustroju ROLNEGO" nie znaczy,
    ze zasada dotyczy tylko nieruchomosci rolnych)."""
    bez = _CUDZYSLOW.sub(" ", tekst)
    return re.split(r"\bart\.|\bartyku|\bustaw|\brozporz|\bkodeks", bez, maxsplit=1, flags=re.IGNORECASE)[0]


def _zakres(tekst: str) -> dict:
    zakresowy = _tekst_zakresu(tekst)
    rodzaje = kategorie.rodzaje_w_zdaniu(zakresowy)
    if "sprzedaz_rolna" in rodzaje and "sprzedaz" in rodzaje and re.search(r"roln", kategorie.bez_ogonkow(zakresowy)):
        rodzaje.remove("sprzedaz")
    return {"rodzaje": rodzaje, "czesci": kategorie.czesci_w_zdaniu(zakresowy)}


def _format_daty_z_przykladu(tekst: str) -> dict | None:
    plaski = kategorie.bez_ogonkow(tekst)
    if m := re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})(\s?r\.|\s?roku)?", tekst):
        return {"styl": "cyfry", "zero": len(m.group(1)) == 2, "sufiks": _sufiks(m.group(4))}
    if m := re.search(r"\b(\d{1,2})\s+(" + "|".join(_MIESIACE_PLASKIE) + r")\s+\d{4}(\s?r\.|\s?roku)?", plaski):
        return {"styl": "miesiac", "zero": len(m.group(1)) == 2, "sufiks": _sufiks(m.group(3))}
    if re.search(r"\bdd\.mm\.rrrr", plaski):
        m = re.search(r"dd\.mm\.rrrr(\s?r\.|\s?roku)?", plaski)
        return {"styl": "cyfry", "zero": True, "sufiks": _sufiks(m.group(1))}
    if re.search(r"slownie|nazw\w* miesi|miesia\w* slown", plaski):
        return {"styl": "miesiac", "zero": False, "sufiks": " r."}
    if re.search(r"cyfr|liczbow|numeryczn", plaski):
        return {"styl": "cyfry", "zero": True, "sufiks": " r."}
    return None


def _sufiks(surowy: str | None) -> str:
    if not surowy:
        return ""
    surowy = surowy.replace("roku", "roku")
    return (" " if surowy.startswith(" ") else "") + surowy.strip()


def _separator_z_tekstu(tekst: str, plaski: str) -> str | None:
    if m := re.search(r"\d{1,3}([ . ])\d{3}(,\d{2})?", tekst):
        return "kropka" if m.group(1) == "." else "spacja"
    if re.search(r"separator\w*|co trzy cyfry|grup\w* cyfr|tysiac\w* oddziel", plaski):
        if "kropk" in plaski:
            return "kropka"
        if "spacj" in plaski:
            return "spacja"
        if re.search(r"\bbez\b", plaski):
            return "brak"
    return None


def interpretuj(tekst: str) -> dict:
    """Zdanie notariusza -> zasada (bez zapisu). Zawsze zwraca zasade -
    gdy typu nie da sie ustalic, jest to "wytyczna" pilnowana przez model."""
    tekst = re.sub(r"\s+", " ", (tekst or "").strip())
    if not tekst:
        raise ValueError("Napisz zasadę, np. „Kwoty zawsze cyframi i słownie”.")
    if len(tekst) > 600:
        raise ValueError("Zasada jest za długa. Jedna zasada = jedno zdanie (do 600 znaków).")
    plaski = kategorie.bez_ogonkow(tekst)
    cytaty = _cytaty(tekst)
    typ, parametry = _rozpoznaj_typ(tekst, plaski, cytaty)
    obszar = TYPY[typ][0]
    if typ == "wytyczna":
        obszar = kategorie.obszar_z_tresci(tekst)
    elif typ in ("wymagana_fraza", "zakaz_frazy") and kategorie.czesci_w_zdaniu(_tekst_zakresu(tekst)):
        obszar = obszar if typ == "zakaz_frazy" else "tresc"
    zasada = {
        "id": "",
        "tekst": tekst,
        "typ": typ,
        "parametry": parametry,
        "zakres": _zakres(tekst),
        "obszar": obszar,
        "poziom": _poziom(plaski),
        "sprawdzanie": TYPY[typ][1],
        "naprawa": TYPY[typ][2],
        "wlaczona": True,
        "zrodlo": "notariusz",
    }
    if typ == "wymagana_czesc":
        zasada["zakres"]["czesci"] = []       # sama czesc jest wymogiem, nie miejscem sprawdzania
    if typ == "wytyczna" and obszar == "inne" and re.search(r"\b(zawsze|musi|musza|kazd\w*)\b", plaski):
        zasada["obszar"] = "tresc"
    zasada["opis"] = opisz(zasada)
    return zasada


def _rozpoznaj_typ(tekst: str, plaski: str, cytaty: list[str]) -> tuple[str, dict]:
    # 1. Zamiana: "zamiast X pisz Y", "nie X, tylko Y", "X zamieniaj na Y", "X -> Y"
    if len(cytaty) >= 2 and re.search(r"\bzamiast\b|\btylko\b|\blecz\b|\bzamien|\bzastep|->|→|\bna\b", plaski):
        if re.search(r"\bzamiast\b", plaski) or re.search(r"\bnie\b.*\b(tylko|lecz|ale)\b", plaski) \
                or re.search(r"\bzamien\w*|\bzastep\w*|->|→", plaski):
            stare, nowe = cytaty[0], cytaty[1]
            if re.search(r"^\s*(zawsze\s+)?(pisz|piszemy|uzywaj|uzywamy|stosuj)\b", plaski) and "zamiast" in plaski:
                stare, nowe = cytaty[1], cytaty[0]          # "Pisz „Y” zamiast „X”"
            return "zamiana", {"zakazane": [stare], "zamiennik": nowe}
    if m := re.match(r"^\s*(.{1,60}?)\s*(?:->|→|=>)\s*(.{1,80}?)\s*$", tekst):
        return "zamiana", {"zakazane": [m.group(1).strip(" „”\"'")], "zamiennik": m.group(2).strip(" „”\"'.")}

    # 2. Format dat
    if re.search(r"\bdat[aeyi]?\b|\bdaty\b|\bdate\b", plaski):
        fmt = _format_daty_z_przykladu(tekst)
        if fmt:
            return "format_daty", fmt

    # 3. Kwoty
    if re.search(r"\bkwot|\bcen[aeyi]\b|\bzl\b|\bzlot", plaski):
        if re.search(r"slown", plaski):
            return "kwoty_slownie", {"prefiks": "słownie: " if re.search(r"slownie\s*:", plaski) else ""}
        sep = _separator_z_tekstu(tekst, plaski)
        if sep:
            return "separator_tysiecy", {"separator": sep}

    # 4. Typografia
    if "§" in tekst and re.search(r"spacj|odstep|bez spacji|lacznie|razem", plaski):
        return "spacja_paragraf", {"spacja": not re.search(r"bez spacj|bez odstep|lacznie|razem z", plaski)}
    if re.search(r"cudzyslow", plaski):
        return "cudzyslowy", {"styl": "polskie"}

    # 5. Zakaz frazy
    zakaz = re.search(r"\b(nigdy|nie)\b.{0,25}\b(uzyw|pisz|stosuj|wpisuj|wstawiaj|dodawaj|wolno|moze)|\bzakaz\w*|"
                      r"\bbez\b.{0,20}(slow|zwrot|skrot|wyrazen|sformulow)|\bunika|\bwykreslaj", plaski)
    if zakaz:
        frazy = cytaty or _fraza_bez_cytatu(tekst)
        if frazy:
            return "zakaz_frazy", {"frazy": frazy}

    # 6. Wymagana czesc aktu ("zawsze pouczenie o RODO", "kazdy akt musi miec wnioski KW")
    wymog = re.search(r"\b(zawsze|kazd\w*|wszystk\w*|musi|musza|obowiazkow\w*|wymagan\w*|nie moze zabraknac|"
                      r"dodawaj|umieszczaj|wpisuj|zamieszczaj)\b", plaski)
    if wymog and not cytaty:
        czesci = kategorie.czesci_w_zdaniu(_tekst_zakresu(tekst))
        odwolania = _odwolania_prawne(tekst)
        if odwolania:
            return "wymagana_fraza", {"frazy": odwolania}
        tylko_czesc = [c for c in czesci if c in ("rodo", "wnioski_kw", "pouczenia", "koszty", "podatki", "wypisy",
                                                   "wydanie", "zamkniecie", "oswiadczenia")]
        if tylko_czesc and not re.search(r"\b(w|we)\s+(komparycj|naglowk)", plaski):
            # najbardziej konkretna: "pouczenie o RODO" to czesc RODO, nie pouczenia ogolnie
            pierwszenstwo = ["rodo", "wnioski_kw", "podatki", "koszty", "wypisy", "wydanie",
                             "oswiadczenia", "zamkniecie", "pouczenia"]
            return "wymagana_czesc", {"czesc": min(tylko_czesc, key=pierwszenstwo.index)}
    # 7. Wymagana fraza w cudzyslowie albo konkretne oznaczenie ("PESEL zawsze w komparycji")
    if wymog and cytaty:
        return "wymagana_fraza", {"frazy": cytaty}
    if wymog and (m := re.search(r"\b(PESEL|NIP|REGON|KRS|BDO|e-mail)\b", tekst)):
        return "wymagana_fraza", {"frazy": [m.group(1)]}

    return "wytyczna", {}


def _odwolania_prawne(tekst: str) -> list[str]:
    """'pouczenie o art. 2 ust. 1 ustawy ...' -> ['art. 2 ust. 1']"""
    return [re.sub(r"\s+", " ", m.group(0)).strip()
            for m in re.finditer(r"\bart\.\s*\d+\w*(?:\s*(?:§|ust\.)\s*\d+\w*)?(?:\s*pkt\s*\d+\w*)?", tekst)]


def _fraza_bez_cytatu(tekst: str) -> list[str]:
    m = re.search(r"(?:slow\w*|zwrot\w*|skrot\w*|wyrazen\w*|sformulowan\w*|uzywaj|uzywamy|piszemy|pisz)\s+"
                  r"([^\s,.;]+(?:\s+[^\s,.;]+)?)", kategorie.bez_ogonkow(tekst))
    if not m:
        return []
    # wracamy do pisowni z ogonkami - ta sama pozycja w oryginale
    start, koniec = m.span(1)
    fraza = tekst[start:koniec].strip()
    return [fraza] if fraza and kategorie.bez_ogonkow(fraza) not in ("nigdy", "nie", "sie") else []


def _lista(frazy: list[str]) -> str:
    return ", ".join(f"„{f}”" for f in frazy)


def _opis_zakresu(zakres: dict) -> str:
    rodzaje = [kategorie.nazwa_rodzaju(r).lower() for r in zakres.get("rodzaje", [])]
    czesci = [kategorie.nazwa_czesci(c).split(" (")[0].lower() for c in zakres.get("czesci", [])]
    opis = "w każdym dokumencie" if not rodzaje else "tylko: " + ", ".join(rodzaje)
    if czesci:
        opis += " · w części: " + ", ".join(czesci)
    return opis


def _opis_daty(p: dict) -> str:
    dzien = "03" if p.get("zero") else "3"
    if p.get("styl") == "miesiac":
        return f"{dzien} grudnia 2025{p.get('sufiks', '')}"
    return f"{dzien}.12.2025{p.get('sufiks', '')}"


def opisz(zasada: dict) -> str:
    """Jednym zdaniem: jak system rozumie zasade. To widzi notariusz."""
    p = zasada.get("parametry", {})
    typ = zasada["typ"]
    if typ == "zamiana":
        co = f"Zamiast {_lista(p['zakazane'])} piszę „{p['zamiennik']}” - poprawiam sam"
    elif typ == "zakaz_frazy":
        co = f"Nie może się pojawić: {_lista(p['frazy'])} (także w innych formach)"
    elif typ == "wymagana_fraza":
        co = f"Dokument musi zawierać: {_lista(p['frazy'])}"
    elif typ == "wymagana_czesc":
        co = f"Dokument musi mieć część: {kategorie.nazwa_czesci(p['czesc']).lower()}"
    elif typ == "kwoty_slownie":
        co = "Każda kwota cyframi i słownie, np. „250.000,00 zł (dwieście pięćdziesiąt tysięcy złotych)” - dopisuję sam"
    elif typ == "separator_tysiecy":
        przyklad = {"kropka": "250.000,00 zł", "spacja": "250 000,00 zł", "brak": "250000,00 zł"}[p["separator"]]
        co = f"Kwoty zapisuję jak „{przyklad}” - poprawiam sam"
    elif typ == "format_daty":
        co = f"Daty zapisuję jak „{_opis_daty(p)}” (bez dat w tytułach ustaw) - poprawiam sam"
    elif typ == "spacja_paragraf":
        co = "Po „§” zawsze spacja: „§ 1” - poprawiam sam" if p.get("spacja") else "„§1” bez spacji - poprawiam sam"
    elif typ == "cudzyslowy":
        co = "Cudzysłowy polskie „…” - poprawiam sam"
    else:
        co = "Wytyczna przekazywana modelowi przy każdym projekcie i sprawdzana przez AI"
    pilnowanie = "nieprzekraczalna" if zasada.get("poziom") == "blokuje" else "wskazówka (tylko ostrzegam)"
    return f"{co} · {_opis_zakresu(zasada.get('zakres', {}))} · {pilnowanie}"


# ---------------------------------------------------------------------------
# Sprawdzanie
# ---------------------------------------------------------------------------
def _wzorzec_frazy(fraza: str, odmiany: bool) -> re.Pattern:
    czesci = [re.escape(s) for s in fraza.split()]
    rdzen = r"\s+".join(czesci)
    if odmiany and len(fraza.split()) == 1 and len(fraza) >= 5 and fraza.isalpha():
        temat = re.sub(r"[aeiouyąęó]+$", "", fraza, flags=re.IGNORECASE)
        if len(temat) >= 4:
            rdzen = re.escape(temat) + r"\w*"
    poczatek = r"(?<!\w)" if fraza[:1].isalnum() else ""
    koniec = r"(?!\w)" if fraza[-1:].isalnum() or rdzen.endswith(r"\w*") else ""
    return re.compile(poczatek + rdzen + koniec, re.IGNORECASE)


def _otoczenie(tekst: str, start: int, koniec: int, margines: int = 50) -> str:
    a, b = max(0, start - margines), min(len(tekst), koniec + margines)
    return ("…" if a else "") + tekst[a:b].replace("\n", " ").strip() + ("…" if b < len(tekst) else "")


_KWOTA = re.compile(r"(?<![\d,.])(\d{1,3}(?:[ . ]\d{3})+|\d+)(,\d{1,2})?\s?(zł|złotych|PLN)(?!\w)")
_DATA_CYFRY = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})\.(\d{4})(\s?r\.|\s?roku)?(?!\d)")
_DATA_MIESIAC = re.compile(r"(?<!\d)(\d{1,2})\s+(" + "|".join(_MIESIACE) + r")\s+(\d{4})(\s?r\.|\s?roku)?",
                           re.IGNORECASE)


def _w_tytule_aktu(tekst: str, start: int) -> bool:
    przed = kategorie.bez_ogonkow(tekst[max(0, start - 90):start])
    return bool(re.search(r"(ustaw|rozporz|kodeks|obwieszcz|dyrektyw|dz\.\s?u)\w*[^.;\n]{0,60}?\bz dnia\s*$", przed))


def _slownie_po(tekst: str, koniec: int) -> bool:
    po = kategorie.bez_ogonkow(tekst[koniec:koniec + 200])
    return bool(re.match(r"\s*\((slownie\s*:?)?[^)]*(zlot|grosz|/100)", po))


def _sformatuj_date(dzien: int, miesiac: int, rok: str, p: dict) -> str:
    d = f"{dzien:02d}" if p.get("zero") else str(dzien)
    if p.get("styl") == "miesiac":
        return f"{d} {_MIESIACE[miesiac - 1]} {rok}{p.get('sufiks', '')}"
    return f"{d}.{miesiac:02d}.{rok}{p.get('sufiks', '')}"


def _daty(tekst: str):
    """(start, koniec, dzien, miesiac, rok) dla dat spoza tytulow aktow prawnych."""
    for m in _DATA_CYFRY.finditer(tekst):
        if 1 <= int(m.group(2)) <= 12 and not _w_tytule_aktu(tekst, m.start()):
            yield m.start(), m.end(), int(m.group(1)), int(m.group(2)), m.group(3), m.group(0)
    for m in _DATA_MIESIAC.finditer(tekst):
        if not _w_tytule_aktu(tekst, m.start()):
            mies = _MIESIACE_PLASKIE.index(kategorie.bez_ogonkow(m.group(2)))
            yield m.start(), m.end(), int(m.group(1)), mies + 1, m.group(3), m.group(0)


def _grupuj(cyfry: str, separator: str) -> str:
    if separator == "brak" or len(cyfry) <= 3:
        return cyfry
    znak = "." if separator == "kropka" else " "
    grupy = []
    while cyfry:
        grupy.insert(0, cyfry[-3:])
        cyfry = cyfry[:-3]
    return znak.join(grupy)


def _naruszenia_reguly(zasada: dict, tekst: str, rozbior: klauzule.Rozbior) -> list[dict]:
    typ, p = zasada["typ"], zasada.get("parametry", {})
    obszar_tekstu = _tekst_w_czesciach(rozbior, zasada["zakres"].get("czesci") or [], tekst)
    wynik = []

    def dodaj(start, koniec, komunikat, naprawialne, zrodlo=None):
        zrodlo = zrodlo or tekst
        wynik.append({"komunikat": komunikat, "fragment": _otoczenie(zrodlo, start, koniec),
                      "trafienie": zrodlo[start:koniec], "naprawialne": naprawialne})

    if typ in ("zamiana", "zakaz_frazy"):
        frazy = p["zakazane"] if typ == "zamiana" else p["frazy"]
        for fraza in frazy:
            dokladny = _wzorzec_frazy(fraza, odmiany=False)
            for m in _wzorzec_frazy(fraza, odmiany=True).finditer(obszar_tekstu):
                naprawialne = typ == "zamiana" and bool(dokladny.fullmatch(m.group(0)))
                rada = f" - zamień na „{p['zamiennik']}”" if typ == "zamiana" else ""
                dodaj(m.start(), m.end(), f"Użyto „{m.group(0)}”{rada}.", naprawialne, obszar_tekstu)
    elif typ == "wymagana_fraza":
        plaski = re.sub(r"\s+", " ", kategorie.bez_ogonkow(obszar_tekstu))
        for fraza in p["frazy"]:
            if re.sub(r"\s+", " ", kategorie.bez_ogonkow(fraza)) not in plaski:
                gdzie = _opis_zakresu({"czesci": zasada["zakres"].get("czesci")}).split(" · ")[-1] \
                    if zasada["zakres"].get("czesci") else "w dokumencie"
                wynik.append({"komunikat": f"Brakuje „{fraza}” ({gdzie}).", "fragment": "", "naprawialne": False})
    elif typ == "wymagana_czesc":
        if p["czesc"] not in rozbior.czesci():
            wynik.append({"komunikat": f"Brakuje części: {kategorie.nazwa_czesci(p['czesc']).lower()}.",
                          "fragment": "", "naprawialne": False})
    elif typ == "kwoty_slownie":
        for m in _KWOTA.finditer(tekst):
            if not _slownie_po(tekst, m.end()):
                dodaj(m.start(), m.end(), f"Kwota „{m.group(0)}” bez zapisu słownie.", True)
    elif typ == "separator_tysiecy":
        for m in _KWOTA.finditer(tekst):
            cyfry = re.sub(r"\D", "", m.group(1))
            if m.group(1) != _grupuj(cyfry, p["separator"]):
                dodaj(m.start(), m.end(), f"Kwota „{m.group(0)}” zapisana inaczej niż „{_grupuj(cyfry, p['separator'])}”.", True)
    elif typ == "format_daty":
        for start, koniec, d, mi, rok, oryginal in _daty(tekst):
            oczekiwana = _sformatuj_date(d, mi, rok, p)
            if oryginal.strip() != oczekiwana.strip():
                dodaj(start, koniec, f"Data „{oryginal.strip()}” - w kancelarii: „{oczekiwana.strip()}”.", True)
    elif typ == "spacja_paragraf":
        wzor = r"§(?=\d)" if p.get("spacja") else r"§\s+(?=\d)"
        for m in re.finditer(wzor, tekst):
            dodaj(m.start(), m.end() + 2, "Zapis „§” niezgodny z zasadą kancelarii.", True)
    elif typ == "cudzyslowy":
        for m in re.finditer(r"\"([^\"\n]{1,200})\"|“([^”\n]{1,200})”", tekst):
            dodaj(m.start(), m.end(), "Cudzysłów inny niż polski „…”.", True)
    return wynik


def _tekst_w_czesciach(rozbior: klauzule.Rozbior, czesci: list[str], caly: str) -> str:
    """Tekst klauzul z danych czesci aktu. Gdy rozbior nie znalazl zadnej
    takiej klauzuli (np. krotki dokument bez wyraznych czesci), sprawdzamy
    caly tekst - lepiej niz zglaszac brak czegos, co w dokumencie jest."""
    if not czesci:
        return caly
    wybrane = [k.tekst for k in rozbior.klauzule if k.czesc in czesci]
    return "\n".join(wybrane) if wybrane else caly


def obowiazuje(zasada: dict, rodzaje: list[str]) -> bool:
    if not zasada.get("wlaczona", True):
        return False
    wymagane = zasada.get("zakres", {}).get("rodzaje") or []
    return not wymagane or bool(set(wymagane) & set(rodzaje))


def sprawdz(tekst: str, ustawienia: dict, rodzaje: list[str] | None = None) -> dict:
    """Raport zgodnosci tekstu z zasadami kancelarii i konstrukcja aktu."""
    rozbior = klauzule.rozbij(tekst)
    rodzaje = rodzaje if rodzaje is not None else [r["rodzaj"] for r in rozbior.rodzaje]
    naruszenia, sprawdzone, ai = [], 0, []
    for zasada in ustawienia.get("zasady", []):
        if not obowiazuje(zasada, rodzaje):
            continue
        if zasada["sprawdzanie"] == "ai":
            ai.append(zasada)
            continue
        sprawdzone += 1
        for n in _naruszenia_reguly(zasada, tekst, rozbior):
            naruszenia.append({**n, "zasada": zasada["id"], "tekst_zasady": zasada["tekst"],
                               "obszar": zasada["obszar"], "poziom": zasada["poziom"]})
    wylaczone = set(ustawienia.get("wbudowane_wylaczone", []))
    for problem in klauzule.sprawdz_konstrukcje(rozbior):
        if problem["kod"] in wylaczone:
            continue
        naruszenia.append({
            "komunikat": problem["komunikat"], "fragment": problem["fragment"],
            "naprawialne": problem["naprawialne"], "zasada": "wbudowana:" + problem["kod"],
            "tekst_zasady": klauzule.KONSTRUKCJA[problem["kod"]], "obszar": "struktura",
            "poziom": "ostrzega" if problem["kod"] == "numeracja_ustepow" else "blokuje",
        })
    sprawdzone += len([k for k in klauzule.KONSTRUKCJA if k not in wylaczone])
    blokujace = [n for n in naruszenia if n["poziom"] == "blokuje"]
    return {
        "zgodny": not blokujace,
        "rodzaje": [{"rodzaj": r, "nazwa": kategorie.nazwa_rodzaju(r)} for r in rodzaje],
        "sprawdzonych": sprawdzone,
        "blokujacych": len(blokujace),
        "ostrzezen": len(naruszenia) - len(blokujace),
        "naruszenia": naruszenia,
        "do_sprawdzenia_ai": ai,
    }


# ---------------------------------------------------------------------------
# Autonaprawa
# ---------------------------------------------------------------------------
def _jak_wielkosc(wzor: str, zamiennik: str) -> str:
    if wzor.isupper() and len(wzor) > 1:
        return zamiennik.upper()
    if wzor[:1].isupper():
        return zamiennik[:1].upper() + zamiennik[1:]
    return zamiennik


def napraw(tekst: str, ustawienia: dict, rodzaje: list[str] | None = None) -> tuple[str, list[dict]]:
    """Poprawki deterministyczne. Zwraca (tekst, [{zasada, opis, ile}])."""
    if rodzaje is None:
        rodzaje = [r["rodzaj"] for r in kategorie.klasyfikuj_dokument(tekst)]
    poprawki = []

    def zapisz(zasada_id: str, opis: str, ile: int) -> None:
        if ile:
            poprawki.append({"zasada": zasada_id, "opis": opis, "ile": ile})

    if "numeracja_paragrafow" not in set(ustawienia.get("wbudowane_wylaczone", [])):
        nowy, zmiany = klauzule.przenumeruj(tekst)
        if zmiany:
            tekst = nowy
            zapisz("wbudowana:numeracja_paragrafow",
                   "Przenumerowane paragrafy i odesłania: " + ", ".join(f"§ {a} → § {b}" for a, b in zmiany.items()),
                   len(zmiany))

    for zasada in ustawienia.get("zasady", []):
        if not obowiazuje(zasada, rodzaje) or not zasada.get("naprawa"):
            continue
        typ, p = zasada["typ"], zasada.get("parametry", {})
        if typ == "zamiana" and not zasada["zakres"].get("czesci"):
            for fraza in p["zakazane"]:
                tekst, ile = _wzorzec_frazy(fraza, odmiany=False).subn(
                    lambda m: _jak_wielkosc(m.group(0), p["zamiennik"]), tekst)
                zapisz(zasada["id"], f"„{fraza}” → „{p['zamiennik']}”", ile)
        elif typ == "kwoty_slownie":
            ile = 0

            def dopisz(m: re.Match) -> str:
                nonlocal ile
                if _slownie_po(tekst_teraz, m.end()):
                    return m.group(0)
                ile += 1
                return f"{m.group(0)} ({p.get('prefiks', '')}{slownie.slownie_kwoty(m.group(1) + (m.group(2) or ''))})"
            tekst_teraz = tekst
            tekst = _KWOTA.sub(dopisz, tekst)
            zapisz(zasada["id"], "Dopisane kwoty słownie", ile)
        elif typ == "separator_tysiecy":
            ile = 0

            def grupuj(m: re.Match) -> str:
                nonlocal ile
                nowe = _grupuj(re.sub(r"\D", "", m.group(1)), p["separator"])
                if nowe == m.group(1):
                    return m.group(0)
                ile += 1
                return nowe + m.group(0)[len(m.group(1)):]
            tekst = _KWOTA.sub(grupuj, tekst)
            zapisz(zasada["id"], "Ujednolicony zapis kwot", ile)
        elif typ == "format_daty":
            ile = 0
            for start, koniec, d, mi, rok, oryginal in sorted(_daty(tekst), key=lambda x: -x[0]):
                nowa = _sformatuj_date(d, mi, rok, p)
                koncowka = oryginal[len(oryginal.rstrip()):]
                if oryginal.strip() != nowa.strip():
                    tekst = tekst[:start] + nowa + koncowka + tekst[koniec:]
                    ile += 1
            zapisz(zasada["id"], f"Daty w formacie „{_opis_daty(p)}”", ile)
        elif typ == "spacja_paragraf":
            if p.get("spacja"):
                tekst, ile = re.subn(r"§(?=\d)", "§ ", tekst)
            else:
                tekst, ile = re.subn(r"§\s+(?=\d)", "§", tekst)
            zapisz(zasada["id"], "Zapis „§” wg zasady", ile)
        elif typ == "cudzyslowy":
            tekst, ile = re.subn(r"\"([^\"\n]{1,200})\"|“([^”\n]{1,200})”",
                                 lambda m: "„" + (m.group(1) or m.group(2)) + "”", tekst)
            zapisz(zasada["id"], "Polskie cudzysłowy", ile)
    return tekst, poprawki


# ---------------------------------------------------------------------------
# Egzekwowanie przed pokazaniem projektu
# ---------------------------------------------------------------------------
def egzekwuj(tekst: str, ustawienia: dict, popraw_modelem=None, sprawdz_modelem=None,
             rodzaje: list[str] | None = None) -> tuple[str, dict]:
    """Projekt po kontroli zasad + raport.

    `popraw_modelem(tekst, naruszenia) -> tekst` i `sprawdz_modelem(tekst,
    wytyczne) -> [{"zasada", "fragment", "uwaga"}]` sa opcjonalne (testy
    i tryb bez modelu). Poprawke modelu przyjmujemy tylko wtedy, gdy
    zmniejszyla liczbe naruszen blokujacych i nie skrocila dokumentu
    wyraznie - model nie moze "naprawic" aktu, wycinajac jego czesc.
    """
    rodzaje = rodzaje if rodzaje is not None else [r["rodzaj"] for r in kategorie.klasyfikuj_dokument(tekst)]
    przed = sprawdz(tekst, ustawienia, rodzaje)
    tekst, poprawki = napraw(tekst, ustawienia, rodzaje)
    raport = sprawdz(tekst, ustawienia, rodzaje)
    poprawka_modelu = None

    blokujace = [n for n in raport["naruszenia"] if n["poziom"] == "blokuje"]
    if blokujace and popraw_modelem:
        try:
            nowy = popraw_modelem(tekst, blokujace)
        except Exception as blad:  # noqa: BLE001 - poprawka jest dodatkiem, nie warunkiem
            poprawka_modelu = {"przyjeta": False, "powod": f"model niedostępny ({type(blad).__name__})"}
        else:
            nowy, dodatkowe = napraw(nowy or "", ustawienia, rodzaje)
            po = sprawdz(nowy, ustawienia, rodzaje)
            if po["blokujacych"] < raport["blokujacych"] and len(nowy) >= 0.85 * len(tekst):
                tekst, raport = nowy, po
                poprawki += dodatkowe
                poprawka_modelu = {"przyjeta": True, "usunietych": len(blokujace) - po["blokujacych"]}
            else:
                poprawka_modelu = {"przyjeta": False, "powod": "poprawka nie usunęła naruszeń"}

    wytyczne = raport.pop("do_sprawdzenia_ai")
    raport["wytyczne_ai"] = len(wytyczne)
    if wytyczne and sprawdz_modelem:
        try:
            uwagi = sprawdz_modelem(tekst, wytyczne)
        except Exception as blad:  # noqa: BLE001
            raport["wytyczne_ai_blad"] = f"nie sprawdzono ({type(blad).__name__})"
            uwagi = []
        po_id = {z["id"]: z for z in wytyczne}
        for uwaga in uwagi or []:
            zasada = po_id.get(uwaga.get("zasada"))
            if not zasada:
                continue
            raport["naruszenia"].append({
                "komunikat": str(uwaga.get("uwaga") or "Niezgodne z wytyczną.")[:300],
                "fragment": str(uwaga.get("fragment") or "")[:300], "naprawialne": False,
                "zasada": zasada["id"], "tekst_zasady": zasada["tekst"], "obszar": zasada["obszar"],
                "poziom": zasada["poziom"], "ai": True,
            })
        raport["sprawdzonych"] += len(wytyczne)
        raport["blokujacych"] = len([n for n in raport["naruszenia"] if n["poziom"] == "blokuje"])
        raport["ostrzezen"] = len(raport["naruszenia"]) - raport["blokujacych"]
        raport["zgodny"] = raport["blokujacych"] == 0

    raport["poprawki"] = poprawki
    raport["poprawka_modelu"] = poprawka_modelu
    raport["naruszen_przed"] = len(przed["naruszenia"])
    return tekst, raport


def blok_do_polecenia(ustawienia: dict, rodzaje: list[str] | None = None) -> str:
    """Zasady kancelarii dla modelu sporzadzajacego projekt."""
    zasady = [z for z in ustawienia.get("zasady", [])
              if z.get("wlaczona", True) and (rodzaje is None or obowiazuje(z, rodzaje))]
    if not zasady:
        return ""
    wiersze = []
    for i, z in enumerate(zasady, start=1):
        znacznik = "NIEPRZEKRACZALNA" if z["poziom"] == "blokuje" else "wskazowka"
        wiersze.append(f"{i}. [{znacznik}] {z['tekst']}")
    return ("ZASADY KANCELARII (projekt jest sprawdzany z nimi automatycznie, zanim zobaczy go notariusz; "
            "zasada NIEPRZEKRACZALNA ma pierwszenstwo przed wzorem i stylem):\n" + "\n".join(wiersze))


# ---------------------------------------------------------------------------
# Przechowywanie (plik kancelarii "zasady")
# ---------------------------------------------------------------------------
def domyslne() -> dict:
    return {"wersja": 1, "zasady": [], "wbudowane_wylaczone": []}


def wczytaj() -> dict:
    import magazyn
    dane = magazyn.wczytaj_plik_kancelarii(PLIK, domyslne())
    for klucz, wartosc in domyslne().items():
        dane.setdefault(klucz, wartosc)
    return dane


def _klucz_identycznosci(z: dict) -> tuple:
    return z["typ"], repr(sorted(z.get("parametry", {}).items())), repr(sorted(z["zakres"].get("rodzaje", []))), \
        repr(sorted(z["zakres"].get("czesci", [])))


def dodaj(tekst: str, nadpisania: dict | None = None, zrodlo: str = "notariusz") -> dict:
    """Zapis nowej zasady. Zwraca {"zasada", "juz_byla", "zastapiona"}."""
    import magazyn
    nowa = interpretuj(tekst)
    nowa["zrodlo"] = zrodlo
    for klucz in ("poziom", "wlaczona"):
        if nadpisania and klucz in nadpisania:
            nowa[klucz] = nadpisania[klucz]
    if nadpisania and nadpisania.get("zakres") is not None:
        nowa["zakres"] = _czysty_zakres(nadpisania["zakres"])
    if nowa["poziom"] not in POZIOMY:
        raise ValueError("Poziom zasady: blokuje albo ostrzega.")
    nowa["opis"] = opisz(nowa)

    def zmiana(dane: dict) -> dict:
        dane.setdefault("zasady", [])
        for z in dane["zasady"]:
            if _klucz_identycznosci(z) == _klucz_identycznosci(nowa) and z["typ"] != "wytyczna" \
                    or kategorie.bez_ogonkow(z["tekst"]) == kategorie.bez_ogonkow(nowa["tekst"]):
                return {"zasada": z, "juz_byla": True, "zastapiona": None}
        zastapiona = None
        if nowa["typ"] in JEDYNE:
            for z in list(dane["zasady"]):
                if z["typ"] == nowa["typ"] and z["zakres"].get("rodzaje") == nowa["zakres"].get("rodzaje"):
                    dane["zasady"].remove(z)
                    zastapiona = z
        nowa["id"] = "z" + uuid.uuid4().hex[:8]
        nowa["utworzono"] = datetime.now().isoformat(timespec="seconds")
        dane["zasady"].append(nowa)
        return {"zasada": nowa, "juz_byla": False, "zastapiona": zastapiona}

    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, domyslne())


def _czysty_zakres(zakres: dict) -> dict:
    rodzaje = [r for r in zakres.get("rodzaje", []) if r in kategorie.RODZAJE]
    czesci = [c for c in zakres.get("czesci", []) if c in kategorie.CZESCI]
    return {"rodzaje": rodzaje, "czesci": czesci}


def zmien(identyfikator: str, zmiany: dict) -> dict:
    import magazyn

    def zmiana(dane: dict) -> dict:
        for z in dane.get("zasady", []):
            if z["id"] != identyfikator:
                continue
            if "tekst" in zmiany and zmiany["tekst"] and zmiany["tekst"].strip() != z["tekst"]:
                nowa = interpretuj(zmiany["tekst"])
                for klucz in ("id", "utworzono", "wlaczona", "zrodlo"):
                    nowa[klucz] = z.get(klucz, nowa.get(klucz))
                z.clear()
                z.update(nowa)
            if "wlaczona" in zmiany:
                z["wlaczona"] = bool(zmiany["wlaczona"])
            if "poziom" in zmiany:
                if zmiany["poziom"] not in POZIOMY:
                    raise ValueError("Poziom zasady: blokuje albo ostrzega.")
                z["poziom"] = zmiany["poziom"]
            if zmiany.get("zakres") is not None:
                z["zakres"] = _czysty_zakres(zmiany["zakres"])
            z["opis"] = opisz(z)
            return z
        raise KeyError(identyfikator)

    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, domyslne())


def usun(identyfikator: str) -> None:
    import magazyn

    def zmiana(dane: dict) -> None:
        przed = len(dane.get("zasady", []))
        dane["zasady"] = [z for z in dane.get("zasady", []) if z["id"] != identyfikator]
        if len(dane["zasady"]) == przed:
            raise KeyError(identyfikator)

    magazyn.zmien_plik_kancelarii(PLIK, zmiana, domyslne())


def ustaw_wbudowana(kod: str, wlaczona: bool) -> dict:
    import magazyn
    if kod not in klauzule.KONSTRUKCJA:
        raise KeyError(kod)

    def zmiana(dane: dict) -> dict:
        wylaczone = set(dane.get("wbudowane_wylaczone", []))
        (wylaczone.discard if wlaczona else wylaczone.add)(kod)
        dane["wbudowane_wylaczone"] = sorted(wylaczone)
        return dane

    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, domyslne())


PRZYKLADY = [
    "Zamiast „w/w” pisz „wyżej wymieniony”",
    "Kwoty zawsze cyframi i słownie",
    "Daty zapisuj jak 03.12.2025 r.",
    "Nigdy nie używaj słowa „niniejszy”",
    "Po § zawsze spacja",
    "W umowach sprzedaży zawsze wnioski wieczystoksięgowe",
    "Każdy akt musi zawierać „Akt ten został odczytany, przyjęty i podpisany”",
    "Nazwiska stawających w komparycji wielkimi literami",
]
