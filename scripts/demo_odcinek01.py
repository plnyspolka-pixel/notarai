"""Dane demo i lokalny serwer do nagrania odcinka 01 „Poniedziałek, 8:57”.

Wszystkie osoby, numery i adresy sa FIKCYJNE (zestaw „Nowak” z kancelarii
„pod Siódemką”). PESEL-e i numer KW maja poprawne sumy kontrolne, zeby
walidacja zachowywala sie jak na prawdziwej sprawie, ale nie naleza do nikogo.
Skany to strony tekstowe z napisem „DOKUMENT FIKCYJNY”, nie podrobki
prawdziwych dokumentow (bez wizerunku dowodu osobistego).

Co zaklada `przygotuj` (powtarzalnie - drugi raz nadpisuje to samo):
- kancelarie demo z czterema osobami: Helena (wlascicielka, notariusz),
  Marta (notariusz), Kuba (aplikant), Basia (sekretariat),
- sprawe „Nowak - Nowak” (sprzedaz lokalu: Irena Nowak sprzedaje synowi
  Pawlowi) z wzorem aktu kancelarii, skanami i wczesniejszym odczytem,
  w ktorym 2 pola wymagaja uwagi (rozbiezna powierzchnia, brak dowodu syna),
- termin w kalendarzu: jutro 11:30-12:30, „sprzedaż nieruchomości”,
  powiazany ze sprawa, plus dwa inne terminy tego dnia (bez spraw),
- dwie zasady kancelarii (kwoty slownie, bez „w/w”).

Uzycie (tryb lokalny, osobny katalog danych - nie miesza sie z dane/):
    python scripts/demo_odcinek01.py przygotuj --dane dane/demo-odcinek01
    python scripts/demo_odcinek01.py serwer --dane dane/demo-odcinek01 --haslo 'Demo-Odc01!'

`serwer` uruchamia aplikacje w trybie wielu kancelarii (jak app.notarai.pl:
logowanie, zespol, stanowiska), ale logowanie sprawdza lokalnie: tylko konta
demo i haslo podane w --haslo. Odmawia startu, gdy srodowisko wskazuje na
chmure (PIECZAPP_MAGAZYN=s3, pula Cognito). Projekt sporzadza prawdziwy model
(Bedrock, eu-central-1) - potrzebne sa poswiadczenia AWS. `--atrapa-modelu`
podmienia model na wypelnianie wzoru bez Bedrock, wylacznie do prob i zrzutow:
tekst projektu zaczyna sie wtedy od „PRÓBA NAGRANIA - atrapa modelu”, wiec
nie da sie go pomylic z prawdziwym wynikiem.

SaaS (app.notarai.pl): `przygotuj --kancelaria <id>` z PIECZAPP_MAGAZYN=s3
i PIECZAPP_S3_BUCKET zapisuje te sama sprawe, kalendarz i zasady do S3
kancelarii demo. Konta zaklada wlasciciel kancelarii demo w oknie „Zespół
kancelarii” (zaproszenia Cognito na prawdziwe skrzynki) - zob.
docs/czeka-na-dostep.md (NA-8).
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN))

KANCELARIA = "kancelaria-pod-siodemka"
NAZWA_KANCELARII = "Kancelaria Notarialna pod Siódemką (DEMO)"
SPRAWA = "e01demo00001"
SYGNATURA = "KPS 47/2026"
DOMENA = "kancelaria-demo.test"   # .test - domena zastrzezona, poczta nigdzie nie trafi
ZESPOL = [
    # email, rola administracyjna, stanowisko, imie (do wyswietlenia w skrypcie)
    (f"helena@{DOMENA}", "wlasciciel", "notariusz", "Helena"),
    (f"marta@{DOMENA}", "czlonek", "notariusz", "Marta"),
    (f"kuba@{DOMENA}", "czlonek", "aplikant", "Kuba"),
    (f"basia@{DOMENA}", "czlonek", "sekretariat", "Basia"),
]
ZNAK_ATRAPY = "PRÓBA NAGRANIA - atrapa modelu (bez Bedrock), nie jest to wynik modelu."


# --- fikcyjne dane, wewnetrznie spojne ----------------------------------------


def pesel(dziesiec: str) -> str:
    from walidacja import WAGI_PESEL
    suma = sum(int(c) * w for c, w in zip(dziesiec, WAGI_PESEL))
    return dziesiec + str((10 - suma % 10) % 10)


def numer_kw(kod: str, numer: str) -> str:
    from walidacja import _ZNAKI_KW
    suma = sum(_ZNAKI_KW.index(z) * (1, 3, 7)[i % 3] for i, z in enumerate(kod + numer))
    return f"{kod}/{numer}/{suma % 10}"


# Irena Nowak ur. 12.03.1958 (kobieta: przedostatnia cyfra parzysta),
# Pawel Nowak ur. 21.07.1986 (mezczyzna: nieparzysta).
IRENA = {"imie": "Irena Nowak", "pesel": pesel("5803120748"), "ojciec": "Stanisław", "matka": "Zofia"}
PAWEL = {"imie": "Paweł Nowak", "pesel": pesel("8607210515"), "ojciec": "Jan", "matka": "Irena"}
KW = numer_kw("WA4M", "00077777")
ADRES_LOKALU = "ul. Siódemki 7 m. 12, 00-777 Warszawa"
ADRES_PAWLA = "ul. Ogrodowa 17 m. 3, 00-717 Warszawa"
TELEFONY = [{"imie": "Irena Nowak", "numer": "+48 123 456 701"},
            {"imie": "Paweł Nowak (syn)", "numer": "+48 123 456 702"}]

WZOR = """aaa – sprzedająca (Jan Kowalski)
ppp – PESEL sprzedającej
aad – adres sprzedającej
bbb – kupujący (Jan Kowalski)
pp2 – PESEL kupującego
bbd – adres kupującego
dd2 – dowód osobisty kupującego
lll – adres lokalu
mmm – powierzchnia użytkowa lokalu
ggg – nr kw
nab – podstawa nabycia lokalu przez sprzedającą
ccc – cena
zzz – data aktu

