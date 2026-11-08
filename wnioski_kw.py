"""Wniosek wieczystoksiegowy notariusza - przygotowanie w notarai.

Jak to dziala w prawie (zrodla w docs/ksiegi-i-giif.md):
- notariusz sklada wniosek o wpis wylacznie przez system teleinformatyczny
  (art. 626^4 par. 1 KPC, art. 92 par. 4 PrNot), opatrzony kwalifikowanym
  podpisem elektronicznym,
- system rejestruje wniosek w centralnym repertorium wnioskow
  elektronicznych (REP.C) i w tej chwili automatycznie umieszcza wzmianke
  w ksiedze; numer wniosku to: oznaczenie REP.C, czteroznakowy kod podmiotu
  (NOTA dla notariuszy), kolejny numer i dwie koncowe cyfry roku (par. 68
  rozporzadzenia MS z 15.02.2016 w sprawie zakladania i prowadzenia ksiag
  wieczystych w systemie teleinformatycznym),
- po wplywie do sadu wniosek dostaje numer w dzienniku ksiag wieczystych
  (kod wydzialu, numer dziennika, rok - par. 71),
- podstawa wpisu "akt notarialny" (pole 1.12.1) zawiera m.in. numer rep. A,
  date sporzadzenia, dane notariusza, siedzibe kancelarii.

Czego notarai nie robi: nie podpisuje i nie wysyla. Publicznego API do
skladania wnioskow nie ma. notarai przygotowuje kompletny wniosek (zadania
per dzial ksiegi, uczestnicy, podstawa wpisu, oplata), sprawdza go i daje
gotowy pakiet do portalu (kopiuj-wklej albo pomocnik w przegladarce
notariusza, ktory zatrzymuje sie przed podpisem). Po wyslaniu notariusz
wpisuje numer REP.C - wniosek trafia do repertorium C kancelarii.
"""
import re
from decimal import Decimal

import ekw
import taksa

DZIALY = {
    "I-O": "Dział I-O - oznaczenie nieruchomości",
    "I-Sp": "Dział I-Sp - spis praw związanych z własnością",
    "II": "Dział II - własność i użytkowanie wieczyste",
    "III": "Dział III - prawa, roszczenia i ograniczenia",
    "IV": "Dzial IV - hipoteka",
}

# Rodzaj zadania -> (dzial, klucz oplaty z taksa.OPLATY_SADOWE, opis dla notariusza)
ZADANIA = {
    "zalozenie_kw": ("I-O", "zalozenie_kw", "Założenie księgi wieczystej (np. wyodrębnienie lokalu)"),
    "odlaczenie": ("I-O", "inny_wpis", "Odłączenie działki / zmiana oznaczenia nieruchomości"),
    "wpis_wlasnosci": ("II", "wpis_wlasnosci", "Wpis własności / użytkowania wieczystego"),
    "wpis_wlasnosci_spadek": ("II", "wpis_wlasnosci_spadek",
                              "Wpis własności na podstawie dziedziczenia, działu spadku, zniesienia współwłasności"),
    "wykreslenie_wlasciciela": ("II", None, "Wykreślenie dotychczasowego właściciela (w ramach wpisu własności)"),
    "wpis_sluzebnosci": ("III", "wpis_ograniczonego_prawa", "Wpis służebności / użytkowania / innego ograniczonego prawa"),
    "wpis_roszczenia": ("III", "wpis_roszczenia", "Wpis roszczenia (umowa deweloperska, przedwstępna, art. 16 ukwh)"),
    "wykreslenie_roszczenia": ("III", "inny_wpis", "Wykreślenie roszczenia lub prawa z działu III"),
    "wpis_hipoteki": ("IV", "wpis_hipoteki", "Wpis hipoteki"),
    "wykreslenie_hipoteki": ("IV", "wykreslenie_hipoteki", "Wykreślenie hipoteki"),
    "inne": (None, "inny_wpis", "Inne żądanie - opisz treść"),
}
ROLE = ("wnioskodawca", "uczestnik", "nabywca", "zbywca", "wierzyciel_hipoteczny", "uprawniony")
KOD_NOTARIUSZA = "NOTA"

