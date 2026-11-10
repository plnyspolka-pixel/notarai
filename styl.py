"""Styl kancelarii: nauka z wczesniejszych aktow i personalizacja projektow.

Notariusz wrzuca swoje stare akty (.docx, .pdf z warstwa tekstowa, .txt).
Dla kazdego aktu:
  1. silnik klauzul rozbiera tekst na klauzule i przypisuje im czesci aktu,
  2. kazda klauzula jest pseudonimizowana (klauzule.pseudonimizuj) -
     do profilu trafia wylacznie szkielet bez danych klientow,
  3. liczymy nawyki redakcyjne: format dat i kwot, zapis §, cudzyslowy,
     wybory slownikowe ("Stawajacy" czy "Stawiajacy"),
  4. podobne sformulowania z roznych aktow lacza sie w jedno (licznik
     wystapien), wiec profil pokazuje, jak kancelaria pisze NAPRAWDE,
     a nie jak napisano jeden akt.
Surowego tekstu aktu nie zapisujemy nigdzie i nie logujemy.

Z profilu powstaja:
  - blok STYL KANCELARII dla modelu sporzadzajacego projekt (wskazowki),
  - sugestie zasad ("w 9 z 10 aktow daty piszesz jak 03.12.2025 r." ->
    jednym kliknieciem nieprzekraczalna zasada w zasady.py).
"""
import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

import kategorie
import klauzule
import zasady

PLIK = "styl"
ROZSZERZENIA = {".docx", ".txt", ".md", ".pdf"}
MAX_SFORMULOWAN = 400
PROG_PODOBIENSTWA = 0.86
MIN_DLUGOSC, MAX_DLUGOSC = 25, 1500

# Wybory slownikowe, ktore kancelarie rozstrzygaja roznie. Kazdy wariant:
# (etykieta, wzorzec na tekscie bez ogonkow, zdanie zasady gdy wariant jest
# "przegrany" - interpretowane przez zasady.interpretuj()).
SLOWNICTWO = {
    "stawajacy": ("Stawający / Stawiający", [
        ("Stawający", r"\bstawajac", "Pisz „Stawający” zamiast „Stawiający”"),
        ("Stawiający", r"\bstawiajac", "Pisz „Stawiający” zamiast „Stawający”"),
    ]),
    "wyzej_wymieniony": ("wyżej wymieniony / w/w", [
        ("wyżej wymieniony", r"wyzej wymienion", "Nigdy nie używaj skrótu „w/w”"),
        ("w/w", r"(?<!\w)w/w(?!\w)", None),
    ]),
    "niniejszy": ("niniejszy akt / ten akt", [
        ("niniejszy", r"\bniniejsz\w*", None),
        ("ten akt", r"\b(tego|ten|tym) aktu?\b", "Staraj się unikać słowa „niniejszy”"),
    ]),
    "zamieszkaly": ("zamieszkały / zam.", [
        ("zamieszkały", r"\bzamieszkal", "Nigdy nie używaj skrótu „zam.”"),
        ("zam.", r"(?<!\w)zam\.", None),
    ]),
    "tozsamosc": ("legitymujący się / tożsamość ustalona", [
        ("legitymujący się", r"legitymujac\w* sie", None),
        ("tożsamość ustalona na podstawie", r"tozsamosc\w*.{0,40}ustal", None),
    ]),
    "waluta": ("zł / PLN", [
        ("zł", r"\d\s?zl\b", "Pisz „zł” zamiast „PLN”"),
        ("PLN", r"\d\s?pln\b", None),
    ]),
    "kupujacy": ("Kupujący / Nabywca", [
        ("Kupujący", r"\bkupujac", None),
        ("Nabywca", r"\bnabywc", None),
    ]),
    "sprzedajacy": ("Sprzedający / Zbywca", [
        ("Sprzedający", r"\bsprzedajac", None),
        ("Zbywca", r"\bzbywc", None),
    ]),
}
_SLOWNICTWO_WZORCE = {k: [(e, re.compile(w), z) for e, w, z in warianty]
                      for k, (_, warianty) in SLOWNICTWO.items()}

