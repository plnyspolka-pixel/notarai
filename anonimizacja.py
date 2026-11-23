"""Maskowanie danych osobowych w stenogramie odczytania aktu.

Dane nie znikają całkiem: zostaje początek i koniec, środek zamieniamy na
gwiazdki. Kto zna treść aktu, dopasuje osobę do roli, a postronny nie
odczyta danych:
  słowa  - pierwsza i ostatnia litera:  "Jan Sobczak"  -> "J*n S*****k",
  numery - dwie pierwsze i dwie ostatnie cyfry (krótsze: po jednej),
           separatory zostają:          "80 01 01 123 45" -> "80 ** ** *** 45".
Uwaga: to pseudonimizacja, nie anonimizacja w rozumieniu RODO. Stenogram
dalej jest daną osobową i leży przy sprawie z tymi samymi zabezpieczeniami.

Surowy stenogram (z rozpoznawania mowy) nigdzie nie jest zapisywany - trzymamy
go w pamięci tylko na czas tej funkcji. Na dysk i do S3 idzie wyłącznie wynik.

Trzy warstwy, od najpewniejszej:
  1. model w Bedrock (profil eu.) wskazuje fragmenty z danymi osobowymi; kod
     sam je maskuje, więc model nie może przeinaczyć treści stenogramu,
  2. dane stron, które notarai odczytał ze skanów sprawy (odczyt.json),
     szukane po rdzeniu słowa - łapie odmianę ("Sobczak" -> "Sobczaka"),
  3. siatka wzorców: PESEL (także podyktowany ze spacjami), dowód, paszport,
     księga wieczysta, telefon, rachunek, e-mail, adres, kod pocztowy.
Na koniec kontrola: gdy został pełny ciąg 11 cyfr albo e-mail, maskujemy i tak.
"""
import json
import logging
import os
import re
from pathlib import Path

import bedrock
import klauzule
import kategorie
import prompty

log = logging.getLogger("pieczapp.anonimizacja")

MODEL_DOMYSLNY = "eu.anthropic.claude-sonnet-4-6"
SLOW_NA_ZAPYTANIE = 2500


def _model_z_env(wartosc: str | None) -> str:
    model = (MODEL_DOMYSLNY if wartosc is None else wartosc).strip()
    if not model.startswith("eu."):
        raise RuntimeError(f"PIECZAPP_STENOGRAM_MODEL '{model}' nie jest profilem EU (prefiks 'eu.').")
    return model


MODEL = _model_z_env(os.getenv("PIECZAPP_STENOGRAM_MODEL"))


# --- maska: początek i koniec zostają ----------------------------------------

_CIAG_CYFR = re.compile(r"\d(?:[\s-]?\d)*")
_LITERY = re.compile(r"[^\W\d_]+")


def zamaskuj(tekst: str) -> str:
    """"Jan Sobczak" -> "J*n S*****k", "80010112345" -> "80*******45"."""
    def cyfry(m: re.Match) -> str:
        ciag = m.group(0)
        pozycje = [i for i, z in enumerate(ciag) if z.isdigit()]
        n = len(pozycje)
        if n < 3:            # numer domu, lokalu - sam niczego nie zdradza
            return ciag
        zostaw = 2 if n >= 6 else 1
        ukryte = set(pozycje[zostaw:n - zostaw])
        return "".join("*" if i in ukryte else z for i, z in enumerate(ciag))

    def slowo(m: re.Match) -> str:
        s = m.group(0)
        if len(s) == 1:
            return s
        if len(s) == 2:
            return s[0] + "*"
        return s[0] + "*" * (len(s) - 2) + s[-1]

    return _LITERY.sub(slowo, _CIAG_CYFR.sub(cyfry, tekst))


# --- 1. model -----------------------------------------------------------------

