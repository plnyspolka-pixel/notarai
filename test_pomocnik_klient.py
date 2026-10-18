"""Testy klienta pomocnika. Atrapa notarai, bez sieci."""
import pytest

from pomocnik import klient
from pomocnik.klient import BladPolaczenia, Notarai, jeden_obieg, pracuj, wykonaj


class AtrapaNotarai(Notarai):
    """notarai, ktore nie wychodzi do sieci."""

    def __init__(self, zlecenia_do_wydania=None, psuj_odsylanie=False):
        super().__init__(adres="https://app.notarai.pl", token="token-testowy")
        self._do_wydania = list(zlecenia_do_wydania or [])
        self.odeslane = []
        self.zapytan = 0
        self.psuj_odsylanie = psuj_odsylanie

    def zlecenia(self):
        self.zapytan += 1
        wynik, self._do_wydania = self._do_wydania, []
        return wynik

    def odeslij(self, identyfikator, raport):
        if self.psuj_odsylanie:
            raise BladPolaczenia("lacze padlo")
        self.odeslane.append((identyfikator, raport))
        return {"stan": "wykonane"}


ZLECENIE_KRZ = {"id": "abc", "rodzaj": "krz", "sprawa": "s1",
                "tresc": {"osoby": [{"pesel": "44051401359", "etykieta": "zbywca"}]}}


class TestKierowaniaZlecen:
    def test_zlecenie_trafia_do_wlasciwego_wykonawcy(self):
        widziane = []
        raport = wykonaj(ZLECENIE_KRZ, {"krz": lambda z: widziane.append(z) or {"ok": True}})
        assert raport == {"ok": True} and widziane == [ZLECENIE_KRZ]

    def test_nieznanego_rodzaju_nie_udajemy(self):
        """Zlecenie, ktorego pomocnik nie umie wykonac, ma wrocic z wyjasnieniem,
        a nie zniknac po cichu - notariusz czeka przy ekranie."""
        raport = wykonaj({"id": "x", "rodzaj": "kosmiczny"}, {"krz": lambda z: {}})
        assert raport["bledy"] and "nie obsluguje" in raport["bledy"][0]


class TestObiegu:
    def test_wykonuje_i_odsyla(self):
        notarai = AtrapaNotarai([ZLECENIE_KRZ])
        zrobione = jeden_obieg(notarai, {"krz": lambda z: {"zapisano": 2}})
        assert zrobione == 1
        assert notarai.odeslane == [("abc", {"zapisano": 2})]

    def test_blad_jednego_zlecenia_nie_przerywa_reszty(self):
        def kapryszny(zlecenie):
            if zlecenie["id"] == "zly":
                raise RuntimeError("cos sie stalo")
            return {"ok": True}

        notarai = AtrapaNotarai([
            {"id": "zly", "rodzaj": "krz"},
            {"id": "dobry", "rodzaj": "krz"},
        ])
        jeden_obieg(notarai, {"krz": kapryszny})
        odeslane = dict(notarai.odeslane)
        assert "bledy" in odeslane["zly"], "blad ma wrocic jako raport, nie zniknac"
        assert odeslane["dobry"] == {"ok": True}

    def test_raport_bledu_nie_niesie_tresci_zlecenia(self):
        """Komunikat bledu trafia do logow serwera. Numery PESEL nie."""
        def wybuchowy(zlecenie):
            raise RuntimeError("blad przy numerze 44051401359")

        notarai = AtrapaNotarai([ZLECENIE_KRZ])
        jeden_obieg(notarai, {"krz": wybuchowy})
        assert "44051401359" not in str(notarai.odeslane)

    def test_brak_zlecen_to_spokojny_obieg(self):
        notarai = AtrapaNotarai([])
        assert jeden_obieg(notarai, {}) == 0
        assert notarai.odeslane == []

    def test_zerwane_odsylanie_nie_wywraca_pomocnika(self):
        notarai = AtrapaNotarai([ZLECENIE_KRZ], psuj_odsylanie=True)
        assert jeden_obieg(notarai, {"krz": lambda z: {"ok": True}}) == 0


class TestPetli:
    def test_konczy_sie_na_zyczenie(self):
        notarai = AtrapaNotarai([])
        obiegi = iter([True, True, False])
        pracuj(notarai, {}, dziala=lambda: next(obiegi), spij=lambda s: None)
        assert notarai.zapytan == 2

    def test_zerwane_lacze_nie_konczy_pomocnika(self):
        """Notariusz zamyka laptopa, traci wi-fi, wraca. To nie jest blad."""
        class Zrywajace(AtrapaNotarai):
            def zlecenia(self):
                self.zapytan += 1
                if self.zapytan == 1:
                    raise BladPolaczenia("brak sieci")
                return []

        notarai = Zrywajace([])
        spania = []
        obiegi = iter([True, True, False])
        pracuj(notarai, {}, dziala=lambda: next(obiegi), spij=spania.append)
        assert notarai.zapytan == 2, "po zerwaniu lacza pomocnik pyta dalej"
        assert klient.PRZERWA_PO_BLEDZIE_S in spania, "po bledzie czekamy dluzej"


