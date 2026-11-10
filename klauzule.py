"""Silnik klauzul: rozbior dokumentu prawnego na klauzule i kontrola konstrukcji.

Wywodzi sie z silnika umow Finance You (`src/lib/contract-engine` w repo
finyou), z ktorego bierzemy dwie zasady:
  - numeracja i odeslania sa sprawa kodu, nie modelu: po kazdej zmianie
    dokumentu przeliczamy je deterministycznie,
  - odeslanie do nieistniejacego miejsca to blad konstrukcyjny, a nie
    "drobiazg do poprawy przez notariusza".

Silnik z finyou SKLADA umowe z biblioteki klauzul. Tutaj dziala w druga
strone i jest uniwersalny: przyjmuje dowolny tekst (stary akt kancelarii,
projekt z modelu, wzor z legenda) i rozbiera go na drzewo klauzul:

  naglowek / paragraf (§) / ustep (1.) / punkt (1)) / litera (a)) / tiret (-)
  / akapit bez numeru

Kazda klauzula dostaje czesc aktu (kategorie.CZESCI), stabilny
identyfikator liczony z tresci po pseudonimizacji i liste odeslan.
Z rozbioru korzystaja: nauka stylu (styl.py), zasady kancelarii
(zasady.py) i kontrola projektu przed pokazaniem go notariuszowi.

Bez zaleznosci spoza biblioteki standardowej.
"""
import hashlib
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher

import kategorie

# ---------------------------------------------------------------------------
# Znaczniki struktury
# ---------------------------------------------------------------------------
_PARAGRAF = re.compile(r"^\s*§\s*(\d+[a-z]?)\s*\.?\s*(.*)$")
_USTEP = re.compile(r"^\s*(\d{1,3})\s*\.\s+(\S.*)$")
_PUNKT = re.compile(r"^\s*(\d{1,3})\s*\)\s*(\S.*)$")
_LITERA = re.compile(r"^\s*([a-z]{1,2})\s*\)\s*(\S.*)$")
_TIRET = re.compile(r"^\s*[-–—•*]\s+(\S.*)$")
_WARIANT = re.compile(r"^\s*//\s*(.*)$")
_REPERTORIUM = re.compile(r"^\s*(repertorium|rep\.)\s", re.IGNORECASE)

POZIOMY = {"naglowek": 0, "paragraf": 1, "ustep": 2, "punkt": 3, "litera": 4, "tiret": 5}

_LUKI = re.compile(r"\?\?|\{\{[^{}]+\}\}|\[\s*[A-ZĄĆĘŁŃÓŚŹŻ][^\[\]]{2,60}?\s*\]")
_ZNACZNIKI_AI = re.compile(r"<<(BRAK|WYBOR):[^>]*>>")


@dataclass
class Klauzula:
    id: str
    typ: str            # naglowek, paragraf, ustep, punkt, litera, tiret, akapit
    poziom: int
    numer: str          # "3" dla § 3, "2" dla ust. 2, "a" dla lit. a; "" bez numeru
    tekst: str
    linia: int          # numer pierwszej linii w tekscie zrodlowym (od 0)
    rodzic: int | None  # indeks klauzuli nadrzednej na liscie
    paragraf: str = ""  # numer paragrafu, w ktorym lezy klauzula
    czesc: str = kategorie.CZESC_INNA
    pewnosc: float = 0.0
    warianty: list[str] = field(default_factory=list)
    luki: int = 0
    odeslania: list[dict] = field(default_factory=list)

    def slownik(self) -> dict:
        return asdict(self)


