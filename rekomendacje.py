"""Neutralna kolejnosc kancelarii i przydzial zgloszen "dowolna kancelaria".

Zasada (docs/rekomendacje-notariuszy.md): to, czy kancelaria korzysta
z notarai albo cokolwiek nam placi, NIGDY nie wplywa na jej miejsce na liscie
ani na to, komu przydzielamy zgloszenie. Ten modul celowo nie dostaje
informacji o abonamencie ani o koncie w notarai, zeby nie dalo sie jej uzyc
przez pomylke. Kancelarie korzystajace z notarai roznia sie od pozostalych
wylacznie tym, JAK obsluza klienta (potwierdzenie online, przypomnienia,
lista dokumentow), a nie tym, GDZIE je widac.

Kryteria kolejnosci, w tej kolejnosci:
  1. To, o co pyta klient: odleglosc od wskazanego punktu, w pasmach
     PASMO_KM (bliskie odleglosci sa sobie rowne, zeby 200 m nie rozstrzygalo).
  2. Czy klient w ogole moze sie z kancelaria skontaktowac (kancelaria bez
     zadnego kontaktu w publicznych wykazach idzie na koniec).
  3. Codzienna rotacja: skrot SHA-256 z (dzien, kontekst, kancelaria). Kazda
     kancelaria ma te sama szanse na kazde miejsce, kolejnosc jest jednakowa
     dla wszystkich odwiedzajacych danego dnia (da sie ja odtworzyc i sprawdzic),
     a jutro jest inna. Zastepuje kolejnosc alfabetyczna, ktora stale
     faworyzuje nazwiska na "A".

Przydzial "dowolna kancelaria w miejscowosci": kolejka sprawiedliwa (ta
kancelaria w miejscowosci, ktora w oknie OKNO_DNI dostala od nas najmniej
przydzialow), remis rozstrzyga ta sama rotacja. Kancelaria spoza notarai
dostaje przydzial na rowni z innymi - zgloszenie przekazuje jej obsluga.
"""
import hashlib
from datetime import date, datetime, timedelta

WERSJA = "2026-11-08"
PASMO_KM = 2.0
OKNO_DNI = 90


def _dzien(dzien: date | None) -> str:
    return (dzien or date.today()).isoformat()


def los(dzien: date | None, kontekst: str, ident) -> int:
    """Liczba z rotacji dziennej. Deterministyczna: ten sam dzien, kontekst
    i kancelaria daja zawsze to samo, wiec kazdy moze to policzyc."""
    tekst = f"notarai|{WERSJA}|{_dzien(dzien)}|{kontekst}|{ident}"
    return int.from_bytes(hashlib.sha256(tekst.encode("utf-8")).digest()[:8], "big")


def pasmo(odleglosc_km: float | None) -> int:
    return 0 if odleglosc_km is None else int(odleglosc_km // PASMO_KM)


def kolejnosc(kancelarie: list[dict], kontekst: str = "", dzien: date | None = None,
              klucz_id: str = "id") -> list[dict]:
    """Kancelarie w neutralnej kolejnosci. Uwzglednia tylko pola
    "odleglosc_km" (gdy klient podal polozenie) i "brak_kontaktu"."""
    return sorted(kancelarie, key=lambda k: (
        pasmo(k.get("odleglosc_km")),
        bool(k.get("brak_kontaktu")),
        los(dzien, kontekst, k[klucz_id]),
    ))


def przydziel(kandydaci: list, wczesniejsze: list[dict], kontekst: str,
              teraz: datetime | None = None) -> object | None:
    """Kancelaria dla zgloszenia bez wybranej kancelarii.

    kandydaci    - identyfikatory kancelarii w miejscowosci (z kontaktem),
    wczesniejsze - dotychczasowe zgloszenia (pola "baza_id", "utworzono",
                   "przydzial"); liczymy tylko przydzialy automatyczne.
    """
    if not kandydaci:
        return None
    teraz = teraz or datetime.now()
    granica = (teraz - timedelta(days=OKNO_DNI)).isoformat(timespec="seconds")
    licznik = {k: 0 for k in kandydaci}
    for z in wczesniejsze:
        if (z.get("przydzial") or {}).get("sposob") == "kolejka" and z.get("utworzono", "") >= granica \
                and z.get("baza_id") in licznik:
            licznik[z["baza_id"]] += 1
    return min(kandydaci, key=lambda k: (licznik[k], los(teraz.date(), kontekst, k)))
