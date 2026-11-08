"""Karta transakcji notarialnej do GIIF i Szefa KAS - plik XML wg oficjalnego XSD.

Schemat: CRWDE 2026/04/28/14250 (namespace http://crd.gov.pl/wzor/2026/04/28/14250/),
obowiazuje od 30.06.2026 (komunikat GIIF nr 110). Kopie XSD w giif_xsd/,
opisy pol w docs/giif/opis-schematu-notarialnego-v4.1.txt (numery pol K1.xx,
K2.xx, K3.xx ponizej pochodza z tego opisu).

Co robi ten modul:
- buduje dokument <Dokument> z jedna lub wieloma kartami (jedna czynnosc =
  jedna karta, ten sam numer repertorium),
- waliduje go wzgledem XSD (lxml, bez sieci: importy crd.gov.pl czytamy z dysku),
- sprawdza reguly, ktorych XSD nie wyraza (INF.2 udzialy stron, INF.3 suma
  wartosci, INF.4 APD/EPS, adres nieruchomosci, sumy kontrolne PESEL/NIP/KW).

Czego nie robi: nie zna slownikow GIIF (TytulTr, IdSlPrzedmiotTyp,
charakterPodmiotu, RodzajDokumentu, FormaOrganizacyjna, USK) - sa dostepne
dopiero po zalogowaniu w SI*GIIF. Kody podaje kancelaria (raz w ustawieniach
albo przy karcie); SI*GIIF sprawdzi je przy przyjeciu pliku. Nie podpisuje
(CAdES) i nie szyfruje - to robi notariusz swoim podpisem kwalifikowanym
(narzedzie GIIF "Bezpieczny plik" albo wysylka przez strone SI*GIIF).
"""
from decimal import Decimal, InvalidOperation, ROUND_UP
from fractions import Fraction
from pathlib import Path

from lxml import etree

import walidacja

NS = "http://crd.gov.pl/wzor/2026/04/28/14250/"
# Elementy wewnatrz typow z typy.xsd (osoby, adresy, dokumenty) sa w jego przestrzeni nazw.
TYP = "http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2018/10/10/giif/typy/"
CRWDE = "2026/04/28/14250"
KATALOG_XSD = Path(__file__).parent / "giif_xsd"
_CRD = "http://crd.gov.pl/"
_SCHEMAT = None

KODY_RODZAJU = {"07": "akt notarialny", "17": "akt poswiadczenia dziedziczenia",
                "27": "europejskie poswiadczenie spadkowe"}
SPOSOB_WYDANIA = {"0": "bez depozytu", "1": "z depozytem dokumentu", "2": "z depozytem pieniedzy",
                  "3": "z depozytem papierow wartosciowych"}
STRONY_TRANSAKCJI = {"Z": "zbywca", "N": "nabywca", "I": "inna strona"}


class _Resolver(etree.Resolver):
    """Importy http://crd.gov.pl/... -> giif_xsd/crd.gov.pl/... (zero sieci)."""

    def resolve(self, url, pubid, context):
        if url and url.startswith(_CRD):
            return self.resolve_filename(str(KATALOG_XSD / "crd.gov.pl" / url[len(_CRD):]), context)
        return None


def schemat() -> etree.XMLSchema:
    global _SCHEMAT
    if _SCHEMAT is None:
        parser = etree.XMLParser(no_network=True)
        parser.resolvers.add(_Resolver())
        sciezka = KATALOG_XSD / "crd.gov.pl" / "wzor" / CRWDE / "schemat.xsd"
        _SCHEMAT = etree.XMLSchema(etree.parse(str(sciezka), parser))
    return _SCHEMAT


# ---------------------------------------------------------------- budowa XML

def _el(rodzic, nazwa, wartosc=None, ns=NS, **atrybuty):
    e = etree.SubElement(rodzic, f"{{{ns}}}{nazwa}", {k: v for k, v in atrybuty.items() if v is not None})
    if wartosc is not None:
        e.text = str(wartosc)
    return e


def _opc(rodzic, nazwa, wartosc, ns=NS):
    if wartosc not in (None, ""):
        _el(rodzic, nazwa, wartosc, ns=ns)