@dataclass
class Rozbior:
    klauzule: list[Klauzula]
    rodzaje: list[dict]
    linie: list[str]

    def paragrafy(self) -> list[Klauzula]:
        return [k for k in self.klauzule if k.typ == "paragraf"]

    def dzieci(self, indeks: int) -> list[Klauzula]:
        return [k for k in self.klauzule if k.rodzic == indeks]

    def tekst_pelny(self, indeks: int) -> str:
        """Tekst klauzuli razem ze wszystkimi podrzednymi."""
        czesci = [self.klauzule[indeks].tekst]
        for i, k in enumerate(self.klauzule):
            if k.rodzic == indeks:
                czesci.append(self.tekst_pelny(i))
        return " ".join(c for c in czesci if c)

    def czesci(self) -> dict[str, int]:
        licznik: dict[str, int] = {}
        for k in self.klauzule:
            licznik[k.czesc] = licznik.get(k.czesc, 0) + 1
        return licznik

    def slownik(self) -> dict:
        return {
            "rodzaje": self.rodzaje,
            "klauzule": [k.slownik() for k in self.klauzule],
            "czesci": self.czesci(),
        }


def _naglowek(linia: str) -> bool:
    tekst = linia.strip()
    if not tekst or len(tekst) > 90:
        return False
    if _REPERTORIUM.match(tekst):
        return True
    litery = [z for z in tekst if z.isalpha()]
    if len(litery) < 4:
        return False
    return sum(1 for z in litery if z.isupper()) / len(litery) >= 0.85


def _koniec_zdania(tekst: str) -> bool:
    return tekst.rstrip().endswith((".", ":", ";", "!", "?"))


def _rozpoznaj(linia: str):
    """(typ, numer, tresc) dla linii ze znacznikiem albo None."""
    if m := _PARAGRAF.match(linia):
        return "paragraf", m.group(1), m.group(2).strip()
    if m := _PUNKT.match(linia):
        return "punkt", m.group(1), m.group(2).strip()
    if m := _LITERA.match(linia):
        return "litera", m.group(1), m.group(2).strip()
    if m := _USTEP.match(linia):
        return "ustep", m.group(1), m.group(2).strip()
    if m := _TIRET.match(linia):
        return "tiret", "", m.group(1).strip()
    return None


