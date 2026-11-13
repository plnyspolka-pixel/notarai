"""Stanowiska w zespole kancelarii: co kto moze zrobic w sprawach.

Rola administracyjna (`wlasciciel` / `czlonek`, autoryzacja.py) mowi, kto
zarzadza zespolem i abonamentem. Stanowisko mowi, co osoba robi w sprawach:

- notariusz   - wszystko, w tym usuniecie sprawy, ksiegi, GIIF, zasady,
- aplikant    - przygotowuje: odczyt skanow, poprawki pol, projekt, rejestry,
- sekretariat - kalendarz, telefony, przesylki, pliki sprawy (takze zdjecia
                aparatem), podglad spraw i projektow; bez modelu i rejestrow.

Wlasciciel kancelarii ma zawsze pelne uprawnienia. Osoba bez nadanego
stanowiska tez - kancelarie zalozone przed ta zmiana dzialaja jak dotad.
Tryb lokalny (jedno stanowisko, bez logowania) nie ma stanowisk wcale.

Uprawnienia egzekwuje middleware (autoryzacja.py) po metodzie i sciezce;
interfejs tylko chowa przyciski, ktorych osoba i tak nie moglaby uzyc.
Zadne stanowisko nie podpisuje ani nie wysyla niczego za notariusza - takich
funkcji w notarai nie ma.
"""
import re

STANOWISKA = ("notariusz", "aplikant", "sekretariat")

NAZWY = {"notariusz": "notariusz", "aplikant": "aplikant", "sekretariat": "sekretariat"}

# Uprawnienia ponad to, co ma kazdy zalogowany czlonek zespolu.
WSZYSTKIE = ("sprawy_ai", "projekt", "rejestry", "usun_plik", "usun_sprawe", "kancelaria")

UPRAWNIENIA = {
    "notariusz": frozenset(WSZYSTKIE),
    "aplikant": frozenset({"sprawy_ai", "projekt", "rejestry", "usun_plik"}),
    "sekretariat": frozenset(),
}

OPISY = {
    "sprawy_ai": "odczyt skanów i rozmowa o sprawie",
    "projekt": "sporządzanie projektu",
    "rejestry": "sprawdzenia w rejestrach",
    "usun_plik": "usuwanie plików sprawy",
    "usun_sprawe": "usuwanie sprawy",
    "kancelaria": "księgi, GIIF i zasady kancelarii",
}

_SPRAWA = r"/api/sprawy/[A-Za-z0-9]+"
_ZAPIS = ("POST", "PUT", "PATCH", "DELETE")

# (metody, wzorzec sciezki, uprawnienie). Pierwsze dopasowanie wygrywa.
_REGULY = [
    (("POST",), r"/api/sprawy", "sprawy_ai"),
    (("POST",), r"/api/odczyt", "sprawy_ai"),
    (("POST",), r"/api/rozmowa", "sprawy_ai"),
    (("POST",), _SPRAWA + r"/rozmowa", "sprawy_ai"),
    (("POST",), r"/api/transkrypcja", "sprawy_ai"),
    (("POST",), r"/api/poswiadczenia(/.*)?", "sprawy_ai"),
    (("POST",), _SPRAWA + r"/projekt", "projekt"),
    (("POST",), r"/api/projekt", "projekt"),
    (("POST",), _SPRAWA + r"/(krz|ekw|aml|crbr|klikamy|sprawdzenia(/.*)?|formularze/.*)", "rejestry"),
    (("POST",), r"/api/formularze/.*", "rejestry"),
    (("DELETE",), _SPRAWA + r"/pliki/.+", "usun_plik"),
    (("DELETE",), _SPRAWA, "usun_sprawe"),
    # Dowody kryptograficzne zawieraja prywatne metadane i sole; tylko notariusz/wlasciciel.
    (None, r"/api/dowody(/.*)?", "kancelaria"),
    (None, r"/api/sealed(/.*)?", "kancelaria"),
    (None, r"/api/giif(/.*)?", "kancelaria"),
    (_ZAPIS, r"/api/ksiegi-kancelarii(/.*)?", "kancelaria"),
    (_ZAPIS, r"/api/personalizacja(/.*)?", "kancelaria"),
]
_SKOMPILOWANE = [(m, re.compile(w + r"/?"), u) for m, w, u in _REGULY]


def wymagane(metoda: str, sciezka: str) -> str | None:
    """Uprawnienie potrzebne do zadania albo None, gdy wystarczy byc w zespole."""
    metoda = metoda.upper()
    for metody, wzorzec, uprawnienie in _SKOMPILOWANE:
        if (metody is None or metoda in metody) and wzorzec.fullmatch(sciezka):
            return uprawnienie
    return None


def uprawnienia(osoba: dict | None) -> frozenset:
    """Uprawnienia osoby z zespolu: wlasciciel i osoba bez stanowiska - wszystkie."""
    if not osoba or osoba.get("rola") == "wlasciciel":
        return frozenset(WSZYSTKIE)
    stanowisko = osoba.get("stanowisko")
    if stanowisko not in UPRAWNIENIA:
        return frozenset(WSZYSTKIE)
    return UPRAWNIENIA[stanowisko]


def sprawdz(stanowisko: str) -> str:
    """Poprawne stanowisko albo ValueError. Puste = bez stanowiska."""
    stanowisko = (stanowisko or "").strip().lower()
    if stanowisko and stanowisko not in STANOWISKA:
        raise ValueError("Stanowisko: notariusz, aplikant albo sekretariat.")
    return stanowisko


def odmowa(uprawnienie: str, stanowisko: str) -> str:
    """Komunikat 403 - bez adresu e-mail, z nazwa stanowiska i czynnosci."""
    return (f"Na stanowisku „{NAZWY.get(stanowisko, stanowisko)}” nie ma uprawnienia: "
            f"{OPISY.get(uprawnienie, uprawnienie)}. Poproś notariusza albo właściciela kancelarii.")
