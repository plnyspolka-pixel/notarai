"""Symulacja tokenomii: czy cennik trzyma narzut >= 100% i ile zarabia kancelaria.

Uruchomienie:  python scripts/symulacja_tokenomii.py
(bez AWS, bez sieci - same liczby z tokenomia.py)

Co robi:
1. Losuje sprawy (liczba stron, dokladnosc, tury rozmowy z rosnacym kontekstem,
   dlugosc wzoru, ksiegi EKW, formularze) i dla kazdej akcji losuje tokeny
   z rozkladu log-normalnego o P50/P90 z profilu akcji.
2. Liczy koszt i przychod sprawy w trzech wersjach cennika:
     v0  "naiwny"  - 2 x koszt typowy (P50), stala cena tury i projektu,
     v1  "twardy"  - 2 x P90 przy najnizszej cenie kredytu,
     v2  "obecny"  - tokenomia.py (P90 przy cenie katalogowej i srednia przy
                     najnizszej cenie; tura i projekt skaluja sie z dlugoscia).
3. Sprawdza ekonomie trzech modeli biznesowych dla trzech profili kancelarii.
"""
from __future__ import annotations

import math
import os
import random
import statistics
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tokenomia as t  # noqa: E402

Z90 = 1.2816


def _los(p50: float, p90: float, gen: random.Random) -> float:
    if p50 <= 0:
        return 0.0
    sigma = math.log(max(p90, p50) / p50) / Z90
    return p50 * math.exp(gen.gauss(0, sigma))


def koszt_losowy(kod: str, gen: random.Random, skala_we: float = 1.0, skala_wy: float = 1.0) -> float:
    """Jedno wykonanie akcji: koszt w zl, z bledami (ponowienia ~8% wywolan)."""
    a = t.AKCJE[kod]
    we50, wy50, we90, wy90 = a.profil
    we = _los(we50 * skala_we, we90 * skala_we, gen)
    wy = _los(wy50 * skala_wy, wy90 * skala_wy, gen)
    koszt = t.koszt_tokenow_zl(a.model or t.MODEL_GLOWNY, int(we), int(wy))
    if gen.random() < 0.08:           # nieudana proba - placimy za nia drugi raz
        koszt *= 2
    return koszt + a.koszt_zewnetrzny_zl


@dataclass
class Sprawa:
    stron: int
    wysilek: str
    tury: int
    znakow_wzoru: int
    ksiag: int
    formularzy: int


def losuj_sprawe(gen: random.Random) -> Sprawa:
    """Rozklad z praktyki kancelarii: wiekszosc spraw 5-25 stron, czasem
    duze sprawy (deweloperskie, spadkowe) po 100+ stron."""
    stron = max(1, int(gen.lognormvariate(math.log(14), 0.75)))
    wysilek = gen.choices(["max", "high", "medium"], [0.6, 0.25, 0.15])[0]
    tury = min(40, int(gen.expovariate(1 / 4)))
    znakow = int(gen.lognormvariate(math.log(22_000), 0.5))
    return Sprawa(stron, wysilek, tury, znakow, gen.choices([0, 1, 2, 4], [0.4, 0.4, 0.15, 0.05])[0],
                  gen.choices([0, 1, 2], [0.7, 0.2, 0.1])[0])


def koszt_sprawy(s: Sprawa, gen: random.Random) -> float:
    koszt = sum(koszt_losowy(t.akcja_odczytu(s.wysilek), gen) for _ in range(s.stron))
    # Zestawienie czyta transkrypcje wszystkich stron (ok. 2 tys. tokenow na strone).
    koszt += koszt_losowy("zalozenie_sprawy", gen, skala_we=1 + s.stron * 2_000 / 14_000)
    kontekst = 14_000 + s.stron * 600
    for _ in range(s.tury):
        koszt += koszt_losowy("rozmowa_tura", gen, skala_we=kontekst / 14_000)
        kontekst += 2_000
    koszt += koszt_losowy("projekt", gen, skala_we=max(1, s.znakow_wzoru / 40_000),
                          skala_wy=max(1, s.znakow_wzoru / 40_000))
    koszt += sum(koszt_losowy("ekw_ksiega", gen) for _ in range(s.ksiag))
    koszt += sum(koszt_losowy("formularz", gen) for _ in range(s.formularzy))
    return koszt


