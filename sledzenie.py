"""Sledzenie przesylek Poczty Polskiej - statusy listow z dziennikow.

Usluga SOAP "Sledzenie" Poczty Polskiej (dokumentacja:
https://www.poczta-polska.pl/dla-biznesu/wsparcie/integracje/systemy-sledzenia/).
Poczta publikuje tam domyslne konto do pojedynczych zapytan
(login sledzeniepp, haslo PPSA, WS-Security UsernameToken PasswordText).
Kancelaria albo notarai moze dostac konto dedykowane (formularz Poczty,
"Wniosek o utworzenie konta WSDL/SOAP") - wtedy podajemy je w zmiennych
PIECZAPP_PP_SLEDZENIE_LOGIN / _HASLO (w chmurze jako referencja do sekretu
w Secrets Manager) i pytamy paczkami (PIECZAPP_PP_SLEDZENIE_PACZKA).
Sprawdzone 08.11.2026: konto domyslne w sprawdzPrzesylki odpowiada tylko
o pierwszy numer, dlatego dla niego pytamy o kazdy numer osobno.

Zasady z dokumentacji:
  - mapujemy KODY zdarzen (P_D, P_NAD...), nie nazwy - nazwy moga sie zmienic,
  - usluga zwraca przesylki ze zdarzeniem z ostatnich 30 dni,
  - danych nie wolno zmieniac merytorycznie - pokazujemy je tak, jak przyszly.

Doreczenie (stan DO albo odbior w placowce/punkcie) uzupelnia w ksiedze date
doreczenia - jako uzupelnienie, nie poprawke. Zwrot do nadawcy oznaczamy na
czerwono. Numery nadania nie sa danymi osobowymi, ale adresy w ksiegach tak:
do Poczty wysylamy wylacznie numery.
"""
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from html import escape

import httpx
from fastapi import APIRouter, HTTPException

import magazyn
import przesylki

log = logging.getLogger("pieczapp.sledzenie")

ADRES = os.getenv("PIECZAPP_PP_SLEDZENIE_ADRES", "https://tt.poczta-polska.pl/Sledzenie/services/Sledzenie")
NS = "http://sledzenie.pocztapolska.pl"
# Konto domyslne opublikowane przez Poczte Polska w dokumentacji uslugi.
LOGIN = os.getenv("PIECZAPP_PP_SLEDZENIE_LOGIN", "sledzeniepp")
HASLO = os.getenv("PIECZAPP_PP_SLEDZENIE_HASLO", "PPSA")
PACZKA = max(1, int(os.getenv("PIECZAPP_PP_SLEDZENIE_PACZKA", "1")))
CZAS = float(os.getenv("PIECZAPP_PP_SLEDZENIE_CZAS", "30"))
PROB = 3
# Jak czesto odswiezac statusy samoczynnie (przy otwarciu widoku).
CO_ILE = timedelta(hours=float(os.getenv("PIECZAPP_PP_SLEDZENIE_CO_GODZIN", "3")))
# Starszych przesylek usluga i tak nie zna (zdarzenie w ostatnich 30 dniach).
DNI_WSTECZ = 45
TRANSPORT = None  # testy podstawiaja httpx.MockTransport

# Kody zdarzen -> stan, wg listy Poczty Polskiej (PPSA_events_lists, 20250205).
DORECZONA = {"P_D", "P_DS", "P_S", "P_ZPNA", "P_OWU", "P_OWP"}
ZWROCONA = {"P_NDZ", "P_ZDUN", "P_ZZPZ", "P_ZZP"}
AWIZO = {"P_A", "P_ADR", "P_APP", "P_PA", "P_DKAO", "P_KWD", "P_PWP"}
NADANA = {"P_NAD", "P_REJ_KN1"}
STANY = {"doreczona": "doręczona", "zwrocona": "zwrócona do nadawcy", "awizo": "awizowana / czeka na odbiór",
         "w_drodze": "w drodze", "nadana": "nadana", "brak": "jeszcze nie ma w systemie Poczty"}


class BladSledzenia(RuntimeError):
    pass