# Jak nazwac rodzaj czynnosci w zdaniu zasady, zeby interpretuj() rozpoznal zakres.
_RODZAJ_W_ZDANIU = {
    "sprzedaz": "W umowach sprzedaży", "sprzedaz_rolna": "Przy sprzedaży nieruchomości rolnych",
    "darowizna": "W umowach darowizny", "zamiana": "W umowach zamiany",
    "przedwstepna": "W umowach przedwstępnych", "deweloperska": "W umowach deweloperskich",
    "odrebna_wlasnosc": "Przy ustanowieniu odrębnej własności lokalu", "sluzebnosc": "Przy służebnościach",
    "hipoteka": "Przy hipotekach", "pelnomocnictwo": "W pełnomocnictwach", "testament": "W testamentach",
    "dzial_spadku": "W działach spadku", "zniesienie_wspolwlasnosci": "Przy zniesieniu współwłasności",
    "podzial_majatku": "Przy podziale majątku", "intercyza": "W intercyzach", "dozywocie": "W umowach dożywocia",
}
_CZESC_W_ZDANIU = {
    "wnioski_kw": "zawsze wnioski wieczystoksięgowe", "rodo": "zawsze klauzula o ochronie danych osobowych",
    "podatki": "zawsze postanowienia o podatkach", "koszty": "zawsze informacja o taksie i kosztach",
    "wypisy": "zawsze postanowienie o wypisach", "pouczenia": "zawsze pouczenia notariusza",
    "zamkniecie": "zawsze formuła odczytania i podpisania", "wydanie": "zawsze wydanie przedmiotu umowy",
}


# ---------------------------------------------------------------------------
# Odczyt pliku
# ---------------------------------------------------------------------------
class NieobslugiwanyPlik(ValueError):
    pass


def tekst_z_pliku(sciezka: Path) -> str:
    rozszerzenie = sciezka.suffix.lower()
    if rozszerzenie not in ROZSZERZENIA:
        raise NieobslugiwanyPlik(
            "Obsługuję .docx, .pdf z tekstem i .txt. Stary .doc zapisz w Wordzie jako .docx.")
    if rozszerzenie == ".pdf":
        import fitz
        with fitz.open(sciezka) as pdf:
            tekst = "\n".join(strona.get_text() for strona in pdf)
        if len(tekst.strip()) < 200:
            raise NieobslugiwanyPlik(
                "Ten PDF to skan bez warstwy tekstowej. Do nauki stylu wgraj akt w Wordzie albo PDF z tekstem.")
        return tekst
    import dokumenty
    return dokumenty.wzor_na_tekst(sciezka)


# ---------------------------------------------------------------------------
# Analiza jednego aktu (nic nie zapisuje)
# ---------------------------------------------------------------------------
def _nawyki(tekst: str) -> dict:
    plaski = kategorie.bez_ogonkow(tekst)
    daty = Counter()
    for _, _, _, _, _, oryginal in zasady._daty(tekst):
        sufiks_m = re.search(r"(\s?r\.|\s?roku)$", oryginal.strip())
        sufiks = zasady._sufiks(sufiks_m.group(1)) if sufiks_m else ""
        rdzen = re.sub(r"(\s?r\.|\s?roku)$", "", oryginal.strip())
        styl = "cyfry" if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", rdzen) else "miesiac"
        zero = bool(re.match(r"0\d", rdzen))
        daty[f"{styl}|{int(zero)}|{sufiks}"] += 1
    kwoty = list(zasady._KWOTA.finditer(tekst))
    slownie_tak = sum(1 for m in kwoty if zasady._slownie_po(tekst, m.end()))
    separatory = Counter()
    for m in kwoty:
        cyfry = m.group(1)
        if len(re.sub(r"\D", "", cyfry)) > 3:
            separatory["kropka" if "." in cyfry else "spacja" if re.search(r"[  ]", cyfry) else "brak"] += 1
    slownictwo = {}
    for klucz, warianty in _SLOWNICTWO_WZORCE.items():
        liczby = {e: len(w.findall(plaski)) for e, w, _ in warianty}
        if any(liczby.values()):
            slownictwo[klucz] = liczby
    return {
        "daty": dict(daty),
        "kwoty_slownie": {"tak": slownie_tak, "nie": len(kwoty) - slownie_tak},
        "separator": dict(separatory),
        "paragraf": {"spacja": len(re.findall(r"§\s+\d", tekst)), "bez": len(re.findall(r"§\d", tekst))},
        "cudzyslowy": {"polskie": len(re.findall(r"„[^”\n]{1,200}”", tekst)),
                       "proste": len(re.findall(r"\"[^\"\n]{1,200}\"", tekst))},
        "slownictwo": slownictwo,
    }


