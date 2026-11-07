"""Centralny Rejestr Beneficjentow Rzeczywistych - oficjalne API Ministerstwa Finansow.

SOAP 1.2, publiczne, bez uwierzytelniania. Operacja
PobierzInformacjeOSpolkachIBeneficjentach, wyszukiwanie po NIP, KRS albo nazwie.

Podstawa: ustawa z 1.03.2018 o przeciwdzialaniu praniu pieniedzy, art. 34 i 37
(ustalenie beneficjenta rzeczywistego klienta bedacego osoba prawna). Notariusz
sprawdza konkretna spolke w konkretnej sprawie, na zadanie - bez cache "na
zapas", wynik trafia do sprawdzenia.json sprawy z zamaskowanymi PESEL-ami.

Logi: NIP spolki (dane podmiotu, nie osoby), status, czas. Bez nazwisk.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from xml.etree import ElementTree as ET

import httpx

import rejestry

log = logging.getLogger("pieczapp.crbr")

ADRES = "https://bramka-crbr.mf.gov.pl:5058/uslugiBiznesowe/uslugiESB/AP/ApiPrzegladoweCRBR/2022/12/01"
ZRODLO = "CRBR Ministerstwa Finansow (bramka-crbr.mf.gov.pl)"
_NS_USLUGA = "http://www.mf.gov.pl/uslugiBiznesowe/uslugiESB/AP/ApiPrzegladoweCRBR/2022/12/01"
_NS_SCHEMAT = "http://www.mf.gov.pl/schematy/AP/ApiPrzegladoweCRBR/2022/12/01"


def normalizuj_nip(tekst: str | None) -> str | None:
    cyfry = re.sub(r"[\s\-_.]", "", tekst or "")
    return cyfry if re.fullmatch(r"\d{10}", cyfry) else None


def normalizuj_krs(tekst: str | None) -> str | None:
    cyfry = re.sub(r"[\s\-_.]", "", tekst or "")
    return cyfry.zfill(10) if re.fullmatch(r"\d{1,10}", cyfry) else None


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def koperta(pole: str, wartosc: str) -> str:
    assert pole in ("NIP", "KRS", "Nazwa")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
        f'xmlns:ns="{_NS_USLUGA}" xmlns:ns1="{_NS_SCHEMAT}">'
        "<soap:Header/><soap:Body>"
        "<ns:PobierzInformacjeOSpolkachIBeneficjentach>"
        "<PobierzInformacjeOSpolkachIBeneficjentachDane>"
        f"<ns1:SzczegolyWniosku><ns1:{pole}>{_xml_escape(wartosc)}</ns1:{pole}></ns1:SzczegolyWniosku>"
        "</PobierzInformacjeOSpolkachIBeneficjentachDane>"
        "</ns:PobierzInformacjeOSpolkachIBeneficjentach>"
        "</soap:Body></soap:Envelope>"
    )


@dataclass
class Osoba:
    imiona: str
    nazwisko: str
    pesel_maska: str | None = None       # nigdy pelny PESEL
    data_urodzenia: str | None = None
    obywatelstwa: list[str] = field(default_factory=list)
    kraj_zamieszkania: str | None = None
    uprawnienia: str | None = None       # beneficjent: charakter uprawnienia
    funkcja: str | None = None           # zglaszajacy: funkcja w spolce

    @property
    def imie_nazwisko(self) -> str:
        return f"{self.imiona} {self.nazwisko}".strip()


@dataclass
class Spolka:
    nip: str | None = None
    krs: str | None = None
    nazwa: str | None = None
    forma: str | None = None
    adres: str | None = None


@dataclass
class WynikCRBR:
    status: str                          # ok | brak | wiele | bledne_dane | blad
    komunikat: str = ""
    kod: str | None = None
    spolka: Spolka | None = None
    beneficjenci: list[Osoba] = field(default_factory=list)
    zglaszajacy: list[Osoba] = field(default_factory=list)
    kandydaci: list[Spolka] = field(default_factory=list)
    identyfikator_wniosku: str | None = None
    data_wniosku: str | None = None
    zrodlo: str = ZRODLO

    def slownik(self) -> dict:
        return asdict(self)


# --- Parsowanie ------------------------------------------------------------------


def _bez_ns(korzen: ET.Element) -> ET.Element:
    for el in korzen.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return korzen


def _t(el: ET.Element | None, *sciezka: str) -> str | None:
    for tag in sciezka:
        if el is None:
            return None
        el = el.find(tag)
    if el is None or el.text is None:
        return None
    return el.text.strip() or None


def _adres(sp: ET.Element) -> str | None:
    czesci = [_t(sp, "Ulica"), _t(sp, "NrDomu")]
    lokal = _t(sp, "NrLokalu")
    ulica = " ".join(c for c in czesci if c) + (f"/{lokal}" if lokal and czesci[1] else "")
    miasto = " ".join(c for c in (_t(sp, "KodPocztowy"), _t(sp, "Miejscowosc")) if c)
    return ", ".join(c for c in (ulica.strip(), miasto) if c) or None


def _spolka(sp: ET.Element) -> Spolka:
    return Spolka(nip=_t(sp, "NIP"), krs=_t(sp, "KRS"), nazwa=_t(sp, "Nazwa"),
                  forma=_t(sp, "OpisFormyOrganizacyjnej") or _t(sp, "KodFormyOrganizacyjnej"),
                  adres=_adres(sp))


def _obywatelstwa(el: ET.Element) -> list[str]:
    wynik = []
    for o in el.findall("Obywatelstwo"):
        wartosc = _t(o, "Nazwa") or _t(o, "Kod") or (o.text or "").strip()
        if wartosc:
            wynik.append(wartosc)
    return wynik


def _osoba(el: ET.Element) -> Osoba:
    pesel = _t(el, "PESEL")
    return Osoba(
        imiona=" ".join(x for x in (_t(el, "PierwszeImie"), _t(el, "KolejneImiona")) if x),
        nazwisko=_t(el, "Nazwisko") or "",
        pesel_maska=rejestry.maskuj_pesel(pesel) if pesel else None,
        data_urodzenia=_t(el, "DataUrodzenia"),
        obywatelstwa=_obywatelstwa(el),
        kraj_zamieszkania=_t(el, "KrajZamieszkania", "Nazwa") or _t(el, "KrajZamieszkania"),
    )


def _beneficjent(el: ET.Element) -> Osoba:
    o = _osoba(el)
    uprawnienia = []
    for u in el.findall("ListaInformacjiOUdzialach/InformacjaOUdzialach"):
        opis = (_t(u, "UprawnieniaWlascicielskieBezposrednie") or _t(u, "UprawnieniaWlascicielskiePosrednie")
                or _t(u, "Opis"))
        if opis:
            uprawnienia.append(opis)
    o.uprawnienia = " | ".join(uprawnienia) or None
    return o


def _zglaszajacy(el: ET.Element) -> Osoba:
    o = _osoba(el)
    funkcje = [f for f in (_t(x, "Opis") for x in el.findall("ListaFunkcjiZglaszajacego/Funkcja")) if f]
    o.funkcja = ", ".join(funkcje) or None
    return o


def parsuj_odpowiedz(xml: str, pole: str = "", wartosc: str = "") -> WynikCRBR:
    """Odpowiedz SOAP -> WynikCRBR. Czysta funkcja, testowana na probce."""
    try:
        korzen = _bez_ns(ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml))
    except ET.ParseError:
        return WynikCRBR("blad", "Nieprawidlowa odpowiedz XML z CRBR", kod="PARSE_ERROR")
    cialo = korzen.find("Body")
    if cialo is None:
        return WynikCRBR("blad", "Nieoczekiwana struktura odpowiedzi z CRBR", kod="UNEXPECTED_RESPONSE")
    blad = cialo.find("Fault")
    if blad is not None:
        powod = _t(blad, "Reason", "Text") or _t(blad, "faultstring") or _t(blad, "Code", "Value") or "SOAP Fault"
        return WynikCRBR("blad", powod, kod="SOAP_FAULT")
    dane = cialo.find("PobierzInformacjeOSpolkachIBeneficjentachOdpowiedz/"
                      "PobierzInformacjeOSpolkachIBeneficjentachOdpowiedzDane")
    if dane is None:
        return WynikCRBR("blad", "Nieoczekiwana struktura odpowiedzi z CRBR", kod="UNEXPECTED_RESPONSE")
    status = _t(dane, "Status")
    wniosek = _t(dane, "IdentyfikatorWniosku")
    data = _t(dane, "DataICzasZlozeniaWniosku")
    if status == "BladFormalny":
        return WynikCRBR("bledne_dane", f"CRBR odrzucilo zapytanie ({pole}={wartosc}) jako niepoprawne formalnie.",
                         kod="FORMAL_ERROR", identyfikator_wniosku=wniosek, data_wniosku=data)
    spolki = dane.findall("ListaInformacjiOSpolkachIBeneficjentach/SpolkaIBeneficjenci")
    if status == "BrakInformacji" or not spolki:
        return WynikCRBR("brak", "Brak wpisu w CRBR dla podanego kryterium.",
                         identyfikator_wniosku=wniosek, data_wniosku=data)
    if pole == "Nazwa" and len(spolki) > 1:
        return WynikCRBR("wiele", f"Znaleziono {len(spolki)} spolek - doprecyzuj po NIP albo KRS.",
                         kandydaci=[_spolka(s) for s in spolki], identyfikator_wniosku=wniosek, data_wniosku=data)
    sp = spolki[0]
    return WynikCRBR(
        "ok", "Wpis w CRBR.", spolka=_spolka(sp),
        beneficjenci=[_beneficjent(b) for b in sp.findall("ListaBeneficjentowRzeczywistych/BeneficjentRzeczywisty")],
        zglaszajacy=[_zglaszajacy(z) for z in sp.findall("ListaZglaszajacych/Zglaszajacy")],
        kandydaci=[_spolka(s) for s in spolki[1:]],
        identyfikator_wniosku=wniosek, data_wniosku=data,
    )


# --- Zapytanie -------------------------------------------------------------------


def sprawdz(nip: str | None = None, krs: str | None = None, nazwa: str | None = None,
            klient: httpx.Client | None = None) -> WynikCRBR:
    """Jedno zapytanie do bramki CRBR. Kolejnosc kryteriow: NIP, KRS, nazwa."""
    n, k, naz = normalizuj_nip(nip), normalizuj_krs(krs), (nazwa or "").strip()
    if n:
        pole, wartosc = "NIP", n
    elif k:
        pole, wartosc = "KRS", k
    elif len(naz) >= 3:
        pole, wartosc = "Nazwa", naz
    else:
        return WynikCRBR("bledne_dane", "Podaj poprawny NIP (10 cyfr), KRS albo nazwe spolki (min. 3 znaki).",
                         kod="INVALID_INPUT")
    start = time.time()
    try:
        wlasny = klient is None
        klient = klient or httpx.Client(timeout=25)
        try:
            odp = klient.post(ADRES, content=koperta(pole, wartosc).encode("utf-8"),
                              headers={"Content-Type": "application/soap+xml; charset=utf-8"})
        finally:
            if wlasny:
                klient.close()
    except httpx.TimeoutException:
        return WynikCRBR("blad", "Bramka CRBR nie odpowiedziala w 25 s.", kod="TIMEOUT")
    except httpx.HTTPError as blad:
        return WynikCRBR("blad", f"Blad sieci przy polaczeniu z bramka CRBR ({type(blad).__name__}).",
                         kod="NETWORK_ERROR")
    wynik = parsuj_odpowiedz(odp.text, pole, wartosc)
    if wynik.status == "blad" and wynik.kod != "SOAP_FAULT" and odp.status_code >= 400:
        wynik = WynikCRBR("blad", f"Bramka CRBR zwrocila HTTP {odp.status_code}", kod=f"HTTP_{odp.status_code}")
    log.info("CRBR %s=%s: status=%s czas=%.1fs", pole, wartosc if pole != "Nazwa" else "(nazwa)",
             wynik.status, time.time() - start)
    return wynik


# --- Dla sladu audytowego -----------------------------------------------------------


def _norm(s: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", (s or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c) and (c.isalpha() or c.isspace()))
    return re.sub(r"\s+", " ", t).strip()


def dopasuj_osoby(imiona_nazwiska: list[str], osoby: list[Osoba]) -> dict[str, bool]:
    """Ktore ze stron czynnosci sa wsrod beneficjentow (po imieniu i nazwisku)."""
    lista = [set(_norm(o.imie_nazwisko).split()) for o in osoby]
    wynik = {}
    for nazwa in imiona_nazwiska:
        n = set(_norm(nazwa).split())
        # "Jan Kowalski" pasuje do "Jan Maria Kowalski": imie i nazwisko strony
        # musza byc wsrod slow beneficjenta (drugie imie nie przeszkadza).
        wynik[nazwa] = len(n) >= 2 and any(b and n <= b for b in lista)
    return wynik


def opis_dla_sladu(w: WynikCRBR) -> str:
    """Tekst do sprawdzenia.json: spolka, beneficjenci i reprezentanci z
    zamaskowanymi PESEL-ami. Nazwiska beneficjentow to tresc jawnego rejestru."""
    if w.status != "ok" or not w.spolka:
        return w.komunikat
    czesci = [f"{w.spolka.nazwa or '?'} (NIP {w.spolka.nip or '?'}, KRS {w.spolka.krs or '?'})"]
    if w.beneficjenci:
        czesci.append("Beneficjenci: " + "; ".join(
            f"{o.imie_nazwisko}" + (f" ur. {o.data_urodzenia}" if o.data_urodzenia else "")
            + (f" ({o.uprawnienia})" if o.uprawnienia else "") for o in w.beneficjenci))
    if w.zglaszajacy:
        czesci.append("Zglaszajacy: " + "; ".join(
            f"{o.imie_nazwisko}" + (f" - {o.funkcja}" if o.funkcja else "") for o in w.zglaszajacy))
    if w.data_wniosku:
        czesci.append(f"wniosek {w.identyfikator_wniosku or ''} z {w.data_wniosku}".strip())
    return " | ".join(czesci)
