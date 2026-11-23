"""Scenariusz V6 → zlecenia produkcyjne: głosy (ElevenLabs v3+), GPU (ai-clip na Salad), montaż (Cloudflare v2).

Kontrakty JSON są opisane w docs/fabryka/KONTRAKTY.md. Ten moduł niczego nie uruchamia i nic
nie kosztuje: tylko pisze pliki zleceń. Uruchomienie (płatne) robi dzienny przebieg według README.
"""
from __future__ import annotations

import json
from pathlib import Path

from .walidatory import PLANSZA_KONCOWA

# ElevenLabs: tylko v3 lub nowszy (twarda reguła repozytorium, CLAUDE.md).
MODELE_GLOSU = ("eleven_v4", "eleven_v3")
DOZWOLONE_MODELE_GLOSU = {"eleven_v4", "eleven_v4_turbo", "eleven_v3", "eleven_v3_conversational"}

# Obsada (głosy i karty postaci) w jednym pliku czytanym przez fabrykę.
OBSADA = json.loads((Path(__file__).with_name("obsada.json")).read_text(encoding="utf-8"))
GLOSY = {k: v["voice_id"] for k, v in OBSADA["postacie"].items() if v.get("voice_id")}

# Magazyn mediów w UE: Supabase „Finance you produkcja” (eu-central-1), publiczny bucket studio-media.
# Montaż v2 (finyou-render, odcinek-cf.mjs) zapisuje wynik w studio-media/rolki/serial/<id>/.
SUPABASE = "https://vkzndnaoxhdxrxlpntcb.supabase.co"
PUBLICZNE = f"{SUPABASE}/storage/v1/object/public/studio-media"
MONTAZ_URL = "https://finyou-render.financeyou.workers.dev/zadanie"

# Prompt ruchu dla mowy (InfiniteTalk) i ujęć niemych (LTX-2.5): opisuje ruch, nie kadr (METODYKA).
PROMPT_MOWY = (
    "A person in a notary office speaks calmly and quietly, like a documentary scene. Neutral composed face, "
    "relaxed closed lips between words, the mouth and jaw move only with the speech. The head stays still with "
    "only slow subtle movements. Small natural blinks. Static locked-off camera. Nothing else in the room moves."
)
PROMPT_NIEMY = "Locked-off camera, no camera movement. Nothing else in the room moves. Quiet office room tone."
RUCHY = {"najazd", "odjazd", "w-lewo", "w-prawo", "w-gore", "w-dol"}


class BladPlanu(ValueError):
    pass


def sprawdz_model_glosu(model: str) -> str:
    if model not in DOZWOLONE_MODELE_GLOSU:
        raise BladPlanu(f"model głosu `{model}` jest niedozwolony (tylko v3 lub nowszy); przerwano")
    return model


def render_planu(plan: str, kamera: str, wariant: str) -> str:
    """Ścieżka renderu planu z Blendera (gałąź scenografia/blender-v1)."""
    return f"scenografia/rendery/{plan}/{kamera}_{wariant}.jpg"


def url_audio(odcinek: str, ujecie: str) -> str:
    return f"{PUBLICZNE}/notarai/serial/{odcinek}/audio/{ujecie}.mp3"


def url_klipu(odcinek: str, ujecie: str) -> str:
    """Zaakceptowany klip GPU po wyborze ziarna, odłożony pod stałą nazwą ujęcia."""
    return f"{PUBLICZNE}/notarai/serial/{odcinek}/klipy/{ujecie}.mp4"


def url_warstwy(odcinek: str, ujecie: str, rozszerzenie: str) -> str:
    """Dokument (PNG z dokumenty.py) albo nagranie ekranu aplikacji (MP4)."""
    return f"{PUBLICZNE}/notarai/serial/{odcinek}/warstwy/{ujecie}.{rozszerzenie}"


def url_wyniku(odcinek: str) -> dict:
    baza = f"{PUBLICZNE}/rolki/serial/{odcinek}/{odcinek}"
    return {"wideo": f"{baza}.mp4", "wideo_16x9": f"{baza}-16x9.mp4", "plakat": f"{baza}.jpg",
            "napisy_json": f"{baza}-napisy.json"}