def _odwolania_w_akcie(rozbior: klauzule.Rozbior) -> set[str]:
    """Przepisy przywolywane w pouczeniach - kandydaci na wymagane pouczenia."""
    wynik = set()
    for k in rozbior.klauzule:
        if k.czesc != "pouczenia":
            continue
        for m in re.finditer(r"\bart\.\s*\d+\w*(?:\s*(?:§|ust\.)\s*\d+\w*)?", k.tekst):
            wynik.add(re.sub(r"\s+", " ", m.group(0)))
    return wynik


def analizuj(tekst: str) -> dict:
    rozbior = klauzule.rozbij(tekst)
    pozycje = []
    for i, k in enumerate(rozbior.klauzule):
        if k.typ == "paragraf" and not k.tekst:
            continue
        szkielet = klauzule.pseudonimizuj(k.tekst)
        if not (MIN_DLUGOSC <= len(szkielet) <= MAX_DLUGOSC) or klauzule.ma_dane_osobowe(szkielet):
            continue
        pozycje.append({"id": klauzule.identyfikator(k.tekst), "czesc": k.czesc, "szkielet": szkielet})
    return {
        "rodzaje": [r["rodzaj"] for r in rozbior.rodzaje],
        "klauzule": pozycje,
        "czesci": sorted({k.czesc for k in rozbior.klauzule}),
        "odwolania": sorted(_odwolania_w_akcie(rozbior)),
        "nawyki": _nawyki(tekst),
    }


# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------
def domyslny() -> dict:
    return {"wersja": 1, "akty": [], "sformulowania": [], "nawyki": {}, "sugestie_odrzucone": []}


def wczytaj() -> dict:
    import magazyn
    dane = magazyn.wczytaj_plik_kancelarii(PLIK, domyslny())
    for klucz, wartosc in domyslny().items():
        dane.setdefault(klucz, wartosc)
    return dane


def _dodaj_licznik(cel: dict, zrodlo: dict) -> None:
    for klucz, wartosc in zrodlo.items():
        if isinstance(wartosc, dict):
            _dodaj_licznik(cel.setdefault(klucz, {}), wartosc)
        else:
            cel[klucz] = cel.get(klucz, 0) + wartosc


def _wlacz_sformulowanie(profil: dict, pozycja: dict, rodzaje: list[str], akt: str) -> None:
    for s in profil["sformulowania"]:
        if s["czesc"] != pozycja["czesc"]:
            continue
        if s["id"] == pozycja["id"] or (
                0.7 <= len(s["szkielet"]) / max(1, len(pozycja["szkielet"])) <= 1.4
                and klauzule.podobienstwo(s["szkielet"], pozycja["szkielet"]) >= PROG_PODOBIENSTWA):
            if akt not in s["akty"]:
                s["wystapien"] += 1
                s["akty"].append(akt)
            s["rodzaje"] = sorted(set(s["rodzaje"]) | set(rodzaje))
            return
    profil["sformulowania"].append({
        "id": pozycja["id"], "czesc": pozycja["czesc"], "szkielet": pozycja["szkielet"],
        "rodzaje": sorted(set(rodzaje)), "wystapien": 1, "akty": [akt],
        "przypiete": False, "ukryte": False, "wlasne": False,
    })


def _przytnij(profil: dict) -> None:
    if len(profil["sformulowania"]) <= MAX_SFORMULOWAN:
        return
    profil["sformulowania"].sort(key=lambda s: (not s["przypiete"], not s.get("wlasne"), -s["wystapien"]))
    profil["sformulowania"] = profil["sformulowania"][:MAX_SFORMULOWAN]


