"""Kalkulator taksy dla klientow kancelarii - publiczne API bez logowania.

Dwie drogi do wyniku:
  - POST /api/taksa/oblicz   - gotowe parametry (formularz na stronie), liczy taksa.py,
  - POST /api/taksa/rozmowa  - rozmowa zwyklym jezykiem; model (Bedrock, region UE)
                               ustala parametry, a kwoty i tak liczy taksa.py.
Do tego GET /api/taksa z katalogiem czynnosci dla formularza.

Strona notarai.pl (hosting az.pl) wola app.notarai.pl z innej domeny, wiec
odpowiedzi na /api/taksa niosa naglowki CORS - tylko dla tych sciezek i tylko
dla domen z PIECZAPP_KALKULATOR_ORIGINS. Reszta API zostaje bez CORS.

Punkt jest otwarty dla kazdego, a kazda tura kosztuje wywolanie modelu, wiec
sa limity na adres IP i na dobe (na proces; kopii aplikacji jest kilka).
Tresci rozmow nie zapisujemy i nie logujemy - klient moze napisac o sobie
wiecej, niz trzeba. Do logow trafiaja liczby: tury, znaki, czy byla kalkulacja.
"""
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import date

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

import autoryzacja
import bedrock
import dziennik
import prompty
import taksa

log = logging.getLogger("pieczapp.kalkulator")

WLACZONY = os.getenv("PIECZAPP_KALKULATOR", "true").lower() == "true"
# Osobny profil modelu dla kalkulatora. Limit zapytan Bedrock jest liczony na
# model, wiec publiczny czat na innym profilu nie dlawi odczytu skanow
# kancelarii (config.MODEL, Opus). Sonnet 4.6 sprawdzony na zywo 07.11.2026:
# czysty JSON, 1,5-3,5 s na odpowiedz, poprawne identyfikatory. Pusto = ten
# sam model co reszta aplikacji.
MODEL_DOMYSLNY = "eu.anthropic.claude-sonnet-4-6"


def _model_z_env(wartosc: str | None) -> str:
    """Profil kalkulatora; jak config.MODEL musi byc profilem EU."""
    model = (MODEL_DOMYSLNY if wartosc is None else wartosc).strip()
    if model and not model.startswith("eu."):
        raise RuntimeError(f"PIECZAPP_KALKULATOR_MODEL '{model}' nie jest profilem EU (prefiks 'eu.').")
    return model


MODEL = _model_z_env(os.getenv("PIECZAPP_KALKULATOR_MODEL"))
ORIGINY = tuple(o.strip().rstrip("/") for o in os.getenv(
    "PIECZAPP_KALKULATOR_ORIGINS", "https://notarai.pl,https://www.notarai.pl").split(",") if o.strip())

# Limity rozmowy z modelem. Formularz (bez modelu) ma limit luzniejszy.
NA_IP_GODZINA = int(os.getenv("PIECZAPP_KALKULATOR_NA_IP", "40"))
NA_DOBE = int(os.getenv("PIECZAPP_KALKULATOR_NA_DOBE", "1500"))
MAX_WIADOMOSC = 1500
MAX_HISTORIA = 24
MAX_TURA_HISTORII = 3000

router = APIRouter(prefix="/api/taksa", tags=["taksa"])


class Limit:
    """Okno przesuwne: tyle prob na adres IP na godzine i tyle lacznie na dobe."""

    def __init__(self, na_ip: int, na_dobe: int):
        self.na_ip, self.na_dobe = na_ip, na_dobe
        self._ip: dict[str, deque] = {}
        self._wszystkie: deque = deque()
        self._blokada = threading.Lock()

    def sprawdz(self, adres_ip: str, komunikat: str) -> None:
        teraz = time.monotonic()
        with self._blokada:
            while self._wszystkie and teraz - self._wszystkie[0] > 86400:
                self._wszystkie.popleft()
            proby = self._ip.setdefault(adres_ip, deque())
            while proby and teraz - proby[0] > 3600:
                proby.popleft()
            if len(proby) >= self.na_ip or len(self._wszystkie) >= self.na_dobe:
                raise HTTPException(429, komunikat)
            proby.append(teraz)
            self._wszystkie.append(teraz)
            if len(self._ip) > 10000:   # porzadek po adresach, ktore dawno nie pisaly
                for ip in [ip for ip, p in self._ip.items() if not p]:
                    del self._ip[ip]

    def wyczysc(self) -> None:
        with self._blokada:
            self._ip.clear()
            self._wszystkie.clear()


