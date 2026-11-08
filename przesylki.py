"""Dziennik przesylanych dokumentow i dziennik korespondencyjny.

Rozporzadzenie Ministra Sprawiedliwosci z 12.04.1991 r. w sprawie prowadzenia
ksiag notarialnych (t.j. Dz.U. 2018 poz. 2039):
  - § 1 ust. 1 pkt 4 i 5: to dwie osobne ksiegi, wiec trzymamy je w dwoch
    osobnych plikach z osobna numeracja,
  - § 5 ust. 1: do dziennika przesylanych dokumentow wpisuje sie wnioski
    i pisma przesylane z urzedu sadom i innym organom (u nas: wypisy aktow),
  - § 5 ust. 2: do dziennika korespondencyjnego - inne pisma wysylane
    i wplywajace, dotyczace dzialalnosci notariusza,
  - § 1 ust. 5: obu dziennikow NIE prowadzi sie w okresach rocznych, wiec
    numeracja pozycji biegnie dalej po Nowym Roku,
  - § 1 ust. 6: ksiegi sa oprawione, a strony ponumerowane - stad wydruk PDF
    z numeracja stron, ktora mozna kontynuowac od kolejnego wydruku,
  - § 1 ust. 7: poprawka ma zostawic czytelna tresc pierwotna, z data. Wpisu
    wiec nie kasujemy (najwyzej "anulowany", przekreslony na wydruku), a kazda
    zmiana zostaje w historii pozycji i jest widoczna w rubryce uwag.
Rozporzadzenie nie zawiera wzoru rubryk - uklad kolumn odpowiada temu, co
kancelarie wpisuja w papierowe dzienniki; kolumny sa w KOLUMNY i latwo je
dostosowac.

Pocztowa ksiazka nadawcza: zestawienie przesylek rejestrowanych z danego
dnia (z obu dziennikow), do podbicia w urzedzie pocztowym. Numer nadania
z naklejki wpisuje sie potem do pozycji - recznie albo czytnikiem kodow
kreskowych (czytnik "pisze" numer i Enter).

Poczta Polska: pelna integracja (numery nadania z puli, etykiety z kodem,
elektroniczna ksiazka nadawcza, statusy doreczen) wymaga umowy i konta
Elektroniczny Nadawca z dostepem do WebAPI. Do tego czasu: eksport CSV do
importu w aplikacji e-Nadawca i link do sledzenia przesylki na stronie Poczty.

Adresaci to czesto osoby fizyczne - dane osobowe: nie trafiaja do logow.
"""
import csv
import html
import io
import re
import uuid
from datetime import date, datetime

import fitz  # PyMuPDF
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

import magazyn

KSIEGI = {
    "przeslane": {"plik": "dziennik_przeslanych", "tytul": "Dziennik przesyłanych dokumentów"},
    "korespondencja": {"plik": "dziennik_korespondencyjny", "tytul": "Dziennik korespondencyjny"},
}
PLIK_USTAWIEN = "przesylki_ustawienia"

SPOSOBY = ("list polecony", "list polecony za potwierdzeniem odbioru", "list zwykły",
           "elektronicznie (ePUAP, e-mail, portal)", "doręczenie osobiste", "inny")
REJESTROWANE = SPOSOBY[:2]
KIERUNKI = ("wychodzące", "przychodzące")
STATUSY = ("aktywny", "anulowany")
SLEDZENIE = "https://emonitoring.poczta-polska.pl/?numer="

# Pola, ktorych zmiana trafia do historii poprawek pozycji.
POLA = ("data", "repertorium", "dokument", "kierunek", "znak_pisma", "data_pisma", "tresc",
        "adresat", "ulica", "kod", "miejscowosc", "sposob", "numer_nadania", "data_doreczenia", "uwagi", "sprawa")
ETYKIETY = {"data": "data", "repertorium": "nr repertorium", "dokument": "dokument", "kierunek": "kierunek",
            "znak_pisma": "znak pisma", "data_pisma": "data pisma", "tresc": "treść", "adresat": "adresat",
            "ulica": "ulica", "kod": "kod", "miejscowosc": "miejscowość", "sposob": "sposób",
            "numer_nadania": "nr nadania", "data_doreczenia": "doręczono", "uwagi": "uwagi", "sprawa": "sprawa"}

_KOD = re.compile(r"\d{2}-\d{3}")
_NUMER = re.compile(r"[A-Z0-9]{8,30}")
_SPRAWA = re.compile(r"[A-Za-z0-9]{1,64}")


# --- zapis -----------------------------------------------------------------