def naucz(analizy: list[dict]) -> dict:
    """Wlaczenie przeanalizowanych aktow do profilu kancelarii."""
    import magazyn

    def zmiana(profil: dict) -> dict:
        for klucz, wartosc in domyslny().items():
            profil.setdefault(klucz, wartosc)
        dodane = []
        for analiza in analizy:
            akt_id = "a" + uuid.uuid4().hex[:8]
            numer = len(profil["akty"]) + 1
            glowny = analiza["rodzaje"][0] if analiza["rodzaje"] else kategorie.RODZAJ_INNY
            profil["akty"].append({
                "id": akt_id, "etykieta": f"Akt {numer} · {kategorie.nazwa_rodzaju(glowny)}",
                "rodzaje": analiza["rodzaje"], "klauzul": len(analiza["klauzule"]),
                "czesci": analiza["czesci"], "odwolania": analiza["odwolania"],
                "dodano": datetime.now().isoformat(timespec="seconds"),
            })
            for pozycja in analiza["klauzule"]:
                _wlacz_sformulowanie(profil, pozycja, analiza["rodzaje"], akt_id)
            _dodaj_licznik(profil["nawyki"], analiza["nawyki"])
            dodane.append(profil["akty"][-1])
        _przytnij(profil)
        return {"dodane": dodane, "aktow": len(profil["akty"]), "sformulowan": len(profil["sformulowania"])}

    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, domyslny())


def zapamietaj_sformulowanie(tekst: str) -> dict:
    """Fragment zaznaczony przez notariusza w projekcie -> wzorcowe sformulowanie."""
    import magazyn
    szkielet = klauzule.pseudonimizuj(tekst)
    if len(szkielet) < 10:
        raise ValueError("Zaznacz dłuższy fragment - co najmniej pół zdania.")
    if len(szkielet) > MAX_DLUGOSC:
        raise ValueError("Zaznaczony fragment jest za długi. Zapamiętuję pojedyncze klauzule.")
    if klauzule.ma_dane_osobowe(szkielet):
        raise ValueError("We fragmencie zostały dane osobowe, których nie umiem usunąć. Zaznacz sam tekst klauzuli.")
    czesc, _ = kategorie.klasyfikuj_czesc(tekst)
    rodzaje = [r["rodzaj"] for r in kategorie.klasyfikuj_dokument(tekst) if r["rodzaj"] != kategorie.RODZAJ_INNY]

    def zmiana(profil: dict) -> dict:
        for klucz, wartosc in domyslny().items():
            profil.setdefault(klucz, wartosc)
        nowe_id = klauzule.identyfikator(tekst)
        for s in profil["sformulowania"]:
            if s["id"] == nowe_id:
                s.update(przypiete=True, ukryte=False)
                return s
        wpis = {"id": nowe_id, "czesc": czesc, "szkielet": szkielet, "rodzaje": rodzaje, "wystapien": 1,
                "akty": [], "przypiete": True, "ukryte": False, "wlasne": True}
        profil["sformulowania"].append(wpis)
        _przytnij(profil)
        return wpis

    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, domyslny())


def zmien_sformulowanie(identyfikator: str, zmiany: dict) -> dict:
    import magazyn

    def zmiana(profil: dict) -> dict:
        for s in profil.get("sformulowania", []):
            if s["id"] == identyfikator:
                for klucz in ("przypiete", "ukryte"):
                    if klucz in zmiany:
                        s[klucz] = bool(zmiany[klucz])
                if zmiany.get("czesc") in kategorie.CZESCI:
                    s["czesc"] = zmiany["czesc"]
                if zmiany.get("szkielet"):
                    nowy = klauzule.pseudonimizuj(zmiany["szkielet"])
                    if klauzule.ma_dane_osobowe(nowy):
                        raise ValueError("W tekście zostały dane osobowe.")
                    s["szkielet"] = nowy
                    s["wlasne"] = True
                return s
        raise KeyError(identyfikator)

    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, domyslny())