limit_rozmowy = Limit(NA_IP_GODZINA, NA_DOBE)
limit_formularza = Limit(NA_IP_GODZINA * 6, NA_DOBE * 20)


# --- CORS tylko dla kalkulatora -------------------------------------------


def _naglowki_cors(origin: str) -> dict:
    return {"Access-Control-Allow-Origin": origin, "Vary": "Origin",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400"}


async def cors(request: Request, call_next):
    """Strona notarai.pl wola kalkulator na app.notarai.pl. Inne sciezki i domeny: bez zmian."""
    origin = request.headers.get("origin", "").rstrip("/")
    if not request.url.path.startswith("/api/taksa") or origin not in ORIGINY:
        return await call_next(request)
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=_naglowki_cors(origin))
    odpowiedz = await call_next(request)
    for klucz, wartosc in _naglowki_cors(origin).items():
        odpowiedz.headers[klucz] = wartosc
    return odpowiedz


# --- API -------------------------------------------------------------------


@router.get("")
def informacje():
    return {"wlaczony": WLACZONY, "dzis": date.today().isoformat(), **taksa.katalog()}


@router.post("/oblicz")
def oblicz(parametry: dict, request: Request):
    """Liczy z gotowych parametrow (formularz na stronie). Bez modelu."""
    limit_formularza.sprawdz(autoryzacja.adres_klienta(request),
                             "Za dużo wyliczeń naraz. Spróbuj za chwilę.")
    if len(json.dumps(parametry)) > 20000:
        raise HTTPException(400, "Za dużo danych.")
    return taksa.oblicz(parametry)


class Rozmowa(BaseModel):
    wiadomosc: str
    historia: list[dict] = []
    # Pole niewidoczne dla czlowieka; wypelnia je tylko automat.
    strona: str = ""


def _tury_dla_modelu(historia: list[dict]) -> list[dict]:
    """Historia z przegladarki -> naprzemienne tury Bedrock.

    Tury asystenta odtwarzamy jako JSON, ktory model mial zwrocic, zeby trzymal
    format. Parametrow z przegladarki nie bierzemy na slowo: kwoty do rozmowy
    liczy taksa.py na nowo, wiec klient nie podstawi modelowi cudzych liczb.
    """
    tury: list[dict] = []
    wynik_poprzedni = ""

    def dodaj(rola: str, tekst: str) -> None:
        if tury and tury[-1]["role"] == rola:
            tury[-1]["content"].append({"text": tekst})
        else:
            tury.append({"role": rola, "content": [{"text": tekst}]})

    for wpis in historia[-MAX_HISTORIA:]:
        if not isinstance(wpis, dict):
            continue
        tresc = str(wpis.get("tresc") or "")[:MAX_TURA_HISTORII]
        if wpis.get("rola") == "uzytkownik":
            if wynik_poprzedni:
                tresc = f"{wynik_poprzedni}\n\nKLIENT: {tresc}"
                wynik_poprzedni = ""
            if tresc.strip():
                dodaj("user", tresc)
        elif wpis.get("rola") == "asystent":
            parametry = wpis.get("parametry") if isinstance(wpis.get("parametry"), dict) else None
            if not tury:
                continue   # powitanie ze strony nie jest tura modelu
            dodaj("assistant", json.dumps({"odpowiedz": tresc, "kalkulacja": parametry}, ensure_ascii=False))
            if parametry:
                wynik = taksa.oblicz(parametry)
                if wynik["pozycje"]:
                    wynik_poprzedni = "WYNIK KALKULATORA dla poprzedniej odpowiedzi:\n" + "\n".join(
                        f"- {p['etykieta']}: {taksa.zl(p['brutto'])}" for p in wynik["pozycje"]
                    ) + f"\nRAZEM: {taksa.zl(wynik['razem'])}"
    return tury, wynik_poprzedni


