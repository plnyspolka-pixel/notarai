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

Plik XML karty transakcji (GIIF + Szef KAS) buduje giif_xml.py wedlug
oficjalnego XSD z CRWDE 2026/04/28/14250 i waliduje go przed zatwierdzeniem.
(Finance You buduje wlasna strukture urn:giif:rest2018:zgloszenie, ktorej
SI*GIIF nie przyjmie - tej czesci nie przenosilismy.)

Dane stron (PESEL, dokumenty, adresy) nie trafiaja do logow.
"""
import hashlib
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import giif_xml
import ksiegi_notarialne
import magazyn

PLIK = "giif"
PROG_EUR = Decimal("15000")
TERMIN_DNI = 7  # 7 dni od sporzadzenia aktu / rejestracji APD (art. 72 ustawy AML, art. 84a Op);
                # sposob liczenia (dni kalendarzowe, swieta) - komunikat GIIF nr 15, do potwierdzenia

RODZAJE = {
    "czynnosc_giif_kas": {"nazwa": "Informacja o czynności notarialnej do GIIF i Szefa KAS",
                          "podstawa": "art. 72 ust. 4 ustawy AML; PCC/SD (eNotariusz)"},
    "czynnosc_giif": {"nazwa": "Informacja o transakcji tylko do GIIF",
                      "podstawa": "art. 72 ust. 4 ustawy AML"},
    "zawiadomienie_74": {"nazwa": "Zawiadomienie o okolicznościach podejrzanych",
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
        raise ValueError(f"Nieobsługiwana waluta {waluta} - przelicz przez PLN albo EUR")
    kurs = _dec(kurs_eur)
    if not kurs:
        raise ValueError("Podaj średni kurs EUR z tabeli A NBP z dnia czynności")
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
    raise RuntimeError(f"Brak tabeli A NBP dla {dzien} (cofnięto 10 dni)")


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
            powody.append(f"wartość {eur} EUR przekracza 15 000 EUR (art. 72 ust. 4)")
            rodzaj = rodzaj or "czynnosc_giif"
    elif rep_a.get("wartosc_przedmiotu"):
        powody.append("podaj kurs EUR, żeby sprawdzić próg 15 000 EUR")
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
        brak.append("Data czynności")
    if not z.get("strony"):
        brak.append("Co najmniej jedna strona")
    for i, s in enumerate(z.get("strony", []), 1):
        if not s["nazwa"]:
            brak.append(f"Strona {i}: imię i nazwisko / nazwa")
        if s["osoba_prawna"]:
            if not s["nip"]:
                brak.append(f"Strona {i}: NIP")
        elif not (s["pesel"] or (s["dokument"] and s["panstwo_dokumentu"])):
            brak.append(f"Strona {i}: PESEL albo dokument tożsamości z państwem wydania")
        if not s["adres"]:
            brak.append(f"Strona {i}: adres")
    if z["rodzaj"] in ZAWIADOMIENIA:
        if not z.get("uzasadnienie"):
            brak.append("Uzasadnienie podejrzenia")
        return brak
    if not z.get("przedmiot"):
        brak.append("Przedmiot transakcji (art. 72 ust. 6 pkt 7a)")
    if not _dec(z.get("kwota")):
        brak.append("Wartość transakcji")
    if z.get("nieruchomosc") is not None:
        n = z["nieruchomosc"]
        if not n.get("adres"):
            brak.append("Nieruchomość: adres lub miejsce położenia")
        if not (n.get("numer_kw") or n.get("identyfikator_dzialki")):
            brak.append("Nieruchomość: numer KW albo identyfikator działki (komunikat nr 110)")
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
        raise ValueError(f"Nieznany rodzaj zgłoszenia: {rodzaj}")
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
        raise LookupError("Nie ma takiego zgłoszenia")
    return magazyn.zmien_plik_kancelarii(PLIK, zmiana, _pusty())


def zmien(identyfikator: str, dane: dict, kto: str = "") -> dict:
    def funkcja(z):
        if z["status"] not in ("szkic", "do_podpisu"):
            raise ValueError("Wysłanego zgłoszenia nie zmienia się - przygotuj korektę jako nowe")
        z.update(_oczysc(dane))
        z["status"] = "szkic"  # kazda zmiana cofa do szkicu: trzeba znow zatwierdzic
        z["historia"].append(_zdarzenie("zmieniono", kto))
        return _przelicz(z)
    return _zmien(identyfikator, funkcja)


def zatwierdz(identyfikator: str, kto: str = "") -> dict:
    """Szkic -> do_podpisu. Tylko gdy nic nie brakuje; zapisujemy skrot tresci.

    Karta do GIIF i Szefa KAS musi miec plik XML zgodny z XSD i regulami -
    wtedy skrot liczymy z pliku, ktory notariusz podpisze.
    """
    ustaw = ustawienia()

    def funkcja(z):
        if z["status"] != "szkic":
            raise ValueError("Zatwierdzić można tylko szkic")
        _przelicz(z)
        if z["braki"]:
            raise ValueError("Uzupelnij: " + "; ".join(z["braki"]))
        if z["rodzaj"] == "czynnosc_giif_kas":
            if not z.get("karta"):
                raise ValueError("Uzupełnij kartę transakcji (dane do pliku XML)")
            wynik = giif_xml.sprawdz([z["karta"]], ustaw)
            if wynik["bledy"]:
                raise ValueError("Plik XML: " + "; ".join(wynik["bledy"]))
            z["sha256_xml"] = hashlib.sha256(wynik["xml"].encode("utf-8")).hexdigest()
            z["schemat"] = wynik["schemat"]
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
        raise ValueError("Podaj identyfikator przesyłki z SI*GIIF")
    dzien = date.fromisoformat(str(dane.get("data_wysylki", ""))[:10]).isoformat()

    def funkcja(z):
        if z["status"] != "do_podpisu":
            raise ValueError("Najpierw zatwierdź zgłoszenie")
        z.update({"status": "wyslane", "identyfikator_si_giif": numer, "data_wysylki": dzien,
                  "po_terminie": bool(z.get("termin")) and dzien > z["termin"]})
        z["historia"].append(_zdarzenie("wyslano", kto, identyfikator=numer))
        return z
    return _zmien(identyfikator, funkcja)


def odczytaj_upo(tresc: bytes) -> dict | None:
    """UPO z SI*GIIF w XML (giif_xsd/UPO2018.xsd) -> pola. Inny plik (np. PDF) -> None."""
    from lxml import etree
    try:
        dok = etree.fromstring(tresc, etree.XMLParser(no_network=True, resolve_entities=False))
    except etree.XMLSyntaxError:
        return None
    ns = "{http://www.giif.mofnet.gov.pl/xsd/upo/2018}"
    if dok.tag != f"{ns}Potwierdzenie":
        return None
    schemat = etree.XMLSchema(etree.parse(str(giif_xml.KATALOG_XSD / "UPO2018.xsd")))
    try:
        zgodny = schemat.validate(dok)
    except etree.XMLSchemaValidateError:  # np. nierozwiniete encje w pliku
        zgodny = False
    pola = {e.tag.replace(ns, ""): (e.text or "").strip() for e in dok if isinstance(e.tag, str)}
    return {"zgodny_ze_schematem": zgodny, **pola}


def zarejestruj_upo(identyfikator: str, tresc_upo: bytes, kto: str = "") -> dict:
    """UPO z SI*GIIF: skrot SHA-256 pliku, a dla UPO w XML takze jego pola.

    Sprawdzamy, czy UPO dotyczy tej przesylki (numer referencyjny) i tego
    notariusza (NIPIO). Niezgodnosc nie blokuje zapisu - pokazujemy ostrzezenie,
    bo identyfikator przesylki notariusz wpisuje recznie i moze sie pomylic.
    """
    if not tresc_upo:
        raise ValueError("Pusty plik UPO")
    sha = hashlib.sha256(tresc_upo).hexdigest()
    upo = odczytaj_upo(tresc_upo)
    nip = "".join(c for c in str(ustawienia().get("nip", "")) if c.isdigit())

    def funkcja(z):
        if z["status"] not in ("wyslane", "upo"):
            raise ValueError("Najpierw zarejestruj wysyłkę")
        ostrzezenia = []
        if upo:
            numer = upo.get("NumerReferencyjny", "")
            if numer and z.get("identyfikator_si_giif") and numer != z["identyfikator_si_giif"]:
                ostrzezenia.append(f"Numer referencyjny w UPO ({numer}) różni się od wpisanego identyfikatora przesyłki")
            if upo.get("NIPIO") and nip and upo["NIPIO"] != nip:
                ostrzezenia.append("NIP w UPO nie jest NIP-em notariusza z ustawień GIIF")
            if not upo["zgodny_ze_schematem"]:
                ostrzezenia.append("Plik UPO nie jest zgodny ze schematem UPO2018")
        z.update({"status": "upo", "sha256_upo": sha, "upo": upo, "ostrzezenia_upo": ostrzezenia})
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


# ---------------------------------------------------------------- karta XML

PLIK_USTAWIEN = "giif_ustawienia"
POLA_USTAWIEN = ("nip", "nr_sekw_js", "tytul", "charakter_zbywcy", "charakter_nabywcy",
                 "rodzaj_dokumentu", "typ_przedmiotu_lokal", "typ_przedmiotu_dom", "typ_przedmiotu_grunt")


def ustawienia() -> dict:
    """NIP notariusza, urzad skarbowy (slownik USK) i domyslne kody ze slownikow GIIF."""
    return magazyn.wczytaj_plik_kancelarii(PLIK_USTAWIEN, {})


def zapisz_ustawienia(dane: dict) -> dict:
    nowe = {k: str(dane.get(k, "") or "").strip().upper() for k in POLA_USTAWIEN if k in dane}

    def zmiana(stare):
        stare.update(nowe)
        return dict(stare)
    return magazyn.zmien_plik_kancelarii(PLIK_USTAWIEN, zmiana, {})


def _imie_nazwisko(nazwa: str) -> tuple[str, str, str]:
    czesci = nazwa.split()
    if len(czesci) < 2:
        return nazwa, "", ""
    return czesci[0], " ".join(czesci[1:-1]), czesci[-1]


_ZBYWCY = ("sprzeda", "zbyw", "darczy", "dluznik", "wydzierz", "oddaj")


def karta_wstepna(z: dict, ustaw: dict | None = None) -> dict:
    """Karta z danych zgloszenia i wpisu rep. A - do uzupelnienia przez kancelarie."""
    ustaw = ustaw if ustaw is not None else ustawienia()
    rep = z.get("rep_a", "")
    numer = rep.replace("Rep. A nr ", "").replace(" ", "")
    strony, podmioty = [], []
    zbywcy = [i for i, s in enumerate(z.get("strony", [])) if any(x in s.get("rola", "").lower() for x in _ZBYWCY)]
    for i, s in enumerate(z.get("strony", [])):
        if s.get("osoba_prawna"):
            strony.append({"osoba_prawna": True, "nazwa": s["nazwa"], "nip": s.get("nip", ""), "forma": "",
                           "adres": {"kraj": "PL", "ulica": s.get("adres", "")}, "upowaznieni": []})
        else:
            imie, drugie, nazwisko = _imie_nazwisko(s.get("nazwa", ""))
            strony.append({"imie": imie, "imie_drugie": drugie, "nazwisko": nazwisko,
                           "obywatelstwo": s.get("obywatelstwo") or "PL", "pesel": s.get("pesel", ""),
                           "dokument": {"kraj": s.get("panstwo_dokumentu") or "PL",
                                        "rodzaj": ustaw.get("rodzaj_dokumentu", "DO"), "numer": s.get("dokument", "")},
                           "adres": {"kraj": "PL", "miejscowosc": "", "kod_pocztowy": "", "ulica": s.get("adres", "")}})
        strona_tr = "Z" if i in zbywcy else "N"
        ile = len(zbywcy) if strona_tr == "Z" else len(z.get("strony", [])) - len(zbywcy)
        podmioty.append({"strona": i, "strona_transakcji": strona_tr,
                         "charakter": ustaw.get("charakter_zbywcy" if strona_tr == "Z" else "charakter_nabywcy", ""),
                         "udzial_licznik": 1, "udzial_mianownik": max(ile, 1)})
    n = z.get("nieruchomosc")
    przedmiot = {"udzial_licznik": 1, "udzial_mianownik": 1, "wartosc": z.get("kwota", ""), "czy_vat": False,
                 "typ": ustaw.get("typ_przedmiotu_lokal", "") if n else "", "nieruchomosc": bool(n),
                 "zwolnienie_vat": False if n else None, "adres": {"kraj": "PL"}, "podmioty": podmioty}
    if n:
        przedmiot["opis_nieruchomosci"] = {"numer_kw": n.get("numer_kw", ""),
                                           "pow_lokalu": n.get("powierzchnia_uzytkowa", ""),
                                           "pow_domu": n.get("powierzchnia_domu", ""),
                                           "liczba_pokoi": n.get("liczba_pokoi", ""),
                                           "kondygnacja": n.get("kondygnacja", "")}
    return {"korekta": False, "dla_giif": z["rodzaj"] != "czynnosc_giif_kas" or bool(
                z.get("rownowartosc_eur") and Decimal(z["rownowartosc_eur"]) > PROG_EUR),
            "czy_odplatna": True, "numer_repertorium": numer, "numer_czynnosci": "1", "nr_crewan": "",
            "data_dokumentu": z.get("data_czynnosci", ""), "rok_repertorium": (z.get("data_czynnosci") or "")[:4],
            "data_tr": z.get("data_czynnosci", ""), "kwota": z.get("kwota", ""), "waluta": z.get("waluta", "PLN"),
            "kod_rodzaju": "07", "tytul": ustaw.get("tytul", ""), "sposob_wydania": "0", "uwagi": "",
            "strony": strony, "przedmioty": [przedmiot]}


def zapisz_karte(identyfikator: str, karta: dict, kto: str = "") -> dict:
    def funkcja(z):
        if z["status"] not in ("szkic", "do_podpisu"):
            raise ValueError("Wysłanego zgłoszenia nie zmienia się - przygotuj korektę jako nowe")
        z["karta"] = karta
        z["status"] = "szkic"
        z["historia"].append(_zdarzenie("karta", kto))
        return _przelicz(z)
    return _zmien(identyfikator, funkcja)


def plik_xml(identyfikator: str) -> dict:
    """XML karty + bledy. Bez karty - karta wstepna z danych zgloszenia."""
    z = next((x for x in lista() if x["id"] == identyfikator), None)
    if z is None:
        raise LookupError("Nie ma takiego zgłoszenia")
    if z["rodzaj"] != "czynnosc_giif_kas":
        raise ValueError("Plik XML budujemy na razie dla karty do GIIF i Szefa KAS (schemat 14250)")
    ustaw = ustawienia()
    karta = z.get("karta") or karta_wstepna(z, ustaw)
    wynik = giif_xml.sprawdz([karta], ustaw)
    return {**wynik, "karta": karta, "nazwa_pliku": f"giif-{karta.get('numer_repertorium', '').replace('/', '-')}.xml"}


def definicje() -> dict:
    return {"rodzaje": RODZAJE, "statusy": STATUSY, "prog_eur": str(PROG_EUR),
            "termin_dni": TERMIN_DNI, "pola_nieruchomosci": POLA_NIERUCHOMOSCI,
            "pola_ustawien": POLA_USTAWIEN, "kody_rodzaju": giif_xml.KODY_RODZAJU,
            "sposob_wydania": giif_xml.SPOSOB_WYDANIA, "schemat": giif_xml.CRWDE}
