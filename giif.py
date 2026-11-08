"""Zgloszenia notariusza do GIIF (i Szefa KAS) - obieg w notarai.

Obieg przeniesiony z Finance You (src/lib/aml/aml-reports.functions.ts):
  szkic -> kompletne (sprawdzenie pol) -> do_podpisu -> wyslane -> upo
Wysylka odbywa sie w SI*GIIF kwalifikowanym podpisem elektronicznym
notariusza; notarai przygotowuje dane, pilnuje terminu, a po wysylce
rejestruje identyfikator przesylki i skrot UPO (slad starannosci).

Stan prawny (sprawdzony 11.2026, zrodla w docs/ksiegi-i-giif.md):
- od 1.03.2023 notariusz przekazuje informacje o czynnosciach do GIIF
  i Szefa KAS wylacznie elektronicznie przez SI*GIIF, w formie
  ustrukturyzowanej wedlug schematu XSD (komunikat KAS z 28.11.2022,
  ustawa z 7.10.2022, Dz.U. poz. 2180) - to tzw. eNotariusz,
- art. 72 ust. 4 ustawy AML: transakcje notariusza > rownowartosc 15 000 EUR,
  art. 72 ust. 6 pkt 7a: przedmiot transakcji, a dla nieruchomosci adres
  lub miejsce polozenia,
- komunikat GIIF nr 110: od 30.06.2026 nowy XSD (CRWDE 2026/04/28/14250)
  z polami: numer KW, identyfikator dzialki, liczba pokoi, kondygnacja,
  powierzchnia uzytkowa lokalu, powierzchnia nieruchomosci zabudowanej
  domem; dla osob fizycznych panstwo wydania dokumentu tozsamosci;
  osobny XSD "tylko do GIIF" (CRWDE 2026/04/30/14252) od 15.06.2026,
- SI*GIIF ma REST API dla oprogramowania kancelarii (dokumentacja po
  zalogowaniu; srodowisko testowe test.giif.mofnet.gov.pl).

Czego tu celowo NIE ma: generatora XML. Finance You buduje wlasna strukture
(urn:giif:rest2018:zgloszenie), ktora nie jest oficjalnym schematem - plik
odrzucilaby walidacja SI*GIIF. Mapowanie na XSD dopiszemy, gdy schemat z
CRWDE trafi do repozytorium (docs/ksiegi-i-giif.md, krok 1).

Dane stron (PESEL, dokumenty, adresy) nie trafiaja do logow.
"""
import hashlib
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import ksiegi_notarialne
import magazyn

PLIK = "giif"
PROG_EUR = Decimal("15000")
TERMIN_DNI = 7  # do potwierdzenia w komunikacie GIIF nr 15 (liczenie terminu)

RODZAJE = {
    "czynnosc_giif_kas": {"nazwa": "Informacja o czynnosci notarialnej do GIIF i Szefa KAS",
                          "podstawa": "art. 72 ust. 4 ustawy AML; PCC/SD (eNotariusz)"},
    "czynnosc_giif": {"nazwa": "Informacja o transakcji tylko do GIIF",
                      "podstawa": "art. 72 ust. 4 ustawy AML"},
    "zawiadomienie_74": {"nazwa": "Zawiadomienie o okolicznosciach podejrzanych",
                         "podstawa": "art. 74 ust. 1 ustawy AML"},
    "zawiadomienie_86": {"nazwa": "Zawiadomienie o planowanej transakcji podejrzanej",
                         "podstawa": "art. 86 ust. 1 ustawy AML"},
    "zawiadomienie_89": {"nazwa": "Zawiadomienie o przeprowadzonej transakcji podejrzanej",
                         "podstawa": "art. 89 ustawy AML"},
}
STATUSY = ("szkic", "do_podpisu", "wyslane", "upo")
ZAWIADOMIENIA = ("zawiadomienie_74", "zawiadomienie_86", "zawiadomienie_89")

POLA_NIERUCHOMOSCI = ("adres", "numer_kw", "identyfikator_dzialki", "liczba_pokoi",
                      "kondygnacja", "powierzchnia_uzytkowa", "powierzchnia_domu")


def _pusty() -> list:
    return []


def _dec(wartosc) -> Decimal | None:
    if wartosc in (None, ""):
        return None
    try:
        return Decimal(str(wartosc).replace(" ", "").replace(",", "."))
    except InvalidOperation:
        raise ValueError("Niepoprawna kwota") from None