def kredyty_sprawy(s: Sprawa, wersja: str) -> float:
    """Kredyty pobrane za sprawe w danej wersji cennika."""
    def cena(kod: str) -> float:
        a = t.AKCJE[kod]
        if wersja == "v0":
            return max(t.KROK_KREDYTU, math.ceil(2 * a.koszt_zl(50) / t.KROK_KREDYTU) * t.KROK_KREDYTU)
        if wersja == "v1":
            return max(t.KROK_KREDYTU, math.ceil(2 * a.koszt_zl(90) / 0.70 / t.KROK_KREDYTU)
                       * t.KROK_KREDYTU)
        return a.kredyty()

    kredyty = cena(t.akcja_odczytu(s.wysilek)) * s.stron + cena("zalozenie_sprawy")
    znakow_kontekstu = (14_000 + s.stron * 600) * t.ZNAKOW_NA_TOKEN
    for _ in range(s.tury):
        kredyty += cena("rozmowa_tura") * (1 if wersja == "v0" else t.jednostki_rozmowy(znakow_kontekstu))
        znakow_kontekstu += 2_000 * t.ZNAKOW_NA_TOKEN
    kredyty += cena("projekt")
    if wersja != "v0":
        kredyty += cena("projekt_dodatek") * t.jednostki_projektu(s.znakow_wzoru)
    kredyty += cena("ekw_ksiega") * s.ksiag + cena("formularz") * s.formularzy
    return kredyty


def symuluj(n: int = 20_000, ziarno: int = 7) -> dict:
    gen = random.Random(ziarno)
    wyniki = {w: {"narzut_tani": [], "narzut_katalog": [], "kredyty": []} for w in ("v0", "v1", "v2")}
    koszty = []
    for _ in range(n):
        s = losuj_sprawe(gen)
        koszt = koszt_sprawy(s, gen)
        koszty.append(koszt)
        for w in wyniki:
            kr = kredyty_sprawy(s, w)
            wyniki[w]["kredyty"].append(kr)
            wyniki[w]["narzut_tani"].append(kr * t.NAJNIZSZA_CENA_KREDYTU_ZL / koszt - 1)
            wyniki[w]["narzut_katalog"].append(kr * t.CENA_KREDYTU_ZL / koszt - 1)
    raport = {"spraw": n, "koszt_sredni_zl": statistics.mean(koszty),
              "koszt_p90_zl": sorted(koszty)[int(0.9 * n)]}
    for w, d in wyniki.items():
        tani = d["narzut_tani"]
        raport[w] = {
            "kredyty_srednio": statistics.mean(d["kredyty"]),
            "kredyty_mediana": statistics.median(d["kredyty"]),
            "narzut_portfela_tani": sum(d["kredyty"]) * t.NAJNIZSZA_CENA_KREDYTU_ZL / sum(koszty) - 1,
            "narzut_portfela_katalog": sum(d["kredyty"]) * t.CENA_KREDYTU_ZL / sum(koszty) - 1,
            "spraw_ponizej_100_tani": sum(1 for x in tani if x < 1.0) / n,
            "spraw_ponizej_100_katalog": sum(1 for x in d["narzut_katalog"] if x < 1.0) / n,
            "spraw_ze_strata_tani": sum(1 for x in tani if x < 0) / n,
            "narzut_p5_tani": sorted(tani)[int(0.05 * n)],
        }
    return raport


# --- ekonomia przedsiewziecia ---------------------------------------------------------