def _t(rodzic, nazwa, wartosc=None):
    """Element z przestrzeni typy.xsd."""
    return _el(rodzic, nazwa, wartosc, ns=TYP)


def _kwota(wartosc) -> str:
    try:
        return str(Decimal(str(wartosc).replace(" ", "").replace(",", ".")).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError):
        return str(wartosc)


def _bool(wartosc) -> str:
    return "true" if wartosc else "false"


def _adres(rodzic, nazwa, a: dict):
    e = _t(rodzic, nazwa)
    _t(e, "Kraj", (a.get("kraj") or "PL").upper())
    _t(e, "Miejscowosc", a.get("miejscowosc", ""))
    kod = _t(e, "KodPocztowy")
    _t(kod, "KodPL" if (a.get("kraj") or "PL").upper() == "PL" else "Kod", a.get("kod_pocztowy", ""))
    _t(e, "Ulica", a.get("ulica", ""))


def _dokument(rodzic, d: dict):
    e = _t(rodzic, "DokumentTozsamosci")
    _t(e, "KrajDokumentu", (d.get("kraj") or "PL").upper())
    _t(e, "RodzajDokumentu", (d.get("rodzaj") or "").upper())
    _t(e, "SeriaINumerDokumentu", (d.get("numer") or "").replace(" ", "").upper())


def _osoba(rodzic, nazwa, o: dict, pelna: bool):
    """TNotarialnaOsobaFizyczna (pelna) albo TNotarialnaOsFizycznaUpowazniona."""
    e = _el(rodzic, nazwa)
    _t(e, "ImiePierwsze", o.get("imie", ""))
    _opc(e, "ImieDrugie", o.get("imie_drugie"), ns=TYP)
    _t(e, "Nazwisko", o.get("nazwisko", ""))
    _t(e, "Obywatelstwo", (o.get("obywatelstwo") or "PL").upper())
    if o.get("pesel"):
        _t(e, "PESEL", o["pesel"])
    else:
        _t(e, "DataUrodzenia", o.get("data_urodzenia", ""))
        _t(e, "KrajUrodzenia", (o.get("kraj_urodzenia") or "").upper())
    _dokument(e, o.get("dokument") or {})
    if pelna and o.get("adres"):
        _adres(e, "AdresZamieszkania", o["adres"])
    return e


def _podmiot(rodzic, p: dict, strona: dict):
    e = _el(rodzic, "DanePodmiotu", charakterPodmiotu=(p.get("charakter") or "").upper())
    if strona.get("osoba_prawna"):
        zl = _el(e, "ZleceniodawcaOsobaPrawna")
        op = _el(zl, "OsobaPrawna")
        _t(op, "NazwaPodmiotu", strona.get("nazwa", ""))
        _t(op, "FormaOrganizacyjna", (strona.get("forma") or "").upper())
        _adres(op, "AdresPodmiotu", strona.get("adres") or {})
        if strona.get("nip"):
            _t(op, "PodmiotNIP", "".join(c for c in strona["nip"] if c.isdigit()))
        else:
            _t(op, "NumerWRejestrze", strona.get("numer_w_rejestrze", ""))
            _t(op, "DataRejestracji", strona.get("data_rejestracji", ""))
            _t(op, "NazwaRejestru", strona.get("nazwa_rejestru", ""))
            _t(op, "Kraj", (strona.get("kraj_rejestru") or "").upper())
        for u in strona.get("upowaznieni", []):
            _osoba(zl, "OsPrawnaOsobaUpowazniona", u, pelna=False)
    else:
        zl = _el(e, "ZleceniodawcaOsobaFizyczna")
        _osoba(zl, "OsobaFizyczna", strona, pelna=True)
        for u in strona.get("upowaznieni", []):
            _osoba(zl, "OsFizycznaOsobaUpowazniona", u, pelna=False)
    _el(e, "UdzialLicznik", p.get("udzial_licznik", 0))
    _el(e, "UdzialMianownik", p.get("udzial_mianownik", 1))


