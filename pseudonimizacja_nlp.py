"""Lokalne NER i fleksja polska. Brak modelu oznacza odmowę, nie fallback.

Wagi są instalowane podczas budowania obrazu, nie podczas obsługi spraw.
Model nie dostaje map pseudonimów; nie używa API ani zdalnego kodu.
"""
import os
import re
import threading
from pathlib import Path
from itertools import product

from pseudonimizacja_aktu import DaneDodatkowe, WymagaWeryfikacji, _norm

_lock = threading.RLock()
_ner = None
_morf = None
MODEL_ID = "radlab/pii-pl-v1.0"
MODEL_REVISION = "97ba763518491bb17dc10ab1870453d3abb4ef09"


def _pipeline():
    global _ner
    with _lock:
        if _ner is None:
            try:
                from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
                katalog = Path(os.environ.get("PIECZAPP_PII_MODEL_DIR", "/opt/notarai/pii-pl"))
                if not katalog.is_dir() or not (katalog / "model.safetensors").is_file():
                    raise ValueError("missing")
                if (katalog / "notarai-revision.txt").read_text("utf-8").strip() != MODEL_REVISION:
                    raise ValueError("unapproved revision")
                tok = AutoTokenizer.from_pretrained(str(katalog), local_files_only=True,
                                                    trust_remote_code=False, use_fast=True)
                model = AutoModelForTokenClassification.from_pretrained(
                    str(katalog), local_files_only=True, trust_remote_code=False,
                    use_safetensors=True)
                tok.model_max_length = 128  # model fine-tuned on 128-token sequences
                _ner = pipeline("token-classification", model=model, tokenizer=tok,
                                aggregation_strategy="simple", device=-1)
            except Exception:
                raise WymagaWeryfikacji("LOCAL_NER_UNAVAILABLE") from None
        return _ner


def propozycje_ner(tekst, *, detektor=None):
    """Każdy fragment jest analizowany, bez cichego obcięcia długich aktów."""
    if not tekst.strip():
        return []
    if len(tekst) > 400000:
        raise WymagaWeryfikacji("LOCAL_NER_INPUT_TOO_LONG")
    typy = {"PERSON": "OSOBA", "CONTACT/NUM": "KONTAKT", "LOCATION": "MIEJSCE",
            "ORGANIZATION": "PODMIOT", "FACILITY": "OBIEKT", "OTHER": "PII",
            "EVENT": "PII", "PRODUCT": "PII"}
    try:
        with _lock:
            pipe = detektor or _pipeline()
            # Fast tokenizer i overlap w jednostkach tokenów; zachowuje offsety
            # względem oryginału także na granicach okien.
            wyniki = pipe(tekst, stride=32)
        out = set()
        for w in wyniki:
            a, b = int(w["start"]), int(w["end"])
            if not 0 <= a < b <= len(tekst):
                raise ValueError("bad offsets")
            label = str(w["entity_group"])
            if label == "O":
                continue
            # Nie ignorujemy nawet etykiet nieznanych ani niskich confidence.
            out.add((a, b, typy.get(label, "PII")))
        return [DaneDodatkowe(a, b, typ) for a, b, typ in sorted(out)]
    except WymagaWeryfikacji:
        raise
    except Exception:
        raise WymagaWeryfikacji("LOCAL_NER_FAILED") from None


def _morfeusz():
    global _morf
    with _lock:
        if _morf is None:
            try:
                import morfeusz2
                _morf = morfeusz2.Morfeusz()
            except Exception:
                raise WymagaWeryfikacji("LOCAL_MORPHOLOGY_UNAVAILABLE") from None
        return _morf


_PRZYPADKI = ("nom", "gen", "dat", "acc", "inst", "loc", "voc")


def _formy(slowo, silnik):
    # Zachowujemy nazwiska nieodmienne oraz człony dwuczłonowe.
    if "-" in slowo:
        slowa = slowo.split("-")
        if len(slowa) > 4 or not all(slowa):
            raise WymagaWeryfikacji("LOCAL_MORPHOLOGY_AMBIGUOUS")
        czesci = [_formy(s, silnik) for s in slowa]
        from math import prod
        if any(prod(len(c[k]) for c in czesci) > 32 for k in _PRZYPADKI):
            raise WymagaWeryfikacji("LOCAL_MORPHOLOGY_AMBIGUOUS")
        return {k: {"-".join(x) for x in product(*(c[k] for c in czesci))}
                for k in _PRZYPADKI}
    wynik = {k: {slowo} for k in _PRZYPADKI}
    # Analiza formy podstawowej zwraca też lematy z identyfikatorem homonimu.
    lematy = {slowo}
    for _, _, interp in silnik.analyse(slowo):
        if _norm(interp[1].split(":")[0]) == _norm(slowo):
            lematy.add(interp[1])
    for lemat in lematy:
        for interp in silnik.generate(lemat):
            forma, _, tag = interp[:3]
            pola = tag.split(":")
            if not pola or pola[0] not in ("subst", "adj", "depr"):
                continue
            if len(pola) < 3 or "sg" not in pola[1].split("."):
                continue
            for k in pola[2].split("."):
                if k in wynik:
                    wynik[k].add(forma)
    if any(len(v) > 32 for v in wynik.values()):
        raise WymagaWeryfikacji("LOCAL_MORPHOLOGY_AMBIGUOUS")
    return wynik


def propozycje_fleksji(tekst, osoby, *, silnik=None):
    """Tylko sugestie pełnego imienia i nazwiska; nigdy scalenie rekordów."""
    if not osoby:
        return []
    try:
        with _lock:
            morf = silnik or _morfeusz()
            indeks = {}
            for o in osoby:
                zestawy = {(*o.imiona, o.nazwisko), (o.imiona[0], o.nazwisko)}
                for nazwa in zestawy:
                    formy = [_formy(s, morf) for s in nazwa]
                    for k in _PRZYPADKI:
                        kombinacje = 1
                        for f in formy:
                            kombinacje *= len(f[k])
                        if kombinacje > 4096:
                            raise WymagaWeryfikacji("LOCAL_MORPHOLOGY_AMBIGUOUS")
                        for wariant in product(*(f[k] for f in formy)):
                            indeks.setdefault(_norm(" ".join(wariant)), set()).add(o.id)
                            if len(indeks) > 30000:
                                raise WymagaWeryfikacji("LOCAL_MORPHOLOGY_AMBIGUOUS")
        wynik = []
        for alias, ids in indeks.items():
            wzor = r"(?<!\w)" + r"\s+".join(map(re.escape, alias.split())) + r"(?!\w)"
            for m in re.finditer(wzor, tekst, re.I):
                wynik.append({"poczatek": m.start(), "koniec": m.end(),
                              "typ": "NAZWA", "kandydaci": sorted(ids),
                              "wymaga_potwierdzenia": True})
        return sorted(wynik, key=lambda w: (w["poczatek"], -w["koniec"]))
    except WymagaWeryfikacji:
        raise
    except Exception:
        raise WymagaWeryfikacji("LOCAL_MORPHOLOGY_FAILED") from None
