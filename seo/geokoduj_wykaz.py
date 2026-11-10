"""Wsadowe polozenie kancelarii z publicznego wykazu -> seo/polozenia.json.

Dzieki temu mapa /notariusze pokazuje WSZYSTKIE kancelarie z wykazu, a nie
tylko korzystajace z notarai (docs/rekomendacje-notariuszy.md).

  python seo/geokoduj_wykaz.py --limit 200     # porcja, mozna przerwac i wznowic
  python seo/geokoduj_wykaz.py --ponow-bledy   # jeszcze raz adresy, ktorych nie znaleziono

Geokoder jak w notariusze.py (PIECZAPP_GEOKODER; domyslnie Nominatim, najwyzej
1 zapytanie/s, czyli ok. godziny na caly wykaz). Wysylamy wylacznie publiczny
adres kancelarii. Postep zapisujemy co 20 adresow, wiec przerwanie nic nie psuje.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import notariusze  # noqa: E402

BAZA = Path(__file__).resolve().parent / "kancelarie.json"


def wczytaj(plik: Path) -> dict:
    return json.loads(plik.read_text("utf-8")) if plik.exists() else {"polozenia": {}}


def zapisz(plik: Path, dane: dict) -> None:
    dane["zaktualizowano"] = datetime.now().isoformat(timespec="seconds")
    tmp = plik.with_suffix(".tmp")
    tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=0, sort_keys=True), "utf-8")
    tmp.replace(plik)


def uruchom(limit: int | None = None, ponow_bledy: bool = False, baza: Path = BAZA,
            cel: Path | None = None, wypisz=print) -> dict:
    cel = cel or notariusze.PLIK_POLOZEN
    kancelarie = json.loads(baza.read_text("utf-8"))["kancelarie"]
    dane = wczytaj(cel)
    poz = dane.setdefault("polozenia", {})
    wynik = {"ustalono": 0, "nieznane": 0, "bledy_sieci": 0, "pominiete": 0}
    zrobione = 0
    for k in kancelarie:
        adres = (k.get("adres") or "").strip()
        stare = poz.get(str(k["id"]))
        if not adres or (stare and stare.get("adres") == adres and (stare.get("lat") is not None or not ponow_bledy)):
            wynik["pominiete"] += 1
            continue
        if limit is not None and zrobione >= limit:
            break
        zrobione += 1
        try:
            znalezione = notariusze.geokoduj(adres)
        except Exception as blad:  # noqa: BLE001 - siec: sprobujemy przy nastepnym uruchomieniu
            wynik["bledy_sieci"] += 1
            wypisz(f"{k['id']}: geokoder niedostepny ({type(blad).__name__})")
            continue
        if znalezione:
            poz[str(k["id"])] = {"adres": adres, **znalezione}
            wynik["ustalono"] += 1
        else:
            poz[str(k["id"])] = {"adres": adres, "lat": None, "blad": "adres nieznany geokoderowi"}
            wynik["nieznane"] += 1
        if zrobione % 20 == 0:
            zapisz(cel, dane)
            wypisz(f"... {zrobione} adresow, {wynik['ustalono']} ustalono")
    zapisz(cel, dane)
    wynik["na_mapie"] = sum(1 for v in poz.values() if v.get("lat") is not None)
    wynik["w_wykazie"] = len(kancelarie)
    return wynik


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--limit", type=int, default=None)
    a.add_argument("--ponow-bledy", action="store_true")
    argumenty = a.parse_args()
    if not notariusze.wlaczone():
        sys.exit("Geokoder wylaczony (PIECZAPP_GEOKODER).")
    print(uruchom(argumenty.limit, argumenty.ponow_bledy))