def _paczki(segmenty: list[dict]) -> list[list[int]]:
    paczki, biezaca, slow = [], [], 0
    for i, s in enumerate(segmenty):
        n = len(s["tekst"].split())
        if biezaca and slow + n > SLOW_NA_ZAPYTANIE:
            paczki.append(biezaca)
            biezaca, slow = [], 0
        biezaca.append(i)
        slow += n
    if biezaca:
        paczki.append(biezaca)
    return paczki


def wskaz_dane(segmenty: list[dict]) -> list[str]:
    """Fragmenty z danymi osobowymi, dokładnie tak, jak stoją w tekście."""
    wynik: list[str] = []
    for paczka in _paczki(segmenty):
        tekst = "\n".join(f"[{i}] {segmenty[i]['tekst']}" for i in paczka)
        surowa = bedrock._rozmowa(prompty.STENOGRAM_ANONIMIZACJA, [{"text": f"STENOGRAM:\n{tekst}"}],
                                  max_tokenow=8000, myslenie=False, model=MODEL)
        for d in bedrock._wczytaj_json_z_naprawa(surowa).get("dane") or []:
            fragment = str((d.get("fragment") if isinstance(d, dict) else d) or "").strip()
            if len(fragment) >= 2:
                wynik.append(fragment)
    return wynik


def _maskuj_fragmenty(tekst: str, fragmenty: list[str]) -> str:
    for fragment in sorted(set(fragmenty), key=len, reverse=True):
        wzor = re.escape(fragment)
        # Granice słowa tylko tam, gdzie fragment zaczyna/kończy się literą lub cyfrą.
        if fragment[0].isalnum():
            wzor = r"(?<!\w)" + wzor
        if fragment[-1].isalnum():
            wzor += r"(?!\w)"
        tekst = re.sub(wzor, lambda m: zamaskuj(m.group(0)), tekst)
    return tekst


# --- 2. dane stron ze sprawy -------------------------------------------------

_SLOWO = re.compile(r"[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż]{2,}")
_CYFRY = re.compile(r"\d(?:[\d\s/.-]{4,}\d)")
_WALUTA = re.compile(r"(?:,\d{1,2})?\s*(?:zł|zl|złot|PLN|EUR|euro)", re.IGNORECASE)


def znane_z_sprawy(katalog: Path) -> list[str]:
    """Słowa własne i długie numery z odczytanych pól sprawy (bez leksykonu prawnego)."""
    try:
        pola = json.loads((katalog / "odczyt.json").read_text("utf-8")).get("pola", [])
    except (OSError, ValueError):
        return []
    znane: set[str] = set()
    for pole in pola:
        wartosc = str(pole.get("wartosc") or "")
        for slowo in _SLOWO.findall(wartosc):
            if kategorie.bez_ogonkow(slowo) not in klauzule._LEKSYKON:
                znane.add(slowo)
        for m in _CYFRY.finditer(wartosc):
            # Kwota to nie dana osobowa, a w stenogramie aktu jest istotna.
            if _WALUTA.match(wartosc, m.end()):
                continue
            cyfry = re.sub(r"\D", "", m.group(0))
            if len(cyfry) >= 6:
                znane.add(cyfry)
    return sorted(znane)


def _rdzen(slowo: str) -> str:
    if len(slowo) <= 3:
        return slowo
    return slowo[:-1] if len(slowo) <= 5 else slowo[:-2]


def _maskuj_znane(tekst: str, znane: list[str]) -> str:
    for wartosc in sorted(znane, key=len, reverse=True):
        if wartosc.isdigit():
            # Numer podyktowany w grupach: "80 01 01 123 45".
            wzor = r"(?<!\d)" + r"[\s-]?".join(wartosc) + r"(?!\d)"
            tekst = re.sub(wzor, lambda m: zamaskuj(m.group(0)), tekst)
        else:
            rdzen = kategorie.bez_ogonkow(_rdzen(wartosc))

            def podmien(m: re.Match, rdzen=rdzen) -> str:
                slowo = m.group(0)
                bez = kategorie.bez_ogonkow(slowo)
                return zamaskuj(slowo) if bez.startswith(rdzen) and len(bez) - len(rdzen) <= 6 else slowo
            # Tylko słowa wielką literą: "Nowak" nie może zamaskować zwykłego "nowa".
            # Do 6 liter końcówki: "Pawlak" -> "Pawlakowej".
            tekst = re.sub(r"(?<!\w)[A-ZĄĆĘŁŃÓŚŹŻ][^\W\d_]{2,}(?!\w)", podmien, tekst)
    return tekst