# Koszt staly platformy (zl/mies.): 2 x Fargate 1 vCPU/2 GB, ALB, CloudWatch,
# Secrets Manager, Cognito, S3, domena, kopia zapasowa. Szacunek z infra/*.yaml.
KOSZT_STALY_ZL = float(os.getenv("SYM_KOSZT_STALY_ZL", "550"))
# Stripe: karta EU 1.5% + 1 zl, Billing 0.7%, Tax 0.5% (od subskrypcji).
STRIPE_PROCENT = 0.027
STRIPE_STALA_ZL = 1.0
# Wsparcie i utrzymanie per kancelaria (zl/mies., czas czlowieka) - konserwatywnie.
WSPARCIE_ZL = 60.0

# Model C: oplata za sprawe, w cenie do 40 stron i 10 tur rozmowy.
OPLATA_C_PLATFORMA = 149
OPLATA_C_ZA_SPRAWE = 49
LIMIT_C_STRON = 40
LIMIT_C_TUR = 10


def nadwyzka_kredytow(s: Sprawa) -> float:
    """Kredyty ponad limit sprawy w modelu C (po cenach v2)."""
    strony = max(0, s.stron - LIMIT_C_STRON) * t.AKCJE[t.akcja_odczytu(s.wysilek)].kredyty()
    tury = max(0, s.tury - LIMIT_C_TUR) * t.AKCJE["rozmowa_tura"].kredyty() * 2
    return strony + tury + t.AKCJE["projekt_dodatek"].kredyty() * t.jednostki_projektu(s.znakow_wzoru)


PROFILE = {
    # spraw z AI miesiecznie
    "mala": 25,
    "srednia": 70,
    "duza": 180,
}


# Plany abonamentowe z wersji cennika sprzed 13.11.2026 - tylko do porownania
# (model A). W aplikacji obowiazuja wylacznie pakiety kredytow (model B).
PLANY_HISTORYCZNE: dict[str, dict] = {
    "start": {"nazwa": "Start", "cena_zl": 290, "pula": 300},
    "kancelaria": {"nazwa": "Kancelaria", "cena_zl": 600, "pula": 700},
    "pro": {"nazwa": "Pro", "cena_zl": 1500, "pula": 1875},
    "pro_plus": {"nazwa": "Kancelaria+", "cena_zl": 3600, "pula": 4500},
}


def _dokup(brak: float) -> float:
    """Najtanszy pasujacy zestaw pakietow na brakujace kredyty."""
    dokup = 0.0
    while brak > 0:
        pak = t.PAKIETY["2000"] if brak > 900 else t.PAKIETY["500"] if brak > 100 else t.PAKIETY["100"]
        dokup += pak["cena_zl"]
        brak -= pak["kredyty"]
    return dokup


