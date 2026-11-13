#!/usr/bin/env python3
"""Scenariusz (Markdown) → odcinek.json jednym wywołaniem modelu, z biblią serialu w cache.

Zamiast sesji agentowej, która przy każdym odcinku czyta od nowa biblię,
scenografię i obsadę (300–800 tys. tokenów), składamy JEDNO zapytanie Bedrock:

  [prefiks stały: biblia intrygi + prompty produkcyjne + obsada + kamery + schemat JSON]
  ── punkt cache ──
  [zmienne: scenariusz odcinka + polecenie]

Prefiks jest identyczny dla wszystkich odcinków, więc od drugiego odcinka
Bedrock czyta go z pamięci podręcznej za ok. 10% ceny (Sonnet 4.6: prefiks
≥ 1024 tokenów; Opus 4.6 / Haiku 4.5: ≥ 4096). Odpowiedź to gotowy
odcinek.json w schemacie ../odcinek-szablon.json, rozszerzony o `prompt_delta`
(dopisek do promptu bazowego), `kwestia_v3` (tekst z tagami ElevenLabs v3) i `napisy`.

Skrypt nie trzyma kluczy: boto3 bierze poświadczenia AWS z profilu/środowiska
(eu-central-1, jak aplikacja). Bez poświadczeń działa `--dry-run`: zapisuje
gotowe zlecenie (JSON) i szacuje tokeny oraz koszt z cache i bez.

Użycie:
  odcinek_json.py EP03 [--model eu.anthropic.claude-sonnet-4-6] [--dry-run] [-o odcinki/EP03.json]
  odcinek_json.py EP01 EP02 EP03 ...        kilka odcinków po kolei (cache grzeje się na pierwszym)

Wybór modelu (konto ma Bedrock do 4.6): Sonnet 4.6 (3/15 USD za 1M) do rozpisania
odcinka; Haiku 4.5 (1/5 USD) do samych napisów i opisów; Opus 4.6 (5/25 USD) tylko
jako kontrola continuity trudnych odcinków. Cache jest per model, więc jedna seria
odcinków = jeden model.
"""
import glob
import json
import os
import re
import sys
import time

TU = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TU, ".."))                      # docs/kampania-komputerku
REPO = os.path.abspath(os.path.join(ROOT, "..", ".."))
SEZON = os.path.join(REPO, "marketing", "komputerku", "sezon-1")
BIBLIA = os.path.join(SEZON, "01_KANON", "BIBLIA_INTRYGI.md")
SCENARIUSZE = os.path.join(SEZON, "02_SCENARIUSZE")
PROMPTY = os.path.join(ROOT, "pakiet", "05_biblia_produkcji", "PROMPTY_PRODUKCYJNE.md")
GLOSY = os.path.join(ROOT, "glosy.md")
SCENO = os.path.join(ROOT, "pakiet", "09_scenografia_v2", "scenografia.json")
POSTACIE = os.path.join(ROOT, "pakiet", "10_obsada_v2", "postacie")
SZABLON = os.path.join(ROOT, "odcinek-szablon.json")

REGION = os.getenv("AWS_REGION", "eu-central-1")
MODEL = os.getenv("ODCINEK_MODEL", "eu.anthropic.claude-sonnet-4-6")
MAX_WYJSCIE = 8000
# USD za 1M tokenów (wejście, wyjście); odczyt z cache 10%, zapis 125%.
CENY = [("claude-opus-4", 5.0, 25.0), ("claude-sonnet-4", 3.0, 15.0), ("claude-haiku-4", 1.0, 5.0),
        ("claude-sonnet-5", 2.0, 10.0), ("claude-opus-5-5", 4.0, 20.0), ("claude-haiku-5", 0.10, 0.50)]
_NOWA_GENERACJA = re.compile(r"claude-(opus-(4-7|4-8|5)|sonnet-5|fable-5|haiku-5)")