def rownowartosc_eur(kwota, waluta: str, kurs_eur) -> Decimal:
    """Jak toEurEquivalent w Finance You: PLN / sredni kurs EUR tabeli A NBP."""
    kwota, waluta = _dec(kwota), (waluta or "PLN").upper()
    if kwota is None:
        raise ValueError("Brak kwoty")
    if waluta == "EUR":
        return kwota.quantize(Decimal("0.01"))
    if waluta != "PLN":
        raise ValueError(f"Nieobslugiwana waluta {waluta} - przelicz przez PLN albo EUR")
    kurs = _dec(kurs_eur)
    if not kurs:
        raise ValueError("Podaj sredni kurs EUR z tabeli A NBP z dnia czynnosci")
    return (kwota / kurs).quantize(Decimal("0.01"))


def kurs_nbp(dzien: str, klient=None) -> dict:
    """Sredni kurs EUR (tabela A NBP); weekend/swieto - cofamy sie do 10 dni."""
    import httpx
    klient = klient or httpx.Client(timeout=10)
    start = date.fromisoformat(dzien)
    for cofniecie in range(11):
        proba = (start - timedelta(days=cofniecie)).isoformat()
        odp = klient.get(f"https://api.nbp.pl/api/exchangerates/rates/a/eur/{proba}/",
                         params={"format": "json"})
        if odp.status_code == 404:
            continue
        if odp.status_code != 200:
            raise RuntimeError(f"NBP API HTTP {odp.status_code}")
        kurs = odp.json()["rates"][0]
        return {"kurs": str(kurs["mid"]), "tabela": kurs["no"], "data_tabeli": kurs["effectiveDate"]}
    raise RuntimeError(f"Brak tabeli A NBP dla {dzien} (cofnieto 10 dni)")


def kwalifikuj(rep_a: dict, kurs_eur=None) -> dict:
    """Podpowiedz, czy czynnosc z rep. A trzeba zglosic. Decyzja nalezy do notariusza."""
    powody, rodzaj = [], None
    podatek = any(_dec(rep_a.get(p)) for p in ("podatek_pcc", "podatek_sd"))
    if podatek:
        powody.append("pobrano PCC lub SD - informacja do Szefa KAS przez SI*GIIF")
        rodzaj = "czynnosc_giif_kas"
    eur = None
    if rep_a.get("wartosc_przedmiotu") and kurs_eur:
        eur = rownowartosc_eur(rep_a["wartosc_przedmiotu"], "PLN", kurs_eur)
        if eur > PROG_EUR:
            powody.append(f"wartosc {eur} EUR przekracza 15 000 EUR (art. 72 ust. 4)")
            rodzaj = rodzaj or "czynnosc_giif"
    elif rep_a.get("wartosc_przedmiotu"):
        powody.append("podaj kurs EUR, zeby sprawdzic prog 15 000 EUR")
    return {"zglosic": rodzaj is not None, "rodzaj": rodzaj, "rownowartosc_eur": str(eur) if eur else "",
            "powody": powody, "termin": termin(rep_a["data_czynnosci"]) if rodzaj else ""}


def termin(data_czynnosci: str) -> str:
    return (date.fromisoformat(data_czynnosci) + timedelta(days=TERMIN_DNI)).isoformat()


def _strona(s: dict) -> dict:
    return {"nazwa": s.get("nazwa", ""), "rola": s.get("rola", ""), "pesel": s.get("pesel", ""),
            "dokument": s.get("dokument", ""), "panstwo_dokumentu": s.get("panstwo_dokumentu", ""),
            "obywatelstwo": s.get("obywatelstwo", ""), "adres": s.get("adres", ""),
            "udzial": s.get("udzial", ""), "osoba_prawna": bool(s.get("osoba_prawna")),
            "nip": s.get("nip", "")}