def usun_sformulowanie(identyfikator: str) -> None:
    import magazyn

    def zmiana(profil: dict) -> None:
        przed = len(profil.get("sformulowania", []))
        profil["sformulowania"] = [s for s in profil.get("sformulowania", []) if s["id"] != identyfikator]
        if len(profil["sformulowania"]) == przed:
            raise KeyError(identyfikator)

    magazyn.zmien_plik_kancelarii(PLIK, zmiana, domyslny())


def zapomnij() -> None:
    """Usuwa caly wyuczony styl (zasady kancelarii zostaja)."""
    import magazyn

    def zmiana(profil: dict) -> None:
        odrzucone = profil.get("sugestie_odrzucone", [])
        profil.clear()
        profil.update(domyslny())
        profil["sugestie_odrzucone"] = odrzucone

    magazyn.zmien_plik_kancelarii(PLIK, zmiana, domyslny())


def odrzuc_sugestie(klucz: str) -> None:
    import magazyn

    def zmiana(profil: dict) -> None:
        profil.setdefault("sugestie_odrzucone", [])
        if klucz not in profil["sugestie_odrzucone"]:
            profil["sugestie_odrzucone"].append(klucz)

    magazyn.zmien_plik_kancelarii(PLIK, zmiana, domyslny())


# ---------------------------------------------------------------------------
# Odczyt profilu: nawyki, sugestie zasad, blok dla modelu
# ---------------------------------------------------------------------------
def _przyklad_daty(klucz: str) -> str:
    styl, zero, sufiks = klucz.split("|")
    return zasady._sformatuj_date(3, 12, "2025", {"styl": styl, "zero": zero == "1", "sufiks": sufiks})


def _przewaga(licznik: dict, minimum: int, udzial: float):
    """(zwyciezca, ile, wszystkich) gdy jeden wariant wyraznie dominuje."""
    razem = sum(licznik.values())
    if razem < minimum:
        return None
    zwyciezca, ile = max(licznik.items(), key=lambda p: p[1])
    return (zwyciezca, ile, razem) if ile / razem >= udzial else None


def nawyki_czytelne(profil: dict) -> list[dict]:
    """Nawyki kancelarii zdaniami, do pokazania notariuszowi."""
    n = profil.get("nawyki", {})
    wynik = []
    if p := _przewaga(n.get("daty", {}), 3, 0.6):
        wynik.append({"obszar": "daty", "tekst": f"Daty piszesz jak „{_przyklad_daty(p[0])}”", "ile": p[1], "z": p[2]})
    ks = n.get("kwoty_slownie", {})
    if sum(ks.values()) >= 3:
        procent = round(100 * ks.get("tak", 0) / max(1, sum(ks.values())))
        wynik.append({"obszar": "kwoty", "tekst": f"Kwoty ze słownym zapisem: {procent}%",
                      "ile": ks.get("tak", 0), "z": sum(ks.values())})
    if p := _przewaga(n.get("separator", {}), 3, 0.6):
        przyklad = {"kropka": "250.000,00 zł", "spacja": "250 000,00 zł", "brak": "250000,00 zł"}[p[0]]
        wynik.append({"obszar": "kwoty", "tekst": f"Kwoty zapisujesz jak „{przyklad}”", "ile": p[1], "z": p[2]})
    if p := _przewaga(n.get("paragraf", {}), 3, 0.6):
        wynik.append({"obszar": "typografia", "tekst": "Po „§” stawiasz spację" if p[0] == "spacja"
                      else "„§” piszesz razem z numerem", "ile": p[1], "z": p[2]})
    for klucz, liczby in n.get("slownictwo", {}).items():
        if p := _przewaga(liczby, 3, 0.75):
            nazwa = SLOWNICTWO.get(klucz, (klucz,))[0]
            wynik.append({"obszar": "slownictwo", "tekst": f"Piszesz „{p[0]}” ({nazwa})", "ile": p[1], "z": p[2]})
    return wynik


