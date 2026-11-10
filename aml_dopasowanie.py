"""Dopasowanie osob i podmiotow do list sankcyjnych i PEP - czysta logika.

Zadnego I/O: ten modul dostaje nazwe, date urodzenia i obywatelstwo strony
czynnosci oraz rekordy z list (aml_listy.py) i zwraca ocene 0-100. Dane
strony nie opuszczaja aplikacji - porownanie liczymy u siebie, w pamieci.

Przeniesione z modulu screeningu Finance You (normalize.ts, scoring.ts),
razem z jego przypadkami testowymi.

Kroki:
 1. normalizacja: male litery, usuniecie tytulow i interpunkcji, rozbicie
    nazwisk dwuczlonowych, transliteracja do ASCII; cyrylica w czterech
    wariantach (polskim, angielskim, ISO 9, ukrainskim),
 2. podobienstwo nazw: najlepsze przypisanie tokenow 1:1 (Jaro-Winkler
    ograniczony odlegloscia edycyjna, dodatkowo "szkielet" fonetyczny),
    niezalezne od kolejnosci imienia i nazwiska,
 3. data urodzenia: zgodna +10, zgodny rok +5, niezgodna -25 (bez
    automatycznego odrzucenia),
 4. obywatelstwo: czesc wspolna +3,
 5. brak daty urodzenia po ktorejkolwiek stronie: wynik najwyzej 89, czyli
    nigdy "silne trafienie" - czlowiek musi zweryfikowac.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date

# --- Normalizacja ------------------------------------------------------------

TYTULY = frozenset("""
dr dra hab inz prof mgr lek med pan pani panna ks ksiadz mr mrs ms miss sir
dame lord lady dott ing phd md msc bsc jr sr jun sen gen plk pplk mjr kpt adm
col maj capt hon sheikh shaikh haji hajji mullah imam esq herr frau monsieur
madame senor senora gospodin gospozha
""".split())

FORMY_PRAWNE = frozenset("""
sp z o oo spolka zoo sa sk ska spk spj sc llc ltd limited inc corp corporation
co company plc gmbh ag kg ooo oao zao pao ao jsc pjsc cjsc ojsc tov pat llp lp
bv nv srl sarl spa fze fzco fzc the
""".split())

_LACINSKIE = {
    "ł": "l", "Ł": "L", "ß": "ss", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe",
    "ø": "o", "Ø": "o", "đ": "d", "Đ": "d", "ð": "d", "þ": "th", "ı": "i",
    "ħ": "h", "ŧ": "t", "ĸ": "k", "ŋ": "n", "ʹ": "", "ʺ": "", "'": "", "’": "",
    "`": "",
}


def ascii_fold(tekst: str) -> str:
    """Usuwa diakrytyki (a->a, l->l, e->e, z->z) i zwraca ASCII ze spacjami."""
    zamienione = "".join(_LACINSKIE.get(z, z) for z in tekst)
    return "".join(z for z in unicodedata.normalize("NFD", zamienione)
                   if not unicodedata.combining(z))


_CYR_WSPOLNE = {
    "а": "a", "б": "b", "д": "d", "з": "z", "к": "k", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "ъ": "", "ь": "",
}
_CYR_PL = {**_CYR_WSPOLNE, "в": "w", "г": "g", "е": "e", "ё": "io", "ж": "ż", "и": "i",
           "й": "j", "л": "l", "х": "ch", "ц": "c", "ч": "cz", "ш": "sz", "щ": "szcz",
           "ы": "y", "э": "e", "ю": "iu", "я": "ia", "і": "i", "ї": "ji", "є": "je",
           "ґ": "g", "ў": "u"}
_CYR_EN = {**_CYR_WSPOLNE, "в": "v", "г": "g", "е": "e", "ё": "yo", "ж": "zh", "и": "i",
           "й": "y", "л": "l", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
           "ы": "y", "э": "e", "ю": "yu", "я": "ya", "і": "i", "ї": "yi", "є": "ye",
           "ґ": "g", "ў": "w"}
_CYR_ISO9 = {**_CYR_WSPOLNE, "в": "v", "г": "g", "е": "e", "ё": "ë", "ж": "ž", "и": "i",
             "й": "j", "л": "l", "х": "h", "ц": "c", "ч": "č", "ш": "š", "щ": "ŝ",
             "ы": "y", "э": "è", "ю": "û", "я": "â", "і": "ì", "ї": "ï", "є": "ê",
             "ґ": "g̀", "ў": "ŭ"}
_CYR_UK = {**_CYR_EN, "г": "h"}
_CYRYLICA = re.compile("[Ѐ-ӿ]")


def ma_cyrylice(tekst: str) -> bool:
    return bool(_CYRYLICA.search(tekst))


def _translituj(tekst: str, mapa: dict) -> str:
    return "".join(mapa.get(z, z) for z in tekst.lower())


def warianty_cyrylicy(tekst: str) -> dict[str, str]:
    return {
        "pl": _translituj(tekst, _CYR_PL),
        "en": _translituj(tekst, _CYR_EN),
        "iso9": _translituj(tekst, _CYR_ISO9),
        "uk": _translituj(tekst, _CYR_UK),
    }


_SEPARATORY = re.compile(r"[-‐‑‒–—_/]")
_NIE_ASCII = re.compile(r"[^a-z0-9\s]")


def tokeny(tekst: str, podmiot: bool = False) -> list[str]:
    """ASCII, male litery, bez tytulow i interpunkcji; "Nowak-Jezioranska"
    daje dwa tokeny. Dla podmiotow pomija formy prawne (sp. z o.o., ltd)."""
    zlozone = ascii_fold(tekst.lower())
    zlozone = _NIE_ASCII.sub(" ", _SEPARATORY.sub(" ", zlozone))
    wynik = []
    for t in zlozone.split():
        if t in TYTULY:
            continue
        if podmiot and t in FORMY_PRAWNE:
            continue
        wynik.append(t)
    return wynik


def znormalizuj(tekst: str, podmiot: bool = False) -> str:
    return " ".join(tokeny(tekst, podmiot))


def szkielet(token: str) -> str:
    """"Szkielet" fonetyczny: Lukaszenko / Lukashenko / Lukasenko daja to samo.
    Uzywany tylko jako drugi, zdyskontowany sposob porownania."""
    t = re.sub(r"szcz|shch|sch", "s", token)
    t = re.sub(r"sz|sh|zh|rz|zs", "s", t)
    t = re.sub(r"tsch|tch|cz|ch|kh|ts|tz|c", "k", t)
    t = t.replace("ph", "f").replace("w", "v").replace("x", "ks")
    t = re.sub(r"[yj]", "i", t)
    t = re.sub(r"ck|q", "k", t)
    t = re.sub(r"(.)\1+", r"\1", t)
    return t.replace("h", "").replace("s", "z")


@dataclass
class Wariant:
    klucz: str
    tokeny: list[str]
    pochodzenie: str


def warianty(tekst: str, podmiot: bool = False, pochodzenie: str = "nazwa") -> list[Wariant]:
    """Zapis oryginalny (po zlozeniu do ASCII) oraz, dla cyrylicy,
    transliteracje PL / EN / ISO 9 / UK. Bez duplikatow."""
    surowe: list[tuple[str, str]] = []
    if ma_cyrylice(tekst):
        w = warianty_cyrylicy(tekst)
        surowe += [(w["pl"], f"{pochodzenie}:translit_pl"), (w["en"], f"{pochodzenie}:translit_en"),
                   (w["iso9"], f"{pochodzenie}:translit_iso9"), (w["uk"], f"{pochodzenie}:translit_uk")]
    else:
        surowe.append((tekst, pochodzenie))
    widziane: set[str] = set()
    wynik = []
    for t, p in surowe:
        tok = tokeny(t, podmiot)
        if not tok:
            continue
        klucz = " ".join(tok)
        if klucz in widziane:
            continue
        widziane.add(klucz)
        wynik.append(Wariant(klucz, tok, p))
    return wynik


# --- Daty i kraje ------------------------------------------------------------

_MIESIACE_PL = {
    "stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04", "maja": "05",
    "czerwca": "06", "lipca": "07", "sierpnia": "08", "wrzesnia": "09",
    "pazdziernika": "10", "listopada": "11", "grudnia": "12",
}


def data_czesciowa(surowe) -> tuple[str | None, int | None]:
    """ISO, DD.MM.YYYY, sam rok, ISO z czasem -> (YYYY-MM-DD albo None, rok)."""
    if surowe is None:
        return None, None
    s = str(surowe).strip()
    if not s:
        return None, None
    m = re.match(r"^\+?(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}", int(m[1])
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$", s)
    if m:
        return f"{m[3]}-{m[2].zfill(2)}-{m[1].zfill(2)}", int(m[3])
    m = re.match(r"^(\d{4})$", s)
    if m:
        return None, int(m[1])
    m = re.search(r"(\d{4})", s)
    return None, (int(m[1]) if m else None)


def data_z_tekstu_pl(tekst: str) -> tuple[str | None, int | None]:
    """"urodzony 5 pazdziernika 1973 r." -> 1973-10-05 (lista MSWiA)."""
    f = ascii_fold(tekst.lower())
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", f)
    if m and m[2] in _MIESIACE_PL:
        return f"{m[3]}-{_MIESIACE_PL[m[2]]}-{m[1].zfill(2)}", int(m[3])
    r = re.search(r"\b(1[89]\d{2}|20\d{2})\b", f)
    return None, (int(r[1]) if r else None)


_KRAJE = {
    "polska": "PL", "poland": "PL", "polish": "PL", "rosja": "RU", "russia": "RU",
    "russian federation": "RU", "russian": "RU", "bialorus": "BY", "belarus": "BY",
    "belarusian": "BY", "ukraina": "UA", "ukraine": "UA", "ukrainian": "UA",
    "niemcy": "DE", "germany": "DE", "german": "DE", "iran": "IR",
    "iran (islamic republic of)": "IR", "syria": "SY", "syrian arab republic": "SY",
    "korea, democratic people's republic of": "KP", "democratic people's republic of korea": "KP",
    "north korea": "KP", "china": "CN", "chiny": "CN", "united states": "US", "usa": "US",
    "united kingdom": "GB", "wielka brytania": "GB", "kazakhstan": "KZ", "litwa": "LT",
    "lithuania": "LT", "lotwa": "LV", "latvia": "LV", "estonia": "EE", "czechy": "CZ",
    "czech republic": "CZ", "slowacja": "SK", "slovakia": "SK", "afghanistan": "AF",
    "iraq": "IQ", "libya": "LY", "sudan": "SD", "yemen": "YE", "venezuela": "VE",
    "cuba": "CU", "myanmar": "MM", "somalia": "SO", "mali": "ML", "lebanon": "LB",
}


def kraj(surowe) -> str | None:
    """ISO alpha-2 wielkimi literami; popularne nazwy krajow mapowane."""
    if surowe is None:
        return None
    s = str(surowe).strip()
    if not s:
        return None
    if re.fullmatch(r"[A-Za-z]{2}", s):
        return s.upper()
    return _KRAJE.get(re.sub(r"\s+", " ", ascii_fold(s.lower())))


# --- Rekordy -----------------------------------------------------------------


@dataclass
class Rekord:
    """Wpis z listy referencyjnej (sankcje albo PEP). Jeden ksztalt dla obu."""
    zrodlo: str                      # eu_fsf | un_sc | mswia | ofac_sdn | sejm | wikidata | kprm
    identyfikator: str
    rodzaj: str                      # osoba | podmiot | statek | samolot | nieznany
    nazwy: list[str]                 # pierwsza = glowna, dalej aliasy
    daty_urodzenia: list[str] = field(default_factory=list)   # 'YYYY-MM-DD' albo 'YYYY'
    obywatelstwa: list[str] = field(default_factory=list)
    program: str | None = None
    wpisano: str | None = None
    wykreslono: str | None = None
    uwagi: str | None = None
    adres_zrodla: str | None = None
    funkcje: list[dict] = field(default_factory=list)   # PEP: {tytul, kod, od, do}
    aktualny: bool | None = None                        # PEP: zrodlo mowi, ze funkcja trwa

    def slownik(self) -> dict:
        return asdict(self)

    @classmethod
    def ze_slownika(cls, d: dict) -> "Rekord":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__} | {
            "nazwy": list(d.get("nazwy") or []),
            "daty_urodzenia": list(d.get("daty_urodzenia") or []),
            "obywatelstwa": list(d.get("obywatelstwa") or []),
            "funkcje": list(d.get("funkcje") or []),
        })


@dataclass
class Podmiot:
    """Strona czynnosci do sprawdzenia."""
    nazwy: list[str]
    rodzaj: str = "osoba"            # osoba | podmiot
    data_urodzenia: str | None = None
    rok_urodzenia: int | None = None
    obywatelstwa: list[str] = field(default_factory=list)


@dataclass
class Ustawienia:
    prog_mozliwe: int = 70
    prog_silne: int = 90
    premia_data: int = 10
    premia_rok: int = 5
    kara_data: int = 25
    premia_kraj: int = 3


DOMYSLNE = Ustawienia()


# --- Podobienstwo ------------------------------------------------------------


def jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    okno = max(0, max(la, lb) // 2 - 1)
    a_dop = [False] * la
    b_dop = [False] * lb
    dopasowania = 0
    for i in range(la):
        for j in range(max(0, i - okno), min(i + okno + 1, lb)):
            if b_dop[j] or a[i] != b[j]:
                continue
            a_dop[i] = b_dop[j] = True
            dopasowania += 1
            break
    if not dopasowania:
        return 0.0
    transpozycje = 0
    k = 0
    for i in range(la):
        if not a_dop[i]:
            continue
        while not b_dop[k]:
            k += 1
        if a[i] != b[k]:
            transpozycje += 1
        k += 1
    return (dopasowania / la + dopasowania / lb + (dopasowania - transpozycje / 2) / dopasowania) / 3


def jaro_winkler(a: str, b: str, p: float = 0.1) -> float:
    j = jaro(a, b)
    l = 0
    while l < 4 and l < len(a) and l < len(b) and a[l] == b[l]:
        l += 1
    return j + l * p * (1 - j)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    poprzedni = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        biezacy = [i]
        for j in range(1, len(b) + 1):
            biezacy.append(min(poprzedni[j] + 1, biezacy[j - 1] + 1,
                               poprzedni[j - 1] + (0 if a[i - 1] == b[j - 1] else 1)))
        poprzedni = biezacy
    return poprzedni[len(b)]


def _podobienstwo_pary(a: str, b: str) -> float:
    """JW ograniczony od gory odlegloscia edycyjna (+0,1). Sam JW jest za
    lagodny dla krotkich nazwisk o wspolnym poczatku (Nowak / Nowicki)."""
    lev = 1 - levenshtein(a, b) / max(len(a), len(b))
    return min(jaro_winkler(a, b), lev + 0.1)


def podobienstwo_tokenow(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b)):
        return 0.9                       # inicjal: "j" vs "jan"
    if len(a) == 1 or len(b) == 1:
        return 0.0
    wprost = _podobienstwo_pary(a, b)
    sa, sb = szkielet(a), szkielet(b)
    fonetycznie = 0.0
    if sa and sb:
        fonetycznie = 0.96 if sa == sb else _podobienstwo_pary(sa, sb) * 0.9
    return max(wprost, fonetycznie)


def _efektywne(sim: float) -> float:
    """Slabe pary (np. inne imie) mocno obnizaja wynik zamiast sie usredniac."""
    return sim if sim >= 0.85 else sim ** 3


def podobienstwo_zbiorow(s: list[str], r: list[str]) -> tuple[float, list[dict], int]:
    """Najlepsze przypisanie tokenow 1:1 metoda zachlanna (zbiory sa male)."""
    S = list(dict.fromkeys(s))
    R = list(dict.fromkeys(r))
    if not S or not R:
        return 0.0, [], max(len(S), len(R))
    kandydaci = sorted(((podobienstwo_tokenow(S[i], R[j]), i, j)
                        for i in range(len(S)) for j in range(len(R))),
                       key=lambda x: -x[0])
    uzyte_s: set[int] = set()
    uzyte_r: set[int] = set()
    pary: list[dict] = []
    k = min(len(S), len(R))
    for sim, i, j in kandydaci:
        if len(pary) >= k:
            break
        if i in uzyte_s or j in uzyte_r:
            continue
        uzyte_s.add(i)
        uzyte_r.add(j)
        pary.append({"podmiot": S[i], "rekord": R[j], "podobienstwo": round(sim, 3)})
    wynik = sum(_efektywne(p["podobienstwo"]) for p in pary) / k
    if k == 1 and max(len(S), len(R)) > 1:
        wynik *= 0.75                    # pojedynczy token to slaby dowod
    niedopasowane = max(len(S), len(R)) - k
    wynik -= min(0.08, 0.03 * niedopasowane)
    return max(0.0, wynik), pary, niedopasowane


# --- Ocena -------------------------------------------------------------------


@dataclass
class Ocena:
    wynik_nazwy: int
    nazwa_podmiotu: str
    nazwa_rekordu: str
    pary: list[dict]
    niedopasowane: int
    data: str                 # zgodna | zgodny_rok | niezgodna | brak_w_zrodle | brak_u_podmiotu | nie_dotyczy
    korekta_daty: int
    kraj: str                 # zgodny | brak_wspolnego | nieznany
    korekta_kraju: int
    ograniczenie: str | None
    razem: int
    pasmo: str                # brak | mozliwe | silne


def _skladnik_daty(podmiot: Podmiot, daty: list[str], u: Ustawienia) -> tuple[str, int]:
    znane = [data_czesciowa(d) for d in daty]
    znane = [(d, r) for d, r in znane if d or r]
    if not podmiot.data_urodzenia and not podmiot.rok_urodzenia:
        return "brak_u_podmiotu", 0
    if not znane:
        return "brak_w_zrodle", 0
    najlepszy = ("niezgodna", -u.kara_data)
    rok_p = podmiot.rok_urodzenia or (int(podmiot.data_urodzenia[:4]) if podmiot.data_urodzenia else None)
    for d, r in znane:
        if podmiot.data_urodzenia and d and podmiot.data_urodzenia == d:
            return "zgodna", u.premia_data
        rok_r = r or (int(d[:4]) if d else None)
        # Zgodny rok liczy sie tylko, gdy jedna ze stron zna wylacznie rok.
        if rok_p and rok_r and rok_p == rok_r and (not podmiot.data_urodzenia or not d):
            najlepszy = ("zgodny_rok", u.premia_rok)
    return najlepszy


def _skladnik_kraju(podmiot: list[str], rekord: list[str], u: Ustawienia) -> tuple[str, int]:
    if not podmiot or not rekord:
        return "nieznany", 0
    zbior = {k.upper() for k in podmiot}
    return ("zgodny", u.premia_kraj) if any(k.upper() in zbior for k in rekord) else ("brak_wspolnego", 0)


def pasmo(wynik: int, u: Ustawienia = DOMYSLNE) -> str:
    if wynik >= u.prog_silne:
        return "silne"
    if wynik >= u.prog_mozliwe:
        return "mozliwe"
    return "brak"


def ocen(podmiot: Podmiot, rekord: Rekord, u: Ustawienia = DOMYSLNE) -> Ocena:
    """Pelna ocena pary strona czynnosci - rekord z listy."""
    jest_podmiotem = podmiot.rodzaj == "podmiot"
    rekord_podmiot = rekord.rodzaj == "podmiot" or jest_podmiotem
    najlepsze = (-1.0, "", "", [], 0)
    w_podmiotu = [w for n in podmiot.nazwy for w in warianty(n, jest_podmiotem)]
    w_rekordu = [w for n in rekord.nazwy for w in warianty(n, rekord_podmiot)]
    for wp in w_podmiotu:
        for wr in w_rekordu:
            wynik, pary, niedop = podobienstwo_zbiorow(wp.tokeny, wr.tokeny)
            if wynik > najlepsze[0]:
                najlepsze = (wynik, wp.klucz, wr.klucz, pary, niedop)
    wynik_nazwy = round(max(0.0, najlepsze[0]) * 100)

    if jest_podmiotem or rekord.rodzaj == "podmiot":
        data, kor_d = "nie_dotyczy", 0
    else:
        data, kor_d = _skladnik_daty(podmiot, rekord.daty_urodzenia, u)
    kraj_, kor_k = _skladnik_kraju(podmiot.obywatelstwa, rekord.obywatelstwa, u)

    razem = wynik_nazwy + kor_d + kor_k
    if wynik_nazwy < u.prog_mozliwe:
        razem = min(razem, wynik_nazwy)  # premie nie podnosza slabej nazwy ponad prog
    razem = max(0, min(100, razem))

    ograniczenie = None
    if data in ("brak_w_zrodle", "brak_u_podmiotu"):
        sufit = u.prog_silne - 1
        if razem > sufit:
            razem = sufit
            ograniczenie = "brak daty urodzenia w zrodle" if data == "brak_w_zrodle" \
                else "brak daty urodzenia strony"

    return Ocena(wynik_nazwy, najlepsze[1], najlepsze[2], najlepsze[3], najlepsze[4],
                 data, kor_d, kraj_, kor_k, ograniczenie, razem, pasmo(razem, u))


# --- Indeks ------------------------------------------------------------------


class Indeks:
    """Rekordy jednej kategorii (sankcje albo PEP) z indeksem tokenow do
    wstepnej selekcji. Bez niego kazda strona czynnosci bylaby porownywana
    z kazdym wpisem listy."""

    def __init__(self, rekordy: list[Rekord]):
        self.rekordy = rekordy
        self.po_tokenie: dict[str, set[int]] = {}
        self.po_szkielecie: dict[str, set[int]] = {}
        self.po_literze: dict[str, set[str]] = {}
        for i, r in enumerate(rekordy):
            podmiot = r.rodzaj == "podmiot"
            for n in r.nazwy:
                for w in warianty(n, podmiot):
                    for t in w.tokeny:
                        if len(t) < 2:
                            continue
                        self.po_tokenie.setdefault(t, set()).add(i)
                        self.po_szkielecie.setdefault(szkielet(t), set()).add(i)
                        self.po_literze.setdefault(t[0], set()).add(t)

    def __len__(self) -> int:
        return len(self.rekordy)

    def kandydaci(self, podmiot: Podmiot) -> set[int]:
        wynik: set[int] = set()
        jest_podmiotem = podmiot.rodzaj == "podmiot"
        szukane = {t for n in podmiot.nazwy for w in warianty(n, jest_podmiotem) for t in w.tokeny}
        for t in szukane:
            if len(t) < 2:
                continue
            wynik |= self.po_tokenie.get(t, set())
            wynik |= self.po_szkielecie.get(szkielet(t), set())
            if len(t) < 3:
                continue
            # Literowki: tokeny o tej samej pierwszej literze i zblizonej dlugosci.
            for inny in self.po_literze.get(t[0], ()):
                if abs(len(inny) - len(t)) <= 3 and inny != t and jaro_winkler(t, inny) >= 0.88:
                    wynik |= self.po_tokenie[inny]
        return wynik

    def szukaj(self, podmiot: Podmiot, u: Ustawienia = DOMYSLNE,
               najwyzej: int = 10) -> list[tuple[Ocena, Rekord]]:
        """Trafienia od progu "mozliwe", najlepsze pierwsze."""
        trafienia = []
        for i in self.kandydaci(podmiot):
            r = self.rekordy[i]
            if podmiot.rodzaj == "osoba" and r.rodzaj not in ("osoba", "nieznany"):
                continue
            if podmiot.rodzaj == "podmiot" and r.rodzaj == "osoba":
                continue
            o = ocen(podmiot, r, u)
            if o.pasmo != "brak":
                trafienia.append((o, r))
        trafienia.sort(key=lambda x: -x[0].razem)
        return trafienia[:najwyzej]


# --- PEP: status czasowy -----------------------------------------------------


def pep_status(rekord: Rekord, dzis: date | None = None, karencja_miesiecy: int = 12) -> str:
    """"pep" gdy funkcja trwa albo skonczyla sie w okresie karencji,
    "byly_pep" gdy dawniej, "nieznany" gdy zrodlo nie podaje dat."""
    dzis = dzis or date.today()
    if rekord.aktualny:
        return "pep"
    koniec: list[date] = []
    for f in rekord.funkcje:
        do = f.get("do")
        if not do:
            if f.get("od") or rekord.aktualny is None:
                return "pep"
            continue
        d, _ = data_czesciowa(do)
        if d:
            koniec.append(date.fromisoformat(d))
    if not koniec:
        return "nieznany" if not rekord.funkcje else "byly_pep"
    ostatni = max(koniec)
    miesiac, rok = dzis.month - karencja_miesiecy, dzis.year
    while miesiac <= 0:
        miesiac += 12
        rok -= 1
    granica = date(rok, miesiac, min(dzis.day, 28))
    return "pep" if ostatni >= granica else "byly_pep"
