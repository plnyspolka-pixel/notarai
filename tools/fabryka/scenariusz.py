"""Scenariusz odcinka V6 przez Bedrock (eu-central-1) z cache promptu.

Stała część (biblia, kontrakt JSON, katalog planów) idzie do bloku systemowego z punktem cache, więc
dwa i cztery odcinki z jednej paczki płacą za nią raz w ciągu 5 minut. Zmienna część (numer,
slot, kotwica z kartą, streszczenie poprzedniego odcinka) idzie w wiadomości. Wynik przechodzi przez
walidatory; przy błędach model dostaje listę problemów i jedną szansę poprawki.
Bez danych klientów: wejście to wyłącznie materiały serialu i zanonimizowana karta sprawy.
"""
from __future__ import annotations

import json
import os
import re

from . import walidatory
from .wspolne import BIBLIA, czytaj

MODEL = os.getenv("FABRYKA_MODEL", os.getenv("PIECZAPP_MODEL", "eu.anthropic.claude-opus-4-6-v1"))
REGION = os.getenv("AWS_REGION", "eu-central-1")
MAX_TOKENY = 16000

KONTRAKT = {
    "id": "s01e09", "sezon": 1, "odcinek": 9, "slot": "09:00", "tytul": "krótki, z napięciem, bez clickbaitu",
    "sprawa_kotwica": "A17", "prowadzi": "helena", "typ_otwarcia": "A|B|C",
    "muzyka": {"typ": "brak|ciepla|dzwieki_kancelarii", "pod_szczytem": False},
    "pytanie_koncowe": "pytanie o ocenę postaci albo decyzji, nigdy o zgadywanie",
    "streszczenie": "3 zdania do kontekstu następnego odcinka",
    "sceny": [{
        "id": "sc1", "rola": "zimne_otwarcie|tytul|swiat|zwrot1|praca|szczyt|zawieszenie|plansza_koncowa",
        "plan": "s02", "kamera": "K03_helena_zblizenie", "wariant": "dzien|wieczor",
        "ujecia": [{
            "id": "u1", "typ": "mowiace|bez_mowy|dokument|ekran|plansza", "postac": "helena",
            "znacznik": "M_Helena_szczyt", "kwestia": "tekst po polsku",
            "kwestia_v3": "[calm] tekst z tagami ElevenLabs v3", "czas_s": 3.5,
            "ruch_kamery": "statyczna|najazd|odjazd|w-lewo|w-prawo",
            "prompt_ruchu": "tylko ruch po angielsku, bez słów o tekście",
            "dokument": {"szablon": "notatka|porownanie_kw", "pola": {}, "fokus": "co widz ma przeczytać"},
            "ekran": {"funkcja": "nazwa funkcji NotarAI do nagrania"},
            "tekst": "tylko dla planszy", "zart": False, "romans": False, "dozwolony_tekst": None,
        }],
    }],
    "lista_kontrolna": {k: {"ok": True, "jak": "jedno zdanie, jak odcinek spełnia punkt"}
                        for k in walidatory.LISTA_THRILLERA},
}

INSTRUKCJA = """Piszesz jeden odcinek serialu „Kancelaria pod Siódemką / Komputerku…” według BIBLII V6
(poniżej). Oddajesz WYŁĄCZNIE obiekt JSON zgodny z kontraktem, bez komentarza.
Twarde zasady: 60–90 s; 7–9 scen + plansza tytułowa i końcowa; jeden szczyt; najwyżej jeden żart
(`zart: true`) i jeden beat romansu (`romans: true`); w pierwszych 3 s tylko ujęcie mówiące lub nieme,
dwa głosy w pierwszych 10 s; ekran programu poza oknem ±5 s od szczytu; co najmniej jedno ujęcie
`dokument`; zero tekstu w ujęciach generowanych; plansza końcowa zawiera dokładnie zdanie:
„{plansza}”; kamery i znaczniki wyłącznie z KATALOGU PLANÓW; kwestie krótkie (≤ 13 znaków na sekundę),
każda z wersją `kwestia_v3` zaczynającą się od tagu w nawiasie kwadratowym; punkt widzenia Heleny;
żadnych sygnatur, kwot, miejscowości ani nazwisk z prawdziwej sprawy; nazwisko notariusza-konsultanta
nigdy nie pada; AI nie wykrywa przestępstw, decyduje notariusz."""


