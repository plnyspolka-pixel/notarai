"""e-Doręczenia: bezpieczny cykl przesyłki (szkic oddzielony od wysyłki) - GOV-02.

Stany: SZKIC -> ZATWIERDZONY (osoba uprawniona, powiązane z hashem treści)
-> WYSYLANIE -> WYSLANY | ODRZUCONY | NIEZNANY. Zasady:
- wysyłka tylko z ZATWIERDZONY i tylko raz (atomowa zmiana stanu, klucz idempotencji),
- zmiana treści cofa do SZKIC (zatwierdzenie dotyczy konkretnej treści),
- niejednoznaczny wynik (timeout) = NIEZNANY: żadnego automatycznego ponowienia,
  tylko uzgodnienie (`uzgodnij`) po sprawdzeniu skrzynki nadawczej,
- ponowienie tylko po jednoznacznym ODRZUCONY,
- wszystko w obrębie kancelarii: inny tenant nie widzi cudzych przesyłek.
Transport (UA API) to port; kontrakt UA API jest dostępny dopiero po dostępie do INT.
"""
import hashlib
import json
import threading
import uuid
from typing import Protocol

SZKIC, ZATWIERDZONY, WYSYLANIE, WYSLANY, ODRZUCONY, NIEZNANY = (
    "SZKIC", "ZATWIERDZONY", "WYSYLANIE", "WYSLANY", "ODRZUCONY", "NIEZNANY")


class BladPrzesylki(RuntimeError):
    pass


class Odrzucone(Exception):
    """Transport: system odrzucił przesyłkę jednoznacznie (nic nie wysłano)."""


class Transport(Protocol):
    def wyslij(self, przesylka: dict, klucz_idempotencji: str) -> str: ...  # zwraca id u dostawcy


def _hash(p):
    return hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Skrzynka:
    """Referencyjny magazyn w pamięci; produkcyjny wymaga trwałego, transakcyjnego."""
    def __init__(self, transport):
        self._t, self._d, self._blokada = transport, {}, threading.Lock()

    def _get(self, kancelaria, pid):
        r = self._d.get((kancelaria, pid))
        if r is None:  # ten sam komunikat dla cudzej i nieistniejącej
            raise BladPrzesylki("Nie ma takiej przesyłki.")
        return r

    def szkic(self, kancelaria, autor, adresat_ade, tytul, tresc):
        pid = str(uuid.uuid4())
        with self._blokada:
            self._d[(kancelaria, pid)] = {
                "id": pid, "stan": SZKIC, "autor": autor, "klucz": str(uuid.uuid4()),
                "przesylka": {"adresat": adresat_ade, "tytul": tytul, "tresc": tresc},
                "zatwierdzono": None, "dostawca_id": None}
        return pid

    def zmien(self, kancelaria, pid, **pola):
        with self._blokada:
            r = self._get(kancelaria, pid)
            if r["stan"] not in (SZKIC, ZATWIERDZONY):
                raise BladPrzesylki("Przesyłki w tym stanie nie wolno zmieniać.")
            if set(pola) - {"adresat", "tytul", "tresc"}:
                raise BladPrzesylki("Niedozwolone pole.")
            r["przesylka"].update(pola)
            r["stan"], r["zatwierdzono"] = SZKIC, None

    def zatwierdz(self, kancelaria, pid, osoba, uprawniony):
        if not uprawniony:
            raise BladPrzesylki("Zatwierdza wyłącznie osoba uprawniona.")
        with self._blokada:
            r = self._get(kancelaria, pid)
            if r["stan"] != SZKIC:
                raise BladPrzesylki("Zatwierdzić można tylko szkic.")
            r["stan"], r["zatwierdzono"] = ZATWIERDZONY, {"osoba": osoba, "hash": _hash(r["przesylka"])}

    def wyslij(self, kancelaria, pid):
        with self._blokada:  # atomowe przejście - drugi wątek zobaczy WYSYLANIE
            r = self._get(kancelaria, pid)
            if r["stan"] != ZATWIERDZONY or r["zatwierdzono"]["hash"] != _hash(r["przesylka"]):
                raise BladPrzesylki("Wysyłka wymaga zatwierdzonej, niezmienionej przesyłki.")
            r["stan"] = WYSYLANIE
            przesylka, klucz = dict(r["przesylka"]), r["klucz"]
        try:
            did = self._t.wyslij(przesylka, klucz)
        except Odrzucone:
            with self._blokada:
                r["stan"] = ODRZUCONY
            raise BladPrzesylki("Przesyłka odrzucona; można ją poprawić i ponowić.") from None
        except Exception:
            with self._blokada:
                r["stan"] = NIEZNANY
            raise BladPrzesylki("Wynik wysyłki nieznany - sprawdź skrzynkę nadawczą, nie wysyłaj ponownie.") from None
        with self._blokada:
            r["stan"], r["dostawca_id"] = WYSLANY, did
        return did

    def uzgodnij(self, kancelaria, pid, wyslano, dostawca_id=None):
        """Ręczne uzgodnienie stanu NIEZNANY po sprawdzeniu skrzynki nadawczej."""
        with self._blokada:
            r = self._get(kancelaria, pid)
            if r["stan"] != NIEZNANY:
                raise BladPrzesylki("Uzgodnienie dotyczy tylko stanu NIEZNANY.")
            if wyslano:
                r["stan"], r["dostawca_id"] = WYSLANY, dostawca_id
            else:
                r["stan"], r["zatwierdzono"], r["klucz"] = SZKIC, None, str(uuid.uuid4())

    def ponow(self, kancelaria, pid):
        with self._blokada:
            r = self._get(kancelaria, pid)
            if r["stan"] != ODRZUCONY:
                raise BladPrzesylki("Ponowić można tylko jednoznacznie odrzuconą przesyłkę.")
            r["stan"], r["zatwierdzono"], r["klucz"] = SZKIC, None, str(uuid.uuid4())

    def stan(self, kancelaria, pid):
        with self._blokada:
            return self._get(kancelaria, pid)["stan"]
