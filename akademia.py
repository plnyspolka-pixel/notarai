"""Akademia notarai: nauka za kredyty, sciezka wdrozenia, polecenia.

Grywalizacja w tonie zawodu zaufania publicznego - bez odznak, rankingow
i serii dni. Notariusz ma obowiazek zapewnic kompetencje AI zespolu
(art. 4 AI Act, docs/prawne/13-zasady-ai-w-kancelarii.md § 3), wiec kazdy
zaliczony modul to jednoczesnie:
  - wpis do dokumentacji kompetencji (zaswiadczenie z data i wersja modulu),
  - kredyty dla kancelarii (partia "nagroda", wazna 90 dni).

Zasady behawioralne, swiadomie dobrane:
  - postep na start (umowa juz zaakceptowana = 1 z 6 krokow sciezki),
  - nastepny krok zawsze nazwany i krotki (gradient celu, malo tarcia),
  - nagroda za kompetencje i wdrozenie, nie za klikanie: kroki sciezki
    sprawdzamy na stanie (sprawa, projekt, zespol, pomocnik), nie na deklaracji,
  - jeden modul uczy oszczedzania kredytow - zachety kancelarii i nasze
    (koszt modelu) ida w te sama strone,
  - zero publicznych wyroznien: status nie trafia na mape ani strone
    notarai.pl (zakaz reklamy, neutralnosc), wlasciciel widzi tylko swoj zespol,
  - bez ciemnych wzorcow: brak sztucznej presji, odliczania, wstydzenia.

Ochrona przed naduzyciem: odpowiedzi sprawdza serwer (przegladarka nie zna
poprawnych), ponowna proba po przerwie, nagroda tylko za pierwsze zaliczenie,
nagradzane osoby tylko z zespolu i najwyzej MAKS_NAGRADZANYCH_OSOB na kancelarie,
polecenie nagradzane dopiero po pierwszej oplaconej fakturze polecanej kancelarii
i nie dla tej samej firmy (NIP).

Dane: w pliku akademii skroty adresow e-mail, nie adresy. Zero danych klientow.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

import tokenomia

log = logging.getLogger("pieczapp.akademia")

KATALOG = "akademia"
PROG_ZALICZENIA = 0.75
PRZERWA_MINUT = int(os.getenv("PIECZAPP_AKADEMIA_PRZERWA_MIN", "10"))
MAKS_NAGRADZANYCH_OSOB = int(os.getenv("PIECZAPP_AKADEMIA_MAKS_OSOB", "6"))
NAGRODA_WDROZENIA = 100.0
NAGRODA_POLECENIA = 200.0
MAKS_POLECEN_ROCZNIE = 10
# Premia stazowa: procent puli planu jako partia "nagroda" przy odnowieniu.
PREMIE_STAZU = ((12, 0.10), (6, 0.05))

# --- tresc ----------------------------------------------------------------------------
# Kazdy modul: krotka lekcja (punkty do przeczytania w 3-5 minut) i 4 pytania.
# Zmiana tresci = nowa wersja; zaswiadczenie podaje wersje, ktora zaliczono.

MODULY: list[dict] = [
    {
        "kod": "co_robi_model", "wersja": 1, "minut": 4, "nagroda": 15,
        "tytul": "Co model robi, a czego nie",
        "lekcja": [
            "notarai odczytuje skany, wypełnia wzór aktu, odpowiada w rozmowie o sprawie i proponuje wartości do formularzy.",
            "Model nie zna stanu prawnego poza wgranymi dokumentami, nie weryfikuje autentyczności dokumentów ani tożsamości osób.",
            "Najczęstsze błędy: pomylone podobne cyfry (3/8, 1/7, 0/O), pomylenie osób przy kilku stronach, odmiana nazwisk, wartość „z domysłu”.",
            "Sumy kontrolne wyłapują część błędów w PESEL, NIP i numerze KW - ale nie w numerach działek, datach, kwotach ani dowodach.",
            "Wszystko, co zwraca model, jest propozycją. Za treść czynności odpowiada notariusz.",
        ],
        "pytania": [
            {"pytanie": "Suma kontrolna przeszła. Co to znaczy dla numeru działki?",
             "odpowiedzi": ["Numer działki jest poprawny", "Nic - sumy kontrolne nie obejmują numerów działek",
                            "Działka jest w księdze wieczystej"], "poprawna": 1},
            {"pytanie": "Czy model sprawdza, czy dowód osobisty jest autentyczny?",
             "odpowiedzi": ["Tak, porównuje ze wzorem", "Nie - odczytuje tylko to, co jest na skanie"], "poprawna": 1},
            {"pytanie": "Przy dwóch małżonkach w akcie najbardziej typowy błąd to:",
             "odpowiedzi": ["przypisanie danych jednej osoby drugiej", "pominięcie całego aktu", "zmiana waluty"],
             "poprawna": 0},
            {"pytanie": "Kto odpowiada za treść czynności przygotowanej z notarai?",
             "odpowiedzi": ["Dostawca notarai", "Model", "Notariusz"], "poprawna": 2},
        ],
    },
    {
        "kod": "sprawdzenie", "wersja": 1, "minut": 4, "nagroda": 15,
        "tytul": "Sprawdzenie przed użyciem",
        "lekcja": [
            "Czerwona krawędź pola: błędna suma kontrolna, niska pewność odczytu albo brak danych.",
            "Brak czerwonej krawędzi nie oznacza, że wartość jest poprawna.",
            "<<BRAK: pole>> - danych nie było w dokumentach. <<WYBOR: opis>> - decyzja należy do notariusza. Oba trzeba usunąć z projektu.",
            "Każdy numer (PESEL, dowód, KW, działka, NIP, rachunek) porównuj z dokumentem źródłowym.",
            "Po każdej poprawce z rozmowy czytaj cały projekt - poprawka mogła zmienić także inne miejsca.",
        ],
        "pytania": [
            {"pytanie": "Pole nie ma czerwonej krawędzi. Co z nim robisz?",
             "odpowiedzi": ["Nic, jest poprawne", "Porównuję je z dokumentem źródłowym jak każde inne"], "poprawna": 1},
            {"pytanie": "W projekcie został znacznik <<WYBOR: forma płatności>>. To znaczy, że:",
             "odpowiedzi": ["model wybrał formę płatności", "decyzja należy do notariusza i znacznik trzeba usunąć",
                            "znacznik zniknie sam przy eksporcie"], "poprawna": 1},
            {"pytanie": "Po poprawce ceny w rozmowie sprawdzasz:",
             "odpowiedzi": ["tylko zdanie z ceną", "cały projekt, bo poprawka mogła zmienić inne miejsca"],
             "poprawna": 1},
            {"pytanie": "Kwotę zapisaną słownie:",
             "odpowiedzi": ["sprawdzam razem z cyframi", "pomijam, wystarczą cyfry"], "poprawna": 0},
        ],
    },
    {
        "kod": "dane_klientow", "wersja": 1, "minut": 3, "nagroda": 15,
        "tytul": "Dane klientów i RODO w praktyce",
        "lekcja": [
            "Wgrywaj tylko dokumenty potrzebne do danej czynności.",
            "Danych o zdrowiu, wyroków i innych danych szczególnych nie wgrywaj, jeśli nie są potrzebne.",
            "Usuwaj sprawę z notarai po czynności - notarai nie jest repertorium ani archiwum.",
            "Kancelaria może trzymać pliki u siebie (tryb „u kancelarii”): serwer wtedy niczego nie zapisuje.",
            "Problem zgłaszaj bez danych klientów: identyfikator sprawy, numer strony, rodzaj pola i błędu.",
        ],
        "pytania": [
            {"pytanie": "Klient przyniósł zaświadczenie lekarskie, które nie jest potrzebne do aktu. Wgrywasz je?",
             "odpowiedzi": ["Tak, na wszelki wypadek", "Nie"], "poprawna": 1},
            {"pytanie": "Zgłaszając błędny odczyt do notarai, podajesz:",
             "odpowiedzi": ["PESEL klienta, żeby było szybciej", "identyfikator sprawy, stronę i rodzaj błędu"],
             "poprawna": 1},
            {"pytanie": "Po podpisaniu aktu sprawa w notarai:",
             "odpowiedzi": ["zostaje na zawsze jako archiwum", "jest usuwana po czynności albo w terminie ustalonym w kancelarii"],
             "poprawna": 1},
            {"pytanie": "W trybie „pliki u kancelarii” skany i projekty są:",
             "odpowiedzi": ["w folderze wskazanym przez kancelarię", "w chmurze notarai"], "poprawna": 0},
        ],
    },
    {
        "kod": "pomocnik", "wersja": 1, "minut": 4, "nagroda": 15,
        "tytul": "Pomocnik i rejestry publiczne",
        "lekcja": [
            "Do portali rejestrów logujesz się sam. Pomocnik nie wpisuje haseł ani PIN-ów i nikomu ich nie przekazujesz.",
            "Pomocnik nie klika „wyślij”, „złóż”, „podpisz” - rozpoznaje je po nazwie, co może zawieść przy nietypowym „Dalej”.",
            "Asystent wykonuje najwyżej 20 kroków na jedno polecenie i nie wychodzi poza zgodzone adresy.",
            "Obserwuj okno przeglądarki i przerwij, gdy agent robi coś nieoczekiwanego.",
            "Wynik sprawdzenia w rejestrze zapisuje się w sprawie ze zrzutem ekranu - to stan z chwili sprawdzenia.",
        ],
        "pytania": [
            {"pytanie": "Pomocnik prosi o hasło do portalu. Co robisz?",
             "odpowiedzi": ["Podaję mu hasło", "Loguję się sam - pomocnik nie wpisuje haseł"], "poprawna": 1},
            {"pytanie": "Ostatni krok wniosku ma przycisk „Dalej”, który faktycznie wysyła wniosek. Ryzyko:",
             "odpowiedzi": ["żadne, pomocnik zawsze to rozpozna", "pomocnik może go nie rozpoznać - obserwuję i sprawdzam pola sam"],
             "poprawna": 1},
            {"pytanie": "Zrzut ekranu z KRZ w sprawie pokazuje:",
             "odpowiedzi": ["stan rejestru w chwili sprawdzenia", "stan aktualny na dziś"], "poprawna": 0},
            {"pytanie": "Ile kroków asystent wykona najwyżej na jedno polecenie?",
             "odpowiedzi": ["bez limitu", "20"], "poprawna": 1},
        ],
    },
    {
        "kod": "oszczedne_kredyty", "wersja": 1, "minut": 3, "nagroda": 20,
        "tytul": "Jak pracować taniej, nie gorzej",
        "lekcja": [
            "Wydruki elektroniczne (wypis KW, zaświadczenia z warstwą tekstową) czytają się dobrze na dokładności standardowej - strona kosztuje mniej.",
            "Maksymalną dokładność zostaw na skany słabej jakości, pismo odręczne i drobny druk tabel.",
            "Czynność, która się nie uda, nic nie kosztuje - możesz spokojnie spróbować ponownie.",
            "Tę samą księgę wieczystą w tej samej sprawie pobierzesz drugi raz w ciągu doby bez opłaty.",
            "Długa rozmowa kosztuje więcej, bo model czyta przy każdej wiadomości całą historię. Zbierz poprawki w jednej wiadomości.",
        ],
        "pytania": [
            {"pytanie": "Elektroniczny wypis z KW (PDF z tekstem). Jaka dokładność wystarczy zwykle?",
             "odpowiedzi": ["maksymalna", "standardowa"], "poprawna": 1},
            {"pytanie": "Odczyt przerwał się błędem przeciążenia. Ile kredytów pobrano?",
             "odpowiedzi": ["pełną cenę", "nic"], "poprawna": 1},
            {"pytanie": "Masz pięć drobnych poprawek do projektu. Najtaniej:",
             "odpowiedzi": ["pięć osobnych wiadomości", "jedna wiadomość z pięcioma poprawkami"], "poprawna": 1},
            {"pytanie": "Pobierasz tę samą KW w tej samej sprawie drugi raz po godzinie. Opłata:",
             "odpowiedzi": ["jak za nową księgę", "bez opłaty"], "poprawna": 1},
        ],
    },
    {
        "kod": "wzor_kancelarii", "wersja": 1, "minut": 4, "nagroda": 20,
        "tytul": "Wzór aktu, który dobrze się wypełnia",
        "lekcja": [
            "Miejsca do wypełnienia oznaczasz jako {{nazwa pola}} albo [NAZWA POLA].",
            "Nazwy z „pesel”, „nip”, „kw”, „cena”, „kwota”, „wartosc” są dodatkowo sprawdzane sumą kontrolną albo formatem.",
            "Opisowe nazwy pomagają: {{pesel sprzedajacego}} jest lepsze niż {{pole3}}.",
            "Wzór wgrany raz możesz wskazać w kolejnej sprawie zamiast wgrywać go ponownie.",
            "Wzór do 40 tys. znaków mieści się w cenie projektu; dłuższy kosztuje dopłatę za każde 10 tys.",
        ],
        "pytania": [
            {"pytanie": "Które oznaczenie pola jest poprawne?",
             "odpowiedzi": ["{{pesel kupujacego}}", "<pesel kupujacego>", "#pesel"], "poprawna": 0},
            {"pytanie": "Pole {{cena}} jest dodatkowo:",
             "odpowiedzi": ["sprawdzane jako kwota", "pomijane przy odczycie"], "poprawna": 0},
            {"pytanie": "Która nazwa pola da lepszy odczyt?",
             "odpowiedzi": ["{{pole7}}", "{{data urodzenia nabywcy}}"], "poprawna": 1},
            {"pytanie": "Ten sam wzór w kolejnej sprawie:",
             "odpowiedzi": ["trzeba wgrać od nowa", "można wskazać ze wcześniejszej sprawy"], "poprawna": 1},
        ],
    },
]
_MODULY = {m["kod"]: m for m in MODULY}

# Sciezka wdrozenia: kroki sprawdzane na stanie kancelarii.
SCIEZKA = [
    ("umowa", "Umowa powierzenia zaakceptowana", ""),
    ("pierwsza_sprawa", "Pierwsza sprawa odczytana", "Wgraj wzór i skany jednej sprawy - odczyt trwa kilka minut."),
    ("pierwszy_projekt", "Pierwszy projekt aktu", "Sporządź projekt z zatwierdzonych pól i pobierz go jako Word."),
    ("zespol", "Druga osoba w zespole", "Zaproś osobę z kancelarii w oknie Zespół - zajmie minutę."),
    ("pomocnik", "Pomocnik połączony", "Zainstaluj pomocnika na komputerze kancelarii, żeby sprawdzać KRZ."),
    ("akademia", "Właściciel ukończył Akademię", "Przejdź moduły Akademii - ok. 22 minuty."),
]


# --- przechowywanie --------------------------------------------------------------------

def _sha(tekst: str) -> str:
    return hashlib.sha256(("notarai-akademia:" + tekst.lower()).encode()).hexdigest()[:20]


def _pusty() -> dict:
    return {"osoby": {}, "nagrodzone": [], "sciezka_nagrodzona": False}


def wczytaj(kancelaria: str) -> dict:
    return tokenomia.wczytaj_portfel(kancelaria, KATALOG) or _pusty()


def _zmien(kancelaria: str, zmiana):
    return tokenomia.zmien_portfel(kancelaria, zmiana, utworz=True, katalog=KATALOG, pusty=_pusty)


def _teraz() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _nagrodz(kancelaria: str, kredyty: float, powod: str, znacznik: str, zrodlo: str = "nagroda") -> float:
    """Kredyty tylko, gdy kancelaria placi kredytami. Idempotentnie po znaczniku."""
    if not kredyty or tokenomia.egzekwowana(kancelaria) is None:
        return 0.0
    tokenomia.doladuj(kancelaria, kredyty, powod, znacznik=znacznik, zrodlo=zrodlo)
    return kredyty


# --- quiz --------------------------------------------------------------------------------

def modul_dla_przegladarki(m: dict) -> dict:
    """Bez poprawnych odpowiedzi - te zna tylko serwer."""
    return {"kod": m["kod"], "tytul": m["tytul"], "wersja": m["wersja"], "minut": m["minut"],
            "nagroda": m["nagroda"], "lekcja": m["lekcja"],
            "pytania": [{"pytanie": p["pytanie"], "odpowiedzi": p["odpowiedzi"]} for p in m["pytania"]]}


def ocen(kod: str, odpowiedzi: list[int]) -> tuple[int, int, list[bool]]:
    m = _MODULY[kod]
    trafione = [i < len(odpowiedzi) and odpowiedzi[i] == p["poprawna"] for i, p in enumerate(m["pytania"])]
    return sum(trafione), len(trafione), trafione


def zalicz(kancelaria: str, email: str, kod: str, odpowiedzi: list[int], w_zespole: bool) -> dict:
    """Ocenia probe, zapisuje zaliczenie i ewentualna nagrode."""
    if kod not in _MODULY:
        raise HTTPException(404, "Nie ma takiego modułu.")
    m = _MODULY[kod]
    osoba = _sha(email or "stanowisko")
    teraz = datetime.now(timezone.utc)
    dobre, wszystkie, trafione = ocen(kod, odpowiedzi)
    zaliczone = dobre / wszystkie >= PROG_ZALICZENIA

    def zmiana(d):
        o = d["osoby"].setdefault(osoba, {"moduly": {}, "proby": {}})
        if kod in o["moduly"]:
            return {"juz": True, "nagroda": 0.0}
        ostatnia = o["proby"].get(kod)
        if ostatnia and teraz - datetime.fromisoformat(ostatnia) < timedelta(minutes=PRZERWA_MINUT):
            raise HTTPException(429, f"Kolejna próba za {PRZERWA_MINUT} minut od poprzedniej. "
                                     "Wróć do lekcji - odpowiedzi są w niej.")
        o["proby"][kod] = teraz.isoformat(timespec="seconds")
        if not zaliczone:
            return {"juz": False, "nagroda": 0.0}
        o["moduly"][kod] = {"zaliczono": _teraz(), "wersja": m["wersja"], "wynik": f"{dobre}/{wszystkie}"}
        nagroda = 0.0
        if w_zespole and (osoba in d["nagrodzone"] or len(d["nagrodzone"]) < MAKS_NAGRADZANYCH_OSOB):
            if osoba not in d["nagrodzone"]:
                d["nagrodzone"].append(osoba)
            nagroda = float(m["nagroda"])
        return {"juz": False, "nagroda": nagroda}
    stan = _zmien(kancelaria, zmiana)
    przyznano = 0.0
    if stan["nagroda"]:
        przyznano = _nagrodz(kancelaria, stan["nagroda"], f"akademia: {m['tytul']}", f"akademia:{osoba}:{kod}")
    log.info("akademia: kancelaria %s, modul %s, wynik %d/%d%s", kancelaria, kod, dobre, wszystkie,
             f", nagroda {przyznano:g} kr." if przyznano else "")
    # Ktore pytania zle - bez podawania poprawnych odpowiedzi (wracasz do lekcji).
    return {"zaliczony": zaliczone or stan["juz"], "wynik": f"{dobre}/{wszystkie}",
            "bledne": [i + 1 for i, ok in enumerate(trafione) if not ok] if not zaliczone else [],
            "nagroda": przyznano, "juz_zaliczony": stan["juz"]}


# --- sciezka wdrozenia ---------------------------------------------------------------------

def kroki_sciezki(kancelaria: str, wpis: dict | None) -> dict[str, bool]:
    """Stan krokow z faktow: rejestr kancelarii, historia portfela, urzadzenia."""
    wpis = wpis or {}
    portfel = tokenomia.wczytaj_portfel(kancelaria) or {}
    akcje = {w.get("akcja") for w in portfel.get("historia", [])}
    for miesiac in (portfel.get("miesiace") or {}).values():
        akcje |= set(miesiac)
    try:
        import urzadzenia
        pomocnik = bool(urzadzenia.lista(kancelaria))
    except Exception:  # noqa: BLE001 - brak magazynu pomocnikow to brak pomocnika
        pomocnik = False
    d = wczytaj(kancelaria)
    wlasciciele = [o["email"] for o in wpis.get("zespol", []) if o.get("rola") == "wlasciciel"]
    akademia = any(len((d["osoby"].get(_sha(e)) or {}).get("moduly", {})) >= len(MODULY) for e in wlasciciele)
    return {
        "umowa": bool((wpis.get("umowa") or {}).get("zaakceptowano")),
        "pierwsza_sprawa": any(a and a.startswith("odczyt_strony") for a in akcje),
        "pierwszy_projekt": "projekt" in akcje,
        "zespol": sum(1 for o in wpis.get("zespol", []) if o.get("dolaczyl")) >= 2,
        "pomocnik": pomocnik,
        "akademia": akademia,
    }


def sciezka(kancelaria: str, wpis: dict | None) -> dict:
    stan = kroki_sciezki(kancelaria, wpis)
    gotowe = sum(stan.values())
    nastepny = next(((k, n, r) for k, n, r in SCIEZKA if not stan[k]), None)
    nagroda = 0.0
    if gotowe == len(SCIEZKA):
        def zmiana(d):
            if d.get("sciezka_nagrodzona"):
                return False
            d["sciezka_nagrodzona"] = _teraz()
            return True
        if _zmien(kancelaria, zmiana):
            nagroda = _nagrodz(kancelaria, NAGRODA_WDROZENIA, "sciezka wdrozenia ukonczona", "akademia:sciezka")
    return {"kroki": [{"kod": k, "nazwa": n, "gotowe": stan[k]} for k, n, _ in SCIEZKA],
            "gotowe": gotowe, "wszystkie": len(SCIEZKA),
            "nastepny": {"kod": nastepny[0], "nazwa": nastepny[1], "jak": nastepny[2]} if nastepny else None,
            "nagroda_za_ukonczenie": NAGRODA_WDROZENIA, "przyznano": nagroda}


# --- polecenia ---------------------------------------------------------------------------

# Kod polecenia podpisuje token admina (w chmurze z Secrets Manager). Kod nie
# otwiera zadnego dostepu - wiaze tylko polecenie z kancelaria.
_SEKRET = os.getenv("PIECZAPP_ADMIN_TOKEN", "") or "notarai-lokalnie"


def kod_polecenia(kancelaria: str) -> str:
    return hmac.new(_SEKRET.encode(), kancelaria.encode(), hashlib.sha256).hexdigest()[:8].upper()


def kancelaria_z_kodu(rejestr: dict, kod: str) -> str | None:
    kod = (kod or "").strip().upper()
    if len(kod) != 8:
        return None
    for wpis in rejestr.values():
        if wpis.get("aktywna", True) and hmac.compare_digest(kod_polecenia(wpis["id"]), kod):
            return wpis["id"]
    return None


def _nip(wpis: dict) -> str:
    return "".join(c for c in str((wpis.get("dane") or {}).get("nip", "")) if c.isdigit())


def nagrodz_polecenie(rejestr: dict, wpis: dict) -> float:
    """Pierwsza oplacona faktura polecanej kancelarii: 200 kr. dla obu stron.
    Nie dla tej samej firmy (NIP), najwyzej 10 polecen rocznie u polecajacego."""
    polecil = wpis.get("polecil")
    if not polecil or wpis.get("polecenie_nagrodzone"):
        return 0.0
    polecajacy = next((w for w in rejestr.values() if w["id"] == polecil), None)
    wpis["polecenie_nagrodzone"] = _teraz()
    if polecajacy is None or (_nip(wpis) and _nip(wpis) == _nip(polecajacy)):
        log.info("akademia: polecenie kancelarii %s bez nagrody (ta sama firma albo brak polecajacego)", wpis["id"])
        return 0.0
    rok = str(datetime.now(timezone.utc).year)

    def zmiana(d):
        lata = d.setdefault("polecenia", {})
        if lata.get(rok, 0) >= MAKS_POLECEN_ROCZNIE:
            return False
        lata[rok] = lata.get(rok, 0) + 1
        return True
    if not _zmien(polecil, zmiana):
        return 0.0
    _nagrodz(polecil, NAGRODA_POLECENIA, "polecenie kancelarii", f"polecenie:{wpis['id']}", "polecenie")
    _nagrodz(wpis["id"], NAGRODA_POLECENIA, "dolaczenie z polecenia", f"polecony:{wpis['id']}", "polecenie")
    log.info("akademia: polecenie %s -> %s nagrodzone", polecil, wpis["id"])
    return NAGRODA_POLECENIA


def premia_stazu(oplaconych_okresow: int, pula: float) -> float:
    for prog, procent in PREMIE_STAZU:
        if oplaconych_okresow >= prog:
            return round(pula * procent, 1)
    return 0.0


def nastepna_premia(oplaconych_okresow: int) -> dict | None:
    for prog, procent in sorted(PREMIE_STAZU):
        if oplaconych_okresow < prog:
            return {"za_okresow": prog - oplaconych_okresow, "procent": int(procent * 100)}
    return None


# --- zaswiadczenie ------------------------------------------------------------------------

def zaswiadczenie(kancelaria_nazwa: str, email: str, d: dict) -> str:
    o = d["osoby"].get(_sha(email or "stanowisko")) or {"moduly": {}}
    linie = ["ZAŚWIADCZENIE O SZKOLENIU Z KORZYSTANIA Z NARZĘDZI AI",
             "(art. 4 rozporządzenia (UE) 2024/1689 - AI Act; Zasady korzystania z AI w kancelarii, § 3)", "",
             f"Kancelaria: {kancelaria_nazwa}", f"Osoba: {email or 'stanowisko lokalne'}", "",
             "Ukończone moduły Akademii notarai:"]
    for m in MODULY:
        z = o["moduly"].get(m["kod"])
        linie.append(f"  [{'x' if z else ' '}] {m['tytul']} (wersja {m['wersja']})"
                     + (f" - zaliczono {z['zaliczono'][:10]}, wynik {z['wynik']}" if z else " - nie ukończono"))
    linie += ["", f"Wygenerowano {_teraz()[:10]} w notarai. Przechowuj z dokumentacją ochrony danych kancelarii."]
    return "\n".join(linie)


# --- API -----------------------------------------------------------------------------------

router = APIRouter(prefix="/api/akademia", tags=["akademia"])


def _kontekst(request: Request) -> tuple[str, str, dict | None, bool]:
    """(kancelaria, e-mail osoby, wpis rejestru, czy osoba jest w zespole)."""
    import autoryzacja
    import magazyn
    kancelaria = magazyn.kancelaria()
    email = (getattr(request.state, "email", "") or "").lower()
    wpis = None
    try:
        wpis = next((w for w in autoryzacja._wczytaj_rejestr().values() if w["id"] == kancelaria), None)
    except Exception:  # noqa: BLE001
        wpis = None
    w_zespole = bool(wpis and email and any(o["email"].lower() == email for o in wpis.get("zespol", [])))
    return kancelaria, email, wpis, w_zespole


@router.get("")
def stan(request: Request):
    kancelaria, email, wpis, _ = _kontekst(request)
    d = wczytaj(kancelaria)
    moje = (d["osoby"].get(_sha(email or "stanowisko")) or {}).get("moduly", {})
    zaplacone = sum(1 for p in (wpis or {}).get("platnosci", []) if p.get("status") == "true")
    return {
        "moduly": [{**modul_dla_przegladarki(m), "zaliczony": m["kod"] in moje,
                    "zaliczono": (moje.get(m["kod"]) or {}).get("zaliczono")} for m in MODULY],
        "ukonczone": len(moje), "wszystkie": len(MODULY),
        "nagrody_do_zdobycia": sum(m["nagroda"] for m in MODULY if m["kod"] not in moje),
        "sciezka": sciezka(kancelaria, wpis),
        "polecenie": {"kod": kod_polecenia(kancelaria), "nagroda": NAGRODA_POLECENIA,
                      "zasada": "Po pierwszej opłaconej fakturze poleconej kancelarii obie dostają kredyty."},
        "staz": {"oplaconych_okresow": zaplacone, "nastepna_premia": nastepna_premia(zaplacone)},
        "kredyty_wlaczone": tokenomia.egzekwowana(kancelaria) is not None,
    }


class Proba(BaseModel):
    odpowiedzi: list[int]


@router.post("/{kod}")
def zdaj(kod: str, proba: Proba, request: Request):
    kancelaria, email, _, w_zespole = _kontekst(request)
    return zalicz(kancelaria, email, kod, proba.odpowiedzi, w_zespole)


@router.get("/zaswiadczenie", response_class=PlainTextResponse)
def moje_zaswiadczenie(request: Request):
    kancelaria, email, wpis, _ = _kontekst(request)
    return zaswiadczenie((wpis or {}).get("nazwa", kancelaria), email, wczytaj(kancelaria))


@router.get("/zespol/postep")
def postep_zespolu(request: Request):
    """Dla wlasciciela: kto ukonczyl ile modulow - dokumentacja kompetencji
    (art. 4 AI Act), bez rankingu."""
    import autoryzacja
    kancelaria, email, wpis, _ = _kontekst(request)
    if not wpis or email not in autoryzacja._wlasciciele(wpis):
        raise HTTPException(403, "Postęp zespołu widzi właściciel kancelarii.")
    d = wczytaj(kancelaria)
    return {"osoby": [{"email": o["email"],
                       "ukonczone": len((d["osoby"].get(_sha(o["email"])) or {}).get("moduly", {})),
                       "wszystkie": len(MODULY)} for o in wpis.get("zespol", [])]}
