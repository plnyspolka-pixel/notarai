"""Publiczne rejestry i katalog dostępów. Bez sekretów, bez automatycznej wysyłki."""
from datetime import date, datetime, timezone
import json
import re
import httpx

MC = "https://www.gov.pl/web/cyfryzacja/"
GEO = "https://uldk.gugik.gov.pl/opis.html"
RN = "https://www.rejestry-notarialne.pl/"
KATALOG = (
 ("uldk","Lokalizacja działek katastralnych","publiczne_api","GUGiK",GEO),
 ("krs","Krajowy Rejestr Sądowy","publiczne_api","Ministerstwo Sprawiedliwości","https://prs.ms.gov.pl/krs/"),
 ("vat","Wykaz podatników VAT","publiczne_api","Ministerstwo Finansów","https://wykazpodatnikowvat.mf.gov.pl/api"),
 ("egib","Ewidencja gruntów i budynków – dane publiczne","portal","GUGiK","https://mapy.geoportal.gov.pl/"),
 ("rcn","Rejestr Cen Nieruchomości","portal","GUGiK","https://mapy.geoportal.gov.pl/"),
 ("mpzp","Plany zagospodarowania przestrzennego","portal","Gminy","https://mapy.geoportal.gov.pl/"),
 ("rznp","Rejestr Zastrzeżeń Numerów PESEL","wymaga_dostepu","Ministerstwo Cyfryzacji / COI",MC+"udostepnianie-danych-z-rejestru-zastrzezen-numerow-pesel"),
 ("pesel","Rejestr PESEL","wymaga_dostepu","Ministerstwo Cyfryzacji",MC+"udostepnianie-danych-z-rejestru-pesel1"),
 ("rdo","Rejestr Dowodów Osobistych","wymaga_dostepu","Ministerstwo Cyfryzacji",MC+"udostepnianie-danych-z-rejestru-dowodow-osobistych1"),
 ("rdp","Rejestr Dokumentów Paszportowych","wymaga_dostepu","Ministerstwo Cyfryzacji",MC+"udostepnienie-danych-z-rejestru-dokumentow-paszportowych"),
 ("rsc","Rejestr Stanu Cywilnego – usługa sieciowa","wymaga_potwierdzenia","Ministerstwo Cyfryzacji",MC+"udostepnianie-danych-z-rejestru-urzedu-stanu-cywilnego"),
 ("rdk","Rejestr Danych Kontaktowych","wymaga_potwierdzenia","Ministerstwo Cyfryzacji",MC+"udostepnianie-danych-z-rejestru-danych-kontaktowych"),
 ("odpis","Odpis aktu urodzenia, małżeństwa lub zgonu","wniosek","Urząd stanu cywilnego","https://www.gov.pl/web/gov/uzyskaj-odpis-aktu-stanu-cywilnego-urodzenia-malzenstwa-zgonu"),
 ("stan_cywilny","Zaświadczenie o stanie cywilnym","wniosek","Urząd stanu cywilnego","https://www.gov.pl/web/gov/uzyskaj-zaswiadczenie-o-stanie-cywilnym"),
 ("wypis","Urzędowy wypis i wyrys z ewidencji gruntów","wniosek","Właściwy starosta lub prezydent miasta","https://www.gov.pl/web/gov/uzyskaj-wypis-i-wyrys-z-ewidencji-gruntow-i-budynkow"),
 ("zsin","Zintegrowany System Informacji o Nieruchomościach","wymaga_potwierdzenia","Główny Geodeta Kraju","https://www.gov.pl/web/gugik/formularze"),
 ("krz","Krajowy Rejestr Zadłużonych","istniejacy_modul","Ministerstwo Sprawiedliwości","https://krz.ms.gov.pl/"),
 ("ekw","Elektroniczne Księgi Wieczyste","istniejacy_modul","Ministerstwo Sprawiedliwości","https://ekw.ms.gov.pl/"),
 ("szukaj_kw","Wielokrotne wyszukiwanie ksiąg wieczystych","wymaga_dostepu","Ministerstwo Sprawiedliwości","https://www.gov.pl/web/sprawiedliwosc/informacje-ogolne"),
 ("ceidg","Centralna Ewidencja i Informacja o Działalności Gospodarczej","portal","Ministerstwo Rozwoju i Technologii","https://www.biznes.gov.pl/pl/wyszukiwarka-firm"),
 ("regon","Rejestr REGON","portal","Główny Urząd Statystyczny","https://wyszukiwarkaregon.stat.gov.pl/"),
 ("crbr","Centralny Rejestr Beneficjentów Rzeczywistych","istniejacy_modul","Ministerstwo Finansów","https://crbr.podatki.gov.pl/"),
 ("spadkowy","Rejestr Spadkowy","portal","Krajowa Rada Notarialna",RN),
 ("nort","Notarialny Rejestr Testamentów","wymaga_dostepu","Krajowa Rada Notarialna",RN),
 ("crewan","Centralne Repozytorium Elektronicznych Wypisów Aktów Notarialnych","wymaga_dostepu","Krajowa Rada Notarialna",RN),
 ("edoreczenia","e-Doręczenia i Baza Adresów Elektronicznych","wymaga_dostepu","Ministerstwo Cyfryzacji / COI","https://www.gov.pl/web/e-doreczenia/integracja-uslugi-e-doreczen-z-systemami-klasy-ezd"),
 ("mobywatel","mObywatel – przekazywanie danych","wymaga_dostepu","Ministerstwo Cyfryzacji","https://wspolpraca.mobywatel.gov.pl/"),
 ("giif","Raportowanie do GIIF i KAS","istniejacy_modul","Ministerstwo Finansów","https://www.giif.mofnet.gov.pl/"),
)
def katalog():
    return [dict(zip(("id","nazwa","sciezka","instytucja","url"),r)) for r in KATALOG]

