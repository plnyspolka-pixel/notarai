"""Poczta Polska: od wniosku o umowe do nadawania przesylek z aplikacji.

Kancelaria przechodzi trzy kroki w oknie "Poczta Polska" (widok Przesylki):

1. Wniosek o umowe. Umowy z Poczta nie da sie zawrzec przez API - zawiera
   ja przedstawiciel handlowy (dokumenty papierowe, weryfikacja w BIG, wg
   relacji kancelarii 3-6 tygodni). Aplikacja robi za kancelarie wszystko,
   co da sie zrobic: wypelnia wniosek danymi z rejestracji (PDF do podpisu),
   przygotowuje e-mail do Poczty i tekst do formularza sprzedazowego Poczty,
   z prosba o konto Elektroniczny Nadawca z dostepem do WebAPI, umowe EPO
   i wylaczenie wymuszonej zmiany hasla dla konta WebAPI.
2. Konto e-Nadawca. Po podpisaniu umowy Poczta przysyla login i haslo.
3. Polaczenie. Kancelaria wkleja login i haslo; sprawdzamy je metoda hello,
   zapisujemy w AWS Secrets Manager (notarai-poczta-<kancelaria>), pobieramy
   urzedy nadania i karty umowy. Haslo nigdy nie wraca do przegladarki.

Potem z dziennika: "Nadaj w e-Nadawcy" (addShipment - numer nadania od razu
w ksiedze), etykiety adresowe z kodem kreskowym (getPrintForParcel),
"Wyslij zbior" (sendEnvelope - musi byc tego samego dnia co addShipment)
i elektroniczna ksiazka nadawcza z Poczty (getOutboxBook). Daty doreczen
uzupelniaja sie z elektronicznego potwierdzenia odbioru (getEPOStatus).

WebAPI: SOAP 1.1 document/literal, HTTP Basic, przestrzen nazw
http://e-nadawca.poczta-polska.pl. Adresy wg dokumentacji WebAPI w97:
produkcja https://e-nadawca.api.poczta-polska.pl/websrv/, srodowisko
integracyjne https://int-e-nadawca.api.poczta-polska.pl/websrv/ (osobne
loginy). Trzy bledne hasla moga zablokowac konto - dlatego niczego nie
ponawiamy automatycznie po odmowie logowania.

Adresy adresatow to dane osobowe: nie trafiaja do logow.
"""
import base64
import html
import io
import json
import logging
import os
import re
import secrets
import string
import threading
import xml.etree.ElementTree as ET
from datetime import date, datetime

import fitz
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

import config
import magazyn
import przesylki

log = logging.getLogger("pieczapp.poczta")

PLIK = "poczta_polska"
NS = "http://e-nadawca.poczta-polska.pl"
SRODOWISKA = {
    "produkcja": "https://e-nadawca.api.poczta-polska.pl/websrv/",
    "integracja": "https://int-e-nadawca.api.poczta-polska.pl/websrv/",
}
FORMULARZ_POCZTY = "https://www.poczta-polska.pl/dla-biznesu/na-skroty/formularz-sprzedazowy/"
REJESTRACJA_ENADAWCY = "https://e-nadawca.poczta-polska.pl/?action=Register"
EMAIL_POCZTY = "kontakt@poczta-polska.pl"
TELEFONY_POCZTY = ("801 333 444", "+48 438 420 600")
WOLUMENY = ("do 100", "do 200", "do 500", "do 1000", "powyżej 1000")
ETAPY = ("start", "wniosek", "umowa", "polaczona")
KATEGORIE = ("EKONOMICZNA", "PRIORYTETOWA")
CZAS = float(os.getenv("PIECZAPP_PP_CZAS", "60"))
PREFIKS_SEKRETU = "notarai-poczta-"
# Testy podstawiaja tu httpx.MockTransport z udawanym e-Nadawca.
TRANSPORT = None


class BladPoczty(RuntimeError):
    """Odpowiedz Poczty z bledem - tresc nadaje sie do pokazania kancelarii."""


class OdmowaLogowania(BladPoczty):
    pass


# --- sejf na login i haslo -------------------------------------------------
# Wylacznie AWS Secrets Manager (zasada projektu). Testy podmieniaja `sejf`.