def glosy(sc: dict, model: str = MODELE_GLOSU[0]) -> dict:
    sprawdz_model_glosu(model)
    sceny = []
    brak = set()
    for scena in sc["sceny"]:
        wejscia = []
        for u in scena.get("ujecia", []):
            if u.get("typ") != "mowiace":
                continue
            vid = GLOSY.get(u["postac"])
            if not vid:
                brak.add(u["postac"])
                continue
            wejscia.append({"ujecie": u["id"], "postac": u["postac"], "voice_id": vid, "text": u["kwestia_v3"],
                            "wynik": url_audio(sc["id"], u["id"])})
        if wejscia:
            sceny.append({"scena": scena["id"], "inputs": wejscia})
    if brak:
        raise BladPlanu(f"brak stałego głosu dla: {sorted(brak)} (Voice Design eleven_ttv_v3 i wpis w obsada.json)")
    return {
        "kontrakt": "glosy-v1",
        "odcinek": sc["id"],
        "model_id": model,
        "model_zapasowy": MODELE_GLOSU[1],
        "language_code": "pl",
        "settings": {"stability": 0.5},
        "seed": int(sc["odcinek"]) * 101,
        "tryb": "text-to-dialogue",
        "sceny": sceny,
    }


# ------------------------------------------------------------------- PUNKT STYKU: tor GPU V6
def adapter_gpu_v6(sc: dict, u: dict, scena: dict, seed: int) -> list[dict]:
    """Jedno ujęcie scenariusza → ujęcia zlecenia ai-clip dla toru V6 (finyou `kampania/tor-gpu-v6`).

    PUNKT STYKU. Fabryka nie zna szczegółów toru GPU; buduje tylko łańcuch opisany w commicie
    daf226fe tamtej gałęzi: najpierw klatka „postać w planie” (`qwenedit.postac`: kadr z Blendera
    + karta postaci → klatka), potem ruch albo mowa z polem `image: "@<slug klatki>"`. Gdy tor V6
    zmieni nazwy pól, zmienia się wyłącznie ta funkcja (test: tests/test_fabryka.py).
    """
    baza = f"k-{sc['id']}-{u['id']}"
    kam = u.get("kamera") or scena.get("kamera")
    tlo = render_planu(scena["plan"], kam, scena.get("wariant", "dzien"))
    wspolne = {"track": "notarai", "seed": seed, "concept": f"komputerku-{sc['id']}-{u['id']}",
               "tags": ["komputerku", sc["id"], u.get("postac") or "bez-postaci"]}
    wynik = []
    start = tlo
    if u.get("postac"):
        postac = OBSADA["postacie"].get(u["postac"], {})
        klatka = {
            **wspolne, "slug": f"{baza}-klatka-s{seed}", "workflow": "qwenedit.postac",
            "image": tlo, "image_ref": postac.get("karta"),  # karta postaci: do uzupełnienia w obsada.json
            "who": postac.get("kto"), "pose": u.get("poza") or "sitting calmly at the table",
            "mark": {"nazwa": u.get("znacznik")},  # px dokłada tor V6 z opis.json → znaczniki_w_kadrze_px
        }
        wynik.append(klatka)
        start = "@" + klatka["slug"]
    if u.get("typ") == "mowiace":
        wynik.append({**wspolne, "slug": f"{baza}-s{seed}", "workflow": "infinitetalk.a2v", "image": start,
                      "audio": url_audio(sc["id"], u["id"]), "seconds": float(u["czas_s"]), "prompt": PROMPT_MOWY})
    else:
        ruch = u.get("ruch_kamery")
        wynik.append({**wspolne, "slug": f"{baza}-s{seed}", "workflow": "ltx25.flf2v", "image": start,
                      "image_last": start, "seconds": min(3.0, float(u["czas_s"])),
                      "prompt": u.get("prompt_ruchu") or PROMPT_NIEMY, "ruch": ruch if ruch in RUCHY else None})
    return wynik