def _odczytaj(odpowiedz: str) -> tuple[str, dict | None]:
    """JSON modelu -> (tekst dla klienta, parametry albo None). Zly JSON = sam tekst."""
    try:
        dane = bedrock._wczytaj_json(odpowiedz)
    except bedrock.NiepoprawnyJson:
        tekst = odpowiedz.strip().strip("`")
        return (tekst or "Nie zrozumiałem. Proszę opisać czynność i jej wartość."), None
    tekst = str(dane.get("odpowiedz") or "").strip()
    parametry = dane.get("kalkulacja")
    if not isinstance(parametry, dict) or not (parametry.get("czynnosci") or parametry.get("stale")):
        parametry = None
    return tekst, parametry


def _system() -> str:
    dzis = date.today()
    return (prompty.TAKSA + f"\nDZIS JEST {dzis.isoformat()}.\n\n" + taksa.opis_dla_modelu(dzis))


@router.post("/rozmowa")
def rozmowa(zadanie: Rozmowa, request: Request):
    if not WLACZONY:
        raise HTTPException(503, "Asystent kosztów jest wyłączony. Skorzystaj z formularza.")
    wiadomosc = zadanie.wiadomosc.strip()
    if not wiadomosc:
        raise HTTPException(400, "Napisz, jaką czynność planujesz.")
    if len(wiadomosc) > MAX_WIADOMOSC:
        raise HTTPException(400, f"Wiadomość jest za długa (najwyżej {MAX_WIADOMOSC} znaków).")
    if zadanie.strona:
        return {"odpowiedz": "Dziękuję.", "kalkulacja": None, "parametry": None}
    limit_rozmowy.sprawdz(autoryzacja.adres_klienta(request),
                          "Za dużo pytań naraz. Spróbuj za godzinę albo skorzystaj z formularza poniżej.")

    tury, wynik_poprzedni = _tury_dla_modelu(zadanie.historia)
    if tury and tury[-1]["role"] == "user":
        tury[-1]["content"].append({"text": wiadomosc})
        ostatnia = tury.pop()
        tresc = "\n".join(c["text"] for c in ostatnia["content"])
    else:
        tresc = f"{wynik_poprzedni}\n\nKLIENT: {wiadomosc}" if wynik_poprzedni else wiadomosc
    try:
        odpowiedz = bedrock.rozmowa_kalkulatora(_system(), tury, tresc, MODEL or None)
    except bedrock.Przeciazenie:
        raise HTTPException(503, "Asystent jest chwilowo zajęty. Spróbuj za minutę albo skorzystaj "
                                 "z formularza poniżej.", headers={"Retry-After": "60"})
    except Exception as blad:
        log.error("kalkulator: blad modelu (%s)", dziennik.opis_bledu(blad))
        raise HTTPException(502, "Asystent nie odpowiada. Skorzystaj z formularza poniżej.")

    tekst, parametry = _odczytaj(odpowiedz)
    wynik = None
    if parametry:
        parametry.pop("data", None)   # liczymy na dzis; stawki sprzed zmiany sa do formularza
        wynik = taksa.oblicz(parametry)
        if not wynik["pozycje"]:
            wynik, parametry = None, None
    log.info("kalkulator: tura %d, znakow %d, kalkulacja=%s",
             len(tury) + 1, len(wiadomosc), "tak" if wynik else "nie")
    return {"odpowiedz": tekst, "kalkulacja": wynik, "parametry": parametry}