class SejfAws:
    def _klient(self):
        import boto3
        sesja = boto3.Session(profile_name=config.PROFIL_AWS or None)
        return sesja.client("secretsmanager", region_name=config.REGION)

    def nazwa(self, kancelaria: str) -> str:
        return PREFIKS_SEKRETU + re.sub(r"[^A-Za-z0-9_+=.@-]", "-", kancelaria)

    def wczytaj(self, kancelaria: str) -> dict | None:
        try:
            odp = self._klient().get_secret_value(SecretId=self.nazwa(kancelaria))
        except Exception as blad:  # noqa: BLE001
            if type(blad).__name__ == "ResourceNotFoundException" or "ResourceNotFound" in str(getattr(blad, "response", "")):
                return None
            raise
        return json.loads(odp["SecretString"])

    def zapisz(self, kancelaria: str, dane: dict) -> None:
        klient, nazwa, tresc = self._klient(), self.nazwa(kancelaria), json.dumps(dane)
        try:
            klient.put_secret_value(SecretId=nazwa, SecretString=tresc)
        except Exception as blad:  # noqa: BLE001
            if type(blad).__name__ != "ResourceNotFoundException" and "ResourceNotFound" not in str(getattr(blad, "response", "")):
                raise
            klient.create_secret(Name=nazwa, SecretString=tresc,
                                 Description="notarai - login WebAPI Elektronicznego Nadawcy kancelarii",
                                 Tags=[{"Key": "projekt", "Value": "notarai"}, {"Key": "kancelaria", "Value": kancelaria}])

    def usun(self, kancelaria: str) -> None:
        try:
            self._klient().delete_secret(SecretId=self.nazwa(kancelaria), RecoveryWindowInDays=7)
        except Exception as blad:  # noqa: BLE001
            if type(blad).__name__ != "ResourceNotFoundException":
                raise


sejf = SejfAws()


# --- SOAP ------------------------------------------------------------------


def _atrybuty(atr: dict) -> str:
    return "".join(f' {k}="{html.escape(str(v), quote=True)}"' for k, v in atr.items() if v not in (None, ""))


def _xml(_element: str, _tresc="", /, **atr) -> str:
    """<e:element atr="...">tresc</e:element>; tresc to gotowy XML albo tekst."""
    return f"<e:{_element}{_atrybuty(atr)}>{_tresc}</e:{_element}>"


def _tekst(wartosc) -> str:
    return html.escape(str(wartosc), quote=False)


def _bez_ns(element: ET.Element) -> ET.Element:
    for e in element.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]
        for k in list(e.attrib):
            if "}" in k:
                e.attrib[k.split("}", 1)[1]] = e.attrib.pop(k)
    return element