def rozbij(tekst: str) -> Rozbior:
    """Rozbior tekstu na klauzule.

    Dziala zarowno na tekscie z Worda (kazdy akapit w osobnej linii, bez
    pustych linii), jak i na zwyklym tekscie z zawinietymi liniami: linia
    bez znacznika jest dalszym ciagiem poprzedniej, chyba ze poprzednia
    konczy zdanie, a ta zaczyna sie wielka litera albo poprzedzila ja
    pusta linia.
    """
    linie = (tekst or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    klauzule: list[Klauzula] = []
    stos: list[int] = []        # indeksy otwartych klauzul numerowanych
    paragraf_teraz = ""
    po_pustej = True

    def dodaj(typ: str, numer: str, tresc: str, nr_linii: int) -> None:
        nonlocal paragraf_teraz
        poziom = POZIOMY.get(typ, 6)
        if typ == "akapit":
            # Akapit bez numeru: pod biezacym paragrafem, a przed pierwszym
            # paragrafem - na poziomie paragrafu (komparycja, wstep).
            poziom = (klauzule[stos[0]].poziom + 1) if stos and klauzule[stos[0]].typ == "paragraf" else 1
        if typ == "ustep" and not any(klauzule[i].typ == "paragraf" for i in stos):
            # "1. Jan Kowalski..." w komparycji przed pierwszym paragrafem
            poziom = 1
        while stos and klauzule[stos[-1]].poziom >= poziom:
            stos.pop()
        if typ == "paragraf":
            paragraf_teraz = numer
        rodzic = stos[-1] if stos else None
        klauzule.append(Klauzula(
            id="", typ=typ, poziom=poziom, numer=numer, tekst=tresc, linia=nr_linii,
            rodzic=rodzic, paragraf=paragraf_teraz,
        ))
        if typ != "akapit" and typ != "naglowek":
            stos.append(len(klauzule) - 1)
        elif typ == "naglowek":
            stos.clear()

    for nr, surowa in enumerate(linie):
        linia = surowa.rstrip()
        if not linia.strip():
            po_pustej = True
            continue
        if m := _WARIANT.match(linia):
            if klauzule:
                klauzule[-1].warianty.append(m.group(1).strip())
            po_pustej = False
            continue
        rozpoznana = _rozpoznaj(linia)
        if rozpoznana:
            typ, numer, tresc = rozpoznana
            # "§ 2. 1. Sprzedajacy sprzedaje..." - pierwszy ustep w linii paragrafu
            wewnetrzny = _USTEP.match(tresc) if typ == "paragraf" else None
            if wewnetrzny:
                dodaj(typ, numer, "", nr)
                dodaj("ustep", wewnetrzny.group(1), wewnetrzny.group(2).strip(), nr)
            else:
                dodaj(typ, numer, tresc, nr)
        elif _naglowek(linia) and (po_pustej or not klauzule or _koniec_zdania(klauzule[-1].tekst)
                                   or _naglowek(linie[nr - 1] if nr else "")):
            dodaj("naglowek", "", linia.strip(), nr)
        elif (klauzule and not po_pustej and klauzule[-1].typ != "naglowek"
              and not (_koniec_zdania(klauzule[-1].tekst) and linia.lstrip()[:1].isupper())):
            klauzule[-1].tekst = (klauzule[-1].tekst + " " + linia.strip()).strip()
        else:
            dodaj("akapit", "", linia.strip(), nr)
        po_pustej = False

    rozbior = Rozbior(klauzule=klauzule, rodzaje=kategorie.klasyfikuj_dokument(tekst or ""), linie=linie)
    _sklasyfikuj(rozbior)
    for k in klauzule:
        k.luki = len(_LUKI.findall(k.tekst)) + sum(len(_LUKI.findall(w)) for w in k.warianty)
        k.odeslania = odeslania_w_tekscie(k.tekst)
        k.id = identyfikator(k.tekst)
    return rozbior


def _sklasyfikuj(rozbior: Rozbior) -> None:
    """Czesc aktu dla kazdej klauzuli.

    Paragraf oceniamy po calej tresci (z ustepami), bo jego pierwsza linia
    bywa samym tytulem. Klauzula podrzedna bez wyraznych slow dziedziczy
    czesc paragrafu; luzny akapit - czesc poprzedniej klauzuli.
    """
    poprzednia = None
    przed_paragrafami = True
    for i, k in enumerate(rozbior.klauzule):
        if k.typ == "paragraf":
            przed_paragrafami = False
            k.czesc, k.pewnosc = kategorie.klasyfikuj_czesc(k.tekst, None)
            if k.pewnosc < 0.4:
                # sam tytul ("§ 3.") albo krotki wstep - decyduja ustepy
                tresc = " ".join([k.tekst] + [d.tekst for d in rozbior.dzieci(i) if d.typ != "akapit"])
                k.czesc, k.pewnosc = kategorie.klasyfikuj_czesc(tresc, poprzednia)
        elif k.typ == "naglowek":
            k.czesc, k.pewnosc = kategorie.klasyfikuj_czesc(k.tekst, None)
            if k.czesc == kategorie.CZESC_INNA and przed_paragrafami:
                k.czesc, k.pewnosc = "naglowek", 0.5
        else:
            nadrzedna = rozbior.klauzule[k.rodzic].czesc if k.rodzic is not None else poprzednia
            k.czesc, k.pewnosc = kategorie.klasyfikuj_czesc(k.tekst, nadrzedna)
            if k.pewnosc < 0.35 and nadrzedna:
                k.czesc = nadrzedna
        poprzednia = k.czesc


# ---------------------------------------------------------------------------
# Odeslania
# ---------------------------------------------------------------------------
_ODESLANIE = re.compile(
    r"§\s*(?P<par>\d+[a-z]?)(?:\s*ust\.?\s*(?P<ust>\d+))?(?:\s*pkt\.?\s*(?P<pkt>\d+))?"
    r"(?:\s*lit\.?\s*(?P<lit>[a-z]))?"
)
_SAM_USTEP = re.compile(r"(?<![§\w.])\bust\.?\s*(?P<ust>\d+)(?!\s*(?:pkt|lit)?\.?\s*\d*\s*(?:art|ustaw|rozporz|kodeks))")
_ZEWNETRZNE_PO = re.compile(
    r"^[\s,.\d\w]{0,25}?\b(rozporz|ustaw|kodeks|k\.\s?c\.|k\.\s?r\.\s?o|k\.\s?p\.\s?c|dz\.\s?u|regulamin|"
    r"statut|umowy spolki|prawa o notariacie|prawo o notariacie|z dnia)",
)
_ZEWNETRZNE_PRZED = re.compile(r"\bart\.?\s*\d+\w*\s*$|\bart\.?\s*\d+\w*\s*(ust\.\s*\d+\s*)?$")


def odeslania_w_tekscie(tekst: str) -> list[dict]:
    """Odeslania wewnetrzne ("§ 3 ust. 2", "ust. 4"). Odeslania do przepisow
    ("art. 158 § 1 kodeksu", "§ 3 rozporzadzenia") pomijamy."""
    wynik = []
    plaski = kategorie.bez_ogonkow(tekst)
    for m in _ODESLANIE.finditer(tekst):
        przed = plaski[max(0, m.start() - 25):m.start()]
        po = plaski[m.end():m.end() + 60]
        if _ZEWNETRZNE_PRZED.search(przed) or _ZEWNETRZNE_PO.search(po):
            continue
        wynik.append({"paragraf": m.group("par"), "ustep": m.group("ust"), "tekst": m.group(0).strip(),
                      "start": m.start(), "koniec": m.end()})
    zajete = [(o["start"], o["koniec"]) for o in wynik]
    for m in _SAM_USTEP.finditer(tekst):
        if any(a <= m.start() < b for a, b in zajete):
            continue
        przed = plaski[max(0, m.start() - 25):m.start()]
        po = plaski[m.end():m.end() + 60]
        if re.search(r"(art\.?\s*\d+\w*|§\s*\d+\w*)\s*$", przed) or _ZEWNETRZNE_PO.search(po):
            continue
        wynik.append({"paragraf": None, "ustep": m.group("ust"), "tekst": m.group(0).strip(),
                      "start": m.start(), "koniec": m.end()})
    return wynik


# ---------------------------------------------------------------------------
# Kontrola konstrukcji (zasady wbudowane - pilnowane w kazdej kancelarii)
# ---------------------------------------------------------------------------
KONSTRUKCJA = {
    "numeracja_paragrafow": "Numeracja paragrafów jest ciągła (§ 1, § 2, § 3…)",
    "numeracja_ustepow": "Numeracja ustępów w paragrafie jest ciągła",
    "odeslania": "Odesłania wewnętrzne wskazują istniejące miejsca aktu",
    "luki": "Nie zostały niewypełnione luki wzoru (??, {{…}}, [POLE])",
    "warianty": "Nie zostały nierozstrzygnięte warianty wzoru (//)",
}


def _liczba(numer: str) -> int | None:
    m = re.match(r"\d+", numer or "")
    return int(m.group(0)) if m else None


def sprawdz_konstrukcje(rozbior: Rozbior) -> list[dict]:
    """Bledy konstrukcyjne: [{kod, komunikat, fragment, klauzula, naprawialne}]."""
    problemy = []
    paragrafy = rozbior.paragrafy()
    # "§ 2a" to swiadomie wstawiony paragraf - nie liczy sie do ciaglosci
    numery = [_liczba(p.numer) for p in paragrafy if p.numer.isdigit()]
    if numery:
        oczekiwane = list(range(1, len(numery) + 1))
        if numery != oczekiwane:
            powtorzone = sorted({n for n in numery if numery.count(n) > 1})
            brakujace = sorted(set(range(1, max(numery) + 1)) - set(numery))
            opis = []
            if brakujace:
                opis.append("brak § " + ", § ".join(map(str, brakujace)))
            if powtorzone:
                opis.append("powtórzone § " + ", § ".join(map(str, powtorzone)))
            if not opis:
                opis.append("paragrafy nie idą po kolei")
            problemy.append({
                "kod": "numeracja_paragrafow", "komunikat": "Numeracja paragrafów: " + "; ".join(opis) + ".",
                "fragment": " ".join(f"§ {p.numer}" for p in paragrafy[:12]), "klauzula": "",
                "naprawialne": True,
            })

    istniejace: dict[str, set[str]] = {}
    for i, k in enumerate(rozbior.klauzule):
        if k.typ == "paragraf":
            ustepy = [d for d in rozbior.dzieci(i) if d.typ == "ustep"]
            istniejace[k.numer] = {d.numer for d in ustepy}
            nr = [_liczba(d.numer) for d in ustepy]
            if nr and nr != list(range(1, len(nr) + 1)):
                problemy.append({
                    "kod": "numeracja_ustepow",
                    "komunikat": f"§ {k.numer}: ustępy nie idą po kolei ({', '.join(d.numer for d in ustepy)}).",
                    "fragment": k.tekst[:120], "klauzula": k.id, "naprawialne": False,
                })

    if istniejace:
        for k in rozbior.klauzule:
            for o in k.odeslania:
                par = o["paragraf"] or k.paragraf
                if not par:
                    continue
                if par not in istniejace:
                    problemy.append({
                        "kod": "odeslania", "komunikat": f"Odesłanie „{o['tekst']}” wskazuje paragraf, którego nie ma w akcie.",
                        "fragment": _otoczenie(k.tekst, o["start"], o["koniec"]), "klauzula": k.id, "naprawialne": False,
                    })
                elif o["ustep"] and istniejace[par] and o["ustep"] not in istniejace[par]:
                    problemy.append({
                        "kod": "odeslania",
                        "komunikat": f"Odesłanie „{o['tekst']}” wskazuje ust. {o['ustep']}, którego nie ma w § {par}.",
                        "fragment": _otoczenie(k.tekst, o["start"], o["koniec"]), "klauzula": k.id, "naprawialne": False,
                    })

    for k in rozbior.klauzule:
        bez_ai = _ZNACZNIKI_AI.sub("", k.tekst)
        if _LUKI.search(bez_ai):
            m = _LUKI.search(bez_ai)
            problemy.append({
                "kod": "luki", "komunikat": "Została niewypełniona luka wzoru.",
                "fragment": _otoczenie(bez_ai, m.start(), m.end()), "klauzula": k.id, "naprawialne": False,
            })
        if k.warianty:
            problemy.append({
                "kod": "warianty", "komunikat": "Zostały warianty rozdzielone „//” - wybierz jeden.",
                "fragment": k.tekst[:80] + " // " + k.warianty[0][:80], "klauzula": k.id, "naprawialne": False,
            })
    return problemy


def _otoczenie(tekst: str, start: int, koniec: int, margines: int = 45) -> str:
    a, b = max(0, start - margines), min(len(tekst), koniec + margines)
    return ("…" if a else "") + tekst[a:b].strip() + ("…" if b < len(tekst) else "")


def przenumeruj(tekst: str) -> tuple[str, dict[str, str]]:
    """Ciagla numeracja paragrafow (§ 1..n) razem z odeslaniami wewnetrznymi.

    Zwraca (nowy tekst, {stary numer: nowy}). Gdy numer paragrafu sie
    powtarza, odeslan do niego nie zmieniamy - nie wiadomo, ktory
    paragraf mialy na mysli; problem zostaje w raporcie konstrukcji.
    """
    linie = tekst.split("\n")
    stare: list[tuple[int, str]] = []
    for nr, linia in enumerate(linie):
        if m := _PARAGRAF.match(linia):
            stare.append((nr, m.group(1)))
    if not stare:
        return tekst, {}
    mapa: dict[str, str] = {}
    powtorzone = {n for _, n in stare if [s for _, s in stare].count(n) > 1}
    for kolejny, (_, numer) in enumerate(stare, start=1):
        if numer not in powtorzone:
            mapa[numer] = str(kolejny)
    zmiany = {s: n for s, n in mapa.items() if s != n}
    if not zmiany and not powtorzone:
        return tekst, {}

    nowe_numery = {nr: str(i) for i, (nr, _) in enumerate(stare, start=1)}
    wynik = []
    for nr, linia in enumerate(linie):
        if nr in nowe_numery:
            linia = re.sub(r"(§\s*)(\d+[a-z]?)", lambda m: m.group(1) + nowe_numery[nr], linia, count=1)
            glowa, _, reszta = linia.partition(nowe_numery[nr])
            linia = glowa + nowe_numery[nr] + _podmien_odeslania(reszta, zmiany)
        else:
            linia = _podmien_odeslania(linia, zmiany)
        wynik.append(linia)
    return "\n".join(wynik), zmiany


def _podmien_odeslania(linia: str, zmiany: dict[str, str]) -> str:
    if not zmiany:
        return linia
    odeslania = [o for o in odeslania_w_tekscie(linia) if o["paragraf"] in zmiany]
    for o in sorted(odeslania, key=lambda o: -o["start"]):
        fragment = linia[o["start"]:o["koniec"]]
        nowy = re.sub(r"(§\s*)(\d+[a-z]?)", lambda m: m.group(1) + zmiany[o["paragraf"]], fragment, count=1)
        linia = linia[:o["start"]] + nowy + linia[o["koniec"]:]
    return linia


# ---------------------------------------------------------------------------
# Pseudonimizacja: szkielet klauzuli bez danych osobowych
# ---------------------------------------------------------------------------
_MIESIACE = ("stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|wrzesnia|września|"
             "pazdziernika|października|listopada|grudnia")

# Slowa pisane wielka litera, ktore NIE sa danymi osobowymi.
_LEKSYKON = set(kategorie.bez_ogonkow("""
Akt Akcie Aktu Notarialny Notarialnego Notarialnym Umowa Umowy Umowie Sąd Sądu Sądzie Rejonowy Rejonowego
Okręgowy Okręgowego Apelacyjny Wydział Wydziale Wydziału Ksiąg Księgi Księga Wieczystych Wieczystej
Wieczysta Kodeksu Kodeks Cywilnego Cywilny Rodzinnego Opiekuńczego Postępowania Rzeczypospolitej
Rzeczpospolita Polskiej Polska Polski Polsce Skarb Skarbu Państwa Urząd Urzędu Urzędzie Skarbowy
Skarbowego Skarbowym Ministra Minister Sprawiedliwości Finansów Notariusz Notariusza Notariuszem
Notariuszowi Kancelaria Kancelarii Notarialnej Krajowy Krajowego Ośrodek Ośrodka Wsparcia Rolnictwa
Dziennik Dziennika Ustaw Ustawa Ustawy Stawający Stawająca Stawającego Stawającej Stawający Stawiający
Kupujący Kupująca Kupującego Kupującej Kupującym Sprzedający Sprzedająca Sprzedającego Sprzedającej
Sprzedającym Darczyńca Darczyńcy Obdarowany Obdarowana Obdarowanego Obdarowanej Strony Stron Stronom
Pan Pani Pana Panią Panu Państwo Ten Ta To Te Ci Dnia Dzień Roku Rok Repertorium Zastępca Zastępcy
Asesor Asesora Gmina Gminy Gminie Powiat Powiatu Województwo Województwa Mazowieckie Mazowieckiego
Starosta Starosty Prezydent Prezydenta Miasta Miasto Burmistrz Burmistrza Wójt Wójta Rada Rady
Nabywca Nabywcy Zbywca Zbywcy Pożyczkodawca Pożyczkobiorca Pełnomocnik Pełnomocnika Mocodawca
Spadkodawca Spadkodawcy Spadkobierca Spadkobiercy Testator Testatora Dożywotnik Wierzyciel Dłużnik
Bank Banku Spółka Spółki Spółdzielnia Spółdzielni Mieszkaniowa Mieszkaniowej Wspólnota Wspólnoty
Dział Działu Działach Ewidencji Gruntów Budynków Rejestru Rejestr Wypis Wypisu Wyrys Obręb Obrębu
Przewodniczący Zgromadzenie Zgromadzenia Walne Nadzwyczajne Zwyczajne Zarząd Zarządu Rada Nadzorcza
Unii Europejskiej Europejskiej Parlamentu Rozporządzenie Rozporządzenia Paragraf Załącznik Załącznika
Wnioskodawca Wnioskodawcy Uczestnik Ogólne Postanowienia Końcowe Przedmiot Przedmiotu Cena Ceny
Oświadczenia Oświadczenie Pouczenie Pouczenia Koszty Taksa Wnioski Wniosek Podatek Podatku
""").split())

_PODSTAWIENIA: list[tuple[re.Pattern, str]] = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "{EMAIL}"),
    (re.compile(r"\b\d{11}\b"), "{PESEL}"),
    (re.compile(r"\b[A-Z]{2}\d[A-Z]/\d{8}/\d\b"), "{KW}"),
    (re.compile(r"\b(NIP|REGON|KRS|nr KRS)\s*:?\s*\d[\d -]{7,14}\d"), r"\1 {NR}"),
    (re.compile(r"\b[A-Z]{3}\s?\d{6}\b"), "{DOWOD}"),
    (re.compile(r"\b[A-Z]{2}\s?\d{7}\b"), "{DOWOD}"),
    (re.compile(r"(\+48[ -]?)?\b\d{3}[ -]\d{3}[ -]\d{3}\b"), "{TELEFON}"),
    (re.compile(r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4}\s?(r\.|roku)?"), "{DATA}"),
    (re.compile(r"\b\d{1,2}\s+(" + _MIESIACE + r")\s+\d{4}\s?(r\.|roku)?", re.IGNORECASE), "{DATA}"),
    (re.compile(r"\d{1,3}(?:[ . ]\d{3})*(?:,\d{1,2})?\s?(zł|złotych|złote|zl|PLN)\b"), "{KWOTA}"),
    (re.compile(r"\((słownie|slownie)?:?\s*[a-ząćęłńóśźż ]+(złot|zlot|grosz)[a-ząćęłńóśźż /]*\)", re.IGNORECASE),
     "({KWOTA_SLOWNIE})"),
    (re.compile(r"\b\d+[,.]\d+\s?(ha|m2|m²|a)\b"), "{POW}"),
    (re.compile(r"\b\d{2}-\d{3}\s+[A-ZŁŚŻŹĆŃÓ][\wąćęłńóśźż-]+"), "{KOD_MIEJSCOWOSC}"),
    (re.compile(r"\b(ul\.|ulicy|ulica|al\.|alei|aleja|os\.|osiedlu|osiedle|pl\.|placu)\s+[^,;\n]{1,40}?\s"
                r"\d+[a-zA-Z]?(\s*/\s*\d+[a-zA-Z]?|\s*(m\.|lok\.|lokal)\s*\d+)?"), r"\1 {ADRES}"),
    (re.compile(r"\b(Repertorium\s+A|Rep\.\s*A)\s*(nr|numer)?\s*[\d_ ./]+", re.IGNORECASE), r"\1 nr {REP}"),
    (re.compile(r"\b(nr|numer|numerem|numerami|numerach)\s+\d+[\d/,\s]*(i\s+\d+[\d/]*)?"), r"\1 {NR} "),
    (re.compile(r"\b(syn|córka|corka|syna|córki|corki|synowie|córki)\s+([A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+)"
                r"(\s+i\s+[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+)?"), r"\1 {IMIONA_RODZICOW}"),
    (re.compile(r"\b(zamieszkał\w*|zamieszkal\w*|zam\.|urodzon\w*|położon\w*|polozon\w*|miejscowości|"
                r"obręb\w*|obreb\w*|w miejscowości)\s+(w|we|w miejscowości)?\s*"
                r"([A-ZŁŚŻŹĆŃÓ][\wąćęłńóśźż]+(?:[- ][A-ZŁŚŻŹĆŃÓ][\wąćęłńóśźż]+)*)"), r"\1 \2 {MIEJSCE}"),
]