def kompletnosc(z: dict) -> list[str]:
    """Braki do uzupelnienia przed podpisem (odpowiednik checkCompleteness)."""
    brak = []
    if not z.get("rep_a"):
        brak.append("Numer repertorium A")
    if not z.get("data_czynnosci"):
        brak.append("Data czynnosci")
    if not z.get("strony"):
        brak.append("Co najmniej jedna strona")
    for i, s in enumerate(z.get("strony", []), 1):
        if not s["nazwa"]:
            brak.append(f"Strona {i}: imie i nazwisko / nazwa")
        if s["osoba_prawna"]:
            if not s["nip"]:
                brak.append(f"Strona {i}: NIP")
        elif not (s["pesel"] or (s["dokument"] and s["panstwo_dokumentu"])):
            brak.append(f"Strona {i}: PESEL albo dokument tozsamosci z panstwem wydania")
        if not s["adres"]:
            brak.append(f"Strona {i}: adres")
    if z["rodzaj"] in ZAWIADOMIENIA:
        if not z.get("uzasadnienie"):
            brak.append("Uzasadnienie podejrzenia")
        return brak
    if not z.get("przedmiot"):
        brak.append("Przedmiot transakcji (art. 72 ust. 6 pkt 7a)")
    if not _dec(z.get("kwota")):
        brak.append("Wartosc transakcji")
    if z.get("nieruchomosc") is not None:
        n = z["nieruchomosc"]
        if not n.get("adres"):
            brak.append("Nieruchomosc: adres lub miejsce polozenia")
        if not (n.get("numer_kw") or n.get("identyfikator_dzialki")):
            brak.append("Nieruchomosc: numer KW albo identyfikator dzialki (komunikat nr 110)")
    return brak


def _oczysc(dane: dict) -> dict:
    wynik = {}
    for pole in ("rep_a", "data_czynnosci", "przedmiot", "kwota", "waluta", "kurs_eur",
                 "tabela_nbp", "uzasadnienie", "rep_a_id"):
        if pole in dane:
            wynik[pole] = str(dane[pole] or "").strip()
    if "strony" in dane:
        wynik["strony"] = [_strona(s) for s in dane["strony"] or []]
    if "nieruchomosc" in dane:
        n = dane["nieruchomosc"]
        wynik["nieruchomosc"] = None if n is None else {p: str(n.get(p, "") or "").strip()
                                                         for p in POLA_NIERUCHOMOSCI}
    return wynik


def _przelicz(z: dict) -> dict:
    z["braki"] = kompletnosc(z)
    z["termin"] = termin(z["data_czynnosci"]) if z.get("data_czynnosci") and z["rodzaj"] not in ZAWIADOMIENIA else ""
    if z.get("kwota") and z.get("kurs_eur"):
        z["rownowartosc_eur"] = str(rownowartosc_eur(z["kwota"], z.get("waluta") or "PLN", z["kurs_eur"]))
    return z


def utworz(rodzaj: str, dane: dict, kto: str = "") -> dict:
    if rodzaj not in RODZAJE:
        raise ValueError(f"Nieznany rodzaj zgloszenia: {rodzaj}")
    z = {"id": uuid.uuid4().hex[:12], "rodzaj": rodzaj, "status": "szkic", "waluta": "PLN",
         "strony": [], "nieruchomosc": None, "historia": [],
         "utworzono": datetime.now().isoformat(timespec="seconds"), "kto": kto}
    z.update(_oczysc(dane))
    _przelicz(z)
    z["historia"].append(_zdarzenie("utworzono", kto))

    def zmiana(lista):
        lista.append(z)
        return z
    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, _pusty())


def z_repertorium(rep_a_id: str, rodzaj: str | None = None, kurs_eur=None, kto: str = "") -> dict:
    """Szkic zgloszenia wypelniony z wpisu repertorium A (strony, wartosc, data)."""
    rep = ksiegi_notarialne.wpis("repertorium_a", rep_a_id)
    if rep is None:
        raise LookupError("Nie ma takiego wpisu w repertorium A")
    rodzaj = rodzaj or kwalifikuj(rep, kurs_eur)["rodzaj"] or "czynnosc_giif_kas"
    wnioski = rep.get("wnioski_kw", [])
    nieruchomosc = {"numer_kw": wnioski[0]["numer_kw"]} if wnioski else None
    return utworz(rodzaj, {
        "rep_a_id": rep["id"], "rep_a": rep["oznaczenie"], "data_czynnosci": rep["data_czynnosci"],
        "przedmiot": rep.get("tresc", ""), "kwota": rep.get("wartosc_przedmiotu", ""),
        "kurs_eur": kurs_eur or "", "strony": rep.get("strony", []), "nieruchomosc": nieruchomosc,
    }, kto)


def _zdarzenie(co: str, kto: str, **szczegoly) -> dict:
    return {"czas": datetime.now().isoformat(timespec="seconds"), "co": co, "kto": kto, **szczegoly}