def ekonomia_modeli(ziarno: int = 11) -> dict:
    """Miesieczny wynik na jednej kancelarii w trzech modelach biznesowych."""
    gen = random.Random(ziarno)
    proba = [losuj_sprawe(gen) for _ in range(3000)]
    koszt_sprawy_sr = statistics.mean(koszt_sprawy(s, gen) for s in proba)
    kredyty_sprawy_sr = statistics.mean(kredyty_sprawy(s, "v2") for s in proba)
    wynik = {"koszt_sprawy_zl": round(koszt_sprawy_sr, 2), "kredyty_sprawy": round(kredyty_sprawy_sr, 1),
             "modele": {}}

    for profil, spraw in PROFILE.items():
        cogs = spraw * koszt_sprawy_sr
        potrzeba_kr = spraw * kredyty_sprawy_sr

        # A. Abonament z pula + dokupowanie pakietow; kancelaria wybiera
        # najtanszy dla siebie plan (tak zachowa sie racjonalny klient).
        def koszt_planu(p: dict) -> float:
            return p["cena_zl"] + _dokup(max(0.0, potrzeba_kr - p["pula"]))
        plan = min(PLANY_HISTORYCZNE, key=lambda k: koszt_planu(PLANY_HISTORYCZNE[k]))
        przychod_a = koszt_planu(PLANY_HISTORYCZNE[plan])
        wynik.setdefault("plan_wybrany", {})[profil] = plan
        # B. Tylko pakiety (pay-as-you-go), bez abonamentu - model obowiazujacy.
        # Kancelaria kupuje najtanszy zestaw pakietow na swoje zuzycie.
        przychod_b = _dokup(potrzeba_kr)
        # C. Oplata za sprawe (akt) z limitem w cenie + oplata platformowa.
        # Ponad limit (stron, tur) dolicza sie kredyty po cenie katalogowej.
        nadwyzka = statistics.mean(nadwyzka_kredytow(s) for s in proba) * t.CENA_KREDYTU_ZL
        przychod_c = OPLATA_C_PLATFORMA + spraw * (OPLATA_C_ZA_SPRAWE + nadwyzka)

        modele = {}
        for nazwa, przychod in (("A_abonament_z_pula", przychod_a), ("B_pakiety", przychod_b),
                                ("C_oplata_za_akt", przychod_c)):
            stripe = przychod * STRIPE_PROCENT + STRIPE_STALA_ZL
            marza_brutto = przychod - cogs - stripe
            modele[nazwa] = {
                "przychod_zl": round(przychod, 0), "koszt_ai_zl": round(cogs, 0),
                "narzut_na_koszcie_ai": round(przychod / cogs - 1, 2) if cogs else None,
                "marza_po_ai_i_stripe_zl": round(marza_brutto, 0),
                "marza_po_wsparciu_zl": round(marza_brutto - WSPARCIE_ZL, 0),
                "cena_za_sprawe_zl": round(przychod / spraw, 1),
            }
        wynik["modele"][f"{profil} ({spraw} spraw/mies.)"] = modele
    # Prog rentownosci kosztow stalych przy modelu B (obowiazujacym), kancelaria srednia.
    srednia = wynik["modele"][f"srednia ({PROFILE['srednia']} spraw/mies.)"]["B_pakiety"]
    wynik["prog_rentownosci_kancelarii"] = math.ceil(KOSZT_STALY_ZL / max(1, srednia["marza_po_wsparciu_zl"]))
    return wynik


def _drukuj() -> None:
    r = symuluj()
    print(f"Spraw w symulacji: {r['spraw']}; koszt AI sprawy: srednio {r['koszt_sredni_zl']:.2f} zl, "
          f"P90 {r['koszt_p90_zl']:.2f} zl\n")
    print(f"{'wersja':6} {'kr/sprawe':>9} {'mediana':>8} {'narzut port.':>12} {'<100% (0,80zl)':>15} "
          f"{'<100% (1zl)':>12} {'strata':>7} {'narzut P5':>10}")
    for w in ("v0", "v1", "v2"):
        d = r[w]
        print(f"{w:6} {d['kredyty_srednio']:9.1f} {d['kredyty_mediana']:8.1f} "
              f"{d['narzut_portfela_tani'] * 100:11.0f}% {d['spraw_ponizej_100_tani'] * 100:14.1f}% "
              f"{d['spraw_ponizej_100_katalog'] * 100:11.1f}% {d['spraw_ze_strata_tani'] * 100:6.1f}% "
              f"{d['narzut_p5_tani'] * 100:9.0f}%")
    e = ekonomia_modeli()
    print(f"\nSrednia sprawa: koszt AI {e['koszt_sprawy_zl']} zl, {e['kredyty_sprawy']} kr.\n")
    for profil, modele in e["modele"].items():
        print(profil)
        for nazwa, m in modele.items():
            print(f"  {nazwa:20} przychod {m['przychod_zl']:7.0f} zl  koszt AI {m['koszt_ai_zl']:6.0f} zl  "
                  f"narzut {m['narzut_na_koszcie_ai'] * 100:5.0f}%  marza po wsparciu "
                  f"{m['marza_po_wsparciu_zl']:7.0f} zl  ({m['cena_za_sprawe_zl']} zl/sprawe)")
    print(f"\nKoszty stale {KOSZT_STALY_ZL:.0f} zl/mies. pokrywa {e['prog_rentownosci_kancelarii']} "
          "kancelaria(e) srednia(e) w modelu B (same pakiety - obowiazujacy).")


if __name__ == "__main__":
    _drukuj()