class Klient:
    """Minimalny klient WebAPI e-Nadawcy - tylko metody, ktorych uzywamy."""

    def __init__(self, login: str, haslo: str, srodowisko: str = "produkcja", transport=None):
        if srodowisko not in SRODOWISKA:
            raise ValueError("Nieznane środowisko e-Nadawcy")
        self.adres = SRODOWISKA[srodowisko]
        self.http = httpx.Client(auth=(login, haslo), timeout=CZAS, transport=transport or TRANSPORT)

    def wywolaj(self, metoda: str, tresc: str = "") -> ET.Element:
        koperta = ('<?xml version="1.0" encoding="utf-8"?>'
                   '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                   f'xmlns:e="{NS}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                   f"<soapenv:Header/><soapenv:Body>{_xml(metoda, tresc)}</soapenv:Body></soapenv:Envelope>")
        try:
            odp = self.http.post(self.adres, content=koperta.encode("utf-8"), headers={
                "Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{NS}/{metoda}"'})
        except httpx.HTTPError as blad:
            raise BladPoczty(f"Brak połączenia z e-Nadawcą ({type(blad).__name__}). Spróbuj za chwilę.")
        if odp.status_code in (401, 403):
            raise OdmowaLogowania("Poczta odrzuciła login lub hasło. Uwaga: kilka błędnych prób blokuje konto "
                                  "- sprawdź dane, zanim spróbujesz ponownie.")
        try:
            korzen = _bez_ns(ET.fromstring(odp.content))
        except ET.ParseError:
            raise BladPoczty(f"Nieczytelna odpowiedź e-Nadawcy (HTTP {odp.status_code}).")
        blad = korzen.find(".//Fault")
        if blad is not None:
            raise BladPoczty("e-Nadawca: " + (blad.findtext("faultstring") or "błąd usługi"))
        cialo = korzen.find("Body")
        wynik = cialo[0] if cialo is not None and len(cialo) else None
        if wynik is None:
            raise BladPoczty(f"Pusta odpowiedź e-Nadawcy (HTTP {odp.status_code}).")
        return wynik

    @staticmethod
    def bledy(element: ET.Element) -> list[str]:
        return [f"{e.get('errorNumber', '')} {e.get('errorDesc', '')}".strip()
                for e in element.iter("error") if e.get("errorNumber") or e.get("errorDesc")]

    def _bez_bledow(self, element: ET.Element) -> ET.Element:
        bledy = self.bledy(element)
        if bledy:
            raise BladPoczty("e-Nadawca: " + "; ".join(bledy))
        return element

    # metody WebAPI

    def hello(self) -> str:
        return self.wywolaj("hello", _xml("in", "notarai")).findtext("out") or ""

    def urzedy_nadania(self) -> list[dict]:
        return [{"id": u.get("urzadNadania"), "opis": u.get("opis") or u.get("nazwaWydruk") or ""}
                for u in self.wywolaj("getUrzedyNadania").iter("urzedyNadania")]

    def karty(self) -> list[dict]:
        return [{"id": k.get("idKarta"), "opis": k.get("opis") or "", "aktywna": k.get("aktywna") == "true"}
                for k in self.wywolaj("getKarty").iter("karta")]

    def ustaw_karte(self, id_karta: str) -> None:
        self._bez_bledow(self.wywolaj("setAktywnaKarta", _xml("idKarta", _tekst(id_karta))))

    def haslo_wygasa(self) -> str:
        return self.wywolaj("getPasswordExpiredDate").findtext("dataWygasniecia") or ""

    def zmien_haslo(self, nowe: str) -> None:
        self._bez_bledow(self.wywolaj("changePassword", _xml("newPassword", _tekst(nowe))))

    def guidy(self, ile: int) -> list[str]:
        wynik = [g.text for g in self.wywolaj("getGuid", _xml("ilosc", str(ile))).iter("guid") if g.text]
        if len(wynik) != ile:
            raise BladPoczty("e-Nadawca nie wydał identyfikatorów przesyłek")
        return wynik

    def dodaj(self, przesylki_xml: list[str]) -> dict[str, dict]:
        odp = self.wywolaj("addShipment", "".join(przesylki_xml))
        return {r.get("guid"): {"numer": r.get("numerNadania") or "", "bledy": self.bledy(r)} for r in odp.iter("retval")}

    def usun_z_bufora(self, guidy: list[str]) -> None:
        self._bez_bledow(self.wywolaj("clearEnvelopeByGuids", "".join(_xml("guid", g) for g in guidy)))

    def etykiety(self, guidy: list[str]) -> bytes:
        tresc = "".join(_xml("guid", g) for g in guidy) + _xml("type", _xml("kind", "ADDRESS_LABEL") + _xml("method", "ALL_PARCELS_IN_ONE_FILE"))
        odp = self._bez_bledow(self.wywolaj("getPrintForParcel", tresc))
        druk = odp.findtext(".//print")
        if not druk:
            raise BladPoczty("e-Nadawca nie zwrócił etykiet")
        return base64.b64decode(druk)

    def wyslij_zbior(self, urzad: str) -> dict:
        odp = self._bez_bledow(self.wywolaj("sendEnvelope", _xml("urzadNadania", _tekst(urzad))))
        return {"id": odp.findtext(".//idEnvelope") or "", "status": odp.findtext(".//envelopeStatus") or ""}

    def ksiazka_nadawcza(self, id_zbioru: str) -> bytes:
        odp = self._bez_bledow(self.wywolaj("getOutboxBook", _xml("idEnvelope", _tekst(id_zbioru))))
        pdf = odp.findtext("pdfContent")
        if not pdf:
            raise BladPoczty("e-Nadawca nie zwrócił książki nadawczej")
        return base64.b64decode(pdf)

    def epo(self, guid: str, id_zbioru: str) -> dict:
        odp = self.wywolaj("getEPOStatus", _xml("guid", guid) + _xml("endedOnly", "false") + _xml("idEnvelope", _tekst(id_zbioru)))
        for e in odp.iter("epo"):
            dor, zwrot = e.find(".//doreczeniePrzesylki"), e.find(".//zwrotPrzesylki")
            return {"status": e.get("statusEPO", ""),
                    "doreczono": (dor.get("data") or "")[:10] if dor is not None else "",
                    "zwrot": (zwrot.get("data") or "")[:10] if zwrot is not None else ""}
        return {}


def przesylka_xml(guid: str, wpis: dict, kategoria: str = "EKONOMICZNA", epo: bool = False) -> str:
    """Wpis z dziennika -> przesylkaPoleconaKrajowaType."""
    ulica, numer_domu, numer_lokalu = rozbij_ulice(wpis.get("ulica", ""))
    nazwa, nazwa2 = podziel_nazwe(wpis["adresat"])
    zpo = wpis.get("sposob") == przesylki.REJESTROWANE[1]
    adres = _xml("adres", nazwa=nazwa, nazwa2=nazwa2, ulica=ulica, numerDomu=numer_domu,
                 numerLokalu=numer_lokalu, miejscowosc=wpis["miejscowosc"][:63],
                 kodPocztowy=re.sub(r"\D", "", wpis["kod"]))
    znak = f"{'DPD' if wpis.get('_ksiega') == 'przeslane' else 'DK'} {wpis['lp']}"
    tresc = adres + ('<e:epo xsi:type="e:EPOSimpleType"/>' if zpo and epo else "")
    return _xml("przesylki", tresc, **{"xsi:type": "e:przesylkaPoleconaKrajowaType", "guid": guid, "opis": znak[:20],
                                       "kategoria": kategoria, "format": "S",
                                       "iloscPotwierdzenOdbioru": "1" if zpo and not epo else ""})


def podziel_nazwe(nazwa: str) -> tuple[str, str]:
    """Pole nazwa ma w e-Nadawcy 60 znakow - reszta idzie do nazwa2, po calym slowie."""
    nazwa = " ".join(nazwa.split())
    if len(nazwa) <= 60:
        return nazwa, ""
    ciecie = nazwa.rfind(" ", 0, 61)
    ciecie = ciecie if ciecie > 20 else 60
    return nazwa[:ciecie].rstrip(" ,"), nazwa[ciecie:].strip()[:60]


def rozbij_ulice(tekst: str) -> tuple[str, str, str]:
    """'ul. Sądowa 12/4' -> ('ul. Sądowa', '12', '4'). Bez numeru - calosc jako ulica."""
    tekst = " ".join(tekst.split())
    m = re.fullmatch(r"(.*?\D)\s*(\d+[A-Za-z]?)(?:\s*(?:/|m\.?|lok\.?)\s*(\w+))?", tekst)
    if not m:
        return tekst, "", ""
    return m.group(1).strip().rstrip(","), m.group(2), m.group(3) or ""


# --- stan kancelarii -------------------------------------------------------


def _pusty() -> dict:
    return {"etap": "start", "wniosek": {}, "polaczenie": {}, "zbiory": [], "ustawienia": {"kategoria": "EKONOMICZNA", "epo": False}}


def stan() -> dict:
    return {**_pusty(), **magazyn.wczytaj_plik_kancelarii(PLIK, {})}


def _zmien(zmiana):
    def opakowanie(d):
        for k, v in _pusty().items():
            d.setdefault(k, v)
        return zmiana(d)
    return magazyn.zmien_plik_kancelarii(PLIK, opakowanie, {})


def dane_rejestracji() -> dict:
    """Dane kancelarii podane przy rejestracji w notarai - podpowiedz wniosku."""
    try:
        import autoryzacja
        wpis = autoryzacja._wczytaj_rejestr().get(magazyn.kancelaria(), {})
    except Exception:  # noqa: BLE001 - tryb lokalny albo brak rejestru
        return {}
    dane = wpis.get("dane") or {}
    return {"nazwa": wpis.get("nazwa", ""), "notariusze": dane.get("notariusze", ""),
            "adres": dane.get("adres", ""), "nip": dane.get("nip", "")}


def _klient_kancelarii(kancelaria: str) -> Klient:
    dane = sejf.wczytaj(kancelaria)
    if not dane:
        raise BladPoczty("Kancelaria nie jest jeszcze połączona z e-Nadawcą")
    return Klient(dane["login"], dane["haslo"], dane.get("srodowisko", "produkcja"))


# --- krok 1: wniosek -------------------------------------------------------

_NIP = re.compile(r"\d{10}")


def sprawdz_wniosek(dane: dict) -> dict:
    w = {k: " ".join(str(dane.get(k) or "").split())[:200] for k in
         ("firma", "nip", "imie", "nazwisko", "email", "telefon", "ulica", "numer", "lokal", "kod", "miejscowosc", "wolumen")}
    w["nip"] = re.sub(r"\D", "", w["nip"])
    w["epo"] = bool(dane.get("epo", True))
    braki = [n for k, n in (("firma", "nazwa kancelarii"), ("imie", "imię"), ("nazwisko", "nazwisko"), ("email", "e-mail"),
                            ("telefon", "telefon"), ("ulica", "ulica"), ("numer", "numer posesji"), ("kod", "kod pocztowy"),
                            ("miejscowosc", "miejscowość")) if not w[k]]
    if braki:
        raise ValueError("Uzupełnij: " + ", ".join(braki))
    if not _NIP.fullmatch(w["nip"]):
        raise ValueError("NIP: 10 cyfr")
    if not re.fullmatch(r"\d{2}-\d{3}", w["kod"]):
        raise ValueError("Kod pocztowy podaj w postaci 00-000")
    if not re.fullmatch(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", w["email"]):
        raise ValueError("Nieprawidłowy adres e-mail")
    if w["wolumen"] not in WOLUMENY:
        w["wolumen"] = WOLUMENY[0]
    return w


def tekst_prosby(w: dict) -> str:
    """Tresc do pola "Uwagi" formularza Poczty i do e-maila."""
    return (
        f"Kancelaria notarialna {w['firma']} (NIP {w['nip']}) prosi o kontakt przedstawiciela handlowego w sprawie umowy na:\n"
        f"1. przesyłki polecone krajowe z potwierdzeniem odbioru (wypisy aktów notarialnych do sądów i urzędów, "
        f"ok. {w['wolumen']} miesięcznie),\n"
        f"2. konto w Elektronicznym Nadawcy z włączonym dostępem do WebAPI - kancelaria nadaje przesyłki z systemu "
        f"NotarAI (notarai.pl),\n"
        + ("3. elektroniczne potwierdzenie odbioru (EPO),\n" if w["epo"] else "")
        + f"{'4' if w['epo'] else '3'}. dla konta WebAPI: wyłączenie wymuszonej zmiany hasła co 30 dni (zgodnie z dokumentacją WebAPI).\n"
        f"Osoba kontaktowa: {w['imie']} {w['nazwisko']}, tel. {w['telefon']}, e-mail {w['email']}.\n"
        f"Adres: {w['ulica']} {w['numer']}{'/' + w['lokal'] if w['lokal'] else ''}, {w['kod']} {w['miejscowosc']}."
    )


def zapisz_wniosek(dane: dict) -> dict:
    w = sprawdz_wniosek(dane)

    def zmiana(d):
        d["wniosek"] = {**w, "zapisano": datetime.now().isoformat(timespec="seconds"), "wyslano": d["wniosek"].get("wyslano", "")}
        return d
    return _zmien(zmiana)


def oznacz_etap(etap: str) -> dict:
    if etap not in ("wniosek", "umowa"):
        raise ValueError("Nieznany etap")

    def zmiana(d):
        if d["etap"] == "polaczona":
            return d
        if etap == "wniosek":
            if not d["wniosek"]:
                raise ValueError("Najpierw wypełnij wniosek")
            d["wniosek"]["wyslano"] = date.today().isoformat()
        d["etap"] = etap
        return d
    return _zmien(zmiana)


def pdf_wniosku(w: dict) -> bytes:
    linie = "".join(f"<p>{html.escape(l)}</p>" for l in tekst_prosby(w).splitlines())
    tresc = f"""
<p style="text-align:right">{html.escape(w['miejscowosc'])}, {date.today().strftime('%d.%m.%Y')}</p>
<p><b>{html.escape(w['firma'])}</b><br>{html.escape(w['ulica'])} {html.escape(w['numer'])}{'/' + html.escape(w['lokal']) if w['lokal'] else ''}<br>
{html.escape(w['kod'])} {html.escape(w['miejscowosc'])}<br>NIP {html.escape(w['nip'])}</p>
<p style="margin-left:55%"><b>Poczta Polska S.A.</b><br>Obsługa klientów biznesowych</p>
<h3 style="text-align:center">Wniosek o zawarcie umowy na usługi pocztowe<br>i udostępnienie Elektronicznego Nadawcy (WebAPI)</h3>
{linie}
<p>Prosimy o przesłanie projektu umowy (umowa na usługi pocztowe, Elektroniczny Nadawca{', EPO' if w['epo'] else ''})
na adres e-mail osoby kontaktowej. Po podpisaniu umowy prosimy o login i hasło do konta z dostępem do WebAPI.</p>
<p style="margin-top:50pt;margin-left:55%">.......................................................<br>podpis i pieczęć notariusza</p>
"""
    css = "* { font-family: sans-serif; } body { font-size: 10.5pt; line-height: 1.35; } p { margin: 0 0 7pt 0; }"
    bufor = io.BytesIO()
    pisarz = fitz.DocumentWriter(bufor)
    story = fitz.Story(html=tresc, user_css=css)
    prostokat = fitz.paper_rect("a4")
    wiecej = True
    while wiecej:
        urzadzenie = pisarz.begin_page(prostokat)
        wiecej, _ = story.place(prostokat + (60, 60, -60, -60))
        story.draw(urzadzenie)
        pisarz.end_page()
    pisarz.close()
    return bufor.getvalue()


# --- krok 3: polaczenie ----------------------------------------------------


def polacz(kancelaria: str, login: str, haslo: str, srodowisko: str) -> dict:
    login, haslo = login.strip(), haslo.strip()
    if not login or not haslo:
        raise ValueError("Podaj login i hasło z e-maila od Poczty Polskiej")
    klient = Klient(login, haslo, srodowisko)
    klient.hello()  # sprawdza login i haslo; odmowa = OdmowaLogowania, bez ponawiania
    urzedy, karty = klient.urzedy_nadania(), klient.karty()
    try:
        wygasa = klient.haslo_wygasa()
    except BladPoczty:
        wygasa = ""
    sejf.zapisz(kancelaria, {"login": login, "haslo": haslo, "srodowisko": srodowisko})

    def zmiana(d):
        d["etap"] = "polaczona"
        d["polaczenie"] = {"srodowisko": srodowisko, "login": login[:2] + "***", "urzedy": urzedy, "karty": karty,
                           "urzad": urzedy[0]["id"] if len(urzedy) == 1 else d["polaczenie"].get("urzad", ""),
                           "karta": next((k["id"] for k in karty if k["aktywna"]), ""),
                           "haslo_wygasa": wygasa, "polaczono": datetime.now().isoformat(timespec="seconds")}
        return d
    log.info("poczta: kancelaria polaczona z e-Nadawca (%s)", srodowisko)
    return _zmien(zmiana)


def ustaw(kancelaria: str, dane: dict) -> dict:
    s = stan()
    if s["etap"] != "polaczona":
        raise ValueError("Najpierw połącz kancelarię z e-Nadawcą")
    urzad, karta = str(dane.get("urzad") or ""), str(dane.get("karta") or "")
    if urzad and urzad not in {u["id"] for u in s["polaczenie"].get("urzedy", [])}:
        raise ValueError("Wybierz urząd nadania z listy")
    if karta and karta != s["polaczenie"].get("karta"):
        if karta not in {k["id"] for k in s["polaczenie"].get("karty", [])}:
            raise ValueError("Wybierz kartę umowy z listy")
        _klient_kancelarii(kancelaria).ustaw_karte(karta)
    kategoria = str(dane.get("kategoria") or "EKONOMICZNA")
    if kategoria not in KATEGORIE:
        raise ValueError("Nieznana kategoria przesyłki")

    def zmiana(d):
        if urzad:
            d["polaczenie"]["urzad"] = urzad
        if karta:
            d["polaczenie"]["karta"] = karta
        d["ustawienia"] = {"kategoria": kategoria, "epo": bool(dane.get("epo"))}
        return d
    return _zmien(zmiana)


def nowe_haslo() -> str:
    """Haslo na zmiane: litery obu wielkosci, cyfra i znak specjalny."""
    znaki = string.ascii_letters + string.digits + "!@#$%^*-_"
    while True:
        haslo = "".join(secrets.choice(znaki) for _ in range(20))
        if (any(c.islower() for c in haslo) and any(c.isupper() for c in haslo)
                and any(c.isdigit() for c in haslo) and any(not c.isalnum() for c in haslo)):
            return haslo


def zmien_haslo(kancelaria: str) -> dict:
    """Zmiana hasla w e-Nadawcy bez udzialu kancelarii.

    Nowe haslo trafia do sejfu jako "oczekujace" PRZED wywolaniem Poczty:
    gdyby zapis po zmianie sie nie udal, kancelaria nie zostalaby bez hasla.
    """
    dane = sejf.wczytaj(kancelaria)
    if not dane:
        raise BladPoczty("Kancelaria nie jest połączona z e-Nadawcą")
    nowe = nowe_haslo()
    sejf.zapisz(kancelaria, {**dane, "haslo_oczekujace": nowe})
    Klient(dane["login"], dane["haslo"], dane.get("srodowisko", "produkcja")).zmien_haslo(nowe)
    sejf.zapisz(kancelaria, {"login": dane["login"], "haslo": nowe, "srodowisko": dane.get("srodowisko", "produkcja")})
    try:
        wygasa = Klient(dane["login"], nowe, dane.get("srodowisko", "produkcja")).haslo_wygasa()
    except BladPoczty:
        wygasa = ""

    def zmiana(d):
        d["polaczenie"]["haslo_wygasa"] = wygasa
        d["polaczenie"]["haslo_zmieniono"] = date.today().isoformat()
        return d
    log.info("poczta: haslo e-Nadawcy zmienione automatycznie")
    return _zmien(zmiana)


def odlacz(kancelaria: str) -> dict:
    sejf.usun(kancelaria)

    def zmiana(d):
        d["etap"] = "umowa"
        d["polaczenie"] = {}
        return d
    return _zmien(zmiana)


# --- nadawanie z dziennika -------------------------------------------------

_blokada_nadania = threading.Lock()


def _pozycje(wybor: list[dict]) -> list[dict]:
    """[{ksiega, id}] -> wpisy z dziennikow (tylko polecone wychodzace)."""
    wynik = []
    for ksiega in przesylki.KSIEGI:
        ids = {p["id"] for p in wybor if p.get("ksiega") == ksiega}
        for w in przesylki.lista(ksiega):
            if w["id"] in ids:
                if w.get("status") == "anulowany" or w.get("sposob") not in przesylki.REJESTROWANE or w.get("kierunek") == "przychodzące":
                    raise ValueError(f"Pozycja {w['lp']} nie jest listem poleconym do nadania")
                wynik.append({**w, "_ksiega": ksiega})
    if not wynik:
        raise ValueError("Zaznacz listy polecone do nadania")
    return wynik


def _zapisz_w_ksiegach(zmiany: dict[tuple[str, str], dict], kto: str = "") -> None:
    for ksiega in przesylki.KSIEGI:
        moje = {i: z for (k, i), z in zmiany.items() if k == ksiega}
        if not moje:
            continue

        def zmiana(d):
            for wpis in d["wpisy"]:
                if wpis["id"] in moje:
                    z = moje[wpis["id"]]
                    pp = {**wpis.get("poczta", {}), **{k: v for k, v in z.items() if k != "numer_nadania"}}
                    wpis["poczta"] = pp
                    if "numer_nadania" in z and z["numer_nadania"] != wpis.get("numer_nadania", ""):
                        przesylki._popraw(wpis, {"numer_nadania": z["numer_nadania"]}, kto)
        magazyn.zmien_plik_kancelarii(przesylki.KSIEGI[ksiega]["plik"], zmiana, przesylki._pusta())


def nadaj(kancelaria: str, wybor: list[dict], kto: str = "") -> dict:
    """addShipment: przesylki trafiaja do bufora e-Nadawcy, numery do ksiegi."""
    s = stan()
    if s["etap"] != "polaczona":
        raise ValueError("Najpierw połącz kancelarię z e-Nadawcą")
    pozycje = [w for w in _pozycje(wybor) if not w.get("poczta", {}).get("guid")]
    if not pozycje:
        raise ValueError("Zaznaczone przesyłki są już w e-Nadawcy")
    for w in pozycje:
        if not (w.get("ulica") and re.fullmatch(r"\d{2}-\d{3}", w.get("kod", "")) and w.get("miejscowosc")):
            raise ValueError(f"Pozycja {w['lp']}: uzupełnij ulicę, kod i miejscowość")
    with _blokada_nadania:
        klient = _klient_kancelarii(kancelaria)
        guidy = klient.guidy(len(pozycje))
        ust = s["ustawienia"]
        wynik = klient.dodaj([przesylka_xml(g, w, ust.get("kategoria", "EKONOMICZNA"), ust.get("epo", False))
                              for g, w in zip(guidy, pozycje)])
        dzis = date.today().isoformat()
        zmiany, bledy = {}, []
        for g, w in zip(guidy, pozycje):
            r = wynik.get(g, {"numer": "", "bledy": ["brak odpowiedzi dla przesyłki"]})
            if r["bledy"] or not r["numer"]:
                bledy.append(f"poz. {w['lp']}: " + "; ".join(r["bledy"] or ["brak numeru nadania"]))
                continue
            zmiany[(w["_ksiega"], w["id"])] = {"guid": g, "numer_nadania": r["numer"], "dodano": dzis, "zbior": ""}
        _zapisz_w_ksiegach(zmiany, kto)
    return {"nadano": len(zmiany), "bledy": bledy}


def _w_buforze() -> list[dict]:
    return [{**w, "_ksiega": k} for k in przesylki.KSIEGI for w in przesylki.lista(k)
            if w.get("poczta", {}).get("guid") and not w["poczta"].get("zbior")]


def etykiety(kancelaria: str, wybor: list[dict]) -> bytes:
    guidy = [w["poczta"]["guid"] for w in _pozycje(wybor) if w.get("poczta", {}).get("guid")]
    if not guidy:
        raise ValueError("Najpierw nadaj zaznaczone przesyłki w e-Nadawcy")
    return _klient_kancelarii(kancelaria).etykiety(guidy)


def wycofaj(kancelaria: str, wybor: list[dict], kto: str = "") -> int:
    """Usuniecie z bufora e-Nadawcy (przed wyslaniem zbioru)."""
    pozycje = [w for w in _pozycje(wybor) if w.get("poczta", {}).get("guid") and not w["poczta"].get("zbior")]
    if not pozycje:
        raise ValueError("Zaznaczone przesyłki nie czekają w buforze e-Nadawcy")
    _klient_kancelarii(kancelaria).usun_z_bufora([w["poczta"]["guid"] for w in pozycje])
    _zapisz_w_ksiegach({(w["_ksiega"], w["id"]): {"guid": "", "numer_nadania": "", "dodano": "", "zbior": ""} for w in pozycje}, kto)
    return len(pozycje)


def wyslij_zbior(kancelaria: str) -> dict:
    s = stan()
    urzad = s["polaczenie"].get("urzad")
    if not urzad:
        raise ValueError("Wybierz urząd nadania w ustawieniach połączenia z Pocztą")
    pozycje = _w_buforze()
    if not pozycje:
        raise ValueError("Nie ma przesyłek czekających na wysłanie zbioru")
    dzis = date.today().isoformat()
    stare = [w for w in pozycje if w["poczta"].get("dodano") != dzis]
    if stare:
        raise ValueError("W buforze są przesyłki z poprzednich dni (poz. " + ", ".join(str(w["lp"]) for w in stare)
                         + "). e-Nadawca przyjmuje zbiór tylko z przesyłek dodanych tego samego dnia - wycofaj je i nadaj ponownie.")
    zbior = _klient_kancelarii(kancelaria).wyslij_zbior(urzad)
    if not zbior["id"]:
        raise BladPoczty("e-Nadawca nie potwierdził przyjęcia zbioru")
    _zapisz_w_ksiegach({(w["_ksiega"], w["id"]): {"zbior": zbior["id"]} for w in pozycje})

    def zmiana(d):
        d["zbiory"].insert(0, {"id": zbior["id"], "data": dzis, "przesylek": len(pozycje), "status": zbior["status"]})
        del d["zbiory"][200:]
        return d
    _zmien(zmiana)
    log.info("poczta: wyslano zbior z %d przesylkami", len(pozycje))
    return {**zbior, "przesylek": len(pozycje)}


def ksiazka_nadawcza(kancelaria: str, id_zbioru: str) -> bytes:
    if id_zbioru not in {z["id"] for z in stan()["zbiory"]}:
        raise ValueError("Nie ma takiego zbioru")
    return _klient_kancelarii(kancelaria).ksiazka_nadawcza(id_zbioru)


def odswiez_doreczenia(kancelaria: str) -> dict:
    """EPO: daty doreczen przesylek z wyslanych zbiorow trafiaja do ksiegi."""
    klient = _klient_kancelarii(kancelaria)
    zmiany, sprawdzono = {}, 0
    for k in przesylki.KSIEGI:
        for w in przesylki.lista(k):
            pp = w.get("poczta", {})
            if not (pp.get("guid") and pp.get("zbior")) or w.get("data_doreczenia") or w.get("status") == "anulowany":
                continue
            sprawdzono += 1
            wynik = klient.epo(pp["guid"], pp["zbior"])
            if wynik.get("doreczono") or wynik.get("zwrot"):
                zmiany[(k, w["id"])] = wynik
    for (k, ident), wynik in zmiany.items():
        def zmiana(d, ident=ident, wynik=wynik):
            for wpis in d["wpisy"]:
                if wpis["id"] == ident:
                    if wynik.get("doreczono"):
                        przesylki._popraw(wpis, {"data_doreczenia": wynik["doreczono"]}, "e-Nadawca (EPO)")
                    wpis.setdefault("poczta", {})["epo"] = wynik
        magazyn.zmien_plik_kancelarii(przesylki.KSIEGI[k]["plik"], zmiana, przesylki._pusta())
    return {"sprawdzono": sprawdzono, "zmieniono": len(zmiany)}


# --- API -------------------------------------------------------------------

router = APIRouter(prefix="/api/poczta", tags=["poczta"])


def _wykonaj(funkcja, *argumenty):
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie - połączenie z Pocztą wymaga zapisu na serwerze.")
    try:
        return funkcja(*argumenty)
    except OdmowaLogowania as blad:
        raise HTTPException(400, str(blad))
    except BladPoczty as blad:
        raise HTTPException(502, str(blad))
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))
    except ValueError as blad:
        raise HTTPException(400, str(blad))


def _publiczny(s: dict) -> dict:
    """Stan dla przegladarki - bez hasla (i tak go tu nie ma) i z podpowiedziami."""
    return {**s, "formularz_poczty": FORMULARZ_POCZTY, "rejestracja_enadawcy": REJESTRACJA_ENADAWCY,
            "email_poczty": EMAIL_POCZTY, "telefony_poczty": TELEFONY_POCZTY, "wolumeny": WOLUMENY,
            "kategorie": KATEGORIE, "srodowiska": list(SRODOWISKA), "rejestracja": dane_rejestracji(),
            "prosba": tekst_prosby(s["wniosek"]) if s.get("wniosek", {}).get("firma") else "",
            "w_buforze": len(_w_buforze())}


class Wniosek(BaseModel):
    firma: str = ""
    nip: str = ""
    imie: str = ""
    nazwisko: str = ""
    email: str = ""
    telefon: str = ""
    ulica: str = ""
    numer: str = ""
    lokal: str = ""
    kod: str = ""
    miejscowosc: str = ""
    wolumen: str = WOLUMENY[0]
    epo: bool = True


class Etap(BaseModel):
    etap: str


class Polaczenie(BaseModel):
    login: str
    haslo: str
    srodowisko: str = "produkcja"


class Ustawienia(BaseModel):
    urzad: str = ""
    karta: str = ""
    kategoria: str = "EKONOMICZNA"
    epo: bool = False


class Wybor(BaseModel):
    pozycje: list[dict]


def _kto(request: Request) -> str:
    return str(getattr(request.state, "email", "") or "")


@router.get("")
def pobierz_stan():
    return _publiczny(_wykonaj(stan))


@router.put("/wniosek")
def zapisz_wniosek_api(dane: Wniosek):
    return _publiczny(_wykonaj(zapisz_wniosek, dane.model_dump()))


@router.get("/wniosek.pdf")
def wniosek_pdf():
    w = _wykonaj(stan)["wniosek"]
    if not w.get("firma"):
        raise HTTPException(400, "Najpierw wypełnij i zapisz wniosek")
    return Response(pdf_wniosku(w), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="wniosek-poczta-polska.pdf"', "Cache-Control": "no-store"})


@router.post("/etap")
def ustaw_etap(dane: Etap):
    return _publiczny(_wykonaj(oznacz_etap, dane.etap))


@router.post("/polacz")
def polacz_api(dane: Polaczenie):
    return _publiczny(_wykonaj(polacz, magazyn.kancelaria(), dane.login, dane.haslo, dane.srodowisko))


@router.put("/ustawienia")
def ustawienia_api(dane: Ustawienia):
    return _publiczny(_wykonaj(ustaw, magazyn.kancelaria(), dane.model_dump()))


@router.post("/haslo")
def haslo_api():
    return _publiczny(_wykonaj(zmien_haslo, magazyn.kancelaria()))


@router.delete("/polaczenie")
def odlacz_api():
    return _publiczny(_wykonaj(odlacz, magazyn.kancelaria()))


@router.post("/nadaj")
def nadaj_api(dane: Wybor, request: Request):
    return _wykonaj(nadaj, magazyn.kancelaria(), dane.pozycje, _kto(request))


@router.post("/wycofaj")
def wycofaj_api(dane: Wybor, request: Request):
    return {"wycofano": _wykonaj(wycofaj, magazyn.kancelaria(), dane.pozycje, _kto(request))}


@router.post("/etykiety.pdf")
def etykiety_api(dane: Wybor):
    return Response(_wykonaj(etykiety, magazyn.kancelaria(), dane.pozycje), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="etykiety.pdf"', "Cache-Control": "no-store"})


@router.post("/zbior")
def zbior_api():
    return _wykonaj(wyslij_zbior, magazyn.kancelaria())


@router.get("/zbior/{id_zbioru}/ksiazka.pdf")
def ksiazka_api(id_zbioru: str):
    return Response(_wykonaj(ksiazka_nadawcza, magazyn.kancelaria(), id_zbioru), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="ksiazka-nadawcza-{id_zbioru}.pdf"', "Cache-Control": "no-store"})


@router.post("/doreczenia")
def doreczenia_api():
    return _wykonaj(odswiez_doreczenia, magazyn.kancelaria())