_WIELKIE_SLOWO = r"[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż]+)?"
_CIAG_WIELKICH = re.compile(rf"{_WIELKIE_SLOWO}(?:\s+{_WIELKIE_SLOWO})+")
_LICZBA = re.compile(r"\d{4,}")
_PRZED_LICZBA_PRAWNA = re.compile(r"(art\.|§|ust\.|pkt|poz\.|dz\.\s?u\.|nr|z)\s*$", re.IGNORECASE)
_KLAMRY = re.compile(r"\{[A-Z_]+\}")


def _osoby(tekst: str) -> str:
    """Ciagi co najmniej dwoch slow wielka litera spoza leksykonu = osoba
    albo nazwa wlasna (Jan KOWALSKI, Anna Maria Nowak, Zielona Gora)."""
    def podmien(m: re.Match) -> str:
        slowa = m.group(0).split()
        wynik, bieg = [], []
        for slowo in slowa + [None]:
            if slowo is not None and kategorie.bez_ogonkow(slowo) not in _LEKSYKON:
                bieg.append(slowo)
                continue
            if len(bieg) >= 2 or (len(bieg) == 1 and wynik and wynik[-1] in ("Pan", "Pani", "Pana", "Panią")):
                wynik.append("{OSOBA}")
            else:
                wynik.extend(bieg)
            bieg = []
            if slowo is not None:
                wynik.append(slowo)
        return " ".join(wynik)
    return _CIAG_WIELKICH.sub(podmien, tekst)


