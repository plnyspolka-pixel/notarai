"""Wejscie kontem Google (pasek One Tap i przycisk): token Google, konto bez
hasla, nowa kancelaria bez zawartej umowy. Cognito i klucze Google zastapione
atrapami, bez sieci. Dane fikcyjne."""
import importlib
import re
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_logowanie import _przywroc_moduly, _wyjatek, logowanie_atrapa  # noqa: F401
from test_zespol import ADMIN, AtrapaZespolu, jako

KLIENT_GOOGLE = "123-test.apps.googleusercontent.com"
KLUCZ = "klucz-wspolny-do-testow"
_RSA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OBCY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token_google(email="anna.sobczak@gmail.com", klucz=_RSA, **zmiany):
    teraz = int(time.time())
    dane = {"iss": "https://accounts.google.com", "aud": KLIENT_GOOGLE, "sub": "1001",
            "email": email, "email_verified": True, "name": "Anna Sobczak",
            "iat": teraz, "exp": teraz + 3600, "jti": f"jti-{time.monotonic_ns()}"}
    dane.update(zmiany)
    return jwt.encode({k: v for k, v in dane.items() if v is not None}, klucz, algorithm="RS256")


class AtrapaGoogle(AtrapaZespolu):
    """Cognito z kontami bez hasla i wlasnym wyzwaniem."""

    def __init__(self):
        super().__init__()
        self.konta = {}          # email -> {"kancelaria", "stan", "aktywne"}
        self.hasla_losowe = []
        self.dowody = []

    def admin_create_user(self, **kw):
        super().admin_create_user(**kw)
        if kw.get("MessageAction") == "RESEND":
            return
        atrybuty = {a["Name"]: a["Value"] for a in kw["UserAttributes"]}
        self.konta[kw["Username"]] = {"kancelaria": atrybuty["custom:kancelaria"],
                                      "stan": "FORCE_CHANGE_PASSWORD", "aktywne": True,
                                      "bez_maila": kw.get("MessageAction") == "SUPPRESS"}

    def admin_get_user(self, **kw):
        konto = self.konta.get(kw["Username"])
        if konto is None:
            raise _wyjatek("UserNotFoundException")
        return {"UserStatus": konto["stan"], "Enabled": konto["aktywne"],
                "UserAttributes": [{"Name": "custom:kancelaria", "Value": konto["kancelaria"]}]}

    def admin_set_user_password(self, **kw):
        assert kw["Permanent"] is True and len(kw["Password"]) > 30
        self.hasla_losowe.append(kw["Username"])
        self.konta[kw["Username"]]["stan"] = "CONFIRMED"

    def initiate_auth(self, **kw):
        if kw["AuthFlow"] != "CUSTOM_AUTH":
            return super().initiate_auth(**kw)
        email = kw["AuthParameters"]["USERNAME"]
        assert self.konta[email]["stan"] == "CONFIRMED", "wyzwanie tylko dla konta z haslem stalym"
        return {"ChallengeName": "CUSTOM_CHALLENGE", "Session": f"sesja|{email}",
                "ChallengeParameters": {"USERNAME": email}}

    def respond_to_auth_challenge(self, **kw):
        if kw["ChallengeName"] != "CUSTOM_CHALLENGE":
            return super().respond_to_auth_challenge(**kw)
        email = kw["Session"].split("|")[1]
        self.dowody.append((email, kw["ChallengeResponses"]["ANSWER"]))
        return {"AuthenticationResult": {
            "IdToken": f"jwt|{email}|{self.konta[email]['kancelaria']}",
            "ExpiresIn": 28800, "RefreshToken": "odnowienie-google"}}


