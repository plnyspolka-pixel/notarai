"""Portal KRZ widziany przez CDP - adapter dla pomocnika.

Wiedza o tym, CO zrobic w KRZ, siedzi w krz_portal.py. Tutaj jest tylko JAK
zrobic to bez Playwrighta, w przegladarce notariusza.

Szukamy po napisach, nie po selektorach CSS. Portal nie gwarantuje nazw klas
ani identyfikatorow, ale gwarantuje napisy - bo te widzi czlowiek. Adres ramki
z formularzem zawiera nazwe srodowiska wdrozeniowego ministerstwa i zmieni sie
przy pierwszej aktualizacji, wiec ramke tez znajdujemy po zawartosci.
"""
from __future__ import annotations

import logging
import time

from pomocnik.cdp import BladPrzegladarki, StronaCDP

log = logging.getLogger("notarai.pomocnik.krz")

ADRES = "https://krz.ms.gov.pl/"
NAPIS_FORMULARZA = "Wyszukaj"
CZEKANIE_NA_WYNIK_S = 15.0


class StronaKRZ:
    """Spelnia protokol krz_portal.StronaKRZ, sterujac przegladarka przez CDP."""

    def __init__(self, strona: StronaCDP):
        self._glowna = strona
        self._ramka: StronaCDP | None = None

    # --- to, czego wymaga krz_portal ---------------------------------------

    def otworz(self) -> None:
        self._ramka = None
        self._glowna.otworz(ADRES)
        self._glowna.poczekaj_na_dokument()
        time.sleep(2.0)  # portal dociaga interfejs po zaladowaniu dokumentu
        self._klik_jesli_jest(self._glowna, "Akceptuj")       # zgoda na ciasteczka
        self._klik_jesli_jest(self._glowna, "Wyszukiwanie podmiotów")
        self._ramka = self._glowna.ramka_z_tekstem(NAPIS_FORMULARZA)

    def wybierz_zakladke(self, nazwa: str) -> None:
        selektor = self._ramka_formularza().selektor_po_tekscie(nazwa)
        if not selektor:
            raise BladPrzegladarki(f"Nie znalazlem zakladki „{nazwa}” w KRZ.")
        self._ramka_formularza().kliknij(selektor)
        time.sleep(0.8)

    def wpisz_identyfikator(self, wartosc: str) -> None:
        ramka = self._ramka_formularza()
        selektor = self._pole(ramka, "Identyfikator")
        if not selektor:
            raise BladPrzegladarki("Nie znalazlem pola Identyfikator w formularzu KRZ.")
        ramka.wpisz(selektor, wartosc)

    def wyszukaj(self) -> None:
        ramka = self._ramka_formularza()
        selektor = self._przycisk(ramka, "Wyszukaj")
        if not selektor:
            raise BladPrzegladarki("Nie znalazlem przycisku Wyszukaj w formularzu KRZ.")
        ramka.kliknij(selektor)
        self._poczekaj_na_wynik(ramka)

    def wyczysc(self) -> None:
        ramka = self._ramka_formularza()
        selektor = self._przycisk(ramka, "Wyczyść")
        if selektor:
            ramka.kliknij(selektor)
            time.sleep(0.5)

    def tekst_wyniku(self) -> str:
        try:
            return self._ramka_formularza().tekst_strony()
        except BladPrzegladarki:
            return ""

    def zrzut(self, cel) -> None:
        self._glowna.zrzut(cel)

    # --- pomocnicze --------------------------------------------------------

    def _ramka_formularza(self) -> StronaCDP:
        if self._ramka is None:
            self._ramka = self._glowna.ramka_z_tekstem(NAPIS_FORMULARZA)
        return self._ramka

    @staticmethod
    def _klik_jesli_jest(strona: StronaCDP, fragment: str) -> None:
        """Rzeczy, ktorych moze nie byc: zgoda na ciasteczka, link do wyszukiwarki."""
        try:
            selektor = strona.selektor_po_tekscie(fragment)
            if selektor:
                strona.kliknij(selektor)
                time.sleep(0.8)
        except BladPrzegladarki:
            pass

    @staticmethod
    def _przycisk(strona: StronaCDP, nazwa: str) -> str | None:
        """Przycisk o dokladnie takim napisie.

        Dokladnie, bo "Wyszukaj" zawiera sie w "Wyszukiwanie podmiotow" i
        klikniecie w ten drugi cofnelo by nas na poczatek.
        """
        szukane = nazwa.strip().lower()
        for element in strona.elementy(limit=300):
            if not element.get("rola", "").startswith(("button", "input:submit", "input:button")):
                continue
            if (element.get("opis") or "").strip().lower() == szukane:
                return element["selektor"]
        return None

    @staticmethod
    def _pole(strona: StronaCDP, fragment: str) -> str | None:
        szukane = fragment.strip().lower()
        for element in strona.elementy(limit=300):
            if not element.get("rola", "").startswith(("input", "textarea")):
                continue
            if szukane in (element.get("opis") or "").strip().lower():
                return element["selektor"]
        return None

    @staticmethod
    def _poczekaj_na_wynik(ramka: StronaCDP) -> None:
        """Czekamy na komunikat portalu, a nie na staly czas.

        Rozpoznanie jest w krz_portal, zeby wzorce byly w jednym miejscu.
        """
        import krz_portal

        koniec = time.monotonic() + CZEKANIE_NA_WYNIK_S
        while time.monotonic() < koniec:
            time.sleep(0.5)
            tekst = ramka.tekst_strony()
            if krz_portal.WZORCE_BRAK.search(tekst):
                return
            if krz_portal.WZORCE_WPIS.search(krz_portal.STALE_TEKSTY.sub(" ", tekst)):
                return
        log.info("krz: minal czas oczekiwania na wynik, ide dalej z tym, co widac")