SYSTEM = (
    "Jestes producentem mikroserialu „Kancelaria pod Siodemka” (NotarAI). Dostajesz staly pakiet "
    "produkcyjny (biblia intrygi, prompty, obsada, kamery, schemat JSON) i scenariusz jednego odcinka. "
    "Rozpisujesz odcinek na ujecia do produkcji. Odpowiadasz WYLACZNIE poprawnym JSON (bez markdown, "
    "bez komentarza), zgodnym ze schematem i regulami z pakietu. Nie wymyslasz funkcji produktu, "
    "nazwisk ani dokumentow poza kanonem. Jezyk kwestii i napisow: polski. prompt_delta: po angielsku."
)

POLECENIE = """Rozpisz powyzszy scenariusz na odcinek.json.

Reguly:
1. Schemat jak w szablonie: seria, odcinek, tytul, funkcja_notarai, format_glowny "9x16", adaptacje, obsada_wersja "obsada-v2", scenografia_wersja "kancelaria-v2", warstwy, ujecia[].
2. Kazde ujecie ma: id (u1, u2, ...), typ (mowiace | bez_mowy | ekran | plansza), czas_s (liczba sekund; dla mowiace szacuj ok. 15 znakow/s, min. 3).
3. mowiace: postac (slug z obsady: helena, marta, basia, kuba; postacie goscinne jako "gosc:<imie>"), kadr (B_85mm dla zblizen do kamery, A_plan_ogolny lub C_przez_ramie dla ujec w planie), kamera (K1..K9 z listy), klatka_startowa (sciezka wzorcowa z kadrow postaci albo "DO_WYGENEROWANIA: <opis>"), kwestia (dokladnie ze scenariusza), kwestia_v3 (ta sama kwestia z tagami ElevenLabs v3 wg zasad z glosy.md, po polsku), emocja, ruch_kamery.
4. bez_mowy: kadr, kamera, klatka_startowa, czas_s (5 albo 10), prompt_delta.
5. ekran: zrodlo "nagranie app.notarai.pl, konto demo, dane testowe", czas_s, co_widac (funkcja z matrycy w scenariuszu; tylko stany rzeczywiscie uzyskiwalne w aplikacji).
6. prompt_delta (kazde ujecie generowane): maksymalnie 25 slow po angielsku, TYLKO to, co zmienia sie wzgledem stalego promptu bazowego (gest, rekwizyt, emocja, kadr). Nie powtarzaj opisu postaci, pokoju ani marki.
7. napisy: lista {od_s, do_s, tekst} dla calego odcinka, wiersze do 42 znakow, czasy spojne z czas_s ujec.
8. Dodaj "kontrola": lista zdan, ktore trzeba sprawdzic przed nagraniem (continuity, funkcje produktu, dane fikcyjne) - wylacznie z tresci scenariusza i biblii.
9. Zaden element nie moze sugerowac funkcji nieistniejacej w produkcie ani lamac kanonu (Pawel nie jest pelnomocnikiem; 640 000 zl; 56,40 m2; wydanie 15 stycznia).
Zwroc sam JSON."""