def _przedmiot(rodzic, p: dict, strony: list[dict]):
    e = _el(rodzic, "DanePrzedmiotu")
    _el(e, "ZbywanyUdzialLicznik", p.get("udzial_licznik", 1))
    _el(e, "ZbywanyUdzialMianownik", p.get("udzial_mianownik", 1))
    _el(e, "WartoscPrzedmiotu", _kwota(p.get("wartosc", 0)))
    _el(e, "CzyVAT", _bool(p.get("czy_vat")))
    _el(e, "IdSlPrzedmiotTyp", p.get("typ", ""))
    _opc(e, "OpisTypInne", p.get("opis_inne"))
    if p.get("zwolnienie_vat") is not None:
        _el(e, "ZwolnienieVAT", _bool(p["zwolnienie_vat"]))
    adres = _el(e, "Adres")
    a = p.get("adres") or {}
    if not p.get("nieruchomosc"):
        _el(adres, "Kraj", (a.get("kraj") or "PL").upper())
    else:
        an = _el(adres, "AdresNieruchomosc")
        kraj = (a.get("kraj") or "PL").upper()
        _t(an, "Kraj", kraj)
        if a.get("kod_pocztowy"):
            kod = _t(an, "KodPocztowy")
            _t(kod, "KodPL" if kraj == "PL" else "Kod", a["kod_pocztowy"])
        if kraj == "PL":
            for pole, xml in (("woj", "WOJ"), ("pow", "POW"), ("gmi", "GMI"), ("rodz", "RODZ"), ("simc", "SIMC")):
                _t(an, xml, a.get(pole, ""))
            for pole, xml in (("ulic", "ULIC"), ("nr_domu", "NrDomu"), ("nr_mieszkania", "NrMieszkania"),
                              ("nr_arkusza_mapy", "NrArkuszaMapy"), ("nr_obrebu", "NrObrebu"),
                              ("nr_dzialki", "NrDzialki")):
                _opc(an, xml, a.get(pole), ns=TYP)
        else:
            _t(an, "Miejscowosc", a.get("miejscowosc", ""))
            _t(an, "Ulica", a.get("ulica", ""))
    for pd in p.get("podmioty", []):
        _podmiot(e, pd, strony[pd["strona"]])
    opis = p.get("opis_nieruchomosci") or {}
    if p.get("nieruchomosc") and any(opis.values()):
        o = _el(e, "OpisNieruchomosci")
        for pole, xml in (("numer_kw", "NrKsiegiWieczystej"), ("pow_lokalu", "PowLokalu"),
                          ("pow_domu", "PowNieruchZabudowanejDomem"), ("liczba_pokoi", "LiczbaPokoi"),
                          ("kondygnacja", "NrKondygnacjiLokalu")):
            wartosc = opis.get(pole)
            if pole in ("pow_lokalu", "pow_domu") and wartosc not in (None, ""):
                wartosc = _kwota(wartosc)
            _opc(o, xml, wartosc)


def _karta(rodzic, k: dict):
    e = _el(rodzic, "Karta", korekta=_bool(k.get("korekta")),
            dataKorekty=k.get("data_korekty") or None,
            dlaGIIF=_bool(k.get("dla_giif")), czyOdplatna=_bool(k.get("czy_odplatna", True)))
    ident = _el(e, "IdentyfikatorTr", nrCREWAN=(k.get("nr_crewan") or "").upper())
    _el(ident, "NumerRepertorium", k.get("numer_repertorium", ""))
    _el(ident, "NumerCzynnosci", k.get("numer_czynnosci", "1"))
    _el(e, "DataDokumentu", k.get("data_dokumentu", ""))
    _el(e, "RokRepertorium", k.get("rok_repertorium", ""))
    _el(e, "DataTr", k.get("data_tr") or k.get("data_dokumentu", ""))
    _el(e, "KwotaTr", _kwota(k.get("kwota", 0)))
    _el(e, "KodWalutyTr", (k.get("waluta") or "PLN").upper())
    _el(e, "KodRodzajuTr", k.get("kod_rodzaju", "07"))
    _el(e, "TytulTr", (k.get("tytul") or "").upper())
    _el(e, "SposobWydaniaDysp", k.get("sposob_wydania", "0"))
    _opc(e, "Uwagi", (k.get("uwagi") or "").replace("\n", " "))
    for p in k.get("przedmioty", []):
        _przedmiot(e, p, k.get("strony", []))


