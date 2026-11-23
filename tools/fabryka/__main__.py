"""Wejście fabryki odcinków.

    python -m tools.fabryka stan                  # bufor, wielkość paczki, kolejne odcinki i sloty
    python -m tools.fabryka karta H23 --sezon 1   # szkic karty sprawy z SAOS (bez danych osobowych)
    python -m tools.fabryka scenariusz s01e09 --tylko-prompt   # prompt dla sesji Claude (domyślna droga)
    python -m tools.fabryka scenariusz s01e09 --waliduj plik.json   # scenariusz od Claude → bramka → zapis
    python -m tools.fabryka scenariusz s01e09     # opcjonalnie: Bedrock pisze sam (wymaga poświadczeń AWS)
    python -m tools.fabryka plan s01e09           # zlecenia: głosy, GPU (tor V6), montaż (finyou-render v2)
    python -m tools.fabryka publikuj s01e09 --akceptacja "…"   # wpis do kolejki; adresy wyniku domyślne
    python -m tools.fabryka dzien                 # cały dzienny przebieg bez kroków płatnych

Kroki płatne (GPU w Salad, ElevenLabs) fabryka tylko przygotowuje; uruchamia je dzienny przebieg
według docs/fabryka/README.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import karta as karty
from . import plan as planer
from . import publikacja, scenariusz, sloty, walidatory
from .wspolne import (GALEZ_SCENOGRAFIA, czas, czytaj_json, id_odcinka, katalog_kart, katalog_odcinkow,
                      teraz, zapisz_json)

PLANY = [f"s{i:02d}" for i in range(1, 11)]


def scenografia() -> dict:
    """opis.json każdego planu, który ma już render (gałąź scenografia/blender-v1)."""
    wynik = {}
    for kod in PLANY:
        d = czytaj_json(f"scenografia/rendery/{kod}/opis.json", GALEZ_SCENOGRAFIA)
        if d:
            wynik[kod] = d
    return wynik


def scenariusze(sezon: int | None = None) -> list[dict]:
    wynik = []
    for p in sorted(Path(katalog_odcinkow(1)).parent.parent.glob("sezon-*/odcinki/s??e??.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if sezon is None or int(d.get("sezon", 0)) == sezon:
            wynik.append(d)
    return wynik


def ostatni_numer(kolejka: dict) -> tuple[int, int] | None:
    # Z kolejki liczą się tylko odcinki z wideo: wpis zastępczy bez pliku (np. s01e01 z PR #95)
    # nie przesuwa numeracji, bo produkcja ruszyła od zera.
    ids = [o["id"] for o in kolejka.get("odcinki", []) if (o.get("pliki") or {}).get("wideo", "").startswith("https://")]
    ids += [s["id"] for s in scenariusze()]
    nums = sorted((int(m[1]), int(m[2])) for i in ids if (m := re.match(r"s(\d+)e(\d+)", i)))
    return nums[-1] if nums else None


def cmd_stan(a) -> dict:
    kol = publikacja.wczytaj()
    chwila = czas(a.teraz) if a.teraz else teraz()
    buf = sloty.bufor(kol, chwila)
    ile = sloty.wielkosc_paczki(buf)
    numery = sloty.nastepne_numery(ostatni_numer(kol), ile)
    plan = karty.plan_sezonu(1)
    wynik = {
        "teraz": chwila.isoformat(timespec="minutes"),
        "bufor": buf, "paczka": ile,
        "nastepne": [{"id": id_odcinka(s, e), "plan": plan.get(e) if s == 1 else None} for s, e in numery],
        "sloty": [d.isoformat(timespec="minutes") for d in sloty.wolne_sloty(kol, chwila, ile)],
        "plany_scenografii": sorted(scenografia()),
    }
    print(json.dumps(wynik, ensure_ascii=False, indent=1))
    return wynik


def _sciezka_karty(sezon: int, kid: str) -> Path:
    return katalog_kart(sezon) / f"KARTA_SPRAWY_{kid}.md"


def cmd_karta(a) -> Path | None:
    kat = karty.katalog()
    rek = kat.get(a.id)
    if not rek:
        print(f"{a.id}: brak w katalogu spraw", file=sys.stderr)
        return None
    p = _sciezka_karty(a.sezon, a.id)
    istniejace = list(katalog_kart(a.sezon).glob(f"KARTA_SPRAWY_{a.id}*.md"))
    if istniejace and not a.nadpisz:
        print(f"karta istnieje: {istniejace[0]}")
        return istniejace[0]
    saos = None
    if rek.saos_id:
        try:
            saos = karty.tekst_saos(rek.saos_id)
        except Exception as e:  # sieć, brak dostępu: karta bez fragmentów, decyzja zostaje konsultantowi
            print(f"{a.id}: SAOS niedostępny ({type(e).__name__}); karta bez fragmentów", file=sys.stderr)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(karty.szkic_karty(rek, saos), encoding="utf-8")
    print(f"zapisano {p}")
    return p


def _karta_tekst(sezon: int, kotwica: str) -> str | None:
    teksty = []
    for kid in karty.kotwice(kotwica):
        for p in katalog_kart(sezon).glob(f"KARTA_SPRAWY_{kid}*.md"):
            teksty.append(p.read_text(encoding="utf-8"))
    return "\n\n".join(teksty) or None


def cmd_scenariusz(a) -> dict | None:
    m = re.match(r"s(\d+)e(\d+)$", a.id)
    s, e = int(m[1]), int(m[2])
    plan = karty.plan_sezonu(s).get(e, {})
    kol = publikacja.wczytaj()
    poprz = [x for x in scenariusze(s) if int(x["odcinek"]) == e - 1]
    uzyte = {k for x in scenariusze(s) if x["id"] != a.id for k in karty.kotwice(x.get("sprawa_kotwica", ""))}
    numer = {"id": a.id, "sezon": s, "odcinek": e, "slot": plan.get("slot") or ("09:00" if e % 2 else "16:00")}
    sceno = scenografia()
    karta = _karta_tekst(s, plan.get("kotwica", ""))
    kontekst = {"uzyte_w_sezonie": uzyte, "poprzedni_typ_otwarcia": (poprz[0] if poprz else {}).get("typ_otwarcia")}
    if getattr(a, "waliduj", None):
        sc = json.loads(Path(a.waliduj).read_text(encoding="utf-8"))
        if sc.get("id") != a.id:
            raise SystemExit(f"plik ma id {sc.get('id')}, oczekiwano {a.id}")
        problemy = walidatory.sprawdz(sc, scenografia=sceno, **kontekst)
        sc["_fabryka"] = {"problemy": problemy, "autor": "sesja Claude", "zrodlo": str(a.waliduj)}
        out = zapisz_json(katalog_odcinkow(s) / f"{a.id}.json", sc)
        print(f"{'ODRZUCONY' if problemy else 'OK'} {out}")
        for p in problemy:
            print(f"  - {p}")
        if problemy:
            raise SystemExit(1)
        return sc
    if a.tylko_prompt:
        system, messages = scenariusz.prompt(numer, plan, karta, poprz[0] if poprz else None, sceno)
        out = katalog_odcinkow(s) / f"{a.id}.prompt.json"
        zapisz_json(out, {"system": system, "messages": messages})
        print(f"prompt zapisany: {out} (planów scenografii: {len(sceno)})")
        return None
    sc, problemy, zuzycie = scenariusz.napisz(numer, plan, karta, poprz[0] if poprz else None, sceno, kontekst)
    sc["_fabryka"] = {"problemy": problemy, "zuzycie": zuzycie, "model": scenariusz.MODEL}
    out = zapisz_json(katalog_odcinkow(s) / f"{a.id}.json", sc)
    print(f"{'ODRZUCONY' if problemy else 'OK'} {out}")
    for p in problemy:
        print(f"  - {p}")
    return sc


def cmd_plan(a) -> dict:
    m = re.match(r"s(\d+)e(\d+)$", a.id)
    sc = json.loads((katalog_odcinkow(int(m[1])) / f"{a.id}.json").read_text(encoding="utf-8"))
    problemy = walidatory.sprawdz(sc, scenografia=scenografia())
    if problemy:
        raise SystemExit(f"{a.id}: scenariusz nie przechodzi bramki: {problemy}")
    pliki = planer.zapisz_plan(sc, katalog_odcinkow(int(m[1])) / "zlecenia")
    print(json.dumps({k: str(v) for k, v in pliki.items()}, ensure_ascii=False, indent=1))
    return pliki


def cmd_publikuj(a) -> dict:
    m = re.match(r"s(\d+)e(\d+)$", a.id)
    sc = json.loads((katalog_odcinkow(int(m[1])) / f"{a.id}.json").read_text(encoding="utf-8"))
    kol = publikacja.wczytaj()
    domyslne = planer.url_wyniku(a.id)
    w = publikacja.dopisz(kol, sc, {"wideo": a.wideo or domyslne["wideo"], "plakat": a.plakat or domyslne["plakat"],
                                    "napisy": a.napisy},
                          a.czas or walidatory.dlugosc(sc), a.akceptacja, czas(a.teraz) if a.teraz else teraz())
    publikacja.zapisz(kol)
    print(json.dumps(w, ensure_ascii=False, indent=1))
    return w


def cmd_dzien(a) -> dict:
    """Dzienny przebieg bez kroków płatnych: stan → karty → scenariusze → bramka → zlecenia."""
    stan = cmd_stan(a)
    raport = {"stan": stan, "odcinki": []}
    for n in stan["nastepne"]:
        m = re.match(r"s(\d+)e(\d+)$", n["id"])
        s = int(m[1])
        for kid in karty.kotwice((n.get("plan") or {}).get("kotwica", "")):
            cmd_karta(argparse.Namespace(id=kid, sezon=s, nadpisz=False))
        sc = cmd_scenariusz(argparse.Namespace(id=n["id"], tylko_prompt=not a.bedrock, waliduj=None))
        wpis = {"id": n["id"], "scenariusz": None if sc is None else ("odrzucony" if sc["_fabryka"]["problemy"] else "ok")}
        if sc and not sc["_fabryka"]["problemy"]:
            wpis["zlecenia"] = {k: str(v) for k, v in cmd_plan(argparse.Namespace(id=n["id"])).items()}
        raport["odcinki"].append(wpis)
    out = zapisz_json(katalog_odcinkow(1).parent / "dziennik" / f"{teraz():%Y-%m-%d}.json", raport)
    print(f"raport dnia: {out}")
    return raport


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m tools.fabryka")
    sub = p.add_subparsers(dest="cmd", required=True)
    for nazwa in ("stan", "dzien"):
        x = sub.add_parser(nazwa)
        x.add_argument("--teraz", help="ISO, do testów i podglądu")
        if nazwa == "dzien":
            x.add_argument("--bedrock", action="store_true",
                           help="scenariusz przez Bedrock; domyślnie tylko prompty dla sesji Claude")
    x = sub.add_parser("karta"); x.add_argument("id"); x.add_argument("--sezon", type=int, default=1)
    x.add_argument("--nadpisz", action="store_true")
    x = sub.add_parser("scenariusz"); x.add_argument("id"); x.add_argument("--tylko-prompt", action="store_true")
    x.add_argument("--waliduj", metavar="PLIK", help="scenariusz JSON napisany w sesji Claude: tylko bramka i zapis")
    x = sub.add_parser("plan"); x.add_argument("id")
    x = sub.add_parser("publikuj"); x.add_argument("id")
    for k in ("wideo", "plakat", "napisy", "akceptacja", "teraz"):
        x.add_argument(f"--{k}")
    x.add_argument("--czas", type=float)
    a = p.parse_args(argv)
    {"stan": cmd_stan, "karta": cmd_karta, "scenariusz": cmd_scenariusz, "plan": cmd_plan,
     "publikuj": cmd_publikuj, "dzien": cmd_dzien}[a.cmd](a)


if __name__ == "__main__":
    main()
