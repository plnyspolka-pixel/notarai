"""Ksiegi notarialne kancelarii: repertorium A i P, ksiega depozytowa, dzienniki.

Podstawa: rozporzadzenie Ministra Sprawiedliwosci z 12.04.1991 w sprawie
prowadzenia ksiag notarialnych oraz przekazywania na przechowanie dokumentow
sadom rejonowym (t.j. Dz.U. 2018 poz. 2039), par. 1 ust. 1:
repertorium A, repertorium P, ksiega depozytowa, dziennik przesylanych
dokumentow, dziennik korespondencyjny, skorowidze alfabetyczno-numerowe.

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

PLIK = "ksiegi_notarialne"
PODSTAWA = ("rozporzadzenie MS z 12.04.1991 w sprawie prowadzenia ksiag notarialnych "
            "(t.j. Dz.U. 2018 poz. 2039)")

# Rubryki kazdej ksiegi. "wymagane" sprawdzamy przy wpisie; reszte mozna
# uzupelnic pozniej (np. potwierdzenie odbioru wypisu).
KSIEGI: dict[str, dict] = {
    "repertorium_a": {
        "nazwa": "Repertorium A",
        "skrot": "Rep. A",
        "roczna": True,
        "opis": "Wszystkie czynnosci notarialne poza protestami, chronologicznie, "
                "niezwlocznie po zakonczeniu czynnosci.",
        "rubryki": {
            "data_czynnosci": "Data czynnosci",
            "strony": "Imiona i nazwiska / nazwy stron, osob prawnych i przedstawicieli",
            "tresc": "Krotka tresc czynnosci",
            "wartosc_przedmiotu": "Wartosc przedmiotu",
            "wynagrodzenie": "Pobrane wynagrodzenie notariusza (netto)",
            "vat": "VAT od wynagrodzenia",
            "oplata_sadowa": "Pobrane oplaty sadowe",
            "oplata_skarbowa": "Pobrana oplata skarbowa",
            "podatek_pcc": "Pobrany podatek od czynnosci cywilnoprawnych",
            "podatek_sd": "Pobrany podatek od spadkow i darowizn",
            "odbior": "Potwierdzenie odbioru dokumentu lub jego przeslania",
        },
        "wymagane": ("data_czynnosci", "strony", "tresc"),
    },
    "repertorium_p": {
        "nazwa": "Repertorium P",
        "skrot": "Rep. P",
        "roczna": True,
        "opis": "Dokumenty oddane do protestu (stosuje sie odpowiednio zasady rep. A).",
        "rubryki": {
            "data_czynnosci": "Data oddania do protestu",
            "strony": "Oddajacy dokument i zobowiazany",
            "tresc": "Oznaczenie dokumentu (weksel, czek) i rodzaj protestu",
            "wartosc_przedmiotu": "Suma wekslowa / czekowa",
            "wynagrodzenie": "Pobrane wynagrodzenie notariusza (netto)",
            "vat": "VAT od wynagrodzenia",
            "odbior": "Potwierdzenie odbioru",
        },
        "wymagane": ("data_czynnosci", "strony", "tresc"),
    },
    "depozytowa": {
        "nazwa": "Ksiega depozytowa",
        "skrot": "Dep.",
        "roczna": False,
        "opis": "Dokumenty, pieniadze i papiery wartosciowe przyjete do depozytu (par. 4).",
        "rubryki": {
            "data_zlozenia": "Data zlozenia",
            "rep_a": "Numer repertorium A",
            "skladajacy": "Imie i nazwisko (nazwa) i adres skladajacego",
            "przedmiot": "Oznaczenie dokumentu albo wyszczegolnienie pieniedzy / papierow",
            "kwota": "Kwota (gdy pieniadze)",
            "waluta": "Waluta",
            "odbiorca": "Osoba, ktorej depozyt ma byc wydany",
            "depozyt_sadowy_bank": "Data zlozenia do depozytu sadowego lub banku i dowod",
            "data_wydania": "Data wydania",
            "pokwitowanie": "Pokwitowanie odbioru",
        },
        "wymagane": ("data_zlozenia", "skladajacy", "przedmiot", "odbiorca"),
    },
    "dziennik_przesylanych": {
        "nazwa": "Dziennik przesylanych dokumentow",
        "skrot": "Dz. P.",
        "roczna": False,
        "opis": "Wnioski i pisma przesylane z urzedu sadom i innym organom - m.in. "
                "wnioski wieczystoksiegowe (art. 92 par. 4 PrNot), wypisy do "
                "organow podatkowych i katastralnych.",
        "rubryki": {
            "data": "Data przeslania",
            "adresat": "Sad / organ",
            "rodzaj": "Rodzaj pisma (np. wniosek o wpis w KW)",
            "rep_a": "Numer repertorium A",
            "numer_kw": "Numer ksiegi wieczystej (gdy dotyczy)",
            "identyfikator": "Identyfikator / sygnatura nadana przez system lub organ",
            "kanal": "Kanal (system teleinformatyczny / poczta / osobiscie)",
        },
        "wymagane": ("data", "adresat", "rodzaj"),
    },
    "dziennik_korespondencyjny": {
        "nazwa": "Dziennik korespondencyjny",
        "skrot": "Dz. K.",
        "roczna": False,
        "opis": "Pozostale pisma wysylane i wplywajace do kancelarii.",
        "rubryki": {
            "data": "Data",
            "kierunek": "Wplyw / wysylka",
            "kontrahent": "Od kogo / do kogo",
            "tresc": "Krotka tresc pisma",
            "rep_a": "Zwiazany numer repertorium A",
        },
        "wymagane": ("data", "kierunek", "kontrahent", "tresc"),
    },
}

KWOTY = ("wartosc_przedmiotu", "wynagrodzenie", "vat", "oplata_sadowa",
         "oplata_skarbowa", "podatek_pcc", "podatek_sd", "kwota")
NALEZNOSCI = ("wynagrodzenie", "vat", "oplata_sadowa", "oplata_skarbowa", "podatek_pcc", "podatek_sd")
STATUSY_WNIOSKU_KW = ("przygotowany", "zlozony", "wpis_dokonany", "zwrot", "oddalony")


def _pusty() -> dict:
    return {nazwa: [] for nazwa in KSIEGI}


def _ksiega(nazwa: str) -> dict:
    if nazwa not in KSIEGI:
        raise ValueError(f"Nieznana ksiega: {nazwa}")
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
        raise ValueError(f"{pole}: kwota nie moze byc ujemna")
    return str(liczba.quantize(Decimal("0.01")))


def _strony(strony) -> list[dict]:
    if isinstance(strony, str):
        strony = [{"nazwa": s.strip()} for s in strony.split(";") if s.strip()]
    wynik = []
    for strona in strony or []:
        nazwa = str(strona.get("nazwa", "")).strip()
        if not nazwa:
            raise ValueError("Kazda strona musi miec imie i nazwisko albo nazwe")
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
        if KSIEGI[nazwa]["roczna"]:
            ostatni = [w for w in wpisy if w["rok"] == wpis["rok"]]
            pole = "data_czynnosci"
            if ostatni and tresc.get(pole) and tresc[pole] < max(w.get(pole, "") for w in ostatni):
                raise ValueError("Repertorium prowadzi sie chronologicznie - w tym roku jest "
                                 "juz wpis z pozniejsza data czynnosci")
        wpis["numer"] = _nastepny_numer(wpisy, nazwa, wpis["rok"])
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
        raise ValueError("Podaj powod poprawki")
    nowe = _oczysc(nazwa, zmiany, czesciowo=True)
    if not nowe:
        raise ValueError("Brak rubryk do poprawienia")

    def funkcja(w):
        poprzednie = {pole: w.get(pole, "") for pole in nowe}
        w.update(nowe)
        brak = [KSIEGI[nazwa]["rubryki"][p] for p in KSIEGI[nazwa]["wymagane"] if not w.get(p)]
        if brak:
            raise ValueError("Poprawka nie moze usunac: " + ", ".join(brak))
        w["korekty"].append({"czas": datetime.now().isoformat(timespec="seconds"), "kto": kto,
                             "powod": powod.strip(), "bylo": poprzednie, "jest": nowe})
        return w
    return _zmien_wpis(nazwa, identyfikator, funkcja)


def dodaj_uwage(nazwa: str, identyfikator: str, tresc: str, kto: str = "") -> dict:
    """Rubryka "uwagi": np. wydanie wypisu, odpisu, wyciagu - komu i kiedy."""
    if not (tresc or "").strip():
        raise ValueError("Uwaga nie moze byc pusta")

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
    """Wniosek wieczystoksiegowy do czynnosci z rep. A.

    Status "przygotowany" - tylko w notarai. Przy "zlozony" (po wyslaniu z
    systemu teleinformatycznego MS z podpisem kwalifikowanym) automatycznie
    powstaje wpis w dzienniku przesylanych dokumentow.
    """
    numer_kw = str(dane.get("numer_kw", "")).strip().upper()
    if not numer_kw:
        raise ValueError("Podaj numer ksiegi wieczystej")
    status = dane.get("status", "przygotowany")
    if status not in STATUSY_WNIOSKU_KW:
        raise ValueError(f"Nieznany status wniosku: {status}")
    if status == "zlozony" and not dane.get("data_zlozenia"):
        raise ValueError("Podaj date zlozenia wniosku")
    wniosek = {"id": uuid.uuid4().hex[:12], "numer_kw": numer_kw, "status": status,
               "zadanie": str(dane.get("zadanie", "")).strip(),
               "sad": str(dane.get("sad", "")).strip(),
               "data_zlozenia": _data(dane["data_zlozenia"], "Data zlozenia") if dane.get("data_zlozenia") else "",
               "identyfikator": str(dane.get("identyfikator", "")).strip(),
               "utworzono": datetime.now().isoformat(timespec="seconds"), "kto": kto}

    def funkcja(w):
        w.setdefault("wnioski_kw", []).append(wniosek)
        return w
    rep = _zmien_wpis("repertorium_a", identyfikator, funkcja)
    if status == "zlozony":
        _do_dziennika(rep, wniosek, kto)
    return rep


def zmien_status_wniosku_kw(identyfikator: str, wniosek_id: str, dane: dict, kto: str = "") -> dict:
    status = dane.get("status")
    if status not in STATUSY_WNIOSKU_KW:
        raise ValueError(f"Nieznany status wniosku: {status}")
    stan = {}

    def funkcja(w):
        for wn in w.get("wnioski_kw", []):
            if wn["id"] == wniosek_id:
                stan["byl"] = wn["status"]
                if status == "zlozony" and not (dane.get("data_zlozenia") or wn["data_zlozenia"]):
                    raise ValueError("Podaj date zlozenia wniosku")
                wn["status"] = status
                for pole in ("identyfikator", "sad"):
                    if dane.get(pole):
                        wn[pole] = str(dane[pole]).strip()
                if dane.get("data_zlozenia"):
                    wn["data_zlozenia"] = _data(dane["data_zlozenia"], "Data zlozenia")
                stan["wniosek"] = dict(wn)
                return w
        raise LookupError("Nie ma takiego wniosku")
    rep = _zmien_wpis("repertorium_a", identyfikator, funkcja)
    if status == "zlozony" and stan["byl"] == "przygotowany":
        _do_dziennika(rep, stan["wniosek"], kto)
    return rep


def _do_dziennika(rep: dict, wniosek: dict, kto: str) -> None:
    dodaj("dziennik_przesylanych", {
        "data": wniosek["data_zlozenia"],
        "adresat": wniosek["sad"] or "Sad rejonowy - wydzial ksiag wieczystych",
        "rodzaj": "Wniosek o wpis w ksiedze wieczystej",
        "rep_a": rep["oznaczenie"], "numer_kw": wniosek["numer_kw"],
        "identyfikator": wniosek["identyfikator"],
        "kanal": "system teleinformatyczny MS (art. 92 par. 4 PrNot)",
    }, kto)


def definicje() -> dict:
    return {"podstawa": PODSTAWA, "ksiegi": KSIEGI, "statusy_wniosku_kw": STATUSY_WNIOSKU_KW}