def _linia(tekst, limit: int) -> str:
    return " ".join(str(tekst or "").split())[:limit]


def _data(tekst, nazwa: str, wymagana: bool = False) -> str:
    tekst = str(tekst or "").strip()
    if not tekst:
        if wymagana:
            raise ValueError(f"Podaj {nazwa}")
        return ""
    try:
        return date.fromisoformat(tekst).isoformat()
    except ValueError:
        raise ValueError(f"{nazwa.capitalize()}: podaj datę w postaci RRRR-MM-DD")


def _ksiega(ksiega: str) -> dict:
    if ksiega not in KSIEGI:
        raise ValueError("Nieznana księga")
    return KSIEGI[ksiega]


def _sprawdz(ksiega: str, dane: dict) -> dict:
    _ksiega(ksiega)
    wpis = {
        "data": _data(dane.get("data"), "datę wysłania" if ksiega == "przeslane" else "datę", wymagana=True),
        "adresat": _linia(dane.get("adresat"), 300),
        "ulica": _linia(dane.get("ulica"), 200),
        "kod": _linia(dane.get("kod"), 10),
        "miejscowosc": _linia(dane.get("miejscowosc"), 100),
        "sposob": str(dane.get("sposob") or SPOSOBY[0]),
        "numer_nadania": re.sub(r"\s", "", str(dane.get("numer_nadania") or "")).upper(),
        "data_doreczenia": _data(dane.get("data_doreczenia"), "datę doręczenia"),
        "uwagi": str(dane.get("uwagi") or "").strip()[:1000],
        "sprawa": str(dane.get("sprawa") or "").strip(),
    }
    if ksiega == "przeslane":
        wpis["repertorium"] = _linia(dane.get("repertorium"), 60)
        wpis["dokument"] = _linia(dane.get("dokument"), 200) or "wypis aktu notarialnego"
        if not re.search(r"\d", wpis["repertorium"]):
            raise ValueError("Podaj numer repertorium aktu (np. A 1234/2026)")
        if not wpis["adresat"]:
            raise ValueError("Podaj adresata (urząd, sąd)")
    else:
        wpis["kierunek"] = str(dane.get("kierunek") or KIERUNKI[0])
        wpis["znak_pisma"] = _linia(dane.get("znak_pisma"), 100)
        wpis["data_pisma"] = _data(dane.get("data_pisma"), "datę pisma")
        wpis["tresc"] = _linia(dane.get("tresc"), 500)
        if wpis["kierunek"] not in KIERUNKI:
            raise ValueError("Nieznany kierunek pisma")
        if not wpis["adresat"]:
            raise ValueError("Podaj nadawcę" if wpis["kierunek"] == "przychodzące" else "Podaj adresata")
        if not wpis["tresc"]:
            raise ValueError("Opisz krótko, czego dotyczy pismo")
    if wpis["sposob"] not in SPOSOBY:
        raise ValueError("Nieznany sposób przesłania")
    if wpis["kod"] and not _KOD.fullmatch(wpis["kod"]):
        raise ValueError("Kod pocztowy podaj w postaci 00-000")
    wysylka_poczta = wpis["sposob"] in REJESTROWANE and wpis.get("kierunek", "wychodzące") == "wychodzące"
    if wysylka_poczta and not (wpis["ulica"] and wpis["kod"] and wpis["miejscowosc"]):
        raise ValueError("List polecony wymaga pełnego adresu: ulica, kod pocztowy i miejscowość")
    if wpis["numer_nadania"] and not _NUMER.fullmatch(wpis["numer_nadania"]):
        raise ValueError("Numer nadania: same litery i cyfry, 8-30 znaków (np. z naklejki Poczty)")
    if wpis["sprawa"] and not _SPRAWA.fullmatch(wpis["sprawa"]):
        raise ValueError("Nieprawidłowy identyfikator sprawy")
    return wpis


def _teraz() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _pusta() -> dict:
    return {"ostatni_lp": 0, "wpisy": []}


def lista(ksiega: str) -> list[dict]:
    dane = magazyn.wczytaj_plik_kancelarii(_ksiega(ksiega)["plik"], _pusta())
    return sorted(dane["wpisy"], key=lambda w: w["lp"])


