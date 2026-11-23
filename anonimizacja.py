"""Anonimizacja stenogramu odczytania aktu.

Surowy stenogram (z rozpoznawania mowy) nigdzie nie jest zapisywany - trzymamy
go w pamieci tylko na czas tej funkcji. Na dysk i do S3 idzie wylacznie wynik.

Trzy warstwy, od najpewniejszej:
  1. model w Bedrock (profil eu.) wskazuje fragmenty z danymi osobowymi; kod
     sam je podmienia, wiec model nie moze przeinaczyc tresci stenogramu,
  2. dane stron, ktore notarai odczytal ze skanow sprawy (odczyt.json), sa
     podmieniane po rdzeniu slowa - lapie odmiane ("Sobczak" -> "Sobczaka"),
  3. siatka wzorcow: PESEL (takze podyktowany ze spacjami), dowod, paszport,
     ksiega wieczysta, telefon, rachunek, e-mail, adres.
Na koniec kontrola: gdy zostal ciag 11 cyfr albo e-mail, zakrywamy go i tak.
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


def wskaz_dane(segmenty: list[dict]) -> list[tuple[str, str]]:
    """[(fragment, oznaczenie)] ze wszystkich paczek; oznaczenia osob spojne."""
    osoby: dict[str, str] = {}
    wynik: list[tuple[str, str]] = []
    for paczka in _paczki(segmenty):
        tekst = "\n".join(f"[{i}] {segmenty[i]['tekst']}" for i in paczka)
        znane = "\n".join(f"- {kto}: {ozn}" for kto, ozn in osoby.items()) or "(brak)"
        tresc = [{"text": f"OSOBY JUZ OZNACZONE:\n{znane}\n\nSTENOGRAM:\n{tekst}"}]
        surowa = bedrock._rozmowa(prompty.STENOGRAM_ANONIMIZACJA, tresc, max_tokenow=8000,
                                  myslenie=False, model=MODEL)
        odp = bedrock._wczytaj_json_z_naprawa(surowa)
        for o in odp.get("osoby") or []:
            if o.get("kto") and o.get("oznaczenie"):
                osoby.setdefault(str(o["kto"]), str(o["oznaczenie"]))
        for d in odp.get("dane") or []:
            fragment = str(d.get("fragment") or "").strip()
            oznaczenie = re.sub(r"[^A-Z0-9_ ]", "", str(d.get("oznaczenie") or "DANE").upper()).strip() or "DANE"
            if len(fragment) >= 2:
                wynik.append((fragment, oznaczenie))
    return wynik


def _podmien_fragmenty(tekst: str, dane: list[tuple[str, str]]) -> str:
    for fragment, oznaczenie in sorted(dane, key=lambda d: -len(d[0])):
        wzor = re.escape(fragment)
        # Granice slowa tylko tam, gdzie fragment zaczyna/konczy sie litera lub cyfra.
        if fragment[0].isalnum():
            wzor = r"(?<!\w)" + wzor
        if fragment[-1].isalnum():
            wzor += r"(?!\w)"
        tekst = re.sub(wzor, f"[{oznaczenie}]", tekst)
    return tekst


# --- 2. dane stron ze sprawy -------------------------------------------------

_SLOWO = re.compile(r"[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż]{2,}")
_CYFRY = re.compile(r"\d(?:[\d\s/.-]{4,}\d)")
_WALUTA = re.compile(r"(?:,\d{1,2})?\s*(?:zł|zl|złot|PLN|EUR|euro)", re.IGNORECASE)


def znane_z_sprawy(katalog: Path) -> list[str]:
    """Slowa wlasne i dlugie numery z odczytanych pol sprawy (bez leksykonu prawnego)."""
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


def _podmien_znane(tekst: str, znane: list[str]) -> str:
    for wartosc in sorted(znane, key=len, reverse=True):
        if wartosc.isdigit():
            # Numer podyktowany w grupach: "80 01 01 123 45".
            wzor = r"(?<!\d)" + r"[\s-]?".join(wartosc) + r"(?!\d)"
            tekst = re.sub(wzor, "[PESEL]" if len(wartosc) == 11 else "[NUMER]", tekst)
        else:
            rdzen = kategorie.bez_ogonkow(_rdzen(wartosc))

            def podmien(m: re.Match, rdzen=rdzen) -> str:
                slowo = m.group(0)
                bez = kategorie.bez_ogonkow(slowo)
                return "[DANE]" if bez.startswith(rdzen) and len(bez) - len(rdzen) <= 6 else slowo
            # Tylko slowa wielka litera: "Nowak" nie moze zakryc zwyklego "nowa".
            # Do 6 liter koncowki: "Pawlak" -> "Pawlakowej".
            tekst = re.sub(r"(?<!\w)[A-ZĄĆĘŁŃÓŚŹŻ][^\W\d_]{2,}(?!\w)", podmien, tekst)
    return tekst


# --- 3. wzorce ---------------------------------------------------------------

_WZORCE = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"(?<!\d)(?:\d[\s-]?){10}\d(?!\d)"), "[PESEL]"),
    (re.compile(r"(?<!\d)(?:\d[\s-]?){25}\d(?!\d)"), "[RACHUNEK]"),
    (re.compile(r"\bPL\s?(?:\d[\s-]?){25}\d\b"), "[RACHUNEK]"),
    (re.compile(r"\b[A-Z]{2}\d[A-Z]\s?/\s?\d{8}\s?/\s?\d\b"), "[KSIEGA]"),
    (re.compile(r"\b[A-Z]{3}\s?\d{6}\b"), "[DOKUMENT]"),
    (re.compile(r"\b[A-Z]{2}\s?\d{7}\b"), "[DOKUMENT]"),
    (re.compile(r"(?:\+48[\s-]?)?(?<!\d)\d{3}[\s-]?\d{3}[\s-]?\d{3}(?!\d)"), "[TELEFON]"),
    (re.compile(r"\b\d{2}-\d{3}\b"), "[KOD]"),
    (re.compile(r"\b(ul\.|ulicy|ulica|ulic[eę]|al\.|alei|aleja|os\.|osiedlu|osiedle)\s+"
                r"[^\s,;.]+(?:\s+[^\s,;.]+)?\s+\d+[a-zA-Z]?(?:\s*(?:/|m\.?|mieszkania|lokalu|lok\.)\s*\d+)?",
                re.IGNORECASE), r"\1 [ADRES]"),
]


def _podmien_wzorce(tekst: str) -> str:
    for wzor, zamiana in _WZORCE:
        tekst = wzor.sub(zamiana, tekst)
    return tekst


def _zostalo(tekst: str) -> bool:
    return bool(re.search(r"(?<!\d)(?:\d[\s-]?){10}\d(?!\d)|@[\w-]+\.", tekst))


# --- calosc ------------------------------------------------------------------

def anonimizuj(segmenty: list[dict], znane: list[str], z_modelem: bool = True) -> list[dict]:
    """segmenty [{start, mowca, tekst}] -> te same segmenty z zakrytymi danymi."""
    dane = wskaz_dane(segmenty) if z_modelem else []
    wynik = []
    for s in segmenty:
        tekst = _podmien_fragmenty(s["tekst"], dane)
        tekst = _podmien_znane(tekst, znane)
        tekst = _podmien_wzorce(tekst)
        if _zostalo(tekst):
            tekst = re.sub(r"\d", "#", tekst)
        tekst = re.sub(r"(\[[A-Z0-9_ ]+\])(?:\s*\1)+", r"\1", tekst)
        wynik.append({**s, "tekst": tekst})
    log.info("anonimizacja: %d wypowiedzi, %d wskazan modelu, %d znanych z sprawy",
             len(segmenty), len(dane), len(znane))
    return wynik
