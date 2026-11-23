"""Wpis gotowego odcinka do kolejki publikacji `serial/odcinki.json` (format z PR #95).

Odcinek trafia na koniec kolejki, w najbliższy wolny slot 09:00/16:00 po ostatnim zajętym.
Pliki wideo, plakatu i napisów to adresy https w magazynie w UE (nie pliki w gicie). Status
`gotowy` dostaje tylko odcinek z wideo i z akceptacją konsultanta; inaczej `w_produkcji`
(generator strony go pomija).
"""
from __future__ import annotations

from datetime import datetime

from . import sloty
from .walidatory import PLANSZA_KONCOWA
from .wspolne import GALEZ_SERIAL, KOLEJKA, KORZEN, czytaj_json, zapisz_json

SERIA = "Kancelaria pod Siódemką"


def wczytaj() -> dict:
    return czytaj_json(KOLEJKA, GALEZ_SERIAL) or {"seria": SERIA, "odcinki": []}


def wpis(sc: dict, publish_at: datetime, pliki: dict, czas_s: float, akceptacja: str | None) -> dict:
    for k in ("wideo", "plakat", "napisy"):
        v = pliki.get(k)
        if v and not str(v).startswith("https://"):
            raise ValueError(f"`{k}` musi być adresem https w magazynie w UE, nie plikiem w repo")
    gotowy = bool(pliki.get("wideo")) and bool((akceptacja or "").strip())
    return {
        "id": sc["id"],
        "sezon": int(sc["sezon"]),
        "odcinek": int(sc["odcinek"]),
        "tytul": sc["tytul"],
        "publish_at": publish_at.isoformat(timespec="seconds"),
        "opis": sc.get("opis_publikacji") or sc.get("streszczenie", ""),
        "kotwica": PLANSZA_KONCOWA,
        "pytanie": sc.get("pytanie_koncowe", ""),
        "pliki": {k: v for k, v in pliki.items() if v},
        "czas_s": round(float(czas_s)),
        "status": "gotowy" if gotowy else "w_produkcji",
        "akceptacja": akceptacja or None,
    }


def dopisz(kolejka: dict, sc: dict, pliki: dict, czas_s: float, akceptacja: str | None,
           teraz: datetime) -> dict:
    for o in list(kolejka.get("odcinki", [])):
        if o.get("id") == sc["id"]:
            if sloty.ma_wideo(o):
                raise ValueError(f"{sc['id']} już jest w kolejce z wideo")
            kolejka["odcinki"].remove(o)  # wpis zastępczy bez pliku zastępujemy prawdziwym
    slot = sloty.wolne_sloty(kolejka, teraz, 1)[0]
    w = wpis(sc, slot, pliki, czas_s, akceptacja)
    kolejka.setdefault("odcinki", []).append(w)
    kolejka["odcinki"].sort(key=lambda o: o["publish_at"])
    return w


def zapisz(kolejka: dict):
    return zapisz_json(KORZEN / KOLEJKA, kolejka)