def dodaj(ksiega: str, dane: dict, kto: str = "") -> dict:
    nowy = _sprawdz(ksiega, dane)

    def zmiana(d):
        # Numer pozycji nadaje serwer pod blokada zapisu, wiec dwie osoby
        # dodajace wpis w tej samej chwili nie dostana tego samego numeru.
        d["ostatni_lp"] = max(d.get("ostatni_lp", 0), *(w["lp"] for w in d["wpisy"]), 0) + 1
        wpis = {"id": uuid.uuid4().hex[:12], "lp": d["ostatni_lp"], **nowy, "status": "aktywny",
                "utworzono": _teraz(), "kto": _linia(kto, 200), "poprawki": []}
        d["wpisy"].append(wpis)
        return wpis
    return magazyn.zmien_plik_kancelarii(_ksiega(ksiega)["plik"], zmiana, _pusta())


def _popraw(wpis: dict, nowe: dict, kto: str) -> dict:
    roznice = {p: [wpis.get(p, ""), nowe[p]] for p in nowe if p in POLA and wpis.get(p, "") != nowe[p]}
    if roznice:
        # Pierwsze wpisanie numeru nadania czy daty doreczenia to uzupelnienie,
        # nie poprawka - nie zasmieca rubryki uwag na wydruku.
        uzupelnienie = all(p in ("numer_nadania", "data_doreczenia") and not stare for p, (stare, _) in roznice.items())
        wpis.setdefault("poprawki", []).append({"kiedy": _teraz(), "kto": _linia(kto, 200),
                                                "pola": roznice, "uzupelnienie": uzupelnienie})
        wpis.update(nowe)
    return wpis


def zmien(ksiega: str, identyfikator: str, dane: dict, kto: str = "") -> dict | None:
    nowe = _sprawdz(ksiega, dane)

    def zmiana(d):
        for wpis in d["wpisy"]:
            if wpis["id"] == identyfikator:
                if wpis.get("status") == "anulowany":
                    raise ValueError("Pozycja jest anulowana - dodaj nową")
                return _popraw(wpis, nowe, kto)
        return None
    return magazyn.zmien_plik_kancelarii(_ksiega(ksiega)["plik"], zmiana, _pusta())


def ustaw_numery(ksiega: str, numery: dict[str, str], kto: str = "") -> int:
    """{id: numer_nadania} - wpisanie numerow z naklejek po wizycie na poczcie."""
    czyste = {}
    for ident, numer in numery.items():
        numer = re.sub(r"\s", "", str(numer or "")).upper()
        if numer and not _NUMER.fullmatch(numer):
            raise ValueError(f"Nieprawidłowy numer nadania: {numer}")
        czyste[ident] = numer

    def zmiana(d):
        ile = 0
        for wpis in d["wpisy"]:
            if wpis["id"] in czyste and wpis.get("status") != "anulowany" and wpis.get("numer_nadania", "") != czyste[wpis["id"]]:
                _popraw(wpis, {"numer_nadania": czyste[wpis["id"]]}, kto)
                ile += 1
        return ile
    return magazyn.zmien_plik_kancelarii(_ksiega(ksiega)["plik"], zmiana, _pusta())


def anuluj(ksiega: str, identyfikator: str, powod: str, kto: str = "") -> dict | None:
    """Pozycja zostaje w ksiedze (i numeracji), na wydruku jest przekreslona."""
    powod = _linia(powod, 300)
    if not powod:
        raise ValueError("Podaj powód anulowania pozycji")

    def zmiana(d):
        for wpis in d["wpisy"]:
            if wpis["id"] == identyfikator:
                if wpis.get("status") != "anulowany":
                    wpis["status"] = "anulowany"
                    wpis.setdefault("poprawki", []).append(
                        {"kiedy": _teraz(), "kto": _linia(kto, 200), "pola": {"status": ["aktywny", "anulowany"]},
                         "powod": powod, "uzupelnienie": False})
                return wpis
        return None
    return magazyn.zmien_plik_kancelarii(_ksiega(ksiega)["plik"], zmiana, _pusta())


def _domyslne_ustawienia() -> dict:
    return {"nadawca": "", "adres_nadawcy": "", "nastepna_strona": {}}


def ustawienia() -> dict:
    return {**_domyslne_ustawienia(), **magazyn.wczytaj_plik_kancelarii(PLIK_USTAWIEN, {})}


def zapisz_ustawienia(dane: dict) -> dict:
    nowe = {"nadawca": _linia(dane.get("nadawca"), 200),
            "adres_nadawcy": "\n".join(_linia(l, 120) for l in str(dane.get("adres_nadawcy") or "").splitlines()[:4] if l.strip())}

    def zmiana(d):
        d.update(nowe)
        return {**_domyslne_ustawienia(), **d}
    return magazyn.zmien_plik_kancelarii(PLIK_USTAWIEN, zmiana, {})