_REP_C = re.compile(r"^REP\.?\s*C\W*(?P<kod>[A-Z]{4})\W*(?P<numer>\d+)\W*(?P<rok>\d{2})$")


def normalizuj_rep_c(tekst: str) -> str:
    """'rep.c/nota/1234/26' -> 'REP.C/NOTA/1234/26'.

    Rozporzadzenie (par. 68 ust. 2) wymienia sklad numeru, nie separatory;
    w zapisie kancelarii uzywamy ukosnika, tak jak w numerach KW.
    """
    dopasowanie = _REP_C.match(str(tekst or "").strip().upper())
    if not dopasowanie:
        raise ValueError("Numer REP.C: oczekiwano REP.C, kodu podmiotu (NOTA), numeru i 2 cyfr roku, "
                         "np. REP.C/NOTA/1234/26")
    if dopasowanie["kod"] != KOD_NOTARIUSZA:
        raise ValueError("Wniosek notariusza ma w numerze REP.C kod podmiotu NOTA")
    return f"REP.C/{dopasowanie['kod']}/{int(dopasowanie['numer'])}/{dopasowanie['rok']}"


def _zadanie(z: dict) -> dict:
    if not isinstance(z, dict):
        raise ValueError("Każde żądanie: obiekt z polem 'rodzaj'")
    rodzaj = z.get("rodzaj", "")
    if not isinstance(rodzaj, str) or rodzaj not in ZADANIA:
        raise ValueError(f"Nieznany rodzaj żądania: {rodzaj}")
    dzial, oplata, opis = ZADANIA[rodzaj]
    dzial = z.get("dzial") or dzial
    if dzial not in DZIALY:
        raise ValueError(f"Żądanie '{opis}': wskaż dział księgi")
    tresc = str(z.get("tresc", "")).strip()
    if rodzaj == "inne" and not tresc:
        raise ValueError("Żądanie 'inne': opisz treść żądania")
    wynik = {"rodzaj": rodzaj, "dzial": dzial, "opis": opis, "tresc": tresc, "oplata": oplata,
             "na_rzecz": [str(x).strip() for x in z.get("na_rzecz", []) if str(x).strip()],
             "udzial": str(z.get("udzial", "")).strip()}
    if rodzaj == "wpis_hipoteki":
        wynik["suma"] = str(z.get("suma", "")).strip()
        wynik["waluta"] = str(z.get("waluta", "PLN")).strip() or "PLN"
        wynik["rodzaj_hipoteki"] = str(z.get("rodzaj_hipoteki", "umowna")).strip()
    return wynik