# --- 3. wzorce ---------------------------------------------------------------

_NIE_KWOTA = r"(?!\s*(?:,\d{1,2})?\s*(?:zł|zl|złot|PLN|EUR|euro))"
_WZORCE = [
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),                                    # e-mail
    re.compile(r"\bPL\s?(?:\d[\s-]?){25}\d\b"),                                     # IBAN
    re.compile(r"(?<!\d)(?:\d[\s-]?){25}\d(?!\d)"),                                 # rachunek
    re.compile(r"(?<!\d)(?:\d[\s-]?){10}\d(?!\d)" + _NIE_KWOTA),                    # PESEL
    re.compile(r"\b[A-Z]{2}\d[A-Z]\s?/\s?\d{8}\s?/\s?\d\b"),                        # księga wieczysta
    re.compile(r"\b[A-Z]{3}\s?\d{6}\b"),                                            # dowód
    re.compile(r"\b[A-Z]{2}\s?\d{7}\b"),                                            # paszport
    re.compile(r"(?:\+48[\s-]?)?(?<!\d)\d{3}[\s-]?\d{3}[\s-]?\d{3}(?!\d)" + _NIE_KWOTA),  # telefon
    re.compile(r"\b\d{2}-\d{3}\b"),                                                 # kod pocztowy
]
# Adres: maskujemy nazwę ulicy, słowo "ulica" i numer domu zostają.
_WIELKA = "A-ZĄĆĘŁŃÓŚŹŻ"
_ADRES = re.compile(r"\b((?i:ul\.|ulicy|ulica|ulic[eę]|al\.|alei|aleja|os\.|osiedlu|osiedle))(\s+)"
                    rf"([{_WIELKA}][^\s,;.\d]*(?:\s+[{_WIELKA}][^\s,;.\d]*)?)")


def _maskuj_wzorce(tekst: str) -> str:
    for wzor in _WZORCE:
        tekst = wzor.sub(lambda m: zamaskuj(m.group(0)), tekst)
    return _ADRES.sub(lambda m: m.group(1) + m.group(2) + zamaskuj(m.group(3)), tekst)


def _zostalo(tekst: str) -> bool:
    return bool(re.search(r"(?<!\d)\d{11}(?!\d)|[\w.+-]{3,}@[\w-]{3,}\.", tekst))


# --- całość ------------------------------------------------------------------

def anonimizuj(segmenty: list[dict], znane: list[str], z_modelem: bool = True) -> list[dict]:
    """segmenty [{start, mowca, tekst}] -> te same segmenty z zamaskowanymi danymi."""
    fragmenty = wskaz_dane(segmenty) if z_modelem else []
    wynik = []
    for s in segmenty:
        tekst = _maskuj_fragmenty(s["tekst"], fragmenty)
        tekst = _maskuj_znane(tekst, znane)
        tekst = _maskuj_wzorce(tekst)
        if _zostalo(tekst):
            tekst = re.sub(r"(?<!\d)\d{11}(?!\d)|[\w.+-]{3,}@[\w-]{3,}\.[\w.]+", lambda m: zamaskuj(m.group(0)), tekst)
        wynik.append({**s, "tekst": tekst})
    log.info("maskowanie: %d wypowiedzi, %d wskazan modelu, %d znanych z sprawy",
             len(segmenty), len(fragmenty), len(znane))
    return wynik