def _zapamietaj_strone(ksiega: str, nastepna: int) -> None:
    def zmiana(d):
        d.setdefault("nastepna_strona", {})[ksiega] = nastepna
    magazyn.zmien_plik_kancelarii(PLIK_USTAWIEN, zmiana, {})


def usun_sprawe(id_sprawy: str) -> None:
    """Usunieta sprawa nie zostawia wskazania; sam wpis w ksiedze zostaje."""
    if magazyn.u_klienta():
        return
    for ksiega in KSIEGI:
        if not any(w.get("sprawa") == id_sprawy for w in lista(ksiega)):
            continue
        def zmiana(d):
            for wpis in d["wpisy"]:
                if wpis.get("sprawa") == id_sprawy:
                    wpis["sprawa"] = ""
        magazyn.zmien_plik_kancelarii(KSIEGI[ksiega]["plik"], zmiana, _pusta())


# --- wydruki ---------------------------------------------------------------

MM = 72 / 25.4
_CSS = """
* { font-family: sans-serif; }
body { font-size: 8.5pt; }
h1 { font-size: 12pt; margin: 0 0 2pt 0; }
p.pod { font-size: 8pt; margin: 0 0 6pt 0; color: #333; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 0.6pt solid #000; padding: 2pt 3pt; vertical-align: top; }
th { background-color: #eee; font-size: 7.5pt; text-align: center; }
td.lp { text-align: right; }
.anul { color: #b00; text-decoration: line-through; }
.popr { color: #b00; font-size: 7pt; }
.puste td { height: 22pt; }
"""

# (naglowek, szerokosc w %, funkcja wartosci) - uklad rubryk wydruku.
KOLUMNY = {
    "przeslane": [
        ("Lp.", 4, lambda w: str(w["lp"])),
        ("Data wysłania", 7, lambda w: _pl(w["data"])),
        ("Nr repertorium", 9, lambda w: w.get("repertorium", "").replace(" ", "\u00a0")),
        ("Rodzaj dokumentu", 13, lambda w: w.get("dokument", "")),
        ("Adresat (nazwa i adres)", 25, lambda w: _adres_jednolinijkowy(w)),
        ("Sposób przesłania", 11, lambda w: w.get("sposob", "")),
        ("Nr nadania / potwierdzenie wysyłki", 13, lambda w: w.get("numer_nadania", "")),
        ("Data doręczenia (ZPO)", 7, lambda w: _pl(w.get("data_doreczenia", ""))),
        ("Uwagi", 11, lambda w: w.get("uwagi", "")),
    ],
    "korespondencja": [
        ("Lp.", 4, lambda w: str(w["lp"])),
        ("Data wpływu / wysłania", 7, lambda w: _pl(w["data"])),
        ("Pismo", 6, lambda w: "wpływ" if w.get("kierunek") == "przychodzące" else "wysyłka"),
        ("Nadawca / adresat (nazwa i adres)", 22, lambda w: _adres_jednolinijkowy(w)),
        ("Znak i data pisma", 10, lambda w: ", ".join(x for x in (w.get("znak_pisma", ""), _pl(w.get("data_pisma", ""))) if x)),
        ("Treść (czego dotyczy)", 19, lambda w: w.get("tresc", "")),
        ("Sposób przesłania", 9, lambda w: w.get("sposob", "")),
        ("Nr nadania", 11, lambda w: w.get("numer_nadania", "")),
        ("Uwagi", 12, lambda w: w.get("uwagi", "")),
    ],
}


def _pl(iso: str) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso and len(iso) >= 10 else (iso or "")


def _adres_linie(w: dict) -> list[str]:
    return [x for x in (w.get("adresat", ""), w.get("ulica", ""), " ".join(x for x in (w.get("kod", ""), w.get("miejscowosc", "")) if x)) if x]


def _adres_jednolinijkowy(w: dict) -> str:
    return ", ".join(_adres_linie(w))


def _opis_poprawek(w: dict) -> str:
    opisy = []
    for p in w.get("poprawki", []):
        if p.get("uzupelnienie"):
            continue
        if "status" in p["pola"]:
            opisy.append(f"anulowano {_pl(p['kiedy'][:10])}: {p.get('powod', '')}")
            continue
        zmiany = "; ".join(f"{ETYKIETY.get(k, k)}: było „{stare or '-'}”" for k, (stare, _) in p["pola"].items())
        opisy.append(f"popr. {_pl(p['kiedy'][:10])} ({zmiany})")
    return " | ".join(opisy)


