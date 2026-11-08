"""Baza kancelarii notarialnych - z arkusza XLSX do seo/kancelarie.json.

Zrodlo: "Baza kancelarii notarialnych Polska 2025" (stan wykazu 31.12.2025):
oficjalny wykaz notariuszy z dane.gov.pl (zbior 22657) uzupelniony o kontakty
z katalogow izb notarialnych i katalogu branzowego. 3501 kancelarii, 604
miejscowosci, 11 izb.

Co robimy z danymi:
  - naprawiamy zepsute kodowanie (czesc adresow to UTF-8 odczytany jako
    Latin-1: "PawÅ\\x82a" zamiast "Pawla"),
  - z kilku wersji adresu i telefonu wybieramy jedna czytelna,
  - laczymy miejscowosci zapisane z literowka ("Nowy Sacz" i "Nowy Sacz"),
  - adresy e-mail zostaja w JSON tylko dla aplikacji (umawianie wizyt);
    na strony WWW nie trafiaja.

Czytamy XLSX bez dodatkowych bibliotek (to zip z XML), zeby obraz aplikacji
nie potrzebowal openpyxl.

    py -3 seo\\baza.py "Baza_kancelarii.xlsx"            -> seo/kancelarie.json
"""
import json
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

KORZEN = Path(__file__).resolve().parent.parent
PLIK_JSON = Path(__file__).resolve().parent / "kancelarie.json"
STAN_WYKAZU = "31.12.2025"

IZBY = {
    "Białymstoku": "Izba Notarialna w Białymstoku",
    "Gdańsku": "Izba Notarialna w Gdańsku",
    "Katowicach": "Izba Notarialna w Katowicach",
    "Krakowie": "Izba Notarialna w Krakowie",
    "Lublinie": "Izba Notarialna w Lublinie",
    "Łodzi": "Izba Notarialna w Łodzi",
    "Poznaniu": "Izba Notarialna w Poznaniu",
    "Rzeszowie": "Izba Notarialna w Rzeszowie",
    "Szczecinie": "Izba Notarialna w Szczecinie",
    "Warszawie": "Izba Notarialna w Warszawie",
    "Wrocławiu": "Izba Notarialna we Wrocławiu",
}
# Miasta siedzib izb - do nazwy okregu i "w poblizu".
MIASTA_IZB = {"Białymstoku": "Białystok", "Gdańsku": "Gdańsk", "Katowicach": "Katowice",
              "Krakowie": "Kraków", "Lublinie": "Lublin", "Łodzi": "Łódź", "Poznaniu": "Poznań",
              "Rzeszowie": "Rzeszów", "Szczecinie": "Szczecin", "Warszawie": "Warszawa",
              "Wrocławiu": "Wrocław"}

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "p": "http://schemas.openxmlformats.org/package/2006/relationships"}


# ---------------------------------------------------------------- xlsx

def _kolumna(ref: str) -> int:
    litery = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for z in litery:
        n = n * 26 + ord(z) - 64
    return n - 1


def wczytaj_xlsx(sciezka: Path, arkusz: str) -> list[list]:
    """Wiersze arkusza jako listy (puste komorki = None), bez openpyxl."""
    with zipfile.ZipFile(sciezka) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        cele = {r.get("Id"): r.get("Target") for r in rels.findall("p:Relationship", _NS)}
        plik = None
        for s in wb.find("m:sheets", _NS):
            if s.get("name") == arkusz:
                cel = cele[s.get("{%s}id" % _NS["r"])].lstrip("/")
                plik = cel if cel.startswith("xl/") else "xl/" + cel
        if plik is None:
            raise ValueError(f"Brak arkusza {arkusz!r}")
        napisy: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
                napisy.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
        wiersze: list[list] = []
        for row in ET.fromstring(z.read(plik)).iter("{%s}row" % _NS["m"]):
            wiersz: list = []
            for c in row.findall("m:c", _NS):
                k = _kolumna(c.get("r", "A1"))
                while len(wiersz) <= k:
                    wiersz.append(None)
                typ = c.get("t")
                v = c.find("m:v", _NS)
                if typ == "s" and v is not None:
                    wartosc = napisy[int(v.text)]
                elif typ == "inlineStr":
                    wartosc = "".join(t.text or "" for t in c.iter("{%s}t" % _NS["m"]))
                elif v is not None:
                    wartosc = v.text
                    if re.fullmatch(r"-?\d+(\.0+)?", wartosc or ""):
                        wartosc = int(float(wartosc))
                else:
                    wartosc = None
                wiersz[k] = wartosc if wartosc != "" else None
            wiersze.append(wiersz)
    return wiersze


# ---------------------------------------------------------------- normalizacja

_MOJIBAKE = re.compile(r"[ÃÅÄ][\x80-\xbf -ÿ]")