def zbuduj(karty: list[dict], ustawienia: dict) -> bytes:
    """Dokument XML (UTF-8) z kartami. ustawienia: nip (notariusza), nr_sekw_js (USK)."""
    nsmap = {None: NS, "typ": TYP}
    dok = etree.Element(f"{{{NS}}}Dokument", nsmap=nsmap,
                        nipIO="".join(c for c in str(ustawienia.get("nip", "")) if c.isdigit()),
                        nrSekwJs=str(ustawienia.get("nr_sekw_js", "")))
    _el(dok, "OpisDokumentu")
    _el(dok, "DaneDokumentu")
    tresc = _el(dok, "TrescDokumentu", format="text/xml", kodowanie="XML", rodzaj="inny")
    for k in karty:
        _karta(tresc, k)
    return etree.tostring(dok, xml_declaration=True, encoding="UTF-8", pretty_print=True)


# ---------------------------------------------------------------- walidacja

def bledy_xsd(xml: bytes) -> list[str]:
    try:
        dok = etree.fromstring(xml, etree.XMLParser(no_network=True, resolve_entities=False))
    except etree.XMLSyntaxError as blad:
        return [f"XML niepoprawny: {blad}"]
    s = schemat()
    if s.validate(dok):
        return []
    return [f"linia {b.line}: {b.message}" for b in s.error_log]


def _ulamek(licznik, mianownik) -> Fraction:
    return Fraction(int(licznik), int(mianownik))