def _wiersz(ksiega: str, w: dict) -> str:
    anul = w.get("status") == "anulowany"
    komorki = []
    for i, (_, _, wartosc) in enumerate(KOLUMNY[ksiega]):
        tekst = html.escape(wartosc(w))
        if i == len(KOLUMNY[ksiega]) - 1:
            popr = _opis_poprawek(w)
            if popr:
                tekst += f'<br><span class="popr">{html.escape(popr)}</span>'
        klasa = ' class="lp"' if i == 0 else ""
        if anul and i > 0 and i < len(KOLUMNY[ksiega]) - 1:
            tekst = f'<span class="anul">{tekst}</span>'
        komorki.append(f"<td{klasa}>{tekst}</td>")
    return "<tr>" + "".join(komorki) + "</tr>"


def _naglowek_tabeli(kolumny) -> str:
    return "<tr>" + "".join(f'<th style="width:{s}%">{html.escape(n)}</th>' for n, s, _ in kolumny) + "</tr>"


def _zmiesci(html_strony: str, obszar: fitz.Rect) -> bool:
    story = fitz.Story(html=html_strony, user_css=_CSS)
    wiecej, _ = story.place(obszar)
    return not wiecej


def _strony_tabeli(gora: str, naglowek: str, wiersze: list[str], obszar: fitz.Rect, puste_wiersze: str = "") -> list[str]:
    """Dzieli wiersze na strony tak, by naglowek tabeli byl na kazdej.

    Dlugie adresy zawijaja sie w komorkach, wiec liczbe wierszy na stronie
    ustalamy proba (wyszukiwanie binarne), a nie na sztywno.
    """
    def strona(czesc: list[str], ogon: str = "") -> str:
        return f"{gora}<table>{naglowek}{''.join(czesc)}{ogon}</table>"

    strony, i = [], 0
    while i < len(wiersze) or not strony:
        lo, hi = 1, len(wiersze) - i
        if hi <= 0:
            strony.append(strona([], puste_wiersze))
            break
        while lo < hi:
            srodek = (lo + hi + 1) // 2
            if _zmiesci(strona(wiersze[i:i + srodek]), obszar):
                lo = srodek
            else:
                hi = srodek - 1
        strony.append(strona(wiersze[i:i + lo]))
        i += lo
    return strony


def _pdf_ze_stron(strony: list[str], prostokat: fitz.Rect, margines: float, stopka) -> bytes:
    bufor = io.BytesIO()
    pisarz = fitz.DocumentWriter(bufor)
    obszar = prostokat + (margines, margines, -margines, -margines - 14)
    for tresc in strony:
        story = fitz.Story(html=tresc, user_css=_CSS)
        urzadzenie = pisarz.begin_page(prostokat)
        story.place(obszar)
        story.draw(urzadzenie)
        pisarz.end_page()
    pisarz.close()
    dokument = fitz.open("pdf", bufor.getvalue())
    for nr, strona in enumerate(dokument):
        tekst = stopka(nr)
        if tekst:
            strona.insert_htmlbox(fitz.Rect(margines, prostokat.height - margines - 10, prostokat.width - margines,
                                            prostokat.height - margines + 4),
                                  f'<div style="font-family:sans-serif;font-size:8pt;text-align:center">{html.escape(tekst)}</div>')
    wynik = dokument.tobytes(garbage=3, deflate=True)
    dokument.close()
    return wynik


def wybierz(ksiega: str, od: str = "", do: str = "", od_lp: int = 0, do_lp: int = 0) -> list[dict]:
    od, do = _data(od, "datę od"), _data(do, "datę do")
    return [w for w in lista(ksiega)
            if (not od or w["data"] >= od) and (not do or w["data"] <= do)
            and (not od_lp or w["lp"] >= od_lp) and (not do_lp or w["lp"] <= do_lp)]


