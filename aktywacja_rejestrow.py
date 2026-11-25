"""Indywidualna aktywacja rejestrów chronionych (GOV-03) - rdzeń domenowy.

Nie zmienia Cognito ani logowania. Podpis kwalifikowany potwierdza TOŻSAMOŚĆ,
nie przyznaje dostępu: dostęp wymaga osobno (1) weryfikacji zawodowej w
wykazie KRN, (2) udokumentowanej decyzji instytucji, (3) klucza w sejfie.
Zewnętrzne porty (weryfikacja podpisu/ścieżki zaufania UE, wykaz KRN, sejf)
są wstrzykiwane; ten moduł nie ufa plikowi certyfikatu ani deklaracji użytkownika.
Magazyn jest referencyjny (pamięć); produkcyjny: trwały, transakcyjny.
"""
import hashlib
import secrets
import threading
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


class Aktywacje:
    def __init__(self, weryfikator, krn, sejf, zegar=time.time):
        self._w, self._krn, self._sejf, self._z = weryfikator, krn, sejf, zegar
        self._ch, self._st, self._bl = {}, {}, threading.Lock()

    # --- challenge: jednorazowy, powiązany z sesją, osobą, kancelarią i celem
    def wystaw_challenge(self, sesja, kancelaria, email, usluga):
        self._usluga(usluga)
        n = secrets.token_urlsafe(32)
        with self._bl:
            self._ch[n] = {"k": (sesja, kancelaria, email, usluga), "do": self._z() + TTL_CHALLENGE_S}
        return n

    def _zuzyj(self, n, sesja, kancelaria, email, usluga):
        with self._bl:  # atomowo: pop = jednorazowość także przy równoległych żądaniach
            c = self._ch.pop(n, None)
        if c is None or c["do"] < self._z() or c["k"] != (sesja, kancelaria, email, usluga):
            raise BladAktywacji("Challenge nieważny, zużyty lub wystawiony dla kogoś innego.")

    @staticmethod
    def _usluga(u):
        if u not in CHRONIONE:
            raise BladAktywacji("Ta usługa nie podlega indywidualnej aktywacji.")

    def _rek(self, kancelaria, email, usluga):
        return self._st.setdefault((kancelaria, email, usluga), {
            "status": BRAK, "tozsamosc": None, "podpis_do": 0.0, "decyzja": None, "zgoda": False})

    # --- czynności użytkownika
    def przygotuj_wniosek(self, kancelaria, email, usluga):
        self._usluga(usluga)
        with self._bl:
            r = self._rek(kancelaria, email, usluga)
            if r["status"] not in (BRAK, WYGASLY, ODWOLANY):
                raise BladAktywacji("Wniosek już istnieje.")
            r.update(status=WNIOSEK, decyzja=None, zgoda=False)

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
        with self._bl:
            r = self._rek(kancelaria, email, usluga)
            if r["status"] != WNIOSEK:
                raise BladAktywacji("Najpierw przygotuj wniosek.")
            osoba_t = {v["tozsamosc"] for (k, e, _), v in self._st.items()
                       if (k, e) == (kancelaria, email) and v["tozsamosc"]}
            if osoba_t and t not in osoba_t:
                raise BladAktywacji("Podpisujący nie jest osobą powiązaną z tym kontem.")
            if any(v["tozsamosc"] == t and (k, e) != (kancelaria, email) for (k, e, _), v in self._st.items()):
                raise BladAktywacji("Ta tożsamość jest już powiązana z innym kontem.")
            r.update(status=ZLOZONY, tozsamosc=t, podpis_do=self._z() + WAZNOSC_PODPISU_S, zgoda=True)

    # --- czynności instytucji / operatora dowodów (NIE wystawiać użytkownikowi)
    def przyznaj(self, kancelaria, email, usluga, decyzja):
        if not (decyzja.instytucja and decyzja.numer and decyzja.hash_dokumentu and decyzja.wazna_do > self._z()):
            raise BladAktywacji("Przyznanie wymaga udokumentowanej, ważnej decyzji.")
        with self._bl:
            r = self._rek(kancelaria, email, usluga)
            if r["status"] != ZLOZONY:
                raise BladAktywacji("Przyznać można tylko złożony wniosek.")
            r.update(status=PRZYZNANY, decyzja=decyzja)

    def skonfigurowano(self, kancelaria, email, usluga):
        with self._bl:
            r = self._rek(kancelaria, email, usluga)
            if r["status"] != PRZYZNANY:
                raise BladAktywacji("Konfiguracja wymaga przyznanego dostępu.")
            if not self._sejf.ma_klucz(kancelaria, email, usluga):
                raise BladAktywacji("Brak klucza w sejfie.")
            r["status"] = SKONFIGUROWANY

    def odwolaj(self, kancelaria, email, usluga):
        with self._bl:
            self._rek(kancelaria, email, usluga)["status"] = ODWOLANY

    def rotacja_klucza(self, kancelaria, email, usluga):
        """Po wymianie klucza w sejfie; wymaga świeżego klucza i nadal ważnej decyzji."""
        with self._bl:
            r = self._rek(kancelaria, email, usluga)
            if r["status"] != SKONFIGUROWANY or not self._sejf.ma_klucz(kancelaria, email, usluga):
                raise BladAktywacji("Rotacja możliwa tylko dla skonfigurowanej usługi z kluczem w sejfie.")

    # --- bramka: jedyne miejsce, które pozwala uruchomić adapter chroniony
    def status(self, kancelaria, email, usluga):
        with self._bl:
            r = self._st.get((kancelaria, email, usluga))
            if not r:
                return BRAK
            if r["status"] in (PRZYZNANY, SKONFIGUROWANY) and r["decyzja"].wazna_do <= self._z():
                r["status"] = WYGASLY
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
        with self._bl:
            r = self._st[(kancelaria, email, usluga)]
            if not r["zgoda"]:
                return False, "brak_zgody"
        if not self._sejf.ma_klucz(kancelaria, email, usluga):
            return False, "brak_klucza"
        return True, ""
