"""Testy logowania uzytkownikow. Cognito zastapione atrapa, bez sieci."""
import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class BladCognito(Exception):
    """Udaje wyjatek boto3 - liczy sie sama nazwa klasy."""


def _wyjatek(nazwa):
    return type(nazwa, (BladCognito,), {})()


class AtrapaCognito:
    def __init__(self):
        self.utworzeni = []
        self.wyslane_kody = []
        self.blad = None

    def initiate_auth(self, **kw):
        if self.blad:
            raise self.blad
        if kw["AuthParameters"]["PASSWORD"] == "tymczasowe":
            return {"ChallengeName": "NEW_PASSWORD_REQUIRED", "Session": "sesja-123"}
        return {"AuthenticationResult": {"IdToken": "token.z.cognito", "ExpiresIn": 28800}}

    def respond_to_auth_challenge(self, **kw):
        if self.blad:
            raise self.blad
        return {"AuthenticationResult": {"IdToken": "token.po.zmianie", "ExpiresIn": 28800}}

    def forgot_password(self, **kw):
        if self.blad:
            raise self.blad
        self.wyslane_kody.append(kw["Username"])

    def confirm_forgot_password(self, **kw):
        if self.blad:
            raise self.blad

    def admin_create_user(self, **kw):
        if self.blad:
            raise self.blad
        self.utworzeni.append(kw["Username"])


@pytest.fixture(autouse=True)
def _przywroc_moduly():
    """Po kazdym tescie przywraca moduly do stanu domyslnego.

    Testy wlaczaja tryb wielu kancelarii i logowanie przez przeladowanie
    modulow. Bez sprzatania kolejne pliki testow dostawalyby 401.
    """
    yield
    import autoryzacja
    import logowanie
    import magazyn
    importlib.reload(magazyn)
    importlib.reload(logowanie)
    importlib.reload(autoryzacja)


@pytest.fixture
def logowanie_atrapa(monkeypatch):
    monkeypatch.setenv("PIECZAPP_COGNITO_POOL", "eu-central-1_TEST")
    monkeypatch.setenv("PIECZAPP_COGNITO_KLIENT", "klient-testowy")
    import logowanie
    importlib.reload(logowanie)
    atrapa = AtrapaCognito()
    monkeypatch.setattr(logowanie, "_klient", lambda: atrapa)
    yield logowanie, atrapa
    monkeypatch.delenv("PIECZAPP_COGNITO_POOL", raising=False)
    monkeypatch.delenv("PIECZAPP_COGNITO_KLIENT", raising=False)
    importlib.reload(logowanie)


class TestLogowanie:
    def test_poprawne_haslo_daje_token(self, logowanie_atrapa):
        logowanie, _ = logowanie_atrapa
        assert logowanie.zaloguj("kto@example.com", "Haslo123456")["token"] == "token.z.cognito"

    def test_haslo_z_zaproszenia_wymusza_zmiane(self, logowanie_atrapa):
        logowanie, _ = logowanie_atrapa
        wynik = logowanie.zaloguj("kto@example.com", "tymczasowe")
        assert wynik["wymagane_nowe_haslo"] is True and wynik["sesja"] == "sesja-123"

    def test_zle_haslo_nie_zdradza_czy_konto_istnieje(self, logowanie_atrapa):
        logowanie, atrapa = logowanie_atrapa
        for nazwa in ("NotAuthorizedException", "UserNotFoundException"):
            atrapa.blad = _wyjatek(nazwa)
            with pytest.raises(logowanie.BladLogowania) as blad:
                logowanie.zaloguj("kto@example.com", "zle")
            assert "e-mail albo haslo" in str(blad.value), "komunikat ma byc taki sam w obu przypadkach"

    def test_slabe_haslo_tlumaczone_na_polski(self, logowanie_atrapa):
        logowanie, atrapa = logowanie_atrapa
        atrapa.blad = _wyjatek("InvalidPasswordException")
        with pytest.raises(logowanie.BladLogowania) as blad:
            logowanie.ustaw_nowe_haslo("kto@example.com", "abc", "sesja-123")
        assert "za slabe" in str(blad.value)