def przygotuj(dane: dict) -> dict:
    """Uporzadkowany wniosek + lista brakow + oplata. Nic nie zapisuje."""
    braki = []
    for pole in ("uczestnicy", "zadania", "dokumenty"):
        if not isinstance(dane.get(pole) or [], list):
            raise ValueError(f"{pole}: lista")
    if not all(isinstance(u, dict) for u in dane.get("uczestnicy") or []):
        raise ValueError("Każdy uczestnik: obiekt z polami nazwa, rola, pesel")
    if not isinstance(dane.get("akt") or {}, dict):
        raise ValueError("Podstawa wpisu (akt): obiekt")
    numer_kw = str(dane.get("numer_kw", "")).strip()
    zalozenie = any(isinstance(z, dict) and z.get("rodzaj") == "zalozenie_kw" for z in dane.get("zadania") or [])
    if numer_kw:
        try:
            numer_kw = ekw.normalizuj_numer(numer_kw)
        except ValueError as blad:
            braki.append(f"Numer KW: {blad}")
    elif not zalozenie:
        braki.append("Numer księgi wieczystej (albo żądanie założenia księgi)")
    if zalozenie and not dane.get("ksiega_macierzysta") and not numer_kw:
        braki.append("Założenie KW: numer księgi, z której odłącza się nieruchomość (albo brak księgi - zaznacz)")

    sad = str(dane.get("sad", "")).strip()
    if not sad:
        braki.append("Sąd rejonowy i wydział ksiąg wieczystych")

    uczestnicy = []
    for i, u in enumerate((dane.get("uczestnicy") or []), 1):
        nazwa = str(u.get("nazwa", "")).strip()
        rola = u.get("rola", "uczestnik")
        if rola not in ROLE:
            raise ValueError(f"Nieznana rola uczestnika: {rola}")
        osoba = {"nazwa": nazwa, "rola": rola, "pesel": str(u.get("pesel", "")).strip(),
                 "imiona_rodzicow": str(u.get("imiona_rodzicow", "")).strip(),
                 "adres": str(u.get("adres", "")).strip(), "krs": str(u.get("krs", "")).strip(),
                 "osoba_prawna": bool(u.get("osoba_prawna"))}
        if not nazwa:
            braki.append(f"Uczestnik {i}: imię i nazwisko / nazwa")
        if osoba["osoba_prawna"]:
            if not osoba["krs"]:
                braki.append(f"Uczestnik {i}: numer KRS / REGON")
        elif rola in ("nabywca", "wierzyciel_hipoteczny", "uprawniony", "wnioskodawca") and not osoba["pesel"]:
            # osoba, na rzecz ktorej nastepuje wpis, musi byc oznaczona PESEL (art. 626^2 par. 4 KPC)
            braki.append(f"Uczestnik {i}: PESEL (osoba, na rzecz której ma nastąpić wpis)")
        if rola in ("nabywca", "uprawniony") and not osoba["osoba_prawna"] and not osoba["imiona_rodzicow"]:
            braki.append(f"Uczestnik {i}: imiona rodziców (do wpisu w dziale II/III)")
        uczestnicy.append(osoba)
    if not uczestnicy:
        braki.append("Co najmniej jeden uczestnik")

    zadania = [_zadanie(z) for z in (dane.get("zadania") or [])]
    if not zadania:
        braki.append("Co najmniej jedno żądanie wpisu")
    nazwy = {u["nazwa"] for u in uczestnicy}
    for z in zadania:
        if z["rodzaj"] in ("wpis_wlasnosci", "wpis_wlasnosci_spadek", "wpis_hipoteki",
                           "wpis_sluzebnosci", "wpis_roszczenia") and not z["na_rzecz"]:
            braki.append(f"{z['opis']}: na rzecz kogo")
        for kto in z["na_rzecz"]:
            if kto not in nazwy:
                braki.append(f"{z['opis']}: '{kto}' nie jest uczestnikiem wniosku")
        if z["rodzaj"] == "wpis_hipoteki" and not z.get("suma"):
            braki.append("Wpis hipoteki: suma hipoteki")

    akt = dane.get("akt", {}) or {}
    podstawa = {"rep_a": str(akt.get("rep_a", "")).strip(), "data": str(akt.get("data", "")).strip(),
                "notariusz": str(akt.get("notariusz", "")).strip(),
                "siedziba": str(akt.get("siedziba", "")).strip(),
                "id_wypisu_crewan": str(akt.get("id_wypisu_crewan", "")).strip()}
    for pole, opis in (("rep_a", "numer rep. A"), ("data", "data aktu"), ("notariusz", "notariusz"),
                       ("siedziba", "siedziba kancelarii")):
        if not podstawa[pole]:
            braki.append(f"Podstawa wpisu: {opis}")

    return {"numer_kw": numer_kw, "sad": sad, "uczestnicy": uczestnicy, "zadania": zadania,
            "ksiega_macierzysta": str(dane.get("ksiega_macierzysta", "") or "").strip(),
            "podstawa": podstawa, "dokumenty": [str(d).strip() for d in (dane.get("dokumenty") or []) if str(d).strip()],
            "oplata": oplata(zadania), "braki": braki, "gotowy": not braki}


