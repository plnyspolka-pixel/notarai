"""Testy warstwy pod oknem pomocnika. Tkinter nie jest tu uruchamiany."""
import json
import queue

from pomocnik import klient, okno, przegladarka


class TestUstawien:
    def test_zapis_i_odczyt(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        okno.zapisz_ustawienia("https://app.notarai.pl", "token-kancelarii")
        assert okno.wczytaj_ustawienia() == {
            "adres": "https://app.notarai.pl", "token": "token-kancelarii"}

    def test_brak_pliku_to_puste_ustawienia(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        assert okno.wczytaj_ustawienia() == {}

    def test_zepsuty_plik_nie_wywraca_pomocnika(self, tmp_path, monkeypatch):
        """Notariusz nie ma jak tego naprawic, wiec startujemy z pustymi."""
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        okno.plik_ustawien().write_text("{to nie jest json", encoding="utf-8")
        assert okno.wczytaj_ustawienia() == {}

    def test_token_zostaje_na_tym_komputerze(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        okno.zapisz_ustawienia("https://app.notarai.pl", "token-kancelarii")
        zapisany = json.loads(okno.plik_ustawien().read_text("utf-8"))
        assert zapisany["token"] == "token-kancelarii"
        assert okno.plik_ustawien().is_relative_to(tmp_path)


class TestPrzegladarki:
    def _flagi(self, monkeypatch, tmp_path, **kw):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(przegladarka, "sciezka_przegladarki", lambda: "chrome.exe")
        zapamietane = {}
        przegladarka.uruchom(start=lambda flagi, **k: zapamietane.setdefault("flagi", flagi), **kw)
        return zapamietane["flagi"]

    def test_osobny_profil_bo_domyslny_jest_zablokowany(self, monkeypatch, tmp_path):
        """Od Chrome 136 sterowanie przegladarka na domyslnym profilu nie dziala."""
        flagi = self._flagi(monkeypatch, tmp_path)
        assert any(f.startswith("--user-data-dir=") for f in flagi)
        assert not any(f == "--user-data-dir=" for f in flagi)

    def test_port_sterowania_tylko_na_localhost(self, monkeypatch, tmp_path):
        flagi = self._flagi(monkeypatch, tmp_path)
        assert "--remote-debugging-address=127.0.0.1" in flagi

    def test_okno_po_prawej_stronie_ekranu(self, monkeypatch, tmp_path):
        flagi = self._flagi(monkeypatch, tmp_path, ekran=(1920, 1080))
        assert "--window-position=960,0" in flagi
        assert "--window-size=960,1080" in flagi

    def test_waskie_ekrany_nie_daja_okienka_na_znaczek(self, monkeypatch, tmp_path):
        flagi = self._flagi(monkeypatch, tmp_path, ekran=(1000, 800))
        assert "--window-size=640,800" in flagi

    def test_bez_przegladarki_mowimy_co_zrobic(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(przegladarka, "sciezka_przegladarki", lambda: None)
        try:
            przegladarka.uruchom(start=lambda *a, **k: None)
        except RuntimeError as blad:
            assert "Zainstaluj" in str(blad)
        else:
            raise AssertionError("brak przegladarki musi byc zglaszany")


class AtrapaKlienta:
    """Serwer: laczy od razu, a przy pracy odrzuca token `odrzuc` razy."""

    def __init__(self, odrzuc=0):
        self.odrzuc = odrzuc
        self.odlaczone = []

    def __call__(self, adres, token=""):
        atrapa = self

        class Klient(klient.Notarai):
            def popros_o_kod(self, nazwa):
                return {"kod": "ABCD-EFGH", "sekret": "s"}

            def odbierz_token(self, kod, sekret):
                return "pom_nowy"

            def zlecenia(self):
                if atrapa.odrzuc:
                    atrapa.odrzuc -= 1
                    raise klient.BladTokenu("odlaczony")
                sterownik.stop()
                return []

            def odlacz(self):
                atrapa.odlaczone.append(self.token)

        return Klient(adres=adres, token=token)


def _sterownik(monkeypatch, tmp_path, atrapa):
    global sterownik
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("NOTARAI_ADRES", raising=False)
    otwarte = []
    sterownik = okno.Sterownik(queue.Queue(), otworz_strone=otwarte.append,
                               wykonawcy={}, nowy_klient=atrapa)
    return sterownik, otwarte


class TestRazUstawiaszIJedziesz:
    def test_pierwsze_uruchomienie_otwiera_notarai_z_kodem(self, monkeypatch, tmp_path):
        sterownik, otwarte = _sterownik(monkeypatch, tmp_path, AtrapaKlienta())
        sterownik.cykl()
        assert otwarte == ["https://app.notarai.pl/#polacz=ABCD-EFGH"]
        assert okno.wczytaj_ustawienia()["token"] == "pom_nowy", "token zapamietany"

    def test_kolejne_uruchomienie_nie_pyta_o_nic(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        okno.zapisz_ustawienia("https://app.notarai.pl", "pom_zapamietany")
        sterownik, otwarte = _sterownik(monkeypatch, tmp_path, AtrapaKlienta())
        sterownik.cykl()
        assert otwarte == [], "polaczony komputer nie otwiera strony laczenia"

    def test_odlaczony_komputer_sam_wraca_do_laczenia(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        okno.zapisz_ustawienia("https://app.notarai.pl", "pom_stary")
        sterownik, otwarte = _sterownik(monkeypatch, tmp_path, AtrapaKlienta(odrzuc=1))
        sterownik.cykl()
        assert otwarte == ["https://app.notarai.pl/#polacz=ABCD-EFGH"]
        assert okno.wczytaj_ustawienia()["token"] == "pom_nowy"

    def test_odlaczenie_z_okna_zapomina_token_i_mowi_serwerowi(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        okno.zapisz_ustawienia("https://app.notarai.pl", "pom_stary")
        atrapa = AtrapaKlienta()
        sterownik, _ = _sterownik(monkeypatch, tmp_path, atrapa)
        sterownik.adres = "https://app.notarai.pl"
        sterownik.odlacz_ten_komputer()
        assert atrapa.odlaczone == ["pom_stary"]
        assert okno.wczytaj_ustawienia()["token"] == ""

    def test_adres_dla_wsparcia_ze_zmiennej(self, monkeypatch):
        monkeypatch.setenv("NOTARAI_ADRES", "http://127.0.0.1:8000/")
        assert okno.adres_notarai({}) == "http://127.0.0.1:8000"