class TestOdzyskiwanieHasla:
    def test_nieznany_adres_nie_jest_bledem(self, logowanie_atrapa):
        """Inaczej formularz zdradzalby, ktore adresy maja konto."""
        logowanie, atrapa = logowanie_atrapa
        atrapa.blad = _wyjatek("UserNotFoundException")
        logowanie.wyslij_kod("nieznany@example.com")

    def test_kod_trafia_do_cognito(self, logowanie_atrapa):
        logowanie, atrapa = logowanie_atrapa
        logowanie.wyslij_kod("kto@example.com")
        assert atrapa.wyslane_kody == ["kto@example.com"]

    def test_zly_kod_ma_czytelny_komunikat(self, logowanie_atrapa):
        logowanie, atrapa = logowanie_atrapa
        atrapa.blad = _wyjatek("CodeMismatchException")
        with pytest.raises(logowanie.BladLogowania) as blad:
            logowanie.ustaw_haslo_kodem("kto@example.com", "000000", "Haslo123456")
        assert "nieprawidlowy albo wygasl" in str(blad.value)

    def test_zbyt_wiele_prob(self, logowanie_atrapa):
        logowanie, atrapa = logowanie_atrapa
        atrapa.blad = _wyjatek("LimitExceededException")
        with pytest.raises(logowanie.BladLogowania):
            logowanie.wyslij_kod("kto@example.com")


class TestTozsamoscTokenu:
    def test_rozpoznanie_tokenu_jwt(self, logowanie_atrapa):
        logowanie, _ = logowanie_atrapa
        assert logowanie.czy_jwt("aaa.bbb.ccc") is True
        assert logowanie.czy_jwt("66e51a1d710c0e1d62e2502f9bb11e7b") is False

    def test_token_bez_kancelarii_odrzucony(self, logowanie_atrapa, monkeypatch):
        logowanie, _ = logowanie_atrapa
        monkeypatch.setattr(logowanie, "_weryfikator", lambda: _AtrapaKluczy())
        import jwt as biblioteka
        monkeypatch.setattr(biblioteka, "decode", lambda *a, **k: {"token_use": "id", "email": "k@x.pl"})
        with pytest.raises(logowanie.BladLogowania) as blad:
            logowanie.dane_z_tokenu("a.b.c")
        assert "kancelarii" in str(blad.value)

    def test_token_dostepowy_nie_jest_tozsamoscia(self, logowanie_atrapa, monkeypatch):
        logowanie, _ = logowanie_atrapa
        monkeypatch.setattr(logowanie, "_weryfikator", lambda: _AtrapaKluczy())
        import jwt as biblioteka
        monkeypatch.setattr(biblioteka, "decode",
                            lambda *a, **k: {"token_use": "access", "custom:kancelaria": "x"})
        with pytest.raises(logowanie.BladLogowania):
            logowanie.dane_z_tokenu("a.b.c")

    def test_poprawny_token_daje_kancelarie(self, logowanie_atrapa, monkeypatch):
        logowanie, _ = logowanie_atrapa
        monkeypatch.setattr(logowanie, "_weryfikator", lambda: _AtrapaKluczy())
        import jwt as biblioteka
        monkeypatch.setattr(biblioteka, "decode", lambda *a, **k: {
            "token_use": "id", "email": "kto@example.com", "custom:kancelaria": "kowalski"})
        assert logowanie.dane_z_tokenu("a.b.c") == {
            "email": "kto@example.com", "kancelaria": "kowalski"}


class _AtrapaKluczy:
    def get_signing_key_from_jwt(self, token):
        return type("Klucz", (), {"key": "nieistotny"})()