def _sugestia(klucz: str, tekst: str, uzasadnienie: str, typ_oczekiwany: str) -> dict | None:
    try:
        podglad = zasady.interpretuj(tekst)
    except ValueError:
        return None
    if podglad["typ"] != typ_oczekiwany:
        return None
    return {"klucz": klucz, "tekst": tekst, "uzasadnienie": uzasadnienie, "podglad": podglad}


def sugestie(profil: dict, ustawienia_zasad: dict) -> list[dict]:
    """Zasady, ktore kancelaria i tak stosuje - do przyjecia jednym kliknieciem."""
    n = profil.get("nawyki", {})
    odrzucone = set(profil.get("sugestie_odrzucone", []))
    istniejace = {zasady._klucz_identycznosci(z) for z in ustawienia_zasad.get("zasady", [])}
    istniejace_typy = {z["typ"] for z in ustawienia_zasad.get("zasady", []) if z["typ"] in zasady.JEDYNE}
    wynik: list[dict | None] = []

    if p := _przewaga(n.get("daty", {}), 5, 0.8):
        wynik.append(_sugestia("daty:" + p[0], f"Daty zapisuj jak {_przyklad_daty(p[0])}",
                               f"Tak zapisana jest {p[1]} z {p[2]} dat w Twoich aktach.", "format_daty"))
    ks = n.get("kwoty_slownie", {})
    if ks.get("tak", 0) >= 5 and ks["tak"] / max(1, sum(ks.values())) >= 0.85:
        wynik.append(_sugestia("kwoty_slownie", "Kwoty zawsze cyframi i słownie",
                               f"{ks['tak']} z {sum(ks.values())} kwot w Twoich aktach ma zapis słowny.",
                               "kwoty_slownie"))
    if p := _przewaga(n.get("separator", {}), 5, 0.85):
        tekst = {"kropka": "Kwoty z kropką co trzy cyfry, np. 250.000,00 zł",
                 "spacja": "Kwoty ze spacją co trzy cyfry, np. 250 000,00 zł",
                 "brak": "Kwoty bez separatora tysięcy"}[p[0]]
        wynik.append(_sugestia("separator:" + p[0], tekst, f"Tak zapisana jest {p[1]} z {p[2]} kwot.",
                               "separator_tysiecy"))
    if p := _przewaga(n.get("paragraf", {}), 8, 0.9):
        tekst = "Po § zawsze spacja" if p[0] == "spacja" else "§ pisz bez spacji, razem z numerem"
        wynik.append(_sugestia("paragraf:" + p[0], tekst, f"Tak w {p[1]} z {p[2]} odwołań do paragrafów.",
                               "spacja_paragraf"))
    cz = n.get("cudzyslowy", {})
    if cz.get("polskie", 0) >= 3 and cz.get("polskie", 0) / max(1, sum(cz.values())) >= 0.9:
        wynik.append(_sugestia("cudzyslowy", "Cudzysłowy tylko polskie „…”",
                               f"{cz['polskie']} z {sum(cz.values())} cytatów w polskich cudzysłowach.", "cudzyslowy"))
    for klucz, liczby in n.get("slownictwo", {}).items():
        p = _przewaga(liczby, 5, 0.9)
        if not p:
            continue
        for etykieta, _, zdanie in _SLOWNICTWO_WZORCE[klucz]:
            if etykieta == p[0] and zdanie:
                typ = zasady.interpretuj(zdanie)["typ"]
                wynik.append(_sugestia(f"slowo:{klucz}:{etykieta}", zdanie,
                                       f"W Twoich aktach „{etykieta}” pojawia się {p[1]} razy na {p[2]}.", typ))

    # Czesci i pouczenia obecne prawie w kazdym akcie danego rodzaju
    akty = profil.get("akty", [])
    for rodzaj in sorted({r for a in akty for r in a.get("rodzaje", [])[:1]}):
        tego_rodzaju = [a for a in akty if a.get("rodzaje", [])[:1] == [rodzaj]]
        if len(tego_rodzaju) < 3 or rodzaj not in _RODZAJ_W_ZDANIU:
            continue
        for czesc, zdanie in _CZESC_W_ZDANIU.items():
            ile = sum(1 for a in tego_rodzaju if czesc in a.get("czesci", []))
            if ile / len(tego_rodzaju) >= 0.8:
                wynik.append(_sugestia(f"czesc:{rodzaj}:{czesc}", f"{_RODZAJ_W_ZDANIU[rodzaj]} {zdanie}",
                                       f"Ta część jest w {ile} z {len(tego_rodzaju)} Twoich aktów tego rodzaju.",
                                       "wymagana_czesc"))
        odwolania = Counter(o for a in tego_rodzaju for o in a.get("odwolania", []))
        for odwolanie, ile in odwolania.most_common(3):
            if ile / len(tego_rodzaju) >= 0.8:
                wynik.append(_sugestia(f"pouczenie:{rodzaj}:{odwolanie}",
                                       f"{_RODZAJ_W_ZDANIU[rodzaj]} zawsze pouczenie o {odwolanie}",
                                       f"Pouczasz o {odwolanie} w {ile} z {len(tego_rodzaju)} aktów tego rodzaju.",
                                       "wymagana_fraza"))

    gotowe = []
    for s in wynik:
        if not s or s["klucz"] in odrzucone:
            continue
        if zasady._klucz_identycznosci(s["podglad"]) in istniejace:
            continue
        if s["podglad"]["typ"] in istniejace_typy and not s["podglad"]["zakres"]["rodzaje"]:
            continue
        gotowe.append(s)
    return gotowe