class Niedostepny(RuntimeError):
    pass

def _get(url, params, client, *, timeout=12):
    try:
        with client.stream("GET",url,params=params,timeout=timeout,follow_redirects=False) as r:
            if r.status_code != 200:
                raise Niedostepny("Źródło nie zwróciło poprawnej odpowiedzi.")
            buf = bytearray()
            for chunk in r.iter_bytes():
                buf.extend(chunk)
                if len(buf)>2_000_000:
                    raise Niedostepny("Odpowiedź przekracza limit.")
            return bytes(buf)
    except httpx.HTTPError:
        raise Niedostepny("Nie udało się połączyć z rejestrem.") from None

def _wynik(zrodlo,dane):
    return {"zrodlo":zrodlo,"pobrano":datetime.now(timezone.utc).isoformat(),
            "dane":dane,"charakter":"Informacja z rejestru; nie zastępuje dokumentu urzędowego ani oceny notariusza."}

POLA=("id","parcel","county","commune","region","voivodeship","datasource")
_ID_DZIALKI=re.compile(r"[0-9]{6}_[0-9]\.[0-9]{4}\.(?:AR_[0-9]+\.)?[0-9]+(?:/[0-9]+)?")

def dzialka(identyfikator,client):
    pelny=bool(_ID_DZIALKI.fullmatch(identyfikator))
    if not pelny and (len(identyfikator)>64 or not re.fullmatch(r"[^\W\d_][\w .'-]* [0-9]+(?:/[0-9]+)?",identyfikator)):
        raise ValueError("Podaj pełny identyfikator albo nazwę obrębu i numer działki, np. Krzewina 134.")
    metoda="GetParcelById" if pelny else "GetParcelByIdOrNr"
    raw=_get("https://uldk.gugik.gov.pl/",{"request":metoda,"id":identyfikator,"result":",".join(POLA)},client,timeout=12 if pelny else 30)
    try:
        lines=raw.decode("utf-8").strip().splitlines()
        if not lines or not re.fullmatch(r"[0-9]{1,3}",lines[0].strip()):
            raise ValueError()
        count=int(lines[0].strip())
        if (pelny and (count!=0 or len(lines)!=2)) or (not pelny and (count!=len(lines)-1 or count>200)):
            raise ValueError()
        rekordy=[]
        for line in lines[1:]:
            fields=[x.strip() for x in line.split("|")]
            if len(fields)!=len(POLA) or not _ID_DZIALKI.fullmatch(fields[0]):
                raise ValueError()
            rekordy.append(dict(zip(POLA,fields)))
        if pelny:
            if rekordy[0]["id"]!=identyfikator:
                raise ValueError()
            return _wynik("GUGiK – ULDK",rekordy[0])
        numer=identyfikator.rsplit(" ",1)[1]
        if len({r["id"] for r in rekordy})!=count or any(r["id"].rsplit(".",1)[1]!=numer for r in rekordy):
            raise ValueError()
        return _wynik("GUGiK – ULDK",{"liczba":count,"kandydaci":rekordy,"wymaga_wyboru":bool(count),
            "uwaga":"Potwierdź pełny identyfikator działki przed użyciem danych."})
    except (ValueError,UnicodeError):
        raise Niedostepny("Brak wiarygodnego wyniku ULDK; sprawdź dane lub Geoportal.") from None

def _json(raw):
    try:
        d=json.loads(raw)
        if not isinstance(d,dict):
            raise ValueError()
        return d
    except (ValueError,UnicodeError):
        raise Niedostepny("Niepoprawny format odpowiedzi.") from None

def krs(numer,client,rejestr="P"):
    if not re.fullmatch(r"[0-9]{10}",numer) or rejestr not in ("P","S"):
        raise ValueError("Podaj 10 cyfr KRS i rodzaj rejestru P lub S.")
    d=_json(_get("https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/"+numer,{"rejestr":rejestr,"format":"json"},client))
    if not isinstance(d.get("odpis"),dict):
        raise Niedostepny("Brak odpisu w odpowiedzi KRS.")
    return _wynik("Ministerstwo Sprawiedliwości – KRS",d)

def vat(nip,dzien,client):
    if not re.fullmatch(r"[0-9]{10}",nip):
        raise ValueError("Podaj NIP (10 cyfr).")
    try:
        if date.fromisoformat(dzien).isoformat()!=dzien or date.fromisoformat(dzien)>date.today():
            raise ValueError()
    except ValueError:
        raise ValueError("Podaj datę YYYY-MM-DD nie późniejszą niż dzisiaj.") from None
    d=_json(_get("https://wykazpodatnikowvat.mf.gov.pl/api/search/nip/"+nip,{"date":dzien},client))
    r=d.get("result")
    if not isinstance(r,dict) or "subject" not in r or not r.get("requestId"):
        raise Niedostepny("Brak prawidłowego wyniku VAT.")
    if r["subject"] is not None and not isinstance(r["subject"],dict):
        raise Niedostepny("Niepoprawna odpowiedź VAT.")
    return _wynik("Ministerstwo Finansów – wykaz VAT",{"data":dzien,"requestId":r["requestId"],"subject":r["subject"]})