class TestInformacjaOPrzechowywaniu:
    """Stopka mowi notariuszowi, gdzie leza skany i projekty.

    W chmurze nie wolno twierdzic, ze dane zostaja na jego komputerze.
    """

    def _strona(self, monkeypatch, tryb, bucket="notarai-sprawy"):
        monkeypatch.setenv("PIECZAPP_MAGAZYN", tryb)
        monkeypatch.setenv("PIECZAPP_S3_BUCKET", bucket)
        import magazyn
        import app as aplikacja
        importlib.reload(magazyn)
        importlib.reload(aplikacja)
        return aplikacja.strona_glowna()

    def test_w_chmurze_nie_obiecujemy_dysku_lokalnego(self, monkeypatch):
        strona = self._strona(monkeypatch, "s3")
        assert "zostaja na tym komputerze" not in strona
        assert "w chmurze AWS" in strona
        assert "eu-central-1" in strona

    def test_na_stanowisku_dane_zostaja_lokalnie(self, monkeypatch):
        strona = self._strona(monkeypatch, "lokalny")
        assert "zostaja na tym komputerze" in strona
        assert "w chmurze AWS" not in strona

    def test_zadne_wydanie_nie_zostawia_tekstu_zastepczego(self, monkeypatch):
        for tryb in ("lokalny", "s3"):
            assert "Sprawdzam, gdzie zapisywane" not in self._strona(monkeypatch, tryb)


class TestApiLogowania:
    def _apka(self, monkeypatch, tmp_path, atrapa):
        monkeypatch.setenv("PIECZAPP_MULTI", "true")
        monkeypatch.setenv("PIECZAPP_ADMIN_TOKEN", "sekret-admina")
        monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
        import config
        import magazyn
        import autoryzacja
        importlib.reload(magazyn)
        importlib.reload(autoryzacja)
        monkeypatch.setattr(config, "DANE", tmp_path)
        monkeypatch.setattr(autoryzacja.logowanie, "_klient", lambda: atrapa)

        app = FastAPI()
        app.middleware("http")(autoryzacja.middleware)
        app.include_router(autoryzacja.router)
        app.include_router(autoryzacja.router_logowania)
        return TestClient(app), autoryzacja

    def test_logowanie_dziala_bez_tokenu_kancelarii(self, logowanie_atrapa, monkeypatch, tmp_path):
        """Ekran logowania musi byc dostepny dla niezalogowanych."""
        _, atrapa = logowanie_atrapa
        klient, _ = self._apka(monkeypatch, tmp_path, atrapa)
        odp = klient.post("/api/logowanie", json={"email": "Kto@Example.PL", "haslo": "Haslo123456"})
        assert odp.status_code == 200 and odp.json()["token"] == "token.z.cognito"

    def test_zle_dane_daja_401(self, logowanie_atrapa, monkeypatch, tmp_path):
        _, atrapa = logowanie_atrapa
        klient, _ = self._apka(monkeypatch, tmp_path, atrapa)
        atrapa.blad = _wyjatek("NotAuthorizedException")
        assert klient.post("/api/logowanie", json={"email": "k@x.pl", "haslo": "zle"}).status_code == 401

    def test_prosba_o_kod_zawsze_potwierdzona(self, logowanie_atrapa, monkeypatch, tmp_path):
        _, atrapa = logowanie_atrapa
        klient, _ = self._apka(monkeypatch, tmp_path, atrapa)
        atrapa.blad = _wyjatek("UserNotFoundException")
        odp = klient.post("/api/logowanie/kod", json={"email": "nieznany@example.com"})
        assert odp.status_code == 200 and odp.json() == {"wyslano": True}

    def test_konto_zaklada_tylko_admin_i_tylko_w_istniejacej_kancelarii(
            self, logowanie_atrapa, monkeypatch, tmp_path):
        _, atrapa = logowanie_atrapa
        klient, _ = self._apka(monkeypatch, tmp_path, atrapa)
        naglowki = {"Authorization": "Bearer sekret-admina"}

        # bez tokenu administratora panel odmawia
        assert klient.post("/api/admin/uzytkownicy",
                           json={"email": "k@x.pl", "kancelaria": "x"}).status_code == 401

        dane = klient.post("/api/admin/kancelarie", json={"nazwa": "Kancelaria Testowa"},
                           headers=naglowki).json()
        assert klient.post("/api/admin/uzytkownicy", headers=naglowki,
                           json={"email": "k@x.pl", "kancelaria": "nie-ma"}).status_code == 404
        odp = klient.post("/api/admin/uzytkownicy", headers=naglowki,
                          json={"email": "Nowy@Example.PL", "kancelaria": dane["id"]})
        assert odp.status_code == 201
        assert atrapa.utworzeni == ["nowy@example.pl"], "adres zapisujemy malymi literami"
