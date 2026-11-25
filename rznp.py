"""Klient Rejestru Zastrzeżeń Numerów PESEL (RZNP), kontrakt OpenAPI 2.0.8.

Zasady (GOV-01): adapter jest domyślnie wyłączony - bez jawnie podanego
środowiska nie wykona żądania; klucz API należy do indywidualnego notariusza
i jest przekazywany przy tworzeniu klienta (nigdy z globalnej konfiguracji);
PESEL nie trafia do komunikatów błędów ani logów; awaria NIGDY nie oznacza
braku zastrzeżenia.
"""
import re
import uuid
from datetime import date, datetime
from urllib.parse import urlsplit

import httpx

KONTRAKT = "2.0.8"
TIMEOUT_S = 5.0  # SLA: maksymalny czas odpowiedzi usługi to 5 s
SRODOWISKA = {
    "int": "https://int-rejestr-zastrzezen.obywatel.gov.pl:20443/api/v1",
    "prod": "https://rejestr-zastrzezen.obywatel.gov.pl:20443/api/v1",
}
STATUSY = ("ZASTRZEZONY", "NIEZASTRZEZONY")
_POWOD = re.compile(r"^[-.,_ a-zA-ZżźćńółęąśŻŹĆŃÓŁĘĄŚ0-9\\/]+$")


class BladRznp(RuntimeError):
    """Bazowy błąd. Zawsze oznacza BRAK ustalenia statusu, nie 'niezastrzeżony'."""
    def __init__(self, komunikat, http=None, kod=None):
        super().__init__(komunikat)
        self.http, self.kod = http, kod


class Niedostepny(BladRznp):
    """5xx, timeout, niedostępność planowana lub brak połączenia."""
    planowana_do = None


class BrakAutoryzacji(BladRznp):
    """401/403/429 - klucz, aktywność konta lub adres IP."""


class NiepoprawneZapytanie(BladRznp):
    """400 lub walidacja lokalna."""


def pesel_poprawny(p):
    if not isinstance(p, str) or not re.fullmatch(r"\d{11}", p):
        return False
    w = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    return (10 - sum(int(c) * k for c, k in zip(p, w)) % 10) % 10 == int(p[10])


def _srodowisko(srodowisko, produkcja, baza):
    if baza:  # tylko stub/emulator lokalny
        h = urlsplit(baza)
        if h.hostname not in ("localhost", "127.0.0.1") or h.scheme not in ("http", "https"):
            raise ValueError("Własny adres dozwolony wyłącznie dla emulatora lokalnego.")
        return baza.rstrip("/")
    if srodowisko == "prod" and not produkcja:
        raise ValueError("Środowisko produkcyjne wymaga jawnej zgody (produkcja=True) i klucza notariusza.")
    if srodowisko not in SRODOWISKA:
        raise ValueError("Nieznane środowisko RZNP (int lub prod).")
    return SRODOWISKA[srodowisko]


class KlientRznp:
    def __init__(self, klucz_api, srodowisko=None, *, produkcja=False,
                 baza_emulatora=None, client=None):
        if not baza_emulatora and not klucz_api:
            raise ValueError("Brak klucza API notariusza - adapter wyłączony.")
        if not baza_emulatora and srodowisko is None:
            raise ValueError("Adapter RZNP jest domyślnie wyłączony - wskaż środowisko.")
        self._baza = _srodowisko(srodowisko, produkcja, baza_emulatora)
        self._klucz = klucz_api
        self._client = client or httpx.Client()

    def __repr__(self):  # klucz nigdy w logach
        return f"KlientRznp({self._baza})"

    @staticmethod
    def _powod(powod):
        if not isinstance(powod, str) or not 3 <= len(powod) <= 512 or not _POWOD.match(powod):
            raise NiepoprawneZapytanie("Powód weryfikacji: 3-512 znaków, bez znaków specjalnych.")
        return powod

    def _post(self, sciezka, tresc):
        rid = str(uuid.uuid4())
        h = {"X-REQUEST-ID": rid, "Accept": "application/json"}
        if self._klucz:
            h["X-API-KEY"] = self._klucz
        try:
            r = self._client.post(self._baza + sciezka, json=tresc, headers=h,
                                  timeout=TIMEOUT_S, follow_redirects=False)
        except httpx.HTTPError:
            raise Niedostepny("Brak odpowiedzi RZNP (timeout lub połączenie). Status nieustalony.") from None
        try:
            d = r.json()
        except ValueError:
            d = {}
        kod = d.get("kod") if isinstance(d, dict) else None
        if r.status_code == 200:
            if not isinstance(d, dict):
                raise Niedostepny("Niepoprawna odpowiedź RZNP. Status nieustalony.", 200)
            return rid, d
        if r.status_code == 400:
            raise NiepoprawneZapytanie("RZNP odrzucił zapytanie.", 400, kod)
        if r.status_code in (401, 403, 429):
            raise BrakAutoryzacji("RZNP odmówił dostępu (klucz, konto lub adres IP).", r.status_code, kod)
        e = Niedostepny("RZNP niedostępny. Status nieustalony.", r.status_code, kod)
        if isinstance(d, dict):
            e.planowana_do = d.get("planowanaNiedostepnoscDo")
        raise e

    @staticmethod
    def _status(o):
        # Uwaga: kontrakt 2.0.8 ma niespójność (required: statusZastrzezenia,
        # properties: status). Wymagamy pola `status` z dozwolonej listy.
        if not isinstance(o, dict) or o.get("status") not in STATUSY:
            raise Niedostepny("Niepoprawny status w odpowiedzi RZNP. Status nieustalony.", 200)
        poczatek = o.get("dataICzasPoczatkuWaznosciStatusu")
        if poczatek is not None:
            try:
                datetime.fromisoformat(poczatek)
            except (TypeError, ValueError):
                raise Niedostepny("Niepoprawna data w odpowiedzi RZNP.", 200) from None
        return {"status": o["status"], "od": poczatek}

    @staticmethod
    def _czas(d):
        try:
            datetime.fromisoformat(d["dataICzasWeryfikacji"])
        except (KeyError, TypeError, ValueError):
            raise Niedostepny("Brak czasu weryfikacji w odpowiedzi RZNP.", 200) from None
        return d["dataICzasWeryfikacji"]

    def aktualny(self, pesel, powod):
        if not pesel_poprawny(pesel):
            raise NiepoprawneZapytanie("Niepoprawny numer PESEL.")
        rid, d = self._post("/status-zastrzezenia/aktualny",
                            {"powodWeryfikacji": self._powod(powod), "PESEL": pesel})
        return {"requestId": rid, "zweryfikowano": self._czas(d),
                **self._status(d.get("aktualnyStatus"))}

    def na_dzien(self, pesel, dzien, powod):
        """Statusy historyczne - NIE do weryfikacji przed podpisaniem umowy."""
        if not pesel_poprawny(pesel):
            raise NiepoprawneZapytanie("Niepoprawny numer PESEL.")
        try:
            if date.fromisoformat(dzien).isoformat() != dzien:
                raise ValueError()
        except (TypeError, ValueError):
            raise NiepoprawneZapytanie("Data w formacie RRRR-MM-DD.") from None
        rid, d = self._post("/status-zastrzezenia/na-dzien",
                            {"powodWeryfikacji": self._powod(powod), "PESEL": pesel, "data": dzien})
        s = d.get("statusy")
        if not isinstance(s, list):
            raise Niedostepny("Niepoprawna lista statusów RZNP.", 200)
        return {"requestId": rid, "zweryfikowano": self._czas(d),
                "statusy": [self._status(x) for x in s]}