def pdf_ksiegi(ksiega: str, od: str = "", do: str = "", od_lp: int = 0, do_lp: int = 0,
               od_strony: int = 0, zapamietaj: bool = True) -> bytes:
    """Ksiega do oprawy: A4 poziomo, naglowek tabeli na kazdej stronie, strony
    numerowane. Kolejny wydruk moze zaczac od nastepnej strony poprzedniego."""
    opis = _ksiega(ksiega)
    wpisy = wybierz(ksiega, od, do, od_lp, do_lp)
    ust = ustawienia()
    pierwsza = od_strony or int(ust.get("nastepna_strona", {}).get(ksiega, 1)) or 1
    zakres = ""
    if wpisy:
        zakres = f"poz. {wpisy[0]['lp']}–{wpisy[-1]['lp']}, {_pl(wpisy[0]['data'])} – {_pl(wpisy[-1]['data'])}"
    gora = (f"<h1>{html.escape(opis['tytul'])}</h1><p class='pod'>{html.escape(ust['nadawca'] or 'Kancelaria notarialna')}"
            f"{' · ' + html.escape(zakres) if zakres else ''} · wydruk z {_pl(date.today().isoformat())}</p>")
    prostokat = fitz.paper_rect("a4-l")
    margines = 12 * MM
    obszar = prostokat + (margines, margines, -margines, -margines - 14)
    kolumny = KOLUMNY[ksiega]
    pusty = "<tr class='puste'>" + "".join("<td></td>" for _ in kolumny) + "</tr>"
    strony = _strony_tabeli(gora, _naglowek_tabeli(kolumny), [_wiersz(ksiega, w) for w in wpisy], obszar, pusty * 3)
    pdf = _pdf_ze_stron(strony, prostokat, margines, lambda nr: f"{opis['tytul']} – strona {pierwsza + nr}")
    if zapamietaj and not od_strony and wpisy:
        _zapamietaj_strone(ksiega, pierwsza + len(strony))
    return pdf


def _do_wysylki(dzien: str, ksiegi=tuple(KSIEGI)) -> list[tuple[str, dict]]:
    wynik = []
    for ksiega in ksiegi:
        for w in lista(ksiega):
            if (w["data"] == dzien and w.get("status") != "anulowany" and w.get("sposob") in REJESTROWANE
                    and w.get("kierunek", "wychodzące") == "wychodzące"):
                wynik.append((ksiega, w))
    return wynik


def pdf_ksiazki_nadawczej(dzien: str) -> bytes:
    """Pocztowa ksiazka nadawcza na jeden dzien - do podbicia w urzedzie."""
    dzien = _data(dzien, "dzień nadania", wymagana=True)
    ust = ustawienia()
    pozycje = _do_wysylki(dzien)
    nadawca = html.escape(ust["nadawca"] or "Kancelaria notarialna")
    adres = "<br>".join(html.escape(l) for l in ust["adres_nadawcy"].splitlines())
    gora = (f"<h1>Pocztowa książka nadawcza</h1><p class='pod'><b>Nadawca:</b> {nadawca}{'<br>' + adres if adres else ''}"
            f"<br><b>Data nadania:</b> {_pl(dzien)} · przesyłek: {len(pozycje)}</p>")
    naglowek = ("<tr><th style='width:4%'>Lp.</th><th style='width:24%'>Adresat (imię i nazwisko lub nazwa)</th>"
                "<th style='width:21%'>Dokładne miejsce doręczenia</th><th style='width:11%'>Rodzaj przesyłki</th>"
                "<th style='width:23%'>Nr nadawczy</th><th style='width:10%'>Uwagi</th><th style='width:7%'>Opłata</th></tr>")
    wiersze = []
    for nr, (ksiega, w) in enumerate(pozycje, 1):
        rodzaj = "polecony ZPO" if w["sposob"] == REJESTROWANE[1] else "polecony"
        znak = f"{'DPD' if ksiega == 'przeslane' else 'DK'}\u00a0{w['lp']}"
        miejsce = html.escape(w["ulica"]) + "<br>" + html.escape(f"{w['kod']} {w['miejscowosc']}")
        wiersze.append(f"<tr><td class='lp'>{nr}</td><td>{html.escape(w['adresat'])}</td><td>{miejsce}</td>"
                       f"<td>{rodzaj}</td><td>{html.escape(w.get('numer_nadania', ''))}</td><td>{znak}</td><td></td></tr>")
    prostokat = fitz.paper_rect("a4")
    margines = 12 * MM
    obszar = prostokat + (margines, margines, -margines, -margines - 14 - 60)
    strony = _strony_tabeli(gora, naglowek, wiersze, obszar)
    podpis = ("<p style='margin-top:18pt;font-size:8pt'>Przyjęto przesyłek: ........ &nbsp;&nbsp; "
              "Opłata: ................ &nbsp;&nbsp; Podpis przyjmującego i datownik: ................................</p>"
              "<p class='pod'>W rubryce „Uwagi”: DPD – dziennik przesyłanych dokumentów, DK – dziennik "
              "korespondencyjny, z numerem pozycji.</p>")
    strony[-1] += podpis
    return _pdf_ze_stron(strony, prostokat, margines, lambda nr: f"Książka nadawcza {_pl(dzien)} – strona {nr + 1}/{len(strony)}")


FORMATY_KOPERT = {"DL": (220, 110), "C5": (229, 162), "C6": (162, 114), "C4": (324, 229)}


