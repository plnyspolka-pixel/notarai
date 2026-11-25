"""Lokalne OCR i propozycje zakresów PII. Wynik zawsze wymaga przeglądu.

Bez pobierania modeli w czasie żądania, bez usług sieciowych. Brak OCR albo
niska jakość to błąd lokalny, nigdy powód do wysłania obrazu do Bedrock.
"""
import csv
import io
import re
import subprocess
from dataclasses import dataclass

from pseudonimizacja_aktu import DaneDodatkowe, WymagaWeryfikacji


@dataclass(frozen=True, repr=False)
class WynikOCR:
    tekst: str
    niska_pewnosc: bool


def ocr_png(obraz: bytes) -> WynikOCR:
    if not isinstance(obraz, bytes) or not obraz.startswith(b"\x89PNG\r\n\x1a\n"):
        raise WymagaWeryfikacji("OCR_INVALID_PNG")
    if len(obraz) > 20 * 1024 * 1024:
        raise WymagaWeryfikacji("OCR_IMAGE_TOO_LARGE")
    try:
        wynik = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", "pol", "tsv"],
            input=obraz, capture_output=True, check=True, timeout=60,
        )
        wiersze = csv.DictReader(io.StringIO(wynik.stdout.decode("utf-8")), delimiter="\t")
        linie = {}
        niska = False
        for w in wiersze:
            tekst = (w.get("text") or "").strip()
            if not tekst or w.get("level") != "5":
                continue
            klucz = tuple(w[k] for k in ("page_num", "block_num", "par_num", "line_num"))
            linie.setdefault(klucz, []).append(tekst)
            niska = niska or float(w["conf"]) < 80
        tekst = "\n".join(" ".join(linia) for linia in linie.values())
        if not tekst.strip():
            raise ValueError("empty")
        return WynikOCR(tekst, niska)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        raise WymagaWeryfikacji("LOCAL_OCR_FAILED") from None


_WZORY = (
    ("EMAIL", r"(?<![\w.])[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}(?!\w)"),
    ("KW", r"(?<!\w)[A-Z]{2}[0-9][A-Z]/[0-9]{8}/[0-9](?!\w)"),
    ("KONTO", r"(?<!\d)(?:PL[ \t]*)?\d(?:[ \t-]*\d){25}(?!\d)"),
    ("DOWOD", r"(?<!\w)[A-Z]{3}[ \t-]*\d{6}(?!\w)"),
    ("NUMER", r"(?<!\d)\d(?:[ \t-]*\d){8,13}(?!\d)"),
    ("KOD_POCZTOWY", r"(?<!\d)\d{2}-\d{3}(?!\d)"),
)


def propozycje(tekst, nlp=None):
    """Kandydaci do przeglądu, nie certyfikat kompletności NER.

    nlp: opcjonalny, lokalny i wcześniej zweryfikowany model spaCy.
    Zwracamy także nakładające się propozycje; człowiek rozstrzyga zakresy.
    """
    wynik = [DaneDodatkowe(m.start(), m.end(), typ)
             for typ, wzor in _WZORY for m in re.finditer(wzor, tekst, re.I)]
    if nlp is not None:
        for e in nlp(tekst).ents:
            wynik.append(DaneDodatkowe(e.start_char, e.end_char, "PII"))
    return sorted(wynik, key=lambda w: (w.poczatek, w.koniec, w.typ))