def podsumowanie(profil: dict) -> dict:
    """Profil dla UI: liczby, nawyki, sformulowania pogrupowane po czesciach."""
    po_czesciach: dict[str, list] = {}
    for s in sorted(profil.get("sformulowania", []), key=lambda s: (not s["przypiete"], -s["wystapien"])):
        po_czesciach.setdefault(s["czesc"], []).append({k: v for k, v in s.items() if k != "akty"})
    kolejnosc = list(kategorie.CZESCI) + [kategorie.CZESC_INNA]
    rodzaje = Counter(a["rodzaje"][0] for a in profil.get("akty", []) if a.get("rodzaje"))
    return {
        "aktow": len(profil.get("akty", [])),
        "sformulowan": len(profil.get("sformulowania", [])),
        "powtarzalnych": sum(1 for s in profil.get("sformulowania", []) if s["wystapien"] > 1),
        "akty": [{k: a[k] for k in ("id", "etykieta", "rodzaje", "klauzul", "dodano")} for a in profil.get("akty", [])],
        "rodzaje": [{"rodzaj": r, "nazwa": kategorie.nazwa_rodzaju(r), "aktow": n} for r, n in rodzaje.most_common()],
        "nawyki": nawyki_czytelne(profil),
        "czesci": [{"czesc": c, "nazwa": kategorie.nazwa_czesci(c), "sformulowania": po_czesciach[c]}
                   for c in kolejnosc if c in po_czesciach],
    }


def blok_do_polecenia(profil: dict, rodzaje: list[str] | None = None, limit_znakow: int = 7000) -> str:
    """Wskazowki redakcyjne dla modelu: nawyki + typowe sformulowania kancelarii."""
    nawyki = nawyki_czytelne(profil)
    rodzaje_set = set(rodzaje or [])
    kandydaci = [
        s for s in profil.get("sformulowania", [])
        if not s.get("ukryte") and (s.get("przypiete") or s["wystapien"] >= 2)
        and (not rodzaje_set or not s["rodzaje"] or rodzaje_set & set(s["rodzaje"]))
    ]
    if not nawyki and not kandydaci:
        return ""
    kandydaci.sort(key=lambda s: (not s.get("przypiete"), -s["wystapien"]))
    na_czesc: Counter = Counter()
    wiersze, dlugosc = [], 0
    for s in kandydaci:
        if na_czesc[s["czesc"]] >= (3 if s.get("przypiete") else 2):
            continue
        wiersz = f"- [{kategorie.nazwa_czesci(s['czesc'])}]{' (wzorcowe)' if s.get('przypiete') else ''} {s['szkielet']}"
        if dlugosc + len(wiersz) > limit_znakow:
            break
        na_czesc[s["czesc"]] += 1
        wiersze.append(wiersz)
        dlugosc += len(wiersz)
    czesci = ["STYL KANCELARII (z wczesniejszych aktow tej kancelarii). To wskazowki redakcyjne: stosuj je, "
              "gdy nie koliduja ze wzorem, danymi, poleceniem i zasadami kancelarii. Znaczniki w klamrach, "
              "np. {OSOBA}, {KWOTA}, {DATA}, to miejsca na dane TEJ sprawy - nigdy nie przepisuj ich do projektu."]
    if nawyki:
        czesci.append("Nawyki kancelarii:\n" + "\n".join(f"- {n['tekst']}" for n in nawyki))
    if wiersze:
        czesci.append("Typowe sformulowania kancelarii (redaguj podobnie odpowiadajace im czesci aktu):\n"
                      + "\n".join(wiersze))
    return "\n\n".join(czesci)