def pdf_kopert(pozycje: list[dict], format_koperty: str = "DL") -> bytes:
    """Nadruk na koperty: nadawca w lewym gornym rogu, adresat w prawej dolnej
    cwiartce, oznaczenie "POLECONY" / "ZA POTWIERDZENIEM ODBIORU"."""
    if format_koperty not in FORMATY_KOPERT:
        raise ValueError("Nieznany format koperty")
    if not pozycje:
        raise ValueError("Nie wybrano żadnej pozycji do druku kopert")
    szer, wys = (x * MM for x in FORMATY_KOPERT[format_koperty])
    ust = ustawienia()
    nadawca = "<br>".join(html.escape(l) for l in [ust["nadawca"], *ust["adres_nadawcy"].splitlines()] if l)
    dokument = fitz.open()
    for w in pozycje:
        strona = dokument.new_page(width=szer, height=wys)
        if nadawca:
            strona.insert_htmlbox(fitz.Rect(10 * MM, 8 * MM, szer * 0.55, wys * 0.45),
                                  f"<div style='font-family:sans-serif;font-size:8pt'>{nadawca}</div>")
        if w.get("sposob") in REJESTROWANE:
            napis = "POLECONY" + ("<br>ZA POTWIERDZENIEM ODBIORU" if w["sposob"] == REJESTROWANE[1] else "")
            strona.insert_htmlbox(fitz.Rect(szer * 0.5, 8 * MM, szer - 10 * MM, wys * 0.3),
                                  f"<div style='font-family:sans-serif;font-size:9pt;font-weight:bold;text-align:right'>{napis}</div>")
        adres = _adres_linie(w)
        linie = "<br>".join(html.escape(l) for l in adres[:-1]) + (f"<br><b>{html.escape(adres[-1])}</b>" if adres else "")
        strona.insert_htmlbox(fitz.Rect(szer * 0.45, wys * 0.5, szer - 12 * MM, wys - 8 * MM),
                              f"<div style='font-family:sans-serif;font-size:11pt;line-height:1.3'>{linie}</div>")
    wynik = dokument.tobytes(garbage=3, deflate=True)
    dokument.close()
    return wynik


def csv_enadawca(pozycje: list[dict]) -> str:
    """CSV do importu przesylek w aplikacji Elektroniczny Nadawca.

    Szablon importu ustawia sie w e-Nadawcy raz (przypisanie kolumn) - stad
    proste, nazwane kolumny. Separator ";" i kodowanie UTF-8 z BOM, bo tak
    plik bez zmian otwiera tez Excel.
    """
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";", lineterminator="\r\n")
    zapis.writerow(["nazwa_adresata", "ulica", "kod_pocztowy", "miejscowosc", "kraj", "rodzaj",
                    "potwierdzenie_odbioru", "numer_nadania", "identyfikator_nadawcy"])
    for w in pozycje:
        zapis.writerow([w["adresat"], w["ulica"], w["kod"], w["miejscowosc"], "Polska", "list polecony",
                        "TAK" if w["sposob"] == REJESTROWANE[1] else "NIE", w.get("numer_nadania", ""),
                        w.get("_znak", "")])
    return "﻿" + bufor.getvalue()


# --- API -------------------------------------------------------------------

router = APIRouter(prefix="/api/przesylki", tags=["przesylki"])


def _tylko_w_chmurze() -> None:
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie, a dzienniki byłyby zapisane na serwerze.")


def _wykonaj(funkcja, *argumenty, **nazwane):
    _tylko_w_chmurze()
    try:
        return funkcja(*argumenty, **nazwane)
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))
    except ValueError as blad:
        raise HTTPException(400, str(blad))


def _kto(request: Request) -> str:
    """Kto dokonal wpisu - e-mail z logowania (tryb lokalny: pusto)."""
    return str(getattr(request.state, "email", "") or "")