@pytest.fixture
def srodowisko(logowanie_atrapa, monkeypatch, tmp_path):
    atrapa = AtrapaGoogle()
    monkeypatch.setenv("PIECZAPP_MULTI", "true")
    monkeypatch.setenv("PIECZAPP_ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    import config
    import magazyn
    import autoryzacja
    import rejestracja
    importlib.reload(magazyn)
    importlib.reload(autoryzacja)
    logowanie = autoryzacja.logowanie
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(logowanie, "_klient", lambda: atrapa)
    monkeypatch.setattr(logowanie, "GOOGLE_KLIENT", KLIENT_GOOGLE)
    monkeypatch.setattr(logowanie, "_GOOGLE_KLUCZ", KLUCZ)
    monkeypatch.setattr(logowanie, "_zuzyte_google", {})

    class Klucze:
        def get_signing_key_from_jwt(self, token):
            return type("K", (), {"key": _RSA.public_key()})()

    monkeypatch.setattr(logowanie, "_weryfikator_google", lambda: Klucze())
    monkeypatch.setattr(logowanie, "dane_z_tokenu",
                        lambda t: {"email": t.split("|")[1], "kancelaria": t.split("|")[2]})
    monkeypatch.setattr(logowanie, "czy_jwt", lambda t: t.startswith("jwt|") or t.count(".") == 2)
    monkeypatch.setattr(rejestracja, "WLACZONA", True)
    rejestracja._wyczysc_limity()

    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    app.include_router(autoryzacja.router)
    app.include_router(autoryzacja.router_zespolu)
    app.include_router(rejestracja.router)
    app.include_router(rejestracja.router_google)
    app.include_router(rejestracja.router_dokumentow)

    @app.get("/api/sprawy")
    def sprawy():
        return []

    return TestClient(app), atrapa, logowanie


def _wejdz(klient, **zmiany):
    return klient.post("/api/logowanie/google", json={"credential": token_google(**zmiany)})


class TestTokenGoogle:
    def test_poprawny_token(self, srodowisko):
        _, _, logowanie = srodowisko
        dane = logowanie.dane_z_google(token_google(email="Anna.Sobczak@Gmail.com"))
        assert dane == {"email": "anna.sobczak@gmail.com", "nazwa": "Anna Sobczak", "pewny": True}

    def test_obca_domena_bez_workspace_nie_jest_pewna(self, srodowisko):
        _, _, logowanie = srodowisko
        assert logowanie.dane_z_google(token_google(email="anna@kancelaria.test"))["pewny"] is False
        assert logowanie.dane_z_google(token_google(email="anna@kancelaria.test",
                                                    hd="kancelaria.test"))["pewny"] is True

    @pytest.mark.parametrize("zmiany", [
        {"aud": "inny-klient.apps.googleusercontent.com"},
        {"iss": "https://accounts.example.com"},
        {"email_verified": False},
        {"email": None},
        {"iat": int(time.time()) - 3600, "exp": int(time.time()) + 600},
        {"exp": int(time.time()) - 600, "iat": int(time.time()) - 700},
        {"klucz": _OBCY},
    ])
    def test_odrzucone(self, srodowisko, zmiany):
        _, _, logowanie = srodowisko
        with pytest.raises(logowanie.BladLogowania):
            logowanie.dane_z_google(token_google(**zmiany))

    def test_ten_sam_token_tylko_raz(self, srodowisko):
        _, _, logowanie = srodowisko
        token = token_google()
        logowanie.dane_z_google(token)
        with pytest.raises(logowanie.BladLogowania):
            logowanie.dane_z_google(token)

    def test_smieci_zamiast_tokenu(self, srodowisko):
        _, _, logowanie = srodowisko
        with pytest.raises(logowanie.BladLogowania):
            logowanie.dane_z_google("to-nie-token")


class TestDowod:
    """Aplikacja i funkcja Lambda z szablonu musza liczyc dowod tak samo."""

    def _lambda(self):
        szablon = Path(__file__).parent.joinpath("infra", "notarai-logowanie.yaml").read_text("utf-8")
        kod = szablon.split("ZipFile: |\n", 1)[1].split("\n  PozwolenieCognito:", 1)[0]
        przestrzen = {}
        exec("\n".join(w[10:] for w in kod.splitlines()), przestrzen)  # noqa: S102
        return przestrzen

    def test_lambda_przyjmuje_dowod_aplikacji(self, srodowisko):
        _, _, logowanie = srodowisko
        funkcja = self._lambda()
        dowod = logowanie.dowod_logowania("Anna@Gmail.com")
        assert funkcja["dowod_poprawny"]("anna@gmail.com", dowod, KLUCZ) is True
        assert funkcja["dowod_poprawny"]("ktos.inny@gmail.com", dowod, KLUCZ) is False
        assert funkcja["dowod_poprawny"]("anna@gmail.com", dowod, "inny-klucz") is False
        assert funkcja["dowod_poprawny"]("anna@gmail.com", "", KLUCZ) is False

    def test_dowod_wygasa(self, srodowisko):
        _, _, logowanie = srodowisko
        funkcja = self._lambda()
        stary = logowanie.dowod_logowania("anna@gmail.com", teraz=time.time() - 600)
        assert funkcja["dowod_poprawny"]("anna@gmail.com", stary, KLUCZ) is False

    def test_przebieg_wyzwania(self, srodowisko, monkeypatch):
        _, _, logowanie = srodowisko
        funkcja = self._lambda()
        monkeypatch.setitem(funkcja, "klucz", lambda: KLUCZ)

        def wywolaj(zrodlo, **zadanie):
            return funkcja["handler"]({"triggerSource": zrodlo, "request": zadanie, "response": {}},
                                      None)["response"]

        assert wywolaj("DefineAuthChallenge_Authentication", session=[])["challengeName"] == "CUSTOM_CHALLENGE"
        assert wywolaj("DefineAuthChallenge_Authentication", session=[], userNotFound=True)["failAuthentication"]
        dobra = [{"challengeName": "CUSTOM_CHALLENGE", "challengeResult": True}]
        zla = [{"challengeName": "CUSTOM_CHALLENGE", "challengeResult": False}]
        assert wywolaj("DefineAuthChallenge_Authentication", session=dobra)["issueTokens"] is True
        assert wywolaj("DefineAuthChallenge_Authentication", session=zla)["failAuthentication"] is True
        # Haslo (SRP) przed wyzwaniem nie daje tokenow ta droga.
        srp = [{"challengeName": "SRP_A", "challengeResult": True}]
        assert wywolaj("DefineAuthChallenge_Authentication", session=srp)["issueTokens"] is False
        assert wywolaj("VerifyAuthChallengeResponse_Authentication",
                       userAttributes={"email": "anna@gmail.com"},
                       challengeAnswer=logowanie.dowod_logowania("anna@gmail.com"))["answerCorrect"] is True
        assert wywolaj("VerifyAuthChallengeResponse_Authentication",
                       userAttributes={"email": "anna@gmail.com"},
                       challengeAnswer="1.zly")["answerCorrect"] is False


class TestWejscie:
    def test_nowy_adres_zaklada_kancelarie_bez_umowy(self, srodowisko):
        klient, atrapa, _ = srodowisko
        odp = _wejdz(klient)
        assert odp.status_code == 200, odp.text
        wynik = odp.json()
        assert wynik["nowe_konto"] is True and wynik["token"].startswith("jwt|anna.sobczak@gmail.com|")
        assert "odnowienie" not in wynik, "token odnawiania tylko w ciasteczku"
        assert "notarai_odnowienie=odnowienie-google" in odp.headers["set-cookie"]
        konto = atrapa.konta["anna.sobczak@gmail.com"]
        assert konto["bez_maila"] is True and konto["stan"] == "CONFIRMED"

        kancelarie = klient.get("/api/admin/kancelarie", headers=ADMIN).json()
        assert [k["nazwa"] for k in kancelarie] == ["Kancelaria Anna Sobczak"]
        id_k = kancelarie[0]["id"]
        ja = jako("anna.sobczak@gmail.com", id_k)
        # Sprawy zamkniete, dopoki wlasciciel nie poda danych i nie zaakceptuje umowy.
        assert klient.get("/api/sprawy", headers=ja).status_code == 428
        stan = klient.get("/api/dokumenty", headers=ja).json()
        assert stan["jestem_wlascicielem"] is True and stan["umowa_zawarta"] is False
        assert klient.post("/api/dokumenty/umowa", headers=ja, json={
            "akceptuje": True, "notariusze": "Anna Sobczak",
            "adres": "ul. Fikcyjna 1, 20-001 Lublin"}).status_code == 200
        assert klient.get("/api/sprawy", headers=ja).status_code == 200

    def test_drugie_wejscie_loguje_to_samo_konto(self, srodowisko):
        klient, atrapa, _ = srodowisko
        pierwszy = _wejdz(klient).json()
        drugi = _wejdz(klient).json()
        assert drugi["nowe_konto"] is False and drugi["token"] == pierwszy["token"]
        assert len(klient.get("/api/admin/kancelarie", headers=ADMIN).json()) == 1
        assert atrapa.hasla_losowe == ["anna.sobczak@gmail.com"], "haslo losowe tylko przy zakladaniu"

    def test_zaproszona_osoba_wchodzi_bez_hasla_tymczasowego(self, srodowisko):
        klient, atrapa, _ = srodowisko
        klient.post("/api/admin/kancelarie", headers=ADMIN,
                    json={"nazwa": "Kancelaria Pawlak", "email": "pawlak@gmail.com"})
        assert atrapa.konta["pawlak@gmail.com"]["stan"] == "FORCE_CHANGE_PASSWORD"
        odp = _wejdz(klient, email="pawlak@gmail.com")
        assert odp.status_code == 200 and odp.json()["nowe_konto"] is False
        assert odp.json()["token"] == "jwt|pawlak@gmail.com|kancelaria-pawlak"
        assert len(klient.get("/api/admin/kancelarie", headers=ADMIN).json()) == 1

    def test_istniejace_konto_tylko_gdy_google_jest_dostawca_skrzynki(self, srodowisko):
        klient, atrapa, _ = srodowisko
        klient.post("/api/admin/kancelarie", headers=ADMIN,
                    json={"nazwa": "Kancelaria Pawlak", "email": "biuro@kancelaria-pawlak.test"})
        odp = _wejdz(klient, email="biuro@kancelaria-pawlak.test")
        assert odp.status_code == 403 and "hasłem" in odp.json()["detail"]
        assert atrapa.dowody == []
        assert _wejdz(klient, email="biuro@kancelaria-pawlak.test",
                      hd="kancelaria-pawlak.test").status_code == 200

    def test_administrator_panelu_nie_wchodzi_jednym_kliknieciem(self, srodowisko):
        klient, atrapa, _ = srodowisko
        atrapa.konta["szef@gmail.com"] = {"kancelaria": "_administracja", "stan": "CONFIRMED",
                                          "aktywne": True}
        assert _wejdz(klient, email="szef@gmail.com").status_code == 403
        assert atrapa.dowody == []

    def test_wylaczone_konto(self, srodowisko):
        klient, atrapa, _ = srodowisko
        atrapa.konta["anna.sobczak@gmail.com"] = {"kancelaria": "k", "stan": "CONFIRMED",
                                                  "aktywne": False}
        assert _wejdz(klient).status_code == 403

    def test_zly_token(self, srodowisko):
        klient, atrapa, _ = srodowisko
        assert _wejdz(klient, klucz=_OBCY).status_code == 401
        assert klient.post("/api/logowanie/google", json={"credential": "x"}).status_code == 401
        assert atrapa.konta == {}

    def test_rejestracja_wylaczona_loguje_ale_nie_zaklada(self, srodowisko, monkeypatch):
        klient, atrapa, _ = srodowisko
        import rejestracja
        monkeypatch.setattr(rejestracja, "WLACZONA", False)
        assert _wejdz(klient).status_code == 403
        assert atrapa.konta == {}

    def test_limit_nowych_kancelarii_na_adres_ip(self, srodowisko):
        klient, _, _ = srodowisko
        kody = [_wejdz(klient, email=f"osoba{i}@gmail.com").status_code for i in range(4)]
        assert kody == [200, 200, 200, 429]

    def test_bez_konfiguracji_wylaczone(self, srodowisko, monkeypatch):
        klient, _, logowanie = srodowisko
        monkeypatch.setattr(logowanie, "_GOOGLE_KLUCZ", "")
        assert klient.get("/api/logowanie/google").json() == {"wlaczone": False, "klient": ""}
        assert _wejdz(klient).status_code == 503

    def test_informacje_dla_ekranu_logowania(self, srodowisko):
        klient, _, _ = srodowisko
        assert klient.get("/api/logowanie/google").json() == {"wlaczone": True, "klient": KLIENT_GOOGLE}

    def test_strona_notarai_moze_odczytac_identyfikator(self, srodowisko):
        klient, _, _ = srodowisko
        odp = klient.get("/api/logowanie/google", headers={"Origin": "https://notarai.pl"})
        assert odp.headers["access-control-allow-origin"] == "https://notarai.pl"
        obca = klient.get("/api/logowanie/google", headers={"Origin": "https://zla-strona.test"})
        assert "access-control-allow-origin" not in obca.headers

    def test_obca_strona_nie_wysle_tokenu(self, srodowisko):
        klient, atrapa, _ = srodowisko
        odp = klient.post("/api/logowanie/google", json={"credential": token_google()},
                          headers={"Origin": "https://zla-strona.test"})
        assert odp.status_code == 403 and atrapa.konta == {}


class TestPowrotZeStrony:
    """Pasek na notarai.pl przysyla token formularzem na adres aplikacji."""

    def _wyslij(self, klient, zrodlo="https://notarai.pl", **zmiany):
        naglowki = {"Origin": zrodlo} if zrodlo else {}
        return klient.post("/api/logowanie/google/powrot", data={"credential": token_google(**zmiany)},
                           headers=naglowki, follow_redirects=False)

    def test_loguje_i_przenosi_do_aplikacji(self, srodowisko):
        klient, atrapa, _ = srodowisko
        odp = self._wyslij(klient)
        assert odp.status_code == 303 and odp.headers["location"] == "/"
        ciastko = odp.headers["set-cookie"]
        assert "notarai_odnowienie=odnowienie-google" in ciastko and "HttpOnly" in ciastko
        assert re.search(r"samesite=strict", ciastko, re.I)
        assert "anna.sobczak@gmail.com" in atrapa.konta

    def test_blad_wraca_kodem_bez_szczegolow(self, srodowisko):
        klient, _, _ = srodowisko
        odp = self._wyslij(klient, klucz=_OBCY)
        assert odp.status_code == 303 and odp.headers["location"] == "/?google=401"
        assert "set-cookie" not in odp.headers

    @pytest.mark.parametrize("zrodlo", ["https://zla-strona.test", ""])
    def test_tylko_ze_strony_notarai(self, srodowisko, zrodlo):
        klient, atrapa, _ = srodowisko
        assert self._wyslij(klient, zrodlo=zrodlo).status_code == 403
        assert atrapa.konta == {}