def _liczniki(dane, glebokosc: int = 0) -> dict:
    """Nawyki: zagniezdzone slowniki z licznikami - nic innego."""
    if not isinstance(dane, dict) or glebokosc > 3:
        return {}
    wynik = {}
    for klucz, wartosc in list(dane.items())[:200]:
        klucz = str(klucz)[:80]
        if isinstance(wartosc, bool):
            continue
        if isinstance(wartosc, int) and wartosc >= 0:
            wynik[klucz] = wartosc
        elif isinstance(wartosc, dict):
            wynik[klucz] = _liczniki(wartosc, glebokosc + 1)
    return wynik


def _napisy(lista, limit: int = 200, dlugosc: int = 120) -> list[str]:
    return [str(x)[:dlugosc] for x in (lista if isinstance(lista, list) else [])[:limit] if isinstance(x, str)]


def normalizuj(profil) -> dict:
    """Plik stylu z folderu kancelarii "u siebie" -> poprawna struktura.
    Odrzucamy wpisy o zlym ksztalcie zamiast wywracac zadanie."""
    wynik = domyslny()
    if not isinstance(profil, dict):
        return wynik
    for a in (profil.get("akty") if isinstance(profil.get("akty"), list) else [])[:1000]:
        if not isinstance(a, dict) or not isinstance(a.get("id"), str):
            continue
        wynik["akty"].append({
            "id": a["id"][:20], "etykieta": str(a.get("etykieta") or "Akt")[:120],
            "rodzaje": [r for r in _napisy(a.get("rodzaje"), 5) if r in kategorie.RODZAJE or r == kategorie.RODZAJ_INNY],
            "klauzul": a["klauzul"] if isinstance(a.get("klauzul"), int) else 0,
            "czesci": [c for c in _napisy(a.get("czesci"), 30) if c in kategorie.CZESCI or c == kategorie.CZESC_INNA],
            "odwolania": _napisy(a.get("odwolania"), 50, 60),
            "dodano": str(a.get("dodano") or "")[:30],
        })
    for s in (profil.get("sformulowania") if isinstance(profil.get("sformulowania"), list) else [])[:MAX_SFORMULOWAN]:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not isinstance(s.get("szkielet"), str):
            continue
        czesc = s.get("czesc") if s.get("czesc") in kategorie.CZESCI else kategorie.CZESC_INNA
        wynik["sformulowania"].append({
            "id": s["id"][:20], "czesc": czesc, "szkielet": s["szkielet"][:MAX_DLUGOSC],
            "rodzaje": [r for r in _napisy(s.get("rodzaje"), 25) if r in kategorie.RODZAJE],
            "wystapien": max(1, s["wystapien"]) if isinstance(s.get("wystapien"), int) else 1,
            "akty": _napisy(s.get("akty"), 1000, 20),
            "przypiete": bool(s.get("przypiete")), "ukryte": bool(s.get("ukryte")), "wlasne": bool(s.get("wlasne")),
        })
    wynik["nawyki"] = _liczniki(profil.get("nawyki"))
    wynik["sugestie_odrzucone"] = _napisy(profil.get("sugestie_odrzucone"), 500, 200)
    return wynik
