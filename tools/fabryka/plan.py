"""Scenariusz V6 → zlecenia produkcyjne: głosy (ElevenLabs v3+), GPU (ai-clip na Salad), montaż.

Kontrakty JSON są opisane w docs/fabryka/KONTRAKTY.md. Ten moduł niczego nie uruchamia i nic
nie kosztuje: tylko pisze pliki zleceń. Uruchomienie (płatne) robi dzienny przebieg według README.
"""
from __future__ import annotations

from pathlib import Path

from .walidatory import PLANSZA_KONCOWA

# ElevenLabs: tylko v3 lub nowszy (twarda reguła repozytorium, CLAUDE.md).
MODELE_GLOSU = ("eleven_v4", "eleven_v3")
DOZWOLONE_MODELE_GLOSU = {"eleven_v4", "eleven_v4_turbo", "eleven_v3", "eleven_v3_conversational"}

# Stałe głosy obsady v2 (docs/kampania-komputerku/glosy.md). Nowe postacie: Voice Design `eleven_ttv_v3`,
# potem wpis tutaj. Brak głosu = zlecenie nie powstaje (zamiast zastępczego głosu).
GLOSY = {
    "basia": "vqyfbWoOfYmPoa0QNkKB",
    "kuba": "l49KzmmcER7qYZfvh1NN",
    "marta": "rOIbi11t4PdzPrW90No0",
    "helena": "0YMlrD87k6Saqi6L1Joy",
}

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
            wejscia.append({"ujecie": u["id"], "postac": u["postac"], "voice_id": vid, "text": u["kwestia_v3"]})
        if wejscia:
            sceny.append({"scena": scena["id"], "inputs": wejscia})
    if brak:
        raise BladPlanu(f"brak stałego głosu dla: {sorted(brak)} (najpierw Voice Design eleven_ttv_v3 i wpis w GLOSY)")
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
        "wynik": f"audio/{sc['id']}/<ujecie>.mp3 (cięte po znacznikach czasu)",
    }


def gpu(sc: dict, seedy_mowa=(101,), seedy_niemy=(101, 202)) -> dict:
    """Zlecenie ai-clip: jedna paczka na wszystkie ujęcia generowane odcinka (InfiniteTalk + LTX-2.5).

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
            kam = u.get("kamera") or scena.get("kamera")
            wariant = scena.get("wariant", "dzien")
            tlo = render_planu(scena["plan"], kam, wariant)
            for seed in (seedy_mowa if t == "mowiace" else seedy_niemy):
                s = {
                    "slug": f"k-{sc['id']}-{u['id']}-s{seed}",
                    "seed": seed,
                    "track": "notarai",
                    "concept": f"komputerku-{sc['id']}-{u['id']}",
                    "tags": ["komputerku", sc["id"], u.get("postac") or "bez-postaci"],
                    # V6: klatka startowa = render planu z wstawioną postacią (krok „postać w planie”).
                    "tlo_planu": tlo,
                    "postac": u.get("postac"),
                    "znacznik": u.get("znacznik"),
                }
                if t == "mowiace":
                    s.update({"workflow": "infinitetalk.a2v", "audio": f"audio/{sc['id']}/{u['id']}.mp3",
                              "seconds": float(u["czas_s"]), "prompt": PROMPT_MOWY})
                else:
                    ruch = u.get("ruch_kamery")
                    s.update({"workflow": "ltx25.flf2v", "seconds": min(3.0, float(u["czas_s"])),
                              "prompt": (u.get("prompt_ruchu") or PROMPT_NIEMY),
                              "ruch": ruch if ruch in RUCHY else None})
                shots.append(s)
            if t == "bez_mowy" and float(u["czas_s"]) > 3:
                # Ujęcie nieme > 3 s: dwa elementy na wspólnej klatce (METODYKA), drugi dokleja montaż.
                shots[-1]["uwaga"] = "dluzsze niz 3 s: druga polowa jako osobny element na wspolnej klatce"
    return {
        "kontrakt": "gpu-v6",
        "opis": f"Komputerku {sc['id']} {sc['tytul']}: ujęcia generowane (jedna paczka GPU)",
        "defaults": {"width": 720, "height": 1280},
        "shots": shots,
    }


def montaz(sc: dict, adres_bazowy: str) -> dict:
    os_czasu = []
    t = 0.0
    for scena in sc["sceny"]:
        for u in scena.get("ujecia", []):
            d = float(u.get("czas_s") or 0)
            typ = u.get("typ")
            if typ in {"mowiace", "bez_mowy"}:
                zrodlo = {"typ": "gpu", "concept": f"komputerku-{sc['id']}-{u['id']}"}
            elif typ == "dokument":
                zrodlo = {"typ": "dokument", "szablon": (u.get("dokument") or {}).get("szablon"),
                          "pola": (u.get("dokument") or {}).get("pola", {}), "fokus": (u.get("dokument") or {}).get("fokus")}
            elif typ == "ekran":
                zrodlo = {"typ": "ekran", "funkcja": u["ekran"]["funkcja"], "nagranie": f"ekrany/{sc['id']}/{u['id']}.mp4"}
            else:
                zrodlo = {"typ": "plansza", "tekst": u.get("tekst", "")}
            os_czasu.append({"ujecie": u["id"], "od_s": round(t, 2), "do_s": round(t + d, 2), "zrodlo": zrodlo,
                             "kwestia": u.get("kwestia"), "reakcja_po_s": 0.7 if u.get("zart") else 0})
            t += d
    return {
        "kontrakt": "montaz-v6",
        "odcinek": sc["id"],
        "formaty": ["9x16", "16x9"],
        "os_czasu": os_czasu,
        "napisy": "z kwestii i czasów głosu (bez ironii, bez tekstu na planszach poza tytułem i końcową)",
        "dzwiek": {"podklad": "pokoj_" + (sc["sceny"][1].get("wariant", "dzien") if len(sc["sceny"]) > 1 else "dzien"),
                   "muzyka": (sc.get("muzyka") or {}).get("typ", "brak"),
                   "kontrola": "dzwiek.mjs kontrola: poza mową <= -45 dB"},
        "znaczek_ai": True,
        "plansza_tytulowa": {"tekst": sc["tytul"], "znak_dzwiekowy": "komputerku-v1", "czas_s": 1.5},
        "plansza_koncowa": PLANSZA_KONCOWA,
        "cel": f"{adres_bazowy.rstrip('/')}/{sc['id']}/",
        "wynik": [f"{sc['id']}.mp4", f"{sc['id']}-16x9.mp4", f"{sc['id']}.jpg", f"{sc['id']}.vtt"],
    }


def zapisz_plan(sc: dict, katalog: Path, adres_bazowy: str) -> dict[str, Path]:
    from .wspolne import zapisz_json
    k = katalog / sc["id"]
    return {
        "glosy": zapisz_json(k / "glosy.json", glosy(sc)),
        "gpu": zapisz_json(k / "gpu.json", gpu(sc)),
        "montaz": zapisz_json(k / "montaz.json", montaz(sc, adres_bazowy)),
    }
