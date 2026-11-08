"""Ksiegi notarialne kancelarii: repertorium A i P, ksiega depozytowa, dzienniki.

Podstawa: rozporzadzenie Ministra Sprawiedliwosci z 12.04.1991 w sprawie
prowadzenia ksiag notarialnych oraz przekazywania na przechowanie dokumentow
sadom rejonowym (t.j. Dz.U. 2018 poz. 2039), par. 1 ust. 1:
repertorium A, repertorium P, ksiega depozytowa, dziennik przesylanych
dokumentow, dziennik korespondencyjny, skorowidze alfabetyczno-numerowe.
Do tego repertorium C - wnioski wieczystoksiegowe zlozone w systemie
teleinformatycznym (numer REP.C nadaje system MS, par. 68 rozporzadzenia MS
z 15.02.2016); w kancelarii prowadzimy jego odpowiednik z przebiegiem wniosku.

Zasady przeniesione z rozporzadzenia do kodu:
- repertoria numeruje sie w rocznych okresach kalendarzowych (par. 1 ust. 5);
  ksiega depozytowa i oba dzienniki maja numeracje ciagla,
- wpis do repertorium A "niezwlocznie po zakonczeniu czynnosci",
  chronologicznie - numer nadaje serwer, nie czlowiek,
- bledu sie nie wymazuje: poprawka zostawia poprzednia tresc, date, powod
  i osobe (odpowiednik przekreslenia na czerwono z data i podpisem),
- adnotacje o wydaniu wypisow/odpisow ida w "uwagach" pod numerem rep. A,
- naleznosci z rep. A sumuje sie dziennie i miesiecznie,
- skorowidz alfabetyczno-numerowy tylko dla czynnosci z rep. A.

Ksiegi trzymamy w pliku kancelarii (magazyn: dysk albo S3 z warunkowym
zapisem). Dane stron to dane osobowe - nic z nich nie trafia do logow.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import magazyn
import walidacja
import wnioski_kw

PLIK = "ksiegi_notarialne"
PODSTAWA = ("rozporządzenie MS z 12.04.1991 w sprawie prowadzenia ksiąg notarialnych "
            "(t.j. Dz.U. 2018 poz. 2039)")

# Rubryki kazdej ksiegi. "wymagane" sprawdzamy przy wpisie; reszte mozna
# uzupelnic pozniej (np. potwierdzenie odbioru wypisu).
KSIEGI: dict[str, dict] = {
    "repertorium_a": {
        "nazwa": "Repertorium A",
        "skrot": "Rep. A",
        "roczna": True,
        "opis": "Wszystkie czynności notarialne poza protestami, chronologicznie, "
                "niezwłocznie po zakończeniu czynności.",
        "rubryki": {
            "data_czynnosci": "Data czynności",
            "strony": "Imiona i nazwiska / nazwy stron, osób prawnych i przedstawicieli",
            "tresc": "Krótka treść czynności",
            "wartosc_przedmiotu": "Wartość przedmiotu",
            "wynagrodzenie": "Pobrane wynagrodzenie notariusza (netto)",
            "vat": "VAT od wynagrodzenia",
            "oplata_sadowa": "Pobrane opłaty sądowe",
            "oplata_skarbowa": "Pobrana opłata skarbowa",
            "podatek_pcc": "Pobrany podatek od czynności cywilnoprawnych",
            "podatek_sd": "Pobrany podatek od spadków i darowizn",
            "odbior": "Potwierdzenie odbioru dokumentu lub jego przesłania",
        },
        "wymagane": ("data_czynnosci", "strony", "tresc"),
    },
    "repertorium_p": {
        "nazwa": "Repertorium P",
        "skrot": "Rep. P",
        "roczna": True,
        "opis": "Dokumenty oddane do protestu (stosuje się odpowiednio zasady rep. A).",
        "rubryki": {
            "data_czynnosci": "Data oddania do protestu",
            "strony": "Oddający dokument i zobowiązany",
            "tresc": "Oznaczenie dokumentu (weksel, czek) i rodzaj protestu",
            "wartosc_przedmiotu": "Suma wekslowa / czekowa",
            "wynagrodzenie": "Pobrane wynagrodzenie notariusza (netto)",
            "vat": "VAT od wynagrodzenia",
            "odbior": "Potwierdzenie odbioru",
        },
        "wymagane": ("data_czynnosci", "strony", "tresc"),
    },
    "depozytowa": {
        "nazwa": "Księga depozytowa",
        "skrot": "Dep.",
        "roczna": False,
        "opis": "Dokumenty, pieniądze i papiery wartościowe przyjęte do depozytu (par. 4).",
        "rubryki": {
            "data_zlozenia": "Data złożenia",
            "rep_a": "Numer repertorium A",
            "skladajacy": "Imię i nazwisko (nazwa) i adres składającego",
            "przedmiot": "Oznaczenie dokumentu albo wyszczególnienie pieniędzy / papierów",
            "kwota": "Kwota (gdy pieniądze)",
            "waluta": "Waluta",
            "odbiorca": "Osoba, której depozyt ma być wydany",
            "depozyt_sadowy_bank": "Data złożenia do depozytu sądowego lub banku i dowód",
            "data_wydania": "Data wydania",
            "pokwitowanie": "Pokwitowanie odbioru",
        },
        "wymagane": ("data_zlozenia", "skladajacy", "przedmiot", "odbiorca"),
    },
    "repertorium_c": {
        "nazwa": "Repertorium C",
        "skrot": "REP.C",
        "roczna": True,
        "numer_z_systemu": True,
        "opis": "Wnioski wieczystoksięgowe złożone przez notariusza w systemie "
                "teleinformatycznym (art. 92 par. 4 PrNot). Numer REP.C nadaje "
                "system MS przy rejestracji wniosku w centralnym repertorium "
                "wniosków elektronicznych (par. 68 rozporządzenia MS z 15.02.2016).",
        "rubryki": {
            "numer_rep_c": "Numer w centralnym repertorium wniosków elektronicznych",
            "data_zlozenia": "Data złożenia (wysłania z podpisem kwalifikowanym)",
            "rep_a": "Numer repertorium A aktu będącego podstawą wpisu",
            "numer_kw": "Numer księgi wieczystej",
            "sad": "Sąd rejonowy - wydział ksiąg wieczystych",
            "zadania": "Żądania wpisu",
            "oplata_sadowa": "Pobrana opłata sądowa",
            "status": "Stan wniosku",
            "sygnatura_dz_kw": "Numer w dzienniku ksiąg wieczystych (sygnatura sądu)",
            "data_wpisu": "Data dokonania wpisu / orzeczenia",
            "data_doreczenia": "Data doręczenia zawiadomienia",
        },
        "wymagane": ("numer_rep_c", "data_zlozenia", "rep_a", "sad"),
    },
    "dziennik_przesylanych": {
        "nazwa": "Dziennik przesyłanych dokumentów",
        "skrot": "Dz. P.",
        "roczna": False,
        "opis": "Wnioski i pisma przesyłane z urzędu sądom i innym organom - m.in. "
                "wnioski wieczystoksięgowe (art. 92 par. 4 PrNot), wypisy do "
                "organów podatkowych i katastralnych. Wnioski składane w systemie "
                "teleinformatycznym idą do repertorium C.",
        "rubryki": {
            "data": "Data przesłania",
            "adresat": "Sad / organ",
            "rodzaj": "Rodzaj pisma (np. wniosek o wpis w KW)",
            "rep_a": "Numer repertorium A",
            "numer_kw": "Numer księgi wieczystej (gdy dotyczy)",
            "identyfikator": "Identyfikator / sygnatura nadana przez system lub organ",
            "kanal": "Kanał (system teleinformatyczny / poczta / osobiście)",
        },
        "wymagane": ("data", "adresat", "rodzaj"),
    },
    "dziennik_korespondencyjny": {
        "nazwa": "Dziennik korespondencyjny",
        "skrot": "Dz. K.",
        "roczna": False,
        "opis": "Pozostałe pisma wysyłane i wpływające do kancelarii.",
        "rubryki": {
            "data": "Data",
            "kierunek": "Wplyw / wysylka",
            "kontrahent": "Od kogo / do kogo",
            "tresc": "Krótka treść pisma",
            "rep_a": "Związany numer repertorium A",
        },
        "wymagane": ("data", "kierunek", "kontrahent", "tresc"),
    },
}

KWOTY = ("wartosc_przedmiotu", "wynagrodzenie", "vat", "oplata_sadowa",
         "oplata_skarbowa", "podatek_pcc", "podatek_sd", "kwota")
NALEZNOSCI = ("wynagrodzenie", "vat", "oplata_sadowa", "oplata_skarbowa", "podatek_pcc", "podatek_sd")
STATUSY_WNIOSKU_KW = ("przygotowany", "zlozony", "w_sadzie", "wpis_dokonany", "zwrot", "oddalony", "odrzucony", "cofniety")


def _pusty() -> dict:
    return {nazwa: [] for nazwa in KSIEGI}


def _ksiega(nazwa: str) -> dict:
    if nazwa not in KSIEGI:
        raise ValueError(f"Nieznana księga: {nazwa}")
    return KSIEGI[nazwa]


def _data(tekst: str, pole: str) -> str:
    try:
        return date.fromisoformat(str(tekst)[:10]).isoformat()
    except ValueError:
        raise ValueError(f"{pole}: podaj date RRRR-MM-DD") from None


def _kwota(wartosc, pole: str) -> str:
    if wartosc in (None, ""):
        return ""
    try:
        liczba = Decimal(str(wartosc).replace(" ", "").replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"{pole}: niepoprawna kwota") from None
    if liczba < 0:
        raise ValueError(f"{pole}: kwota nie może być ujemna")
    return str(liczba.quantize(Decimal("0.01")))


def _strony(strony) -> list[dict]:
    if isinstance(strony, str):
        # Szybki wpis z formularza: "Jan Sobczak, sprzedajacy, 80010112345; Anna Pawlak, kupujaca"
        lista_stron = []
        for segment in strony.split(";"):
            czesci = [c.strip() for c in segment.split(",") if c.strip()]
            if not czesci:
                continue
            pesel = next((c for c in czesci[1:] if c.isdigit() and len(c) == 11), "")
            rola = next((c for c in czesci[1:] if c != pesel), "")
            lista_stron.append({"nazwa": czesci[0], "rola": rola, "pesel": pesel})
        strony = lista_stron
    if not isinstance(strony, list) or not all(isinstance(s, dict) for s in strony):
        raise ValueError("Strony: lista osób albo tekst 'Imię Nazwisko, rola, PESEL; ...'")
    wynik = []
    for strona in strony or []:
        nazwa = str(strona.get("nazwa", "")).strip()
        if not nazwa:
            raise ValueError("Każda strona musi mieć imię i nazwisko albo nazwę")
        pesel = str(strona.get("pesel", "") or "").strip()
        if pesel and not walidacja.pesel(pesel)[0]:
            raise ValueError(f"Strona {nazwa}: niepoprawny PESEL (suma kontrolna)")
        wynik.append({"nazwa": nazwa, "rola": str(strona.get("rola", "")).strip(),
                      "pesel": str(strona.get("pesel", "")).strip(),
                      "reprezentowany": str(strona.get("reprezentowany", "")).strip()})
    return wynik


def _oczysc(nazwa: str, dane: dict, czesciowo: bool = False) -> dict:
    ksiega = _ksiega(nazwa)
    wynik = {}
    for pole in ksiega["rubryki"]:
        if pole not in dane:
            continue
        wartosc = dane[pole]
        if pole == "strony":
            wartosc = _strony(wartosc)
        elif pole in KWOTY:
            wartosc = _kwota(wartosc, ksiega["rubryki"][pole])
        elif pole == "zadania":
            wartosc = [str(z).strip() for z in (wartosc or []) if str(z).strip()]
        elif pole.startswith("data"):
            wartosc = _data(wartosc, ksiega["rubryki"][pole]) if wartosc else ""
        else:
            wartosc = str(wartosc or "").strip()
        wynik[pole] = wartosc
    if not czesciowo:
        brak = [ksiega["rubryki"][p] for p in ksiega["wymagane"] if not wynik.get(p)]
        if brak:
            raise ValueError("Brakuje: " + ", ".join(brak))
    return wynik


def _rok(wpis: dict) -> int:
    for pole in ("data_czynnosci", "data_zlozenia", "data"):
        if wpis.get(pole):
            return int(wpis[pole][:4])
    return int(wpis["utworzono"][:4])


def oznaczenie(nazwa: str, wpis: dict) -> str:
    ksiega = KSIEGI[nazwa]
    if ksiega["roczna"]:
        return f"{ksiega['skrot']} nr {wpis['numer']}/{wpis['rok']}"
    return f"{ksiega['skrot']} nr {wpis['numer']}"


def _nastepny_numer(wpisy: list[dict], nazwa: str, rok: int) -> int:
    if KSIEGI[nazwa]["roczna"]:
        numery = [w["numer"] for w in wpisy if w["rok"] == rok]
    else:
        numery = [w["numer"] for w in wpisy]
    return max(numery, default=0) + 1


def dodaj(nazwa: str, dane: dict, kto: str = "") -> dict:
    """Nowy wpis z numerem nadanym przez serwer (nastepny w roku lub ciagly)."""
    tresc = _oczysc(nazwa, dane)
    teraz = datetime.now().isoformat(timespec="seconds")

    def zmiana(wszystko):
        wpisy = wszystko.setdefault(nazwa, [])
        wpis = {"id": uuid.uuid4().hex[:12], **tresc, "utworzono": teraz, "kto": kto,
                "uwagi": [], "korekty": []}
        wpis["rok"] = _rok(wpis)
        if KSIEGI[nazwa]["roczna"] and not KSIEGI[nazwa].get("numer_z_systemu"):
            ostatni = [w for w in wpisy if w["rok"] == wpis["rok"]]
            pole = "data_czynnosci"
            if ostatni and tresc.get(pole) and tresc[pole] < max(w.get(pole, "") for w in ostatni):
                raise ValueError("Repertorium prowadzi się chronologicznie - w tym roku jest "
                                 "już wpis z późniejszą datą czynności")
        wpis["numer"] = _nastepny_numer(wpisy, nazwa, wpis["rok"])
        if KSIEGI[nazwa].get("numer_z_systemu"):
            numer = wnioski_kw.normalizuj_rep_c(tresc["numer_rep_c"])
            if any(w.get("numer_rep_c") == numer for w in wpisy):
                raise ValueError(f"Wniosek {numer} jest już w repertorium C")
            wpis["numer_rep_c"] = wpis["oznaczenie"] = numer
        else:
            wpis["oznaczenie"] = oznaczenie(nazwa, wpis)
        if nazwa == "repertorium_a":
            wpis["wnioski_kw"] = []
        wpisy.append(wpis)
        return wpis
    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, _pusty())


def lista(nazwa: str, rok: int | None = None) -> list[dict]:
    _ksiega(nazwa)
    wpisy = magazyn.wczytaj_plik_kancelarii(PLIK, _pusty()).get(nazwa, [])
    if rok is not None:
        wpisy = [w for w in wpisy if w["rok"] == rok]
    return sorted(wpisy, key=lambda w: (w["rok"], w["numer"]))


def wpis(nazwa: str, identyfikator: str) -> dict | None:
    return next((w for w in lista(nazwa) if w["id"] == identyfikator), None)


def _zmien_wpis(nazwa: str, identyfikator: str, funkcja):
    def zmiana(wszystko):
        for w in wszystko.setdefault(nazwa, []):
            if w["id"] == identyfikator:
                return funkcja(w)
        raise LookupError("Nie ma takiego wpisu")
    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, _pusty())


def popraw(nazwa: str, identyfikator: str, zmiany: dict, powod: str, kto: str = "") -> dict:
    """Poprawka bez wymazywania: poprzednia tresc zostaje w historii korekt.

    Numer, rok i oznaczenie sa nienaruszalne - poprawka nie przenumerowuje ksiegi.
    """
    if not (powod or "").strip():
        raise ValueError("Podaj powód poprawki")
    nowe = _oczysc(nazwa, zmiany, czesciowo=True)
    if not nowe:
        raise ValueError("Brak rubryk do poprawienia")

    def funkcja(w):
        poprzednie = {pole: w.get(pole, "") for pole in nowe}
        w.update(nowe)
        brak = [KSIEGI[nazwa]["rubryki"][p] for p in KSIEGI[nazwa]["wymagane"] if not w.get(p)]
        if brak:
            raise ValueError("Poprawka nie może usunąć: " + ", ".join(brak))
        w["korekty"].append({"czas": datetime.now().isoformat(timespec="seconds"), "kto": kto,
                             "powod": powod.strip(), "bylo": poprzednie, "jest": nowe})
        return w
    return _zmien_wpis(nazwa, identyfikator, funkcja)


def dodaj_uwage(nazwa: str, identyfikator: str, tresc: str, kto: str = "") -> dict:
    """Rubryka "uwagi": np. wydanie wypisu, odpisu, wyciagu - komu i kiedy."""
    if not (tresc or "").strip():
        raise ValueError("Uwaga nie może być pusta")

    def funkcja(w):
        w["uwagi"].append({"czas": datetime.now().isoformat(timespec="seconds"),
                           "kto": kto, "tresc": tresc.strip()})
        return w
    return _zmien_wpis(nazwa, identyfikator, funkcja)


def sumy(rok: int, miesiac: int | None = None, nazwa: str = "repertorium_a") -> dict:
    """Naleznosci z repertorium - sumy dzienne i za okres (rok albo miesiac)."""
    wpisy = [w for w in lista(nazwa, rok)
             if miesiac is None or int(w.get("data_czynnosci", "0000-00")[5:7]) == miesiac]
    pola = [p for p in NALEZNOSCI if p in KSIEGI[nazwa]["rubryki"]]
    zero = {p: Decimal("0.00") for p in pola}
    dzienne: dict[str, dict] = {}
    razem = dict(zero)
    for w in wpisy:
        dzien = dzienne.setdefault(w["data_czynnosci"], dict(zero))
        for p in pola:
            kwota = Decimal(w.get(p) or "0")
            dzien[p] += kwota
            razem[p] += kwota
    tekst = lambda d: {p: str(v) for p, v in d.items()}  # noqa: E731
    return {"rok": rok, "miesiac": miesiac, "liczba_wpisow": len(wpisy),
            "dzienne": {d: tekst(s) for d, s in sorted(dzienne.items())},
            "razem": tekst(razem)}


def skorowidz(rok: int) -> list[dict]:
    """Skorowidz alfabetyczno-numerowy do repertorium A (nazwisko -> numery)."""
    indeks: dict[str, list[str]] = {}
    for w in lista("repertorium_a", rok):
        for strona in w.get("strony", []):
            nazwa = strona["nazwa"]
            klucz = nazwa.split()[-1] if " " in nazwa and not strona.get("rola") == "osoba_prawna" else nazwa
            indeks.setdefault(f"{klucz}|{nazwa}", []).append(w["oznaczenie"])
    wynik = []
    for klucz in sorted(indeks, key=lambda k: k.casefold()):
        nazwa = klucz.split("|", 1)[1]
        wynik.append({"nazwa": nazwa, "numery": sorted(set(indeks[klucz]), key=indeks[klucz].index)})
    return wynik


def zarejestruj_wniosek_kw(identyfikator: str, dane: dict, kto: str = "") -> dict:
    """Wniosek wieczystoksiegowy przygotowany do czynnosci z rep. A.

    Tresc przechodzi przez wnioski_kw.przygotuj() (zadania, uczestnicy,
    podstawa wpisu, oplata, braki). Podstawa wpisu i strony uzupelniaja sie
    z wpisu rep. A. Status "przygotowany" - istnieje tylko w notarai.
    """
    rep = wpis("repertorium_a", identyfikator)
    if rep is None:
        raise LookupError("Nie ma takiego wpisu")
    akt = {"rep_a": rep["oznaczenie"], "data": rep["data_czynnosci"], **(dane.get("akt") or {})}
    uczestnicy = dane.get("uczestnicy") or [{"nazwa": s["nazwa"], "pesel": s.get("pesel", ""),
                                             "rola": "uczestnik"} for s in rep.get("strony", [])]
    przygotowany = wnioski_kw.przygotuj({**dane, "akt": akt, "uczestnicy": uczestnicy})
    wniosek = {"id": uuid.uuid4().hex[:12], "status": "przygotowany", **przygotowany,
               "utworzono": datetime.now().isoformat(timespec="seconds"), "kto": kto}

    def funkcja(w):
        w.setdefault("wnioski_kw", []).append(wniosek)
        return w
    return _zmien_wpis("repertorium_a", identyfikator, funkcja)


def zmien_wniosek_kw(identyfikator: str, wniosek_id: str, dane: dict, kto: str = "") -> dict:
    """Poprawka tresci przygotowanego wniosku (przed zlozeniem)."""
    rep = wpis("repertorium_a", identyfikator)
    stary = next((wn for wn in (rep or {}).get("wnioski_kw", []) if wn["id"] == wniosek_id), None)
    if stary is None:
        raise LookupError("Nie ma takiego wniosku")
    if stary["status"] != "przygotowany":
        raise ValueError("Złożonego wniosku nie zmienia się - zmiany idą przez sąd")
    zrodlo = {"numer_kw": stary["numer_kw"], "sad": stary["sad"], "uczestnicy": stary["uczestnicy"],
              "zadania": stary["zadania"], "akt": stary["podstawa"], "dokumenty": stary["dokumenty"]}
    zrodlo.update({k: v for k, v in dane.items() if k in zrodlo})
    nowy = wnioski_kw.przygotuj(zrodlo)

    def funkcja(w):
        for wn in w["wnioski_kw"]:
            if wn["id"] == wniosek_id:
                wn.update(nowy)
                return w
    return _zmien_wpis("repertorium_a", identyfikator, funkcja)


def pakiet_wniosku_kw(identyfikator: str, wniosek_id: str) -> dict:
    rep = wpis("repertorium_a", identyfikator)
    wn = next((x for x in (rep or {}).get("wnioski_kw", []) if x["id"] == wniosek_id), None)
    if wn is None:
        raise LookupError("Nie ma takiego wniosku")
    return {"gotowy": wn["gotowy"], "braki": wn["braki"], "kroki": wnioski_kw.pakiet_portalu(wn),
            "formularz": {"system": "wniosek_kw_portal_ms", "dane": wnioski_kw.dane_formularza(wn)}}


def zmien_status_wniosku_kw(identyfikator: str, wniosek_id: str, dane: dict, kto: str = "") -> dict:
    """Przebieg wniosku. Przy "zlozony" wymagany numer REP.C - powstaje wpis w repertorium C."""
    status = dane.get("status")
    if status not in STATUSY_WNIOSKU_KW or status == "przygotowany":
        raise ValueError(f"Niedozwolony status wniosku: {status}")
    rep = wpis("repertorium_a", identyfikator)
    wn = next((x for x in (rep or {}).get("wnioski_kw", []) if x["id"] == wniosek_id), None)
    if wn is None:
        raise LookupError("Nie ma takiego wniosku")

    if wn["status"] == "przygotowany":
        if status != "zlozony":
            raise ValueError("Najpierw oznacz wniosek jako złożony (z numerem REP.C)")
        if not wn["gotowy"]:
            raise ValueError("Wniosek ma braki: " + "; ".join(wn["braki"]))
        if not dane.get("numer_rep_c") or not dane.get("data_zlozenia"):
            raise ValueError("Podaj numer REP.C i date złożenia z systemu MS")
        numer = wnioski_kw.normalizuj_rep_c(dane["numer_rep_c"])
        rep_c = dodaj("repertorium_c", {
            "numer_rep_c": numer, "data_zlozenia": dane["data_zlozenia"], "rep_a": rep["oznaczenie"],
            "numer_kw": wn["numer_kw"], "sad": wn["sad"],
            "zadania": [z["opis"] + (f": {z['tresc']}" if z["tresc"] else "") for z in wn["zadania"]],
            "oplata_sadowa": dane.get("oplata_sadowa") or wn["oplata"]["razem"], "status": "zlozony",
        }, kto)
        zmiany = {"status": "zlozony", "numer_rep_c": numer, "rep_c_id": rep_c["id"],
                  "data_zlozenia": rep_c["data_zlozenia"]}
    else:
        if wn["status"] in ("wpis_dokonany", "oddalony", "odrzucony", "cofniety") and status != wn["status"]:
            raise ValueError("Wniosek jest już zakończony")
        zmiany = {"status": status}
        rubryki = {"status": status}
        for pole in ("sygnatura_dz_kw", "data_wpisu", "data_doreczenia"):
            if dane.get(pole):
                rubryki[pole] = dane[pole]
        popraw("repertorium_c", wn["rep_c_id"], rubryki, f"przebieg wniosku: {status}", kto)
        zmiany.update({k: v for k, v in rubryki.items() if k != "status"})

    def funkcja(w):
        for x in w["wnioski_kw"]:
            if x["id"] == wniosek_id:
                x.update(zmiany)
                x.setdefault("historia", []).append(
                    {"czas": datetime.now().isoformat(timespec="seconds"), "kto": kto, "status": status})
                return w
    return _zmien_wpis("repertorium_a", identyfikator, funkcja)


def definicje() -> dict:
    return {"podstawa": PODSTAWA, "ksiegi": KSIEGI, "statusy_wniosku_kw": STATUSY_WNIOSKU_KW,
            "wniosek_kw": wnioski_kw.definicje()}


# ---------------------------------------------------------------- wydruk i eksport

def _tekst_rubryki(wpis: dict, pole: str) -> str:
    wartosc = wpis.get(pole, "")
    if pole == "strony":
        return "; ".join(s["nazwa"] + (f" ({s['rola']})" if s.get("rola") else "") +
                         (f", PESEL {s['pesel']}" if s.get("pesel") else "") for s in wartosc or [])
    if isinstance(wartosc, list):
        return "; ".join(str(x) for x in wartosc)
    return str(wartosc or "")


def wiersze(nazwa: str, rok: int | None = None) -> tuple[list[str], list[list[str]]]:
    """Naglowki i wiersze ksiegi w kolejnosci rubryk z rozporzadzenia (+ uwagi, poprawki)."""
    ksiega = _ksiega(nazwa)
    naglowki = ["Nr"] + list(ksiega["rubryki"].values()) + ["Uwagi", "Poprawki"]
    dane = []
    for w in lista(nazwa, rok):
        uwagi = "; ".join(f"{u['czas'][:10]}: {u['tresc']}" for u in w.get("uwagi", []))
        poprawki = "; ".join(
            f"{k['czas'][:10]} " + ", ".join(f"{ksiega['rubryki'].get(p, p)}: było \"{_tekst_rubryki(k['bylo'], p)}\""
                                            for p in k["bylo"])
            + f" ({k['powod']}{', ' + k['kto'] if k.get('kto') else ''})" for k in w.get("korekty", []))
        dane.append([w["oznaczenie"]] + [_tekst_rubryki(w, p) for p in ksiega["rubryki"]] + [uwagi, poprawki])
    return naglowki, dane


def csv_ksiegi(nazwa: str, rok: int | None = None) -> str:
    import csv
    import io
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";")
    naglowki, dane = wiersze(nazwa, rok)
    zapis.writerow(naglowki)
    for wiersz in dane:
        # Excel wykonuje komorki zaczynajace sie od =, +, -, @ - neutralizujemy.
        zapis.writerow(["'" + k if k[:1] in ("=", "+", "-", "@") else k for k in wiersz])
    return "﻿" + bufor.getvalue()


def wydruk_html(nazwa: str, rok: int | None = None, kancelaria: str = "") -> str:
    """Strona do wydruku (A4 poziomo): ksiega za rok, z poprawkami i sumami miesiecznymi."""
    from html import escape
    ksiega = _ksiega(nazwa)
    naglowki, dane = wiersze(nazwa, rok)
    tytul = f"{ksiega['nazwa']}{f' - rok {rok}' if rok else ''}"
    tabela = "".join(f"<th>{escape(n)}</th>" for n in naglowki)
    tresc = "".join("<tr>" + "".join(f"<td>{escape(k)}</td>" for k in w) + "</tr>" for w in dane)
    podsumowanie = ""
    if nazwa == "repertorium_a" and rok:
        miesiace = []
        for m in range(1, 13):
            s = sumy(rok, m)
            if s["liczba_wpisow"]:
                miesiace.append("<tr><td>" + f"{m:02d}/{rok}</td><td>{s['liczba_wpisow']}</td>" +
                                "".join(f"<td>{escape(s['razem'][p])}</td>" for p in s["razem"]) + "</tr>")
        if miesiace:
            kolumny = "".join(f"<th>{escape(ksiega['rubryki'][p])}</th>" for p in sumy(rok)["razem"])
            podsumowanie = (f"<h2>Sumy miesięczne należności</h2><table><tr><th>Miesiąc</th><th>Wpisów</th>{kolumny}</tr>"
                            + "".join(miesiace) + "</table>")
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>{escape(tytul)}</title>
<style>@page{{size:A4 landscape;margin:12mm}}body{{font:10px/1.35 Georgia,serif;color:#000}}
h1{{font-size:15px;margin:0 0 4px}}p{{margin:0 0 8px}}table{{border-collapse:collapse;width:100%;margin-bottom:12px}}
th,td{{border:1px solid #000;padding:3px;vertical-align:top;text-align:left}}th{{background:#eee}}
tr{{page-break-inside:avoid}}@media screen{{body{{max-width:1200px;margin:16px auto;padding:0 16px}}}}</style></head>
<body><h1>{escape(tytul)}</h1><p>{escape(kancelaria)} {escape(PODSTAWA if nazwa != 'repertorium_c' else 'rozporządzenie MS z 15.02.2016 (Dz.U. poz. 312), par. 68')}.
Wydruk z notarai: {datetime.now().strftime('%d.%m.%Y %H:%M')}. Wpisów: {len(dane)}.</p>
<table><tr>{tabela}</tr>{tresc}</table>{podsumowanie}
<script>window.onload=()=>window.print()</script></body></html>"""