class TestRozmowyZSerwerem:
    def test_token_idzie_w_naglowku(self, monkeypatch):
        zapisane = {}

        class AtrapaOdpowiedzi:
            def read(self): return b"[]"
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def podgladnij(zadanie, timeout=None, context=None):
            zapisane["naglowki"] = dict(zadanie.headers)
            zapisane["adres"] = zadanie.full_url
            return AtrapaOdpowiedzi()

        monkeypatch.setattr(klient.urllib.request, "urlopen", podgladnij)
        Notarai("https://app.notarai.pl/", "tajny-token").zlecenia()
        assert zapisane["naglowki"]["Authorization"] == "Bearer tajny-token"
        assert zapisane["adres"].startswith("https://app.notarai.pl/api/pomocnik/zlecenia")

    def test_odrzucony_token_mowi_co_zrobic(self, monkeypatch):
        import io

        def odmow(zadanie, timeout=None, context=None):
            # fp musi byc prawdziwym strumieniem: przy None HTTPError tworzy plik
            # tymczasowy i zostawia go otwartego.
            raise klient.urllib.error.HTTPError(
                zadanie.full_url, 401, "Unauthorized", {}, io.BytesIO(b""))

        monkeypatch.setattr(klient.urllib.request, "urlopen", odmow)
        with pytest.raises(klient.BladTokenu, match="nie jest już połączony"):
            Notarai("https://app.notarai.pl", "zly").zlecenia()


class TestOdlaczonegoKomputera:
    def test_odrzucony_token_konczy_prace_zamiast_ponawiac(self):
        """Zerwane lacze przeczekujemy, odlaczony komputer - nie: ponawianie
        w nieskonczonosc ukryloby przed notariuszem, ze trzeba polaczyc ponownie."""
        class Odlaczone(AtrapaNotarai):
            def zlecenia(self):
                raise klient.BladTokenu("odlaczony")

        with pytest.raises(klient.BladTokenu):
            pracuj(Odlaczone(), {}, dziala=lambda: True, spij=lambda s: None)


class AtrapaLaczenia(Notarai):
    """Serwer, ktory potwierdza kod za `po_ilu` pytaniem."""

    def __init__(self, po_ilu=2, wygasa_pierwszy=False, zrywa_raz=False):
        super().__init__(adres="https://app.notarai.pl")
        self.po_ilu, self.wygasa_pierwszy, self.zrywa_raz = po_ilu, wygasa_pierwszy, zrywa_raz
        self.wydane = []
        self.pytan = 0

    def popros_o_kod(self, nazwa):
        if self.zrywa_raz:
            self.zrywa_raz = False
            raise BladPolaczenia("brak sieci")
        kod = f"KOD{len(self.wydane) + 1}"
        self.wydane.append(kod)
        return {"kod": kod, "sekret": "s", "wazny_s": 600}

    def odbierz_token(self, kod, sekret):
        if self.wygasa_pierwszy and kod == "KOD1":
            raise klient.KodNieaktualny("wygasl")
        self.pytan += 1
        return "pom_token" if self.pytan >= self.po_ilu else None


class TestLaczenia:
    def test_czeka_na_klikniecie_i_zwraca_token(self):
        pokazane = []
        token = klient.polacz(AtrapaLaczenia(po_ilu=3), "BIURO", pokazane.append,
                              spij=lambda s: None)
        assert token == "pom_token"
        assert pokazane == ["KOD1"], "kod pokazujemy raz, nie przy kazdym pytaniu"

    def test_wygasly_kod_wymienia_sam(self):
        pokazane = []
        serwer = AtrapaLaczenia(wygasa_pierwszy=True)
        assert klient.polacz(serwer, "BIURO", pokazane.append, spij=lambda s: None)
        assert pokazane == ["KOD1", "KOD2"]

    def test_zerwane_lacze_przeczekuje(self):
        spania = []
        serwer = AtrapaLaczenia(zrywa_raz=True)
        assert klient.polacz(serwer, "BIURO", lambda k: None, spij=spania.append)
        assert klient.PRZERWA_PO_BLEDZIE_S in spania

    def test_zatrzymanie_w_trakcie(self):
        obiegi = iter([True, False])
        assert klient.polacz(AtrapaLaczenia(po_ilu=99), "BIURO", lambda k: None,
                             dziala=lambda: next(obiegi), spij=lambda s: None) is None

    def test_bez_tokenu_nie_wysyla_naglowka_autoryzacji(self, monkeypatch):
        zapisane = {}

        class Odp:
            def read(self): return b'{"kod": "ABCD-EFGH", "sekret": "s"}'
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def podgladnij(zadanie, timeout=None, context=None):
            zapisane["naglowki"] = dict(zadanie.headers)
            return Odp()

        monkeypatch.setattr(klient.urllib.request, "urlopen", podgladnij)
        Notarai("https://app.notarai.pl").popros_o_kod("BIURO")
        assert "Authorization" not in zapisane["naglowki"]