def _zmien(identyfikator: str, funkcja):
    def zmiana(lista):
        for z in lista:
            if z["id"] == identyfikator:
                return funkcja(z)
        raise LookupError("Nie ma takiego zgloszenia")
    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, _pusty())


def zmien(identyfikator: str, dane: dict, kto: str = "") -> dict:
    def funkcja(z):
        if z["status"] not in ("szkic", "do_podpisu"):
            raise ValueError("Wyslanego zgloszenia nie zmienia sie - przygotuj korekte jako nowe")
        z.update(_oczysc(dane))
        z["status"] = "szkic"  # kazda zmiana cofa do szkicu: trzeba znow zatwierdzic
        z["historia"].append(_zdarzenie("zmieniono", kto))
        return _przelicz(z)
    return _zmien(identyfikator, funkcja)


def zatwierdz(identyfikator: str, kto: str = "") -> dict:
    """Szkic -> do_podpisu. Tylko gdy nic nie brakuje; zapisujemy skrot tresci."""
    def funkcja(z):
        if z["status"] != "szkic":
            raise ValueError("Zatwierdzic mozna tylko szkic")
        _przelicz(z)
        if z["braki"]:
            raise ValueError("Uzupelnij: " + "; ".join(z["braki"]))
        z["status"] = "do_podpisu"
        z["sha256_tresci"] = skrot(z)
        z["historia"].append(_zdarzenie("zatwierdzono", kto, sha256=z["sha256_tresci"]))
        return z
    return _zmien(identyfikator, funkcja)


def skrot(z: dict) -> str:
    import json
    tresc = {k: z.get(k) for k in ("rodzaj", "rep_a", "data_czynnosci", "przedmiot", "kwota",
                                   "waluta", "strony", "nieruchomosc", "uzasadnienie")}
    return hashlib.sha256(json.dumps(tresc, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def zarejestruj_wysylke(identyfikator: str, dane: dict, kto: str = "") -> dict:
    """Wysylka wykonana w SI*GIIF podpisem kwalifikowanym - zapis identyfikatora."""
    numer = str(dane.get("identyfikator_si_giif", "")).strip()
    if not numer:
        raise ValueError("Podaj identyfikator przesylki z SI*GIIF")
    dzien = date.fromisoformat(str(dane.get("data_wysylki", ""))[:10]).isoformat()

    def funkcja(z):
        if z["status"] != "do_podpisu":
            raise ValueError("Najpierw zatwierdz zgloszenie")
        z.update({"status": "wyslane", "identyfikator_si_giif": numer, "data_wysylki": dzien,
                  "po_terminie": bool(z.get("termin")) and dzien > z["termin"]})
        z["historia"].append(_zdarzenie("wyslano", kto, identyfikator=numer))
        return z
    return _zmien(identyfikator, funkcja)


def zarejestruj_upo(identyfikator: str, tresc_upo: bytes, kto: str = "") -> dict:
    """UPO z SI*GIIF: zapisujemy skrot SHA-256 (plik trzyma kancelaria)."""
    if not tresc_upo:
        raise ValueError("Pusty plik UPO")
    sha = hashlib.sha256(tresc_upo).hexdigest()

    def funkcja(z):
        if z["status"] not in ("wyslane", "upo"):
            raise ValueError("Najpierw zarejestruj wysylke")
        z.update({"status": "upo", "sha256_upo": sha})
        z["historia"].append(_zdarzenie("upo", kto, sha256=sha))
        return z
    return _zmien(identyfikator, funkcja)


def lista(status: str | None = None) -> list[dict]:
    wszystkie = magazyn.wczytaj_plik_kancelarii(PLIK, _pusty())
    if status:
        wszystkie = [z for z in wszystkie if z["status"] == status]
    return sorted(wszystkie, key=lambda z: (z.get("termin") or "9999", z["utworzono"]))


def zalegle(dzis: str | None = None) -> list[dict]:
    """Niewyslane zgloszenia z terminem dzis lub wczesniej."""
    dzis = dzis or date.today().isoformat()
    return [z for z in lista() if z["status"] in ("szkic", "do_podpisu")
            and z.get("termin") and z["termin"] <= dzis]


def definicje() -> dict:
    return {"rodzaje": RODZAJE, "statusy": STATUSY, "prog_eur": str(PROG_EUR),
            "termin_dni": TERMIN_DNI, "pola_nieruchomosci": POLA_NIERUCHOMOSCI}