def gpu(sc: dict, seedy_mowa=(101,), seedy_niemy=(101, 202)) -> dict:
    """Zlecenie ai-clip: jedna paczka (jedno wynajęcie) na wszystkie ujęcia generowane odcinka.

    Koszt (dzienniki wydatków 18–22.11): ujęcie mówione InfiniteTalk to ok. 5 min RTX 5090, czyli
    ok. 0,05 USD; ujęcie nieme LTX 3 s ok. 0,005 USD. Dlatego mowa idzie w jednym ziarnie (odrzut =
    poprawka tylko tego ujęcia), a tanie ujęcia nieme w dwóch ziarnach do wyboru.
    """
    shots = []
    for scena in sc["sceny"]:
        for u in scena.get("ujecia", []):
            t = u.get("typ")
            if t not in {"mowiace", "bez_mowy"}:
                continue
            for seed in (seedy_mowa if t == "mowiace" else seedy_niemy):
                shots += adapter_gpu_v6(sc, u, scena, seed)
    return {
        "kontrakt": "gpu-v6",
        "opis": f"Komputerku {sc['id']} {sc['tytul']}: ujęcia generowane (jedna paczka GPU)",
        "defaults": {"width": 720, "height": 1280},
        "shots": shots,
    }


# ------------------------------------------------------------------- montaż: odcinek-cf.mjs (v2)
def montaz(sc: dict) -> dict:
    """Zlecenie `{"odcinek": …}` dla finyou-render v2 (services/ai-clip/rolki/odcinek-cf.mjs).

    Ujęcia: `klip` (zaakceptowany klip GPU albo nagranie ekranu; dźwięk klipu wyłączony), `obraz`
    (dokument z dokumenty.py, powolny najazd na fokus), `kolor` (plansza tytułowa z napisem).
    Głosy jako `nagranie` z czasem startu; napisy z kwestii; plansza końcowa i znaczek AI w montażu.
    """
    ujecia, glosy_, napisy = [], [], []
    t = 0.0
    for scena in sc["sceny"]:
        if scena.get("rola") == "plansza_koncowa":
            continue  # plansza końcowa jest częścią montażu v2
        for u in scena.get("ujecia", []):
            d = round(float(u.get("czas_s") or 0), 2)
            typ = u.get("typ")
            if typ in {"mowiace", "bez_mowy"}:
                ujecia.append({"typ": "klip", "url": url_klipu(sc["id"], u["id"]), "od": 0, "do": d, "dzwiek": "brak"})
            elif typ == "ekran":
                ujecia.append({"typ": "klip", "url": url_warstwy(sc["id"], u["id"], "mp4"), "od": 0, "do": d,
                               "dzwiek": "brak"})
            elif typ == "dokument":
                fokus = (u.get("dokument") or {}).get("fokus_xy") or [0.5, 0.5]
                ujecia.append({"typ": "obraz", "url": url_warstwy(sc["id"], u["id"], "png"), "czas": d, "fokus": fokus})
            else:  # plansza tytułowa
                ujecia.append({"typ": "kolor", "kolor": "#071D49", "czas": d})
                if u.get("tekst"):
                    napisy.append({"od": round(t, 2), "do": round(t + d, 2), "tekst": u["tekst"][:160]})
            if typ == "mowiace":
                glosy_.append({"typ": "nagranie", "url": url_audio(sc["id"], u["id"]), "start": round(t, 2)})
                napisy.append({"od": round(t, 2), "do": round(t + d, 2), "tekst": u["kwestia"][:160]})
            t += d
    return {
        "kontrakt": "odcinek-cf",
        "adres": MONTAZ_URL,
        "odcinek": {
            "id": sc["id"],
            "cel": f"rolki/serial/{sc['id']}",
            "ujecia": ujecia,
            "glosy": glosy_,
            "napisy": napisy,
            "tlo": {"url": f"{PUBLICZNE}/notarai/serial/podklad/pokoj_dzien.mp3"},
            "plansza_koncowa": {"tekst": PLANSZA_KONCOWA, "czas": 3},
            "znaczek_ai": True,
            "plakat_s": 1,
            "wersja_16x9": True,
        },
        "wynik": url_wyniku(sc["id"]),
    }


def zapisz_plan(sc: dict, katalog: Path) -> dict[str, Path]:
    from .wspolne import zapisz_json
    k = katalog / sc["id"]
    return {
        "glosy": zapisz_json(k / "glosy.json", glosy(sc)),
        "gpu": zapisz_json(k / "gpu.json", gpu(sc)),
        "montaz": zapisz_json(k / "montaz.json", montaz(sc)),
    }