Repertorium A nr ________/2026

AKT NOTARIALNY

Dnia zzz roku w Kancelarii Notarialnej pod Siódemką w Warszawie, przed notariuszem Martą Siódmą, stawili się:
1. aaa, córka Stanisława i Zofii, PESEL ppp, zamieszkała aad,
2. bbb, syn Jana i Ireny, PESEL pp2, legitymujący się dowodem osobistym dd2, zamieszkały bbd.
Tożsamość stawających notariusz ustaliła na podstawie okazanych dowodów osobistych.

UMOWA SPRZEDAŻY

§ 1. aaa oświadcza, że jest właścicielką samodzielnego lokalu mieszkalnego położonego przy lll, o powierzchni użytkowej mmm m², dla którego Sąd Rejonowy dla Warszawy-Mokotowa w Warszawie prowadzi księgę wieczystą nr ggg; lokal nabyła na podstawie nab.
§ 2. aaa oświadcza, że w dziale III i IV księgi wieczystej nie ma wpisów // w dziale IV księgi wieczystej wpisana jest hipoteka, która zostanie wykreślona przed wydaniem lokalu.
§ 3. aaa sprzedaje bbb lokal opisany w § 1 za cenę ccc zł, a bbb lokal ten kupuje.
§ 4. Cena została zapłacona przed podpisaniem tego aktu // Cena zostanie zapłacona przelewem w terminie 7 dni od dnia zawarcia umowy.
§ 5. Wydanie lokalu nastąpi w dniu podpisania tego aktu.
§ 6. Koszty tego aktu ponosi kupujący.
§ 7. Akt ten został odczytany, przyjęty i podpisany.
"""

SKANY = {
    "skan-1-odpis-kw.png": [
        "DOKUMENT FIKCYJNY - DANE DEMO (NotarAI)",
        "Odpis zwykły księgi wieczystej",
        f"Numer księgi: {KW}",
        "Sąd Rejonowy dla Warszawy-Mokotowa, VI Wydział Ksiąg Wieczystych",
        "Dział I-O: lokal mieszkalny nr 12, " + ADRES_LOKALU,
        "Powierzchnia użytkowa: 48,02 m²",
        f"Dział II: właściciel - {IRENA['imie']}, córka Stanisława i Zofii, PESEL {IRENA['pesel']}",
        "Dział III: brak wpisów.   Dział IV: brak wpisów.",
    ],
    "skan-2-akt-nabycia.png": [
        "DOKUMENT FIKCYJNY - DANE DEMO (NotarAI)",
        "Wypis aktu notarialnego Rep. A nr 3157/2009 z dnia 14.05.2009 r.",
        "Umowa sprzedaży lokalu mieszkalnego",
        f"Kupująca: {IRENA['imie']}, PESEL {IRENA['pesel']}",
        "Lokal mieszkalny nr 12 przy ul. Siódemki 7 w Warszawie,",
        "powierzchnia użytkowa 48,20 m², księga wieczysta " + KW,
        "zamieszkała: " + ADRES_LOKALU,
    ],
    "skan-3-dane-stron.png": [
        "DOKUMENT FIKCYJNY - DANE DEMO (NotarAI)",
        "Notatka sekretariatu: dane stron przekazane przez klientkę",
        f"Sprzedająca: {IRENA['imie']}, PESEL {IRENA['pesel']}, tel. {TELEFONY[0]['numer']}",
        f"Kupujący (syn): {PAWEL['imie']}, PESEL {PAWEL['pesel']}, tel. {TELEFONY[1]['numer']}",
        "Adres kupującego: " + ADRES_PAWLA,
        "Cena uzgodniona: 385 000 zł",
        "Dowód osobisty syna: dosłać przed aktem.",
    ],
}

# Wczesniejszy odczyt skanow: dwa pola wymagaja uwagi - rozbiezna powierzchnia
# (akt nabycia 48,20 m², KW 48,02 m²) i brak dowodu osobistego kupujacego.
POLA = [
    {"nazwa": "aaa: sprzedająca", "wartosc": IRENA["imie"], "zrodlo": "skan-1-odpis-kw.png, s. 1"},
    {"nazwa": "ppp: PESEL sprzedającej", "wartosc": IRENA["pesel"], "zrodlo": "skan-1-odpis-kw.png, s. 1"},
    {"nazwa": "aad: adres sprzedającej", "wartosc": ADRES_LOKALU, "zrodlo": "skan-2-akt-nabycia.png, s. 1"},
    {"nazwa": "bbb: kupujący", "wartosc": PAWEL["imie"], "zrodlo": "skan-3-dane-stron.png, s. 1"},
    {"nazwa": "pp2: PESEL kupującego", "wartosc": PAWEL["pesel"], "zrodlo": "skan-3-dane-stron.png, s. 1"},
    {"nazwa": "bbd: adres kupującego", "wartosc": ADRES_PAWLA, "zrodlo": "skan-3-dane-stron.png, s. 1"},
    {"nazwa": "dd2: dowód osobisty kupującego", "wartosc": None, "zrodlo": "",
     "uwaga": "W materiałach nie ma dowodu osobistego kupującego - notatka: „dosłać przed aktem”."},
    {"nazwa": "lll: adres lokalu", "wartosc": ADRES_LOKALU, "zrodlo": "skan-1-odpis-kw.png, s. 1"},
    {"nazwa": "mmm: powierzchnia użytkowa lokalu", "wartosc": "48,02", "zrodlo": "skan-1-odpis-kw.png, s. 1",
     "pewnosc": "niska", "uwaga": "Rozbieżność: odpis KW 48,02 m², akt nabycia 48,20 m²."},
    {"nazwa": "ggg: nr kw", "wartosc": KW, "zrodlo": "skan-1-odpis-kw.png, s. 1"},
    {"nazwa": "nab: podstawa nabycia lokalu przez sprzedającą",
     "wartosc": "umowy sprzedaży z dnia 14 maja 2009 roku, Rep. A nr 3157/2009",
     "zrodlo": "skan-2-akt-nabycia.png, s. 1"},
    {"nazwa": "ccc: cena", "wartosc": "385 000,00", "zrodlo": "skan-3-dane-stron.png, s. 1"},
    {"nazwa": "zzz: data aktu", "wartosc": None, "zrodlo": "",
     "uwaga": "Data aktu - z kalendarza kancelarii, po potwierdzeniu terminu."},
]
BRAKI = ["Dowód osobisty kupującego (Paweł Nowak) - dosłać przed aktem."]
ROZBIEZNOSCI = ["Powierzchnia użytkowa lokalu: odpis KW 48,02 m², akt nabycia Rep. A 3157/2009 48,20 m²."]
INNI_W_KALENDARZU = ("Zielińska", "Wiśniewscy")
ZASADY = ["Kwoty zawsze cyframi i słownie.", "Zamiast „w/w” pisz „wyżej wymieniony”."]


def _strona_png(linie: list[str]) -> bytes:
    """Strona A4 (150 dpi) z tekstem i znakiem „DOKUMENT FIKCYJNY”."""
    import io

    from PIL import Image, ImageDraw, ImageFont
    obraz = Image.new("RGB", (1240, 1754), "white")
    rysuj = ImageDraw.Draw(obraz)
    czcionka = None
    for kandydat in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "arial.ttf"):
        try:
            czcionka = ImageFont.truetype(kandydat, 30)
            duza = ImageFont.truetype(kandydat, 90)
            break
        except OSError:
            continue
    if czcionka is None:
        czcionka = duza = ImageFont.load_default()
    y = 120
    for i, linia in enumerate(linie):
        rysuj.text((100, y), linia, fill=(160, 0, 0) if i == 0 else "black", font=czcionka)
        y += 70 if i == 0 else 56
    rysuj.text((180, 1300), "DOKUMENT FIKCYJNY", fill=(235, 200, 200), font=duza)
    bufor = io.BytesIO()
    obraz.save(bufor, "PNG")
    return bufor.getvalue()


# --- przygotowanie ---------------------------------------------------------------


def _ustaw_dane(katalog: str | None) -> None:
    import config
    if katalog:
        config.DANE = Path(katalog).resolve()
        config.DANE.mkdir(parents=True, exist_ok=True)


def _zespol_w_rejestrze() -> None:
    """Kancelaria demo w rejestrze (tylko tryb lokalny - w SaaS zespol zaklada
    wlasciciel przez zaproszenia Cognito)."""
    import autoryzacja
    rejestr = autoryzacja._wczytaj_rejestr()
    skrot, wpis = autoryzacja._znajdz(rejestr, KANCELARIA)
    if wpis is None:
        skrot = "demo-" + hashlib.sha256(KANCELARIA.encode()).hexdigest()[:16]
        wpis = rejestr[skrot] = {"id": KANCELARIA, "nazwa": NAZWA_KANCELARII, "aktywna": True,
                                 "utworzono": autoryzacja._teraz()}
    import dokumenty_prawne
    teraz = autoryzacja._teraz()
    wpis["nazwa"] = NAZWA_KANCELARII
    wpis["dane"] = {"notariusze": "Helena Siódma, Marta Siódma (DEMO)",
                    "adres": "ul. Siódemki 7, 00-777 Warszawa (DEMO)", "nip": ""}
    # Dane demo: akceptacja odnotowana jako przygotowanie nagrania, nie jako
    # oswiadczenie zadnej osoby. Bez niej aplikacja nie wpuscilaby do spraw.
    wpis["umowa"] = {"regulamin": dokumenty_prawne.wersja("regulamin"), "umowa": dokumenty_prawne.wersja("umowa"),
                     "zaakceptowano": teraz, "email": ZESPOL[0][0], "ip": "127.0.0.1",
                     "sposob": "dane demo do nagrania (scripts/demo_odcinek01.py)"}
    wpis["dpia"] = {"wersja": dokumenty_prawne.wersja("dpia"), "przyjeto": teraz}
    wpis["zespol"] = [{"email": e, "rola": r, "stanowisko": s, "zaproszono": teraz, "dolaczyl": teraz,
                       "instrukcja": {"wersja": dokumenty_prawne.wersja("instrukcja"), "data": teraz}}
                      for e, r, s, _ in ZESPOL]
    autoryzacja._zapisz_rejestr(rejestr)


def przygotuj(katalog: str | None, kancelaria: str, dzien: date) -> dict:
    """Zaklada (albo odtwarza) dane demo. Zwraca podsumowanie bez danych osobowych."""
    _ustaw_dane(katalog)
    import magazyn
    znacznik = magazyn.kancelaria_var.set(kancelaria)
    try:
        if magazyn.TRYB != "s3":
            _zespol_w_rejestrze()
        return _sprawa_kalendarz_zasady(dzien)
    finally:
        magazyn.kancelaria_var.reset(znacznik)


def _sprawa_kalendarz_zasady(dzien: date) -> dict:
    import shutil

    import app as aplikacja
    import config
    import dokumenty
    import kalendarz
    import magazyn
    import osoby
    import prompty
    import zasady

    katalog = config.SPRAWY / SPRAWA
    if katalog.exists():
        shutil.rmtree(katalog)
    (katalog / "skany").mkdir(parents=True)
    (katalog / "wzor.txt").write_text(WZOR, encoding="utf-8")
    for nazwa, linie in SKANY.items():
        (katalog / "skany" / nazwa).write_bytes(_strona_png(linie))
    analiza = dokumenty.analizuj_wzor(WZOR)
    kolejnosc = {nazwa: i for i, nazwa in enumerate(analiza["pola"])}
    assert set(kolejnosc) == {p["nazwa"] for p in POLA}, "pola odczytu musza odpowiadac wzorowi"
    pola = aplikacja._zwaliduj(sorted(POLA, key=lambda p: kolejnosc[p["nazwa"]]))
    utworzono = datetime.combine(dzien - timedelta(days=3), datetime.min.time()).replace(hour=14, minute=12)
    aplikacja._zapisz_json(katalog / "sprawa.json", {
        "id": SPRAWA, "nazwa": "Nowak - Nowak", "nazwa_reczna": True, "sygnatura": SYGNATURA,
        "utworzono": utworzono.isoformat(timespec="seconds"),
        "polecenie": "Umowa sprzedaży lokalu mieszkalnego: Irena Nowak sprzedaje synowi Pawłowi.",
        "wzor": "wzor.txt", "skany": list(SKANY), "stron": len(SKANY), "wysilek": "high",
        "pola_wzoru": analiza["pola"], "legenda": analiza["legenda"], "warianty": analiza["warianty"],
    })
    aplikacja._zapisz_json(katalog / "odczyt.json", {"pola": pola, "braki": BRAKI, "rozbieznosci": ROZBIEZNOSCI})
    aplikacja._zapisz_json(katalog / "transkrypcje.json",
                           [{"plik": n, "strona": 1, "tekst": "\n".join(l)} for n, l in SKANY.items()])
    (katalog / "kontekst.txt").write_text(
        prompty.kontekst_rozmowy(pola, BRAKI, ROZBIEZNOSCI, "Umowa sprzedaży lokalu mieszkalnego."), encoding="utf-8")
    aplikacja._zapisz_rozmowe(katalog, [])
    magazyn.utrwal_sprawe(katalog)

    jutro = (dzien + timedelta(days=1)).isoformat()
    # Poprzednie terminy demo usuwamy, zeby skrypt byl powtarzalny.
    for wpis in kalendarz.lista():
        if wpis.get("sprawa") == SPRAWA or wpis.get("uczestnicy") in INNI_W_KALENDARZU:
            kalendarz.usun(wpis["id"])
    kalendarz.dodaj({"data": jutro, "godzina": "09:00", "koniec": "09:30", "rodzaj": "poświadczenie podpisów",
                     "uczestnicy": "Zielińska"})
    termin = kalendarz.dodaj({"data": jutro, "godzina": "11:30", "koniec": "12:30",
                              "rodzaj": "sprzedaż nieruchomości", "uczestnicy": "Irena Nowak, Paweł Nowak",
                              "telefony": TELEFONY, "sprawa": SPRAWA,
                              "uwagi": "Syn dosyła dowód osobisty przed aktem."})
    kalendarz.dodaj({"data": jutro, "godzina": "13:30", "koniec": "14:30", "rodzaj": "darowizna",
                     "uczestnicy": "Wiśniewscy"})
    # Telefony stron w „Osobach i telefonach” - bez nich termin ma czerwony pasek.
    for osoba, telefon in ((IRENA, TELEFONY[0]), (PAWEL, TELEFONY[1])):
        osoby.ustaw_telefon(osoby._identyfikator("p:" + osoba["pesel"]), telefon["numer"])

    obecne = {z["tekst"] for z in zasady.wczytaj().get("zasady", [])}
    for tekst in ZASADY:
        if tekst not in obecne:
            zasady.dodaj(tekst)
    return {"kancelaria": magazyn.kancelaria(), "sprawa": SPRAWA, "sygnatura": SYGNATURA,
            "termin": f"{jutro} 11:30-12:30", "id_terminu": termin["id"],
            "pola_wymagajace_uwagi": sum(1 for p in pola if p["wymaga_uwagi"]),
            "konta": [f"{imie}: {e} ({s})" for e, _, s, imie in ZESPOL]}


# --- serwer demo: logowanie lokalne, bez Cognito ----------------------------------


def _b64(dane: bytes) -> str:
    return base64.urlsafe_b64encode(dane).rstrip(b"=").decode("ascii")


def _z_b64(tekst: str) -> bytes:
    return base64.urlsafe_b64decode(tekst + "=" * (-len(tekst) % 4))


class LogowanieDemo:
    """Zastepuje Cognito w procesie serwera demo: tokeny HS256 z kluczem
    losowanym przy kazdym starcie, wylacznie konta z ZESPOL."""

    def __init__(self, haslo: str):
        self.haslo = haslo
        self.klucz = secrets.token_bytes(32)
        self.konta = {e: KANCELARIA for e, _, _, _ in ZESPOL}

    def token(self, email: str, sekund: int, rodzaj: str = "id") -> str:
        naglowek = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        ladunek = _b64(json.dumps({"email": email, "custom:kancelaria": self.konta[email],
                                   "token_use": rodzaj, "exp": int(time.time()) + sekund}).encode())
        podpis = _b64(hmac.new(self.klucz, f"{naglowek}.{ladunek}".encode(), hashlib.sha256).digest())
        return f"{naglowek}.{ladunek}.{podpis}"

    def sprawdz(self, token: str, rodzaj: str = "id") -> dict:
        import logowanie
        try:
            naglowek, ladunek, podpis = token.split(".")
            wlasciwy = _b64(hmac.new(self.klucz, f"{naglowek}.{ladunek}".encode(), hashlib.sha256).digest())
            dane = json.loads(_z_b64(ladunek))
        except (ValueError, json.JSONDecodeError) as blad:
            raise logowanie.BladLogowania("Token wygasl albo jest nieprawidlowy.") from blad
        if not hmac.compare_digest(podpis, wlasciwy) or dane.get("exp", 0) < time.time() \
                or dane.get("token_use") != rodzaj:
            raise logowanie.BladLogowania("Token wygasl albo jest nieprawidlowy.")
        return {"email": dane["email"], "kancelaria": dane["custom:kancelaria"]}

    def zaloguj(self, email: str, haslo: str) -> dict:
        import logowanie
        if email not in self.konta or not hmac.compare_digest(haslo.encode(), self.haslo.encode()):
            raise logowanie.BladLogowania("Nieprawidlowy adres e-mail albo haslo.")
        return {"token": self.token(email, 8 * 3600), "wygasa_za": 8 * 3600,
                "odnowienie": self.token(email, 30 * 86400, "odnowienie")}

    def odnow(self, token_odnowienia: str) -> dict:
        dane = self.sprawdz(token_odnowienia, "odnowienie")
        return {"token": self.token(dane["email"], 8 * 3600), "wygasa_za": 8 * 3600, "odnowienie": ""}

    def podepnij(self) -> None:
        import logowanie
        logowanie.wlaczone = lambda: True
        logowanie.zaloguj = self.zaloguj
        logowanie.odnow = self.odnow
        logowanie.wyloguj = lambda token_odnowienia: None
        logowanie.dane_z_tokenu = self.sprawdz
        # Zaproszenia w demo nie wysylaja poczty - konto dziala od razu.
        logowanie.utworz_uzytkownika = lambda email, kancelaria: self.konta.__setitem__(email, kancelaria)
        logowanie.ponow_zaproszenie = lambda email: None
        logowanie.usun_uzytkownika = lambda email: self.konta.pop(email, None)


def atrapa_projektu(sekund: float):
    """Wypelnia wzor danymi z pol bez modelu. Tylko do prob i zrzutow."""
    import re

    def sporzadz(wzor, dane, opis, legenda=None, rozmowa=None, personalizacja="", ksiegi=""):
        time.sleep(sekund)
        # Tresc ksiegi z EKW (prompty.blok_ksiag) rozstrzyga warianty o dzialach
        # III/IV - tak jak instrukcja dla modelu: puste oba = pierwszy wariant.
        puste = {d: bool(re.search(rf"--- DZIAL {d}:[^\n]*\nBRAK WPISOW", ksiegi or ""))
                 for d in ("III", "IV")}

        def wariant(m):
            pierwszy, drugi = m.group(2).strip(), m.group(3).strip()
            if ksiegi and re.search(r"dzia[lł]\w*\s+(III|IV)", pierwszy, re.I):
                return m.group(1) + (pierwszy if all(puste.values()) else drugi)
            return f"{m.group(1)}<<WYBOR: {pierwszy} / {drugi}>>"
        legenda = legenda or {}
        wartosci = {}
        for pole in dane:
            kod = str(pole.get("nazwa", "")).split(":")[0].strip()
            wartosci[kod] = pole.get("wartosc")
        linie = [l for l in wzor.splitlines() if not re.match(r"^\s*\w{2,4}\s*[–-]\s", l)]
        tekst = "\n".join(linie).strip()
        for kod in sorted(legenda, key=len, reverse=True):
            wartosc = wartosci.get(kod) or f"<<BRAK: {legenda[kod]['opis']}>>"
            tekst = re.sub(rf"(?<!\w){re.escape(kod)}(?!\w)", lambda _: wartosc, tekst)
        tekst = re.sub(r"(\s*)([^.\n]*?) // ([^\n]*)", wariant, tekst)
        return ZNAK_ATRAPY + "\n\n" + tekst
    return sporzadz


def serwer(katalog: str, haslo: str, host: str, port: int, atrapa: float | None) -> None:
    if os.getenv("PIECZAPP_MAGAZYN", "lokalny") != "lokalny" or os.getenv("PIECZAPP_COGNITO_POOL"):
        sys.exit("Serwer demo dziala tylko lokalnie (PIECZAPP_MAGAZYN=lokalny, bez puli Cognito).")
    if len(haslo) < 8:
        sys.exit("Podaj haslo demo (--haslo, co najmniej 8 znakow).")
    os.environ["PIECZAPP_MULTI"] = "true"
    os.environ.setdefault("PIECZAPP_AML_LISTY", "0")
    _ustaw_dane(katalog)
    import autoryzacja
    import bedrock
    import uvicorn
    LogowanieDemo(haslo).podepnij()
    if atrapa is not None:
        bedrock.sporzadz_projekt = atrapa_projektu(atrapa)
        print(f"  UWAGA: atrapa modelu ({atrapa:g} s) - projekt NIE pochodzi z Bedrock.")
    import app as aplikacja
    assert autoryzacja.MULTI, "tryb wielu kancelarii nie wlaczyl sie"
    print(f"\n  NotarAI demo odc. 01 -> http://{host}:{port}   (dane: {katalog})")
    for email, _, stanowisko, imie in ZESPOL:
        print(f"    {imie:<6} {stanowisko:<12} {email}")
    if host not in ("127.0.0.1", "localhost"):
        print("  UWAGA: serwer slucha w sieci lokalnej - tylko na czas nagrania, dane sa fikcyjne.")
    uvicorn.run(aplikacja.app, host=host, port=port, access_log=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="polecenie", required=True)
    p = sub.add_parser("przygotuj", help="zaloz albo odtworz dane demo")
    p.add_argument("--dane", help="katalog danych (tryb lokalny), np. dane/demo-odcinek01")
    p.add_argument("--kancelaria", default=KANCELARIA, help="identyfikator kancelarii demo")
    p.add_argument("--dzien", help="dzien nagrania RRRR-MM-DD (termin bedzie nazajutrz); domyslnie dzis")
    s = sub.add_parser("serwer", help="lokalny serwer z kontami demo")
    s.add_argument("--dane", required=True)
    s.add_argument("--haslo", required=True, help="haslo wszystkich kont demo")
    s.add_argument("--host", default="127.0.0.1", help="0.0.0.0, zeby telefon w tej samej sieci mogl wejsc")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--atrapa-modelu", type=float, metavar="SEKUND", default=None,
                   help="projekt bez Bedrock po tylu sekundach (tylko proby i zrzuty)")
    args = parser.parse_args()
    if args.polecenie == "przygotuj":
        dzien = date.fromisoformat(args.dzien) if args.dzien else date.today()
        print(json.dumps(przygotuj(args.dane, args.kancelaria, dzien), ensure_ascii=False, indent=2))
    else:
        serwer(args.dane, args.haslo, args.host, args.port, args.atrapa_modelu)


if __name__ == "__main__":
    main()