def pseudonimizuj(tekst: str) -> str:
    """Szkielet klauzuli: tresc bez PESEL, nazwisk, adresow, kwot, dat i numerow.

    Szkielet zachowuje sposob redagowania (slownictwo, szyk, odwolania do
    przepisow), a gubi to, co identyfikuje klienta. Tylko szkielety trafiaja
    do profilu stylu kancelarii - surowego tekstu aktu nigdy nie zapisujemy.
    """
    wynik = tekst or ""
    for wzorzec, zamiana in _PODSTAWIENIA:
        wynik = wzorzec.sub(zamiana, wynik)
    wynik = _osoby(wynik)

    def liczba(m: re.Match) -> str:
        return m.group(0) if _PRZED_LICZBA_PRAWNA.search(wynik[max(0, m.start() - 8):m.start()]) else "{N}"
    wynik = _LICZBA.sub(liczba, wynik)
    wynik = re.sub(r"(\{[A-Z_]+\})(\s*,?\s*\1)+", r"\1", wynik)
    return re.sub(r"\s+", " ", wynik).strip()


def ma_dane_osobowe(tekst: str) -> bool:
    """Ostatnia zapora przed zapisem: czy w szkielecie zostal PESEL, KW,
    numer dowodu albo e-mail. Nazwisk nie da sie tak sprawdzic - te usuwa
    pseudonimizuj()."""
    return bool(re.search(r"\b\d{11}\b|\b[A-Z]{2}\d[A-Z]/\d{8}/\d\b|\b[A-Z]{3}\s?\d{6}\b|@[\w-]+\.", tekst or ""))


def identyfikator(tekst: str) -> str:
    """Stabilny identyfikator klauzuli z jej szkieletu - ta sama klauzula
    w dwoch aktach (z innymi stronami) ma ten sam identyfikator."""
    norma = kategorie.bez_ogonkow(pseudonimizuj(tekst))
    norma = re.sub(r"[^\w{}]+", " ", norma).strip()
    return "k" + hashlib.sha1(norma.encode("utf-8")).hexdigest()[:10]


def podobienstwo(a: str, b: str) -> float:
    """0..1 - jak bardzo dwie klauzule sa tym samym sformulowaniem."""
    sa = kategorie.bez_ogonkow(a).split()
    sb = kategorie.bez_ogonkow(b).split()
    if not sa or not sb:
        return 0.0
    return SequenceMatcher(None, sa, sb, autojunk=False).ratio()


def pola_szkieletu(szkielet: str) -> list[str]:
    return sorted(set(_KLAMRY.findall(szkielet or "")))
