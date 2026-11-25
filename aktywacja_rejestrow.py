"""Indywidualna aktywacja rejestrów chronionych (GOV-03) - rdzeń domenowy.

Nie zmienia Cognito ani logowania. Podpis kwalifikowany potwierdza TOŻSAMOŚĆ,
nie przyznaje dostępu: dostęp wymaga osobno (1) weryfikacji zawodowej w
wykazie KRN, (2) udokumentowanej decyzji instytucji, (3) klucza w sejfie.
Zewnętrzne porty (weryfikacja podpisu/ścieżki zaufania UE, wykaz KRN, sejf)
są wstrzykiwane; ten moduł nie ufa plikowi certyfikatu ani deklaracji użytkownika.
Stan trzyma magazyn (pamięć w testach, DynamoDB w produkcji; zapisy warunkowe).
"""
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Protocol

import rejestry_panstwowe as rp

BRAK, WNIOSEK, ZLOZONY, PRZYZNANY, SKONFIGUROWANY, WYGASLY, ODWOLANY = (
    "brak", "wniosek_przygotowany", "zlozony", "przyznany", "skonfigurowany", "wygasly", "odwolany")
TTL_CHALLENGE_S = 300
WAZNOSC_PODPISU_S = 12 * 3600  # jak długo świeża weryfikacja tożsamości uprawnia do aktywacji
CHRONIONE = frozenset(r["id"] for r in rp.katalog() if r["sciezka"] in ("wymaga_dostepu", "wymaga_potwierdzenia"))


class BladAktywacji(RuntimeError):
    pass


@dataclass(frozen=True)
class DowodPodpisu:
    """Wynik weryfikacji zewnętrznej (QTSP/EU trust list). Wszystkie pola muszą być True."""
    integralnosc: bool
    sciezka_zaufania_ue: bool       # łańcuch do zaufanej listy UE, nie samopodpisany
    kwalifikowany: bool             # certyfikat kwalifikowany w statusie 'granted' w chwili podpisu
    nieodwolany: bool               # brak odwołania (CRL/OCSP)
    podpisany_challenge: str        # dokładnie ten nonce, który wystawiono
    identyfikator_podpisujacego: str  # stabilny identyfikator osoby z certyfikatu


class WeryfikatorPodpisu(Protocol):
    def zweryfikuj(self, podpis: bytes) -> DowodPodpisu: ...


class WykazKrn(Protocol):
    def czynny_notariusz(self, identyfikator_podpisujacego: str) -> bool: ...


class Sejf(Protocol):
    def ma_klucz(self, kancelaria: str, email: str, usluga: str) -> bool: ...


@dataclass(frozen=True)
class Decyzja:
    """Udokumentowana decyzja instytucji (nie deklaracja użytkownika)."""
    instytucja: str
    numer: str
    data: str
    hash_dokumentu: str
    wazna_do: float  # epoch


def _h(s):
    return hashlib.sha256(s.encode()).hexdigest()


class Konflikt(Exception):
    """Zapis warunkowy nie powiódł się (równoległa zmiana)."""


class Pamiec:
    """Magazyn w pamięci (testy, tryb lokalny). Semantyka taka sama jak DynamoMagazyn."""
    def __init__(self):
        import threading
        self._l, self._ch, self._r, self._t = threading.Lock(), {}, {}, {}

    def zapisz_challenge(self, n, dane):
        with self._l:
            self._ch[n] = dane

    def zuzyj_challenge(self, n):  # atomowo: zwraca i usuwa
        with self._l:
            return self._ch.pop(n, None)

    def czytaj(self, k, e, u):
        with self._l:
            r = self._r.get((k, e, u))
            return (dict(r[0]), r[1]) if r else (None, 0)

    def zapisz(self, k, e, u, rek, wersja):  # warunkowo po wersji
        with self._l:
            akt = self._r.get((k, e, u))
            if (akt[1] if akt else 0) != wersja:
                raise Konflikt()
            self._r[(k, e, u)] = (dict(rek), wersja + 1)

    def tozsamosc_osoby(self, k, e):
        with self._l:
            return self._t.get(("o", k, e))

    def zwiaz_tozsamosc(self, k, e, t):
        """Wiąże tożsamość z kontem i konto z tożsamością (wszystko albo nic); True, gdy zgodne."""
        with self._l:
            a, b = self._t.get(("o", k, e)), self._t.get(("t", t))
            if (a not in (None, t)) or (b not in (None, (k, e))):
                return False
            self._t[("o", k, e)], self._t[("t", t)] = t, (k, e)
            return True


    def krn_potwierdz(self, t, czynny=True):
        with self._l:
            self._t[("krn", t)] = bool(czynny)

    def krn_czy(self, t):
        with self._l:
            return bool(self._t.get(("krn", t)))