def _katalog_planow(scenografia: dict) -> str:
    linie = []
    for kod, p in sorted(scenografia.items()):
        kam = "; ".join(f"{k['nazwa']} ({k.get('uzycie', '')})" for k in p.get("kamery", []))
        zn = "; ".join(f"{z['nazwa']} ({z.get('opis', '')})" for z in p.get("znaczniki", []))
        linie.append(f"- {kod} {p.get('nazwa', '')}: warianty {p.get('warianty')}\n  kamery: {kam}\n  znaczniki: {zn}")
    return "\n".join(linie)


def prompt(numer: dict, plan_sezonu: dict, karta: str | None, poprzedni: dict | None,
           scenografia: dict) -> tuple[list[dict], list[dict]]:
    """(system, messages) dla Bedrock Converse; system z punktem cache."""
    biblia = czytaj(BIBLIA) or ""
    system = [
        {"text": INSTRUKCJA.format(plansza=walidatory.PLANSZA_KONCOWA)},
        {"text": "KONTRAKT JSON (przykład pól):\n" + json.dumps(KONTRAKT, ensure_ascii=False, indent=1)},
        {"text": "BIBLIA V6:\n" + biblia},
        {"text": "KATALOG PLANÓW (Blender, scenografia/blender-v1):\n" + _katalog_planow(scenografia)},
        {"cachePoint": {"type": "default"}},
    ]
    zadanie = {
        "odcinek": numer,
        "plan_sezonu_dla_odcinka": plan_sezonu,
        "poprzedni_odcinek": {k: (poprzedni or {}).get(k) for k in ("id", "tytul", "streszczenie", "typ_otwarcia", "prowadzi")},
        "karta_sprawy": karta or "brak karty: użyj kotwicy wyłącznie jako ogólnego motywu",
    }
    messages = [{"role": "user", "content": [{"text": json.dumps(zadanie, ensure_ascii=False, indent=1)}]}]
    return system, messages


def _json_z_odpowiedzi(t: str) -> dict:
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        raise ValueError("odpowiedź bez obiektu JSON")
    return json.loads(m.group(0))


def _wywolaj(system, messages) -> tuple[str, dict]:
    import boto3  # dostępne w środowisku aplikacji (requirements.txt)
    k = boto3.client("bedrock-runtime", region_name=REGION)
    r = k.converse(modelId=MODEL, system=system, messages=messages,
                   inferenceConfig={"maxTokens": MAX_TOKENY, "temperature": 0.7})
    tekst = "".join(c.get("text", "") for c in r["output"]["message"]["content"])
    return tekst, r.get("usage", {})


def napisz(numer: dict, plan_sezonu: dict, karta: str | None, poprzedni: dict | None, scenografia: dict,
           kontekst_walidacji: dict, wywolaj=_wywolaj) -> tuple[dict, list[str], list[dict]]:
    """Zwraca (scenariusz, problemy, zużycie). Problemy puste = scenariusz przechodzi bramkę."""
    system, messages = prompt(numer, plan_sezonu, karta, poprzedni, scenografia)
    zuzycie = []
    tekst, u = wywolaj(system, messages)
    zuzycie.append(u)
    sc = _json_z_odpowiedzi(tekst)
    problemy = walidatory.sprawdz(sc, scenografia=scenografia, **kontekst_walidacji)
    if problemy:
        messages += [
            {"role": "assistant", "content": [{"text": json.dumps(sc, ensure_ascii=False)}]},
            {"role": "user", "content": [{"text": "Popraw tylko te problemy i oddaj cały JSON:\n- " + "\n- ".join(problemy)}]},
        ]
        tekst, u = wywolaj(system, messages)
        zuzycie.append(u)
        sc = _json_z_odpowiedzi(tekst)
        problemy = walidatory.sprawdz(sc, scenografia=scenografia, **kontekst_walidacji)
    return sc, problemy, zuzycie