def oplata(zadania: list[dict]) -> dict:
    """Oplata sadowa od wniosku: kazde zadanie liczy sie osobno (u.k.s.c. art. 42-46)."""
    pozycje, razem = [], Decimal("0")
    for z in zadania:
        if not z["oplata"]:
            continue
        nazwa, kwota = taksa.OPLATY_SADOWE[z["oplata"]]
        pozycje.append({"zadanie": z["opis"], "podstawa": nazwa, "kwota": str(kwota)})
        razem += kwota
    return {"pozycje": pozycje, "razem": str(razem.quantize(Decimal("0.01")))}


def pakiet_portalu(wniosek: dict) -> list[dict]:
    """Kroki w kolejnosci formularza portalu: co i gdzie wpisac (kopiuj-wklej / pomocnik)."""
    kroki = [{"krok": "Sad i ksiega", "pola": {"Sad / wydzial": wniosek["sad"],
                                               "Numer księgi wieczystej": wniosek["numer_kw"]}}]
    for u in wniosek["uczestnicy"]:
        pola = {"Rola": u["rola"], "Nazwa / imie i nazwisko": u["nazwa"]}
        pola.update({k: v for k, v in (("PESEL", u["pesel"]), ("KRS/REGON", u["krs"]),
                                       ("Imiona rodziców", u["imiona_rodzicow"]),
                                       ("Adres", u["adres"])) if v})
        kroki.append({"krok": "Uczestnik", "pola": pola})
    for z in wniosek["zadania"]:
        pola = {"Dzial": DZIALY[z["dzial"]], "Zadanie": z["opis"]}
        if z["tresc"]:
            pola["Treść żądania"] = z["tresc"]
        if z["na_rzecz"]:
            pola["Na rzecz"] = ", ".join(z["na_rzecz"]) + (f" ({z['udzial']})" if z["udzial"] else "")
        if z.get("suma"):
            pola["Suma hipoteki"] = f"{z['suma']} {z['waluta']} ({z['rodzaj_hipoteki']})"
        kroki.append({"krok": "Zadanie", "pola": pola})
    p = wniosek["podstawa"]
    kroki.append({"krok": "Podstawa wpisu - akt notarialny",
                  "pola": {"Numer rep. A": p["rep_a"], "Data sporządzenia": p["data"],
                           "Notariusz": p["notariusz"], "Siedziba kancelarii": p["siedziba"],
                           **({"Identyfikator wypisu w CREWAN": p["id_wypisu_crewan"]} if p["id_wypisu_crewan"] else {})}})
    if wniosek["dokumenty"]:
        kroki.append({"krok": "Dokumenty dołączone", "pola": {f"Dokument {i}": d for i, d in
                                                               enumerate(wniosek["dokumenty"], 1)}})
    kroki.append({"krok": "Opłata sądowa", "pola": {"Razem": f"{wniosek['oplata']['razem']} zł"}})
    kroki.append({"krok": "STOP - podpis i wyslanie", "pola": {
        "Kto": "notariusz, kwalifikowanym podpisem elektronicznym w portalu MS",
        "Potem": "wpisz w notarai numer REP.C - wniosek trafi do repertorium C"}})
    return kroki


def definicje() -> dict:
    return {"dzialy": DZIALY, "zadania": {k: {"dzial": v[0], "oplata": v[1], "opis": v[2]}
                                          for k, v in ZADANIA.items()}, "role": ROLE}


def dane_formularza(wniosek: dict) -> dict:
    """Plaskie wartosci pod `zrodlo` z formularze/wniosek_kw_portal_ms.yaml."""
    dane = {"sad": wniosek["sad"], "numer_kw": wniosek["numer_kw"],
            "rep_a": wniosek["podstawa"]["rep_a"], "data_aktu": wniosek["podstawa"]["data"]}
    for i, u in enumerate(wniosek["uczestnicy"], 1):
        dane[f"uczestnik_{i}_nazwa"], dane[f"uczestnik_{i}_pesel"] = u["nazwa"], u["pesel"]
    for i, z in enumerate(wniosek["zadania"], 1):
        dane[f"zadanie_{i}_dzial"] = z["dzial"]
        dane[f"zadanie_{i}_tresc"] = z["tresc"] or (z["opis"] + (" na rzecz " + ", ".join(z["na_rzecz"])
                                                                  if z["na_rzecz"] else ""))
    return dane