def _pdf(tresc: bytes, nazwa: str) -> Response:
    return Response(tresc, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{nazwa}"', "Cache-Control": "no-store"})


class Wpis(BaseModel):
    data: str
    adresat: str = ""
    ulica: str = ""
    kod: str = ""
    miejscowosc: str = ""
    sposob: str = SPOSOBY[0]
    numer_nadania: str = ""
    data_doreczenia: str = ""
    uwagi: str = ""
    sprawa: str = ""
    repertorium: str = ""
    dokument: str = ""
    kierunek: str = KIERUNKI[0]
    znak_pisma: str = ""
    data_pisma: str = ""
    tresc: str = ""


class Anulowanie(BaseModel):
    powod: str


class Numery(BaseModel):
    numery: dict[str, str]


class Ustawienia(BaseModel):
    nadawca: str = ""
    adres_nadawcy: str = ""


class Wybor(BaseModel):
    pozycje: list[str]
    format: str = "DL"


@router.get("/slowniki")
def slowniki():
    return {"sposoby": SPOSOBY, "rejestrowane": REJESTROWANE, "kierunki": KIERUNKI,
            "formaty_kopert": list(FORMATY_KOPERT), "sledzenie": SLEDZENIE,
            "ksiegi": {k: v["tytul"] for k, v in KSIEGI.items()}}


@router.get("/ustawienia")
def pobierz_ustawienia():
    return _wykonaj(ustawienia)


@router.put("/ustawienia")
def zmien_ustawienia(dane: Ustawienia):
    return _wykonaj(zapisz_ustawienia, dane.model_dump())


@router.get("/ksiazka-nadawcza.pdf")
def ksiazka_nadawcza(dzien: str = ""):
    tresc = _wykonaj(pdf_ksiazki_nadawczej, dzien or date.today().isoformat())
    return _pdf(tresc, f"ksiazka-nadawcza-{dzien or date.today().isoformat()}.pdf")


@router.get("/do-wysylki")
def do_wysylki(dzien: str = ""):
    """Przesylki rejestrowane z dnia (z obu ksiag) - np. do wpisania numerow."""
    dzien = _wykonaj(_data, dzien or date.today().isoformat(), "dzień")
    return [{**w, "ksiega": k} for k, w in _wykonaj(_do_wysylki, dzien)]


@router.get("/{ksiega}")
def lista_wpisow(ksiega: str):
    return _wykonaj(lista, ksiega)


@router.post("/{ksiega}")
def dodaj_wpis(ksiega: str, dane: Wpis, request: Request):
    return _wykonaj(dodaj, ksiega, dane.model_dump(), _kto(request))


@router.put("/{ksiega}/numery")
def wpisz_numery(ksiega: str, dane: Numery, request: Request):
    return {"zmieniono": _wykonaj(ustaw_numery, ksiega, dane.numery, _kto(request))}


@router.get("/{ksiega}/ksiega.pdf")
def wydruk_ksiegi(ksiega: str, od: str = "", do: str = "", od_lp: int = 0, do_lp: int = 0, od_strony: int = 0,
                  podglad: bool = False):
    tresc = _wykonaj(pdf_ksiegi, ksiega, od, do, od_lp, do_lp, od_strony, not podglad)
    return _pdf(tresc, f"{KSIEGI[ksiega]['plik']}.pdf")


def _wybrane(ksiega: str, identyfikatory: list[str]) -> list[dict]:
    wszystkie = {w["id"]: w for w in _wykonaj(lista, ksiega)}
    wynik = []
    for ident in identyfikatory:
        if ident in wszystkie and wszystkie[ident].get("status") != "anulowany":
            w = dict(wszystkie[ident])
            w["_znak"] = f"{'DPD' if ksiega == 'przeslane' else 'DK'} {w['lp']}"
            wynik.append(w)
    return wynik


@router.post("/{ksiega}/koperty.pdf")
def koperty(ksiega: str, dane: Wybor):
    return _pdf(_wykonaj(pdf_kopert, _wybrane(ksiega, dane.pozycje), dane.format), "koperty.pdf")


@router.post("/{ksiega}/e-nadawca.csv")
def eksport_enadawca(ksiega: str, dane: Wybor):
    pozycje = [w for w in _wybrane(ksiega, dane.pozycje) if w.get("sposob") in REJESTROWANE]
    if not pozycje:
        raise HTTPException(400, "Wybierz listy polecone do eksportu")
    return Response(csv_enadawca(pozycje).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="e-nadawca.csv"', "Cache-Control": "no-store"})


@router.put("/{ksiega}/{identyfikator}")
def zmien_wpis(ksiega: str, identyfikator: str, dane: Wpis, request: Request):
    wpis = _wykonaj(zmien, ksiega, identyfikator, dane.model_dump(), _kto(request))
    if not wpis:
        raise HTTPException(404, "Nie ma takiej pozycji")
    return wpis


@router.post("/{ksiega}/{identyfikator}/anuluj")
def anuluj_wpis(ksiega: str, identyfikator: str, dane: Anulowanie, request: Request):
    wpis = _wykonaj(anuluj, ksiega, identyfikator, dane.powod, _kto(request))
    if not wpis:
        raise HTTPException(404, "Nie ma takiej pozycji")
    return wpis