def _koperta(metoda: str, numery: list[str]) -> bytes:
    cialo = "".join(f"<sle:numer>{escape(n)}</sle:numer>" for n in numery)
    return (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        f'xmlns:sle="{NS}"><soapenv:Header>'
        '<wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">'
        f"<wsse:UsernameToken><wsse:Username>{escape(LOGIN)}</wsse:Username>"
        '<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">'
        f"{escape(HASLO)}</wsse:Password></wsse:UsernameToken></wsse:Security></soapenv:Header>"
        f"<soapenv:Body><sle:{metoda}>{cialo}</sle:{metoda}></soapenv:Body></soapenv:Envelope>"
    ).encode("utf-8")


def _bez_ns(korzen: ET.Element) -> ET.Element:
    for e in korzen.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]
    return korzen


def _wywolaj(metoda: str, numery: list[str]) -> ET.Element:
    """Usluga bywa chwilowo niedostepna (zerwane polaczenie) - ponawiamy.
    To odczyt publicznej uslugi, ponowienie niczego nie psuje."""
    ostatni = None
    with httpx.Client(timeout=CZAS, transport=TRANSPORT) as http:
        for proba in range(PROB):
            try:
                odp = http.post(ADRES, content=_koperta(metoda, numery),
                                headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"urn:{metoda}"'})
            except httpx.HTTPError as blad:
                ostatni = blad
                time.sleep(min(2 ** proba, 4) if TRANSPORT is None else 0)
                continue
            try:
                korzen = _bez_ns(ET.fromstring(odp.content))
            except ET.ParseError:
                raise BladSledzenia(f"Nieczytelna odpowiedź usługi śledzenia (HTTP {odp.status_code})")
            blad = korzen.find(".//Fault")
            if blad is not None:
                raise BladSledzenia("Śledzenie Poczty: " + (blad.findtext("faultstring") or "błąd").strip())
            return korzen
    raise BladSledzenia(f"Usługa śledzenia Poczty nie odpowiada ({type(ostatni).__name__}). Spróbuj później.")


def _stan(zdarzenia: list[dict]) -> str:
    kody = [z["kod"] for z in zdarzenia]
    if any(k in DORECZONA for k in kody):
        return "doreczona"
    if any(k in ZWROCONA for k in kody):
        return "zwrocona"
    if not kody:
        return "nadana"
    if kody[-1] in AWIZO:
        return "awizo"
    return "nadana" if kody[-1] in NADANA else "w_drodze"


def _przesylka(p: ET.Element) -> dict:
    numer = (p.findtext("numer") or "").strip()
    status = int(p.findtext("status") or -99)
    if status not in (0, 1):
        return {"numer": numer, "status": status, "stan": "brak", "zdarzenia": []}
    zdarzenia = []
    for z in p.iter("zdarzenie"):
        zdarzenia.append({"czas": (z.findtext("czas") or "").strip(), "kod": (z.findtext("kod") or "").strip(),
                          "nazwa": (z.findtext("nazwa") or "").strip(), "konczace": z.findtext("konczace") == "true",
                          "jednostka": (z.findtext("jednostka/nazwa") or "").strip()})
    zdarzenia.sort(key=lambda z: z["czas"])
    stan = _stan(zdarzenia)
    kluczowe = next((z for z in reversed(zdarzenia) if z["kod"] in (DORECZONA if stan == "doreczona" else ZWROCONA)), None)
    return {"numer": numer, "status": status, "stan": stan, "zdarzenia": zdarzenia,
            "ostatnie": zdarzenia[-1] if zdarzenia else None,
            "doreczono": kluczowe["czas"][:10] if stan == "doreczona" and kluczowe else "",
            "zwrot": kluczowe["czas"][:10] if stan == "zwrocona" and kluczowe else ""}


def sprawdz(numery: list[str]) -> dict[str, dict]:
    """{numer: wynik}. Jedno zapytanie na numer (konto domyslne) albo paczkami."""
    wynik = {}
    numery = list(dict.fromkeys(n for n in numery if n))
    for i in range(0, len(numery), PACZKA):
        czesc = numery[i:i + PACZKA]
        if len(czesc) == 1:
            korzen = _wywolaj("sprawdzPrzesylke", czesc)
            for p in korzen.iter("return"):
                w = _przesylka(p)
                wynik[w["numer"] or czesc[0]] = w
            continue
        korzen = _wywolaj("sprawdzPrzesylki", czesc)
        status = int(korzen.findtext(".//return/status") or 0)
        if status in (-1, -2):  # za duzo albo brak uprawnien do wielu - pojedynczo
            for n in czesc:
                wynik.update(_jeden(n))
            continue
        for p in korzen.iter("przesylka"):
            w = _przesylka(p)
            wynik[w["numer"]] = w
    return wynik


def _jeden(numer: str) -> dict[str, dict]:
    korzen = _wywolaj("sprawdzPrzesylke", [numer])
    return {numer: _przesylka(next(korzen.iter("return")))}


# --- dzienniki -------------------------------------------------------------


def _do_sprawdzenia() -> list[tuple[str, dict]]:
    granica = (date.today() - timedelta(days=DNI_WSTECZ)).isoformat()
    wynik = []
    for ksiega in przesylki.KSIEGI:
        for w in przesylki.lista(ksiega):
            s = w.get("sledzenie") or {}
            if (w.get("numer_nadania") and w.get("status") != "anulowany" and w.get("data", "") >= granica
                    and s.get("stan") not in ("doreczona", "zwrocona") and not w.get("data_doreczenia")):
                wynik.append((ksiega, w))
    return wynik


def odswiez(wymus: bool = True) -> dict:
    """Pyta Poczte o przesylki w drodze i zapisuje statusy w ksiegach."""
    ust = przesylki.ustawienia()
    ostatnio = ust.get("sledzenie_sprawdzono", "")
    if not wymus and ostatnio and datetime.fromisoformat(ostatnio) > datetime.now() - CO_ILE:
        return {"sprawdzono": 0, "doreczone": 0, "zwrocone": 0, "pominieto": True, "ostatnio": ostatnio}
    pozycje = _do_sprawdzenia()
    statusy = sprawdz([w["numer_nadania"] for _, w in pozycje]) if pozycje else {}
    teraz = datetime.now().isoformat(timespec="seconds")
    licznik = {"doreczone": 0, "zwrocone": 0}
    for ksiega in przesylki.KSIEGI:
        moje = {w["id"]: statusy[w["numer_nadania"]] for k, w in pozycje if k == ksiega and w["numer_nadania"] in statusy}
        if not moje:
            continue

        def zmiana(d, moje=moje):
            for wpis in d["wpisy"]:
                s = moje.get(wpis["id"])
                if not s:
                    continue
                wpis["sledzenie"] = {"stan": s["stan"], "ostatnie": s.get("ostatnie"), "sprawdzono": teraz,
                                     "zwrot": s.get("zwrot", "")}
                if s["stan"] == "doreczona" and s.get("doreczono") and not wpis.get("data_doreczenia"):
                    przesylki._popraw(wpis, {"data_doreczenia": s["doreczono"]}, "Poczta Polska (śledzenie)")
                    licznik["doreczone"] += 1
                if s["stan"] == "zwrocona":
                    licznik["zwrocone"] += 1
        magazyn.zmien_plik_kancelarii(przesylki.KSIEGI[ksiega]["plik"], zmiana, przesylki._pusta())

    def zapamietaj(d):
        d["sledzenie_sprawdzono"] = teraz
    magazyn.zmien_plik_kancelarii(przesylki.PLIK_USTAWIEN, zapamietaj, {})
    log.info("sledzenie: sprawdzono %d przesylek, doreczone %d, zwroty %d", len(pozycje), licznik["doreczone"], licznik["zwrocone"])
    return {"sprawdzono": len(pozycje), **licznik, "pominieto": False, "ostatnio": teraz}


def historia(numer: str) -> dict:
    numer = "".join(numer.split()).upper()
    if not przesylki._NUMER.fullmatch(numer):
        raise ValueError("Nieprawidłowy numer nadania")
    return sprawdz([numer]).get(numer) or {"numer": numer, "stan": "brak", "zdarzenia": []}


# --- API -------------------------------------------------------------------

router = APIRouter(prefix="/api/sledzenie", tags=["sledzenie"])


def _wykonaj(funkcja, *argumenty):
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie - statusy przesyłek zapisywałyby się na serwerze.")
    try:
        return funkcja(*argumenty)
    except BladSledzenia as blad:
        raise HTTPException(502, str(blad))
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))
    except ValueError as blad:
        raise HTTPException(400, str(blad))


@router.post("")
def odswiez_api(wymus: bool = True):
    """Odswiezenie statusow. wymus=false: tylko gdy ostatnio dawniej niz CO_ILE."""
    return _wykonaj(odswiez, wymus)


@router.get("/{numer}")
def historia_api(numer: str):
    return {**_wykonaj(historia, numer), "opisy_stanow": STANY}