# Gdy po drodze zginal bajt (np. "DÄ brÃ³wki"), dekodowanie sie nie uda -
# wtedy podmieniamy znane pary literka po literce.
_RESZTKI = [("Ã³", "ó"), ("Ã\x93", "Ó"), ("Ä\x85", "ą"), ("Ä ", "ą"), ("Ä\x87", "ć"), ("Ä\x99", "ę"),
            ("Å\x82", "ł"), ("Å\x81", "Ł"), ("Å\x84", "ń"), ("Å\x9b", "ś"), ("Å\x9a", "Ś"),
            ("Å\xba", "ź"), ("Å\xbc", "ż"), ("Å»", "Ż"), ("Ã\xa0", "ą"), ("â\x80\x93", "–"), ("Â", "")]


def napraw_kodowanie(tekst) -> str:
    """UTF-8 odczytany jako Latin-1 -> z powrotem; kazdy fragment osobno."""
    if tekst is None:
        return ""
    tekst = str(tekst)
    if not _MOJIBAKE.search(tekst) and "â" not in tekst:
        return tekst
    czesci = []
    for czesc in re.split(r"(\s*;\s*)", tekst):
        if _MOJIBAKE.search(czesc) or "â" in czesc:
            try:
                czesc = czesc.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                for zle, dobre in _RESZTKI:
                    czesc = czesc.replace(zle, dobre)
        czesci.append(czesc)
    return "".join(czesci)


def slug(tekst: str) -> str:
    tekst = tekst.replace("ł", "l").replace("Ł", "L")
    tekst = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", tekst.lower()).strip("-")


def _czysty(tekst) -> str:
    return " ".join(str(tekst or "").split())


_SKROTY = {"Ul.": "ul.", "Al.": "al.", "Pl.": "pl.", "Os.": "os.", "Lok.": "lok.", "Im.": "im.",
           "Gen.": "gen.", "Ks.": "ks.", "Św.": "św.", "Nr": "nr", "M.": "m.", "Ii": "II", "Iii": "III",
           "Xx": "XX", "Xxx": "XXX", "Ii.": "II.", "Pow.": "pow.", "Bł.": "bł."}


def _tytulowo(tekst: str) -> str:
    """WIELKIE LITERY z katalogu europejskiego -> zwykly zapis adresu."""
    if tekst != tekst.upper() or not re.search(r"[A-ZĄĆĘŁŃÓŚŹŻ]", tekst):
        return tekst
    slowa = []
    for slowo in tekst.title().split(" "):
        slowo = re.sub(r"(['-])(\w)", lambda m: m.group(1) + m.group(2).upper(), slowo)
        slowa.append(_SKROTY.get(slowo, slowo))
    return " ".join(slowa)


def adres(tekst, miejscowosc: str, izba: str) -> str:
    """Jedna czytelna linia adresu z kilku wersji rozdzielonych srednikiem."""
    tekst = napraw_kodowanie(tekst or "")
    kandydaci = []
    for czesc in re.split(r"\s*;\s*", tekst):
        czesc = _czysty(czesc)
        if not czesc:
            continue
        czesc = re.sub(r",?\s*(POLAND|Polska)$", "", czesc, flags=re.I)
        # katalog europejski doklada miasto izby: "..., BARCZEWO, BIAŁYSTOK"
        czesc = re.sub(r",\s*" + re.escape(MIASTA_IZB.get(izba, "")) + r"$", "", czesc, flags=re.I) if MIASTA_IZB.get(izba) and MIASTA_IZB[izba].lower() != miejscowosc.lower() else czesc
        czesc = _tytulowo(czesc)
        kandydaci.append(czesc)
    if not kandydaci:
        return ""
    z_kodem = [k for k in kandydaci if re.search(r"\b\d{2}-\d{3}\b", k)]
    wybor = max(z_kodem or kandydaci, key=len)
    # bez powtorzonej miejscowosci na koncu, gdy juz jest w srodku
    if wybor.lower().count(miejscowosc.lower()) > 1:
        wybor = re.sub(r",\s*" + re.escape(miejscowosc) + r"$", "", wybor, flags=re.I)
    if miejscowosc.lower() not in wybor.lower():
        wybor = f"{wybor}, {miejscowosc}"
    return wybor


# Poczatki numerow komorkowych (dwie pierwsze cyfry); reszta to stacjonarne
# z dwucyfrowym numerem kierunkowym.
_KOMORKOWE = {"45", "50", "51", "53", "57", "60", "66", "69", "72", "73", "78", "79", "88"}


def telefony(tekst) -> list[str]:
    """Numery do pokazania: bez faksow i etykiet, najwyzej dwa, format 'xxx xxx xxx'."""
    tekst = napraw_kodowanie(str(tekst) if tekst is not None else "")
    if not tekst:
        return []
    wynik: list[str] = []
    for czesc in re.split(r"[;/,]|\s(?:lub|albo|i)\s", tekst):
        czesc = czesc.strip()
        if not czesc or re.search(r"\bfax\b", czesc, re.I) and not re.search(r"\btel", czesc, re.I):
            continue
        cyfry = re.sub(r"\D", "", czesc)
        if cyfry.startswith("0048"):
            cyfry = cyfry[4:]
        elif cyfry.startswith("48") and len(cyfry) == 11:
            cyfry = cyfry[2:]
        if len(cyfry) != 9:
            continue
        if cyfry[:2] in _KOMORKOWE:
            numer = f"{cyfry[:3]} {cyfry[3:6]} {cyfry[6:]}"
        else:   # stacjonarny: dwucyfrowy numer kierunkowy
            numer = f"{cyfry[:2]} {cyfry[2:5]} {cyfry[5:7]} {cyfry[7:]}"
        if numer not in wynik:
            wynik.append(numer)
    return wynik[:2]