class KrnReczne:
    """Do czasu oficjalnego API KRN (GOV-09): operator potwierdza czynny status notariusza
    (po sprawdzeniu w wykazie KRN). Klucz = skrót identyfikatora z certyfikatu."""
    def __init__(self, magazyn):
        self._m = magazyn

    def czynny_notariusz(self, identyfikator):
        return self._m.krn_czy(_h(identyfikator))


class Aktywacje:
    def __init__(self, weryfikator, krn, sejf, magazyn=None, zegar=time.time):
        self._w, self._krn, self._sejf, self._z = weryfikator, krn, sejf, zegar
        self._m = magazyn or Pamiec()

    # --- challenge: jednorazowy, powiązany z sesją, osobą, kancelarią i celem
    def wystaw_challenge(self, sesja, kancelaria, email, usluga):
        self._usluga(usluga)
        n = secrets.token_urlsafe(32)
        self._m.zapisz_challenge(n, {"k": [sesja, kancelaria, email, usluga], "do": self._z() + TTL_CHALLENGE_S})
        return n

    def _zuzyj(self, n, sesja, kancelaria, email, usluga):
        c = self._m.zuzyj_challenge(n)  # atomowe usunięcie = jednorazowość także w wielu kontenerach
        if c is None or c["do"] < self._z() or list(c["k"]) != [sesja, kancelaria, email, usluga]:
            raise BladAktywacji("Challenge nieważny, zużyty lub wystawiony dla kogoś innego.")

    @staticmethod
    def _usluga(u):
        if u not in CHRONIONE:
            raise BladAktywacji("Ta usługa nie podlega indywidualnej aktywacji.")

    def _zmien(self, k, e, u, fn):
        """Odczyt-modyfikacja-zapis z kontrolą wersji; ponawia przy konflikcie."""
        for _ in range(5):
            r, w = self._m.czytaj(k, e, u)
            r = r or {"status": BRAK, "tozsamosc": None, "podpis_do": 0.0, "decyzja": None, "zgoda": False}
            r = fn(r)
            try:
                self._m.zapisz(k, e, u, r, w)
                return r
            except Konflikt:
                continue
        raise BladAktywacji("Równoległa zmiana - spróbuj ponownie.")

    # --- czynności użytkownika
    def przygotuj_wniosek(self, kancelaria, email, usluga):
        self._usluga(usluga)

        def f(r):
            if r["status"] not in (BRAK, WYGASLY, ODWOLANY):
                raise BladAktywacji("Wniosek już istnieje.")
            return {**r, "status": WNIOSEK, "decyzja": None, "zgoda": False}
        self._zmien(kancelaria, email, usluga, f)

    def zloz_z_podpisem(self, sesja, kancelaria, email, usluga, challenge, podpis, zgoda_na_zakres):
        if not zgoda_na_zakres:
            raise BladAktywacji("Brak zgody notariusza na zakres i warunki dostępu.")
        self._zuzyj(challenge, sesja, kancelaria, email, usluga)  # zużyty także przy odrzuceniu
        d = self._w.zweryfikuj(podpis)
        if not (d.integralnosc and d.sciezka_zaufania_ue and d.kwalifikowany and d.nieodwolany):
            raise BladAktywacji("Podpis nie spełnia wymogów (ścieżka UE, status kwalifikowany, odwołanie, integralność).")
        if d.podpisany_challenge != challenge:
            raise BladAktywacji("Podpis nie dotyczy tego challenge.")
        if not self._krn.czynny_notariusz(d.identyfikator_podpisujacego):
            raise BladAktywacji("Status zawodowy niepotwierdzony w wykazie KRN.")
        t = _h(d.identyfikator_podpisujacego)

        def f(r):
            if r["status"] != WNIOSEK:
                raise BladAktywacji("Najpierw przygotuj wniosek.")
            return {**r, "status": ZLOZONY, "tozsamosc": t, "podpis_do": self._z() + WAZNOSC_PODPISU_S, "zgoda": True}
        # tożsamość wiązana raz na konto i raz na osobę - sprawdzenie przed zapisem statusu
        r0, _ = self._m.czytaj(kancelaria, email, usluga)
        if not r0 or r0["status"] != WNIOSEK:
            raise BladAktywacji("Najpierw przygotuj wniosek.")
        if not self._m.zwiaz_tozsamosc(kancelaria, email, t):
            raise BladAktywacji("Podpisujący nie jest osobą powiązaną z tym kontem (lub tożsamość należy do innego konta).")
        self._zmien(kancelaria, email, usluga, f)

    # --- czynności instytucji / operatora dowodów (NIE wystawiać użytkownikowi)
    def przyznaj(self, kancelaria, email, usluga, decyzja):
        if not (decyzja.instytucja and decyzja.numer and decyzja.hash_dokumentu and decyzja.wazna_do > self._z()):
            raise BladAktywacji("Przyznanie wymaga udokumentowanej, ważnej decyzji.")

        def f(r):
            if r["status"] != ZLOZONY:
                raise BladAktywacji("Przyznać można tylko złożony wniosek.")
            return {**r, "status": PRZYZNANY, "decyzja": {"instytucja": decyzja.instytucja, "numer": decyzja.numer,
                    "data": decyzja.data, "hash_dokumentu": decyzja.hash_dokumentu, "wazna_do": decyzja.wazna_do}}
        self._zmien(kancelaria, email, usluga, f)

    def skonfigurowano(self, kancelaria, email, usluga):
        def f(r):
            if r["status"] != PRZYZNANY:
                raise BladAktywacji("Konfiguracja wymaga przyznanego dostępu.")
            if not self._sejf.ma_klucz(kancelaria, email, usluga):
                raise BladAktywacji("Brak klucza w sejfie.")
            return {**r, "status": SKONFIGUROWANY}
        self._zmien(kancelaria, email, usluga, f)

    def odwolaj(self, kancelaria, email, usluga):
        self._zmien(kancelaria, email, usluga, lambda r: {**r, "status": ODWOLANY})

    def rotacja_klucza(self, kancelaria, email, usluga):
        """Po wymianie klucza w sejfie; wymaga świeżego klucza i nadal ważnej decyzji."""
        r, _ = self._m.czytaj(kancelaria, email, usluga)
        if not r or r["status"] != SKONFIGUROWANY or not self._sejf.ma_klucz(kancelaria, email, usluga):
            raise BladAktywacji("Rotacja możliwa tylko dla skonfigurowanej usługi z kluczem w sejfie.")

    # --- bramka: jedyne miejsce, które pozwala uruchomić adapter chroniony
    def status(self, kancelaria, email, usluga):
        r, _ = self._m.czytaj(kancelaria, email, usluga)
        if not r:
            return BRAK
        if r["status"] in (PRZYZNANY, SKONFIGUROWANY) and r["decyzja"]["wazna_do"] <= self._z():
            self._zmien(kancelaria, email, usluga, lambda x: {**x, "status": WYGASLY})
            return WYGASLY
        return r["status"]

    def moze_uzyc(self, sesja_indywidualna, kancelaria, email, usluga):
        """(True, '') tylko gdy spełnione WSZYSTKIE warunki."""
        if usluga not in CHRONIONE:
            return False, "nie_chroniona"
        if not sesja_indywidualna:
            return False, "tylko_indywidualna_sesja"  # demo, serwis, komputer
        s = self.status(kancelaria, email, usluga)
        if s != SKONFIGUROWANY:
            return False, "status_" + s
        r, _ = self._m.czytaj(kancelaria, email, usluga)
        if not r["zgoda"]:
            return False, "brak_zgody"
        if not self._sejf.ma_klucz(kancelaria, email, usluga):
            return False, "brak_klucza"
        return True, ""