def bledy_regul(k: dict, ustawienia: dict) -> list[str]:
    """Reguly z opisu schematu (INF.1-9) i sumy kontrolne - przed wyslaniem."""
    b = []
    nip = "".join(c for c in str(ustawienia.get("nip", "")) if c.isdigit())
    if not walidacja.nip(nip)[0]:
        b.append("Ustawienia GIIF: NIP notariusza (nipIO) niepoprawny")
    if not str(ustawienia.get("nr_sekw_js", "")).isdigit():
        b.append("Ustawienia GIIF: numer urzedu skarbowego (nrSekwJs, slownik USK)")
    kod = k.get("kod_rodzaju", "07")
    if kod not in KODY_RODZAJU:
        b.append("Kod rodzaju transakcji: 07, 17 albo 27")
    if k.get("sposob_wydania", "0") not in SPOSOB_WYDANIA:
        b.append("Sposob wydania dyspozycji: 0-3")
    if not k.get("tytul"):
        b.append("Tytul transakcji (K1.08, kod ze slownika GIIF, np. litera i dwie cyfry)")
    if not k.get("nr_crewan"):
        b.append("Numer CREWAN (K1.03); dla aktow nie zglaszanych do CREWAN: XX900")
    if k.get("korekta") and not k.get("data_korekty"):
        b.append("Korekta wymaga daty korekty")
    przedmioty, strony = k.get("przedmioty", []), k.get("strony", [])
    if not przedmioty:
        b.append("Co najmniej jeden przedmiot transakcji")
    if kod in ("17", "27"):
        if Decimal(_kwota(k.get("kwota", 0))) != 0 or k.get("dla_giif"):
            b.append("APD/EPS: kwota 0 i dlaGIIF=false (INF.4)")
    suma = sum((Decimal(_kwota(p.get("wartosc", 0))) for p in przedmioty), Decimal("0"))
    if suma.quantize(Decimal("0.01"), ROUND_UP) != Decimal(_kwota(k.get("kwota", 0))):
        b.append(f"Suma wartosci przedmiotow ({suma}) rozni sie od kwoty transakcji (INF.3)")
    for i, s in enumerate(strony, 1):
        if s.get("osoba_prawna"):
            if s.get("nip") and not walidacja.nip(s["nip"])[0]:
                b.append(f"Strona {i}: NIP niepoprawny")
            if not s.get("upowaznieni"):
                b.append(f"Strona {i}: osoba prawna wymaga co najmniej jednej osoby upowaznionej")
        else:
            if s.get("pesel") and not walidacja.pesel(s["pesel"])[0]:
                b.append(f"Strona {i}: PESEL niepoprawny")
            if not s.get("pesel") and not (s.get("data_urodzenia") and s.get("kraj_urodzenia")):
                b.append(f"Strona {i}: PESEL albo data i kraj urodzenia")
            if not (s.get("dokument") or {}).get("rodzaj") or not (s.get("dokument") or {}).get("numer"):
                b.append(f"Strona {i}: dokument tozsamosci (rodzaj ze slownika, np. DO, PA, i numer)")
    for i, p in enumerate(przedmioty, 1):
        if int(p.get("udzial_licznik", 1)) > int(p.get("udzial_mianownik", 1)):
            b.append(f"Przedmiot {i}: zbywany udzial wiekszy niz calosc")
        if not str(p.get("typ", "")).isdigit():
            b.append(f"Przedmiot {i}: kod rodzaju przedmiotu (IdSlPrzedmiotTyp, slownik GIIF)")
        if not p.get("podmioty"):
            b.append(f"Przedmiot {i}: co najmniej jeden podmiot")
        sumy = {"Z": Fraction(0), "N": Fraction(0)}
        for pd in p.get("podmioty", []):
            if not 0 <= pd.get("strona", -1) < len(strony):
                b.append(f"Przedmiot {i}: podmiot wskazuje nieistniejaca strone")
                continue
            if not pd.get("charakter"):
                b.append(f"Przedmiot {i}: charakter podmiotu (charakterPodmiotu, slownik GIIF)")
            strona_tr = pd.get("strona_transakcji", "I")
            if strona_tr in sumy:
                sumy[strona_tr] += _ulamek(pd.get("udzial_licznik", 0), pd.get("udzial_mianownik", 1))
            elif int(pd.get("udzial_licznik", 0)) != 0:
                b.append(f"Przedmiot {i}: inna strona transakcji ma udzial 0/1 (INF.2)")
        for strona_tr, s in sumy.items():
            if any(pd.get("strona_transakcji") == strona_tr for pd in p.get("podmioty", [])) and s != 1:
                b.append(f"Przedmiot {i}: udzialy ({STRONY_TRANSAKCJI[strona_tr]}) sumuja sie do {s}, a musza do 1 (INF.2)")
        if p.get("nieruchomosc"):
            a = p.get("adres") or {}
            if (a.get("kraj") or "PL").upper() == "PL":
                if not all(a.get(x) for x in ("woj", "pow", "gmi", "rodz", "simc")):
                    b.append(f"Przedmiot {i}: adres TERYT (WOJ, POW, GMI, RODZ, SIMC; dzialka bez adresu: SIMC 0000000)")
                if not a.get("nr_domu") and not (a.get("nr_obrebu") and a.get("nr_dzialki")):
                    b.append(f"Przedmiot {i}: numer domu albo numer obrebu i dzialki (INF.7)")
                if a.get("nr_obrebu") and not (str(a["nr_obrebu"]).isdigit() and len(str(a["nr_obrebu"])) <= 4):
                    b.append(f"Przedmiot {i}: numer obrebu - tylko cyfry, 1-4")
                if a.get("nr_dzialki") and not all(c.isdigit() or c == "/" for c in str(a["nr_dzialki"])):
                    b.append(f"Przedmiot {i}: numer dzialki - tylko cyfry i ukosnik")
                kw = (p.get("opis_nieruchomosci") or {}).get("numer_kw")
                if kw and not walidacja.ksiega_wieczysta(kw)[0]:
                    b.append(f"Przedmiot {i}: numer KW niepoprawny (suma kontrolna)")
            if kod == "07" and p.get("zwolnienie_vat") is None:
                b.append(f"Przedmiot {i}: oswiadczenie o zwolnieniu z VAT (K2.07) dla nieruchomosci")
    return b


def sprawdz(karty: list[dict], ustawienia: dict) -> dict:
    """XML + bledy (reguly i XSD). Plik jest gotowy do podpisu, gdy bledy == []."""
    bledy = []
    for n, k in enumerate(karty, 1):
        bledy += [f"Karta {n}: {x}" for x in bledy_regul(k, ustawienia)]
    xml = zbuduj(karty, ustawienia)
    bledy += [f"XSD: {x}" for x in bledy_xsd(xml)]
    return {"xml": xml.decode("utf-8"), "bledy": bledy, "schemat": CRWDE}
