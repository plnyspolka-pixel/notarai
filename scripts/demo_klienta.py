"""Stanowisko deweloperskie aplikacji klienta: zaklada w lokalnym katalogu dane/
fikcyjna kancelarie z terminarzem online, zeby aplikacja mobilna miala co
pokazac bez AWS i bez Twilio.

Uruchomienie (z katalogu repozytorium):
    set PIECZAPP_SMS_TRYB=test
    .venv\\Scripts\\python scripts\\demo_klienta.py
    .venv\\Scripts\\python -m uvicorn app:app --port 8000

Tryb test: SMS nie wychodzi, kod weryfikacyjny wraca w odpowiedzi API
(aplikacja wpisuje go sama). Dane sa fikcyjne, katalog dane/ jest poza gitem.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("PIECZAPP_SMS_TRYB", "test")

import autoryzacja  # noqa: E402
import magazyn  # noqa: E402
import rezerwacje_hurtowe as hurtowe  # noqa: E402

KANCELARIE = [
    {"id": "demo-lublin", "nazwa": "Kancelaria Notarialna Demo Lublin", "notariusze": "Anna Przykładowa",
     "adres": "ul. Krakowskie Przedmieście 1, 20-002 Lublin", "miasto": "Lublin",
     "lat": 51.2480, "lon": 22.5660, "godziny": {str(i): ["09:00", "17:00"] for i in range(5)}, "czas": 60},
    {"id": "demo-warszawa", "nazwa": "Kancelaria Notarialna Demo Warszawa", "notariusze": "Jan Przykładowy",
     "adres": "ul. Marszałkowska 10, 00-590 Warszawa", "miasto": "Warszawa",
     "lat": 52.2297, "lon": 21.0122, "godziny": {**{str(i): ["08:00", "18:00"] for i in range(5)}, "5": ["09:00", "13:00"]},
     "czas": 30},
]


def glowna() -> None:
    if magazyn.TRYB != "lokalny":
        raise SystemExit("Ten skrypt dziala tylko w trybie lokalnym (PIECZAPP_MAGAZYN=lokalny).")
    rejestr = autoryzacja._wczytaj_rejestr()
    for k in KANCELARIE:
        skrot = f"demo-{k['id']}"
        rejestr[skrot] = {
            "id": k["id"], "nazwa": k["nazwa"], "aktywna": True, "przechowywanie": "chmura",
            "umowa": {"zaakceptowano": "2026-11-01T00:00:00"},
            "dane": {"adres": k["adres"], "notariusze": k["notariusze"]},
            "mapa": {"adres": k["adres"], "lat": k["lat"], "lon": k["lon"], "dokladnosc": "adres",
                     "sprawdzono": "2026-11-01T00:00:00"},
            "na_mapie": True,
            "zespol": [{"email": f"demo@{k['id']}.test", "rola": "wlasciciel"}],
        }
        polityka = {"wlaczone": False, "klienci": True, "miasto": k["miasto"], "adres": k["adres"],
                    "godziny": k["godziny"], "czas_minut": k["czas"], "wyprzedzenie_godzin": 2, "max_dni": 60}
        with hurtowe._WBiurze(k["id"]):
            magazyn.zmien_plik_kancelarii("rezerwacje_hurtowe", lambda p, polityka=polityka: p.update(polityka), {})
    autoryzacja._zapisz_rejestr(rejestr)
    print("Kancelarie demo z terminarzem online:")
    for k in KANCELARIE:
        print(f"  {k['id']:<15} {k['nazwa']} ({k['miasto']}), wizyta {k['czas']} min")
    print("\nTeraz: .venv\\Scripts\\python -m uvicorn app:app --port 8000   (PIECZAPP_SMS_TRYB=test)")
    print("Aplikacja: cd mobilna && npm run web   (EXPO_PUBLIC_API_URL=http://127.0.0.1:8000)")


if __name__ == "__main__":
    glowna()