def czytaj(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


def prefiks_staly() -> str:
    """Identyczny dla kazdego odcinka - to on jest cache'owany."""
    sceno = json.load(open(SCENO, encoding="utf-8"))
    kamery = [{k: v for k, v in kam.items() if k in ("id", "nazwa", "opis", "ogniskowa", "obiektyw", "kadr", "cel")}
              for kam in sceno.get("kamery", [])]
    obsada = []
    for p in sorted(glob.glob(os.path.join(POSTACIE, "*", "postac.json"))):
        d = json.load(open(p, encoding="utf-8"))
        obsada.append({
            "slug": os.path.basename(os.path.dirname(p)),
            "imie": d.get("imie") or d.get("nazwa"),
            "rola": d.get("rola"),
            "wyglad": d.get("wyglad") or d.get("opis"),
            "kadry": [{"kamera": k.get("kamera"), "plik": k.get("plik"), "glowny": k.get("glowny")}
                      for k in d.get("kadry", []) if k.get("plik")],
            "glos": (d.get("glos") or {}).get("elevenlabs_voice_id"),
        })
    glosy = czytaj(GLOSY)
    # z glosy.md bierzemy tylko zasady tagowania (sekcja 3), nie historie testow
    m = re.search(r"(## 3\..*?)(?=\n## 4\.)", glosy, re.S)
    zasady_glosow = m.group(1) if m else glosy[:4000]
    czesci = [
        "=== BIBLIA INTRYGI (kanon, nie zmieniac) ===\n" + czytaj(BIBLIA),
        "=== PROMPTY PRODUKCYJNE (prompt bazowy, warianty kadrow, negatyw) ===\n" + czytaj(PROMPTY),
        "=== ZASADY TAGOWANIA KWESTII (ElevenLabs v3) ===\n" + zasady_glosow,
        "=== KAMERY (scenografia v2) ===\n" + json.dumps(kamery, ensure_ascii=False, indent=1),
        "=== OBSADA v2 ===\n" + json.dumps(obsada, ensure_ascii=False, indent=1),
        "=== SZABLON odcinek.json (schemat wyjscia; wartosci przykladowe) ===\n" + czytaj(SZABLON),
    ]
    return "\n\n".join(czesci)


def scenariusz(ep: str) -> tuple[str, str]:
    pliki = sorted(glob.glob(os.path.join(SCENARIUSZE, f"{ep.upper()}_*.md")))
    if not pliki:
        sys.exit(f"brak scenariusza {ep} w {SCENARIUSZE}")
    return pliki[0], czytaj(pliki[0])


def zlecenie(ep: str, model: str) -> dict:
    _, tekst = scenariusz(ep)
    tresc = [
        {"text": prefiks_staly()},
        {"cachePoint": {"type": "default"}},
        {"text": f"=== SCENARIUSZ {ep.upper()} ===\n{tekst}\n\n{POLECENIE}"},
    ]
    z = {
        "modelId": model,
        "system": [{"text": SYSTEM}],
        "messages": [{"role": "user", "content": tresc}],
        "inferenceConfig": {"maxTokens": MAX_WYJSCIE},
    }
    if not _NOWA_GENERACJA.search(model):
        z["inferenceConfig"]["temperature"] = 0
    return z


def tokeny(tekst: str) -> int:
    # Polski tekst: ok. 3 znaki na token (ostroznie); bez wywolania count_tokens.
    return int(len(tekst) / 3.0)


def ceny_modelu(model: str) -> tuple[float, float]:
    for fragment, we, wy in CENY:
        if fragment in model:
            return we, wy
    return 5.0, 25.0


def szacunek(z: dict, odcinkow: int = 8) -> str:
    staly = tokeny(z["messages"][0]["content"][0]["text"]) + tokeny(SYSTEM)
    zmienny = tokeny(z["messages"][0]["content"][2]["text"])
    wyjscie = 3500
    we, wy = ceny_modelu(z["modelId"])
    bez = ((staly + zmienny) * we + wyjscie * wy) / 1e6
    z_cache_1 = ((staly * 1.25 + zmienny) * we + wyjscie * wy) / 1e6           # pierwszy odcinek: zapis
    z_cache_n = ((staly * 0.10 + zmienny) * we + wyjscie * wy) / 1e6           # kolejne: odczyt
    seria_bez = bez * odcinkow
    seria_cache = z_cache_1 + z_cache_n * (odcinkow - 1)
    return (f"prefiks staly ≈ {staly:,} tok., zmienny ≈ {zmienny:,} tok., wyjscie ≈ {wyjscie:,} tok. ({z['modelId']})\n"
            f"koszt odcinka: bez cache {bez:.3f} USD; z cache {z_cache_n:.3f} USD (pierwszy {z_cache_1:.3f})\n"
            f"seria {odcinkow} odc.: bez cache {seria_bez:.2f} USD, z cache {seria_cache:.2f} USD\n"
            f"(sesja agentowa, ktora czyta to samo 10-30 razy: 1-10 USD za odcinek)")


def wywolaj(z: dict) -> tuple[dict, dict]:
    import boto3  # dopiero tu: --dry-run dziala bez boto3
    klient = boto3.client("bedrock-runtime", region_name=REGION)
    odp = klient.converse(**z)
    tekst = "".join(b.get("text", "") for b in odp["output"]["message"]["content"])
    tekst = re.sub(r"^```(?:json)?\s*|\s*```$", "", tekst.strip(), flags=re.M)
    poczatek, koniec = tekst.find("{"), tekst.rfind("}")
    dane = json.loads(tekst[poczatek:koniec + 1])
    return dane, odp.get("usage", {})


def sprawdz(dane: dict, ep: str) -> list[str]:
    uwagi = []
    for klucz in ("seria", "odcinek", "tytul", "ujecia", "napisy"):
        if klucz not in dane:
            uwagi.append(f"brak klucza {klucz}")
    for u in dane.get("ujecia", []):
        if u.get("typ") == "mowiace":
            if u.get("postac") not in ("helena", "marta", "basia", "kuba") and not str(u.get("postac", "")).startswith("gosc:"):
                uwagi.append(f"{u.get('id')}: nieznana postac {u.get('postac')}")
            if not u.get("kwestia"):
                uwagi.append(f"{u.get('id')}: brak kwestii")
        if u.get("typ") in ("mowiace", "bez_mowy") and len(str(u.get("prompt_delta", "")).split()) > 30:
            uwagi.append(f"{u.get('id')}: prompt_delta za dlugi")
    nr = re.sub(r"\D", "", ep)
    if nr and str(dane.get("odcinek")) != str(int(nr)):
        uwagi.append(f"numer odcinka {dane.get('odcinek')} != {int(nr)}")
    return uwagi


def main(a: list[str]) -> None:
    if not a:
        sys.exit(__doc__)
    model, dry, out, epki = MODEL, False, None, []
    i = 0
    while i < len(a):
        if a[i] == "--model":
            model = a[i + 1]; i += 2
        elif a[i] == "--dry-run":
            dry = True; i += 1
        elif a[i] == "-o":
            out = a[i + 1]; i += 2
        else:
            epki.append(a[i]); i += 1
    os.makedirs(os.path.join(ROOT, "odcinki"), exist_ok=True)
    for ep in epki:
        z = zlecenie(ep, model)
        cel = out or os.path.join(ROOT, "odcinki", f"{ep.upper()}.json")
        if dry:
            plik = os.path.join(ROOT, "odcinki", f"{ep.upper()}.zlecenie.json")
            json.dump(z, open(plik, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"[{ep}] zlecenie zapisane: {plik}\n{szacunek(z)}\n")
            continue
        start = time.time()
        dane, uzycie = wywolaj(z)
        uwagi = sprawdz(dane, ep)
        dane["_produkcja"] = {"model": model, "uzycie": uzycie, "uwagi": uwagi, "czas_s": round(time.time() - start, 1)}
        json.dump(dane, open(cel, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        we, wy = ceny_modelu(model)
        koszt = (uzycie.get("inputTokens", 0) * we + uzycie.get("cacheReadInputTokens", 0) * we * 0.1
                 + uzycie.get("cacheWriteInputTokens", 0) * we * 1.25 + uzycie.get("outputTokens", 0) * wy) / 1e6
        print(f"[{ep}] zapisano {cel}: {len(dane.get('ujecia', []))} ujec; tokeny: wejscie {uzycie.get('inputTokens')}, "
              f"cache odczyt {uzycie.get('cacheReadInputTokens')}, cache zapis {uzycie.get('cacheWriteInputTokens')}, "
              f"wyjscie {uzycie.get('outputTokens')}; koszt ≈ {koszt:.3f} USD")
        for u in uwagi:
            print(f"   UWAGA: {u}")


if __name__ == "__main__":
    main(sys.argv[1:])
