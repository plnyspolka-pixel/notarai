"""Testy warstwy pod oknem pomocnika. Tkinter nie jest tu uruchamiany."""
import json

from pomocnik import okno, przegladarka


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