def osoba(tekst: str) -> str:
    """'Kisiel Małgorzata' -> 'Małgorzata Kisiel' (w wykazie nazwisko jest pierwsze)."""
    czesci = _czysty(tekst).split(" ")
    if len(czesci) < 2:
        return tekst
    return " ".join(czesci[1:] + czesci[:1])


def nazwa_kancelarii(notariusze: str, forma: str) -> str:
    osoby = [osoba(n) for n in re.split(r"\s*,\s*", _czysty(notariusze)) if n]
    forma = (forma or "").lower().replace("spóła", "spółka")
    if len(osoby) == 1 and not forma:
        return f"Kancelaria Notarialna {osoby[0]}"
    skrot = " s.c." if "cywilna" in forma else (" sp.p." if "partnerska" in forma else "")
    return "Kancelaria Notarialna " + ", ".join(osoby) + skrot


def www(tekst) -> tuple[str, str]:
    """(strona kancelarii, profil w katalogu) - pierwszy adres kazdego rodzaju."""
    strona, profil = "", ""
    for adres_www in re.split(r"[;\s]+", _czysty(tekst)):
        if not adres_www.startswith("http"):
            continue
        if "notaries-directory.eu" in adres_www:
            profil = profil or adres_www
        else:
            strona = strona or adres_www
    return strona, profil


def normalizuj(wiersze: list[list]) -> dict:
    naglowek = [str(h or "") for h in wiersze[0]]
    idx = {nazwa: i for i, nazwa in enumerate(naglowek)}

    def pole(w, nazwa):
        i = idx.get(nazwa)
        return w[i] if i is not None and i < len(w) else None

    surowe = []
    for w in wiersze[1:]:
        if not w or pole(w, "ID") in (None, ""):
            continue
        surowe.append(w)

    # miejscowosci: lacz literowki (ten sam slug) pod nazwa z polskimi znakami
    nazwy: dict[str, Counter] = defaultdict(Counter)
    for w in surowe:
        m = _czysty(napraw_kodowanie(pole(w, "Miejscowość")))
        nazwy[slug(m)][m] += 1
    kanon = {}
    for s, licznik in nazwy.items():
        kanon[s] = max(licznik, key=lambda n: (n == n.title() or n == n.title().replace(" I ", " i "),
                                               sum(ch > "\x7f" for ch in n), licznik[n]))

    kancelarie = []
    for w in surowe:
        izba = _czysty(pole(w, "Izba notarialna"))
        s = slug(_czysty(napraw_kodowanie(pole(w, "Miejscowość"))))
        miejscowosc = kanon[s]
        notariusze = _czysty(napraw_kodowanie(pole(w, "Notariusz / notariusze")))
        forma = _czysty(pole(w, "Forma prowadzenia")).replace("spóła", "spółka")
        strona, profil = www(pole(w, "Strona WWW / profil"))
        status = _czysty(pole(w, "Status weryfikacji"))
        kancelarie.append({
            "id": int(pole(w, "ID")),
            "izba": izba,
            "miejscowosc": miejscowosc,
            "slug": s,
            "notariusze": notariusze,
            "nazwa": nazwa_kancelarii(notariusze, forma),
            "forma": forma,
            "adres": adres(pole(w, "Adres kancelarii"), miejscowosc, izba),
            "telefony": telefony(pole(w, "Telefon")),
            "email": _czysty(pole(w, "E-mail")).lower(),
            "www": strona,
            "profil": profil,
            "zweryfikowany": "oficjalny" in status or "izby" in status,
            "brak_kontaktu": status.startswith("brak"),
        })
    kancelarie.sort(key=lambda k: (k["slug"], not k["zweryfikowany"], k["nazwa"]))

    licznik = Counter(k["slug"] for k in kancelarie)
    izba_miasta = {k["slug"]: k["izba"] for k in kancelarie}
    miejscowosci = [{"slug": s, "nazwa": kanon[s], "izba": izba_miasta[s], "liczba": n}
                    for s, n in sorted(licznik.items(), key=lambda p: p[0])]
    return {"stan": STAN_WYKAZU,
            "zrodla": ["https://dane.gov.pl/pl/dataset/22657", "wyszukiwarki izb notarialnych",
                       "katalog branżowy (kontakty do ponownej weryfikacji)"],
            "izby": IZBY, "miejscowosci": miejscowosci, "kancelarie": kancelarie}


def wczytaj_json(plik: Path = PLIK_JSON) -> dict:
    return json.loads(plik.read_text("utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    dane = normalizuj(wczytaj_xlsx(Path(argv[1]), "Baza kancelarii"))
    cel = Path(argv[2]) if len(argv) > 2 else PLIK_JSON
    cel.write_text(json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(dane['kancelarie'])} kancelarii, {len(dane['miejscowosci'])} miejscowosci -> {cel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
