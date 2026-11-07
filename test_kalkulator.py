"""Kalkulator taksy dla klientow - API na atrapie modelu, limity, CORS, logi."""
import json
import logging
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app as aplikacja
import autoryzacja
import bedrock
import kalkulator
import taksa

ODPOWIEDZ_MODELU = json.dumps({
    "odpowiedz": "Przyjąłem zakup mieszkania za 450 tys. zł bez kredytu i 6 wypisów.",
    "kalkulacja": {"czynnosci": [{"rodzaj": "sprzedaz_lokalu", "wartosc": 450000, "opis": "zakup mieszkania"}]},
}, ensure_ascii=False)


@pytest.fixture
def klient():
    kalkulator.limit_rozmowy.wyczysc()
    kalkulator.limit_formularza.wyczysc()
    return TestClient(aplikacja.app)


class TestInformacjeIFormularz:
    def test_katalog(self, klient):
        odp = klient.get("/api/taksa")
        assert odp.status_code == 200
        dane = odp.json()
        assert dane["wlaczony"] is True and dane["wniosek_kw"] == 300.0
        assert any(r["id"] == "sprzedaz_lokalu" for r in dane["rodzaje"])
        assert any(c["id"] == "testament" and c["kwota"] == 200.0 for c in dane["stale"])

    def test_oblicz_z_formularza(self, klient):
        odp = klient.post("/api/taksa/oblicz", json={"czynnosci": [{"rodzaj": "sprzedaz_lokalu", "wartosc": 450000}]})
        assert odp.status_code == 200
        assert odp.json()["sumy"]["pcc"] == 9000.0 and "RAZEM" in odp.json()["tekst"]

    def test_oblicz_odrzuca_za_duzo_danych(self, klient):
        odp = klient.post("/api/taksa/oblicz", json={"czynnosci": [{"rodzaj": "x", "opis": "a" * 30000}]})
        assert odp.status_code == 400

    def test_strona_kalkulatora(self, klient):
        odp = klient.get("/kalkulator")
        assert odp.status_code == 200
        assert "/static/favicon.png" in odp.text and "../favicon.png" not in odp.text
        assert "api/taksa" in odp.text


class TestRozmowa:
    def test_pierwsza_tura_liczy_w_kodzie(self, klient):
        with patch("bedrock.rozmowa_kalkulatora", return_value=ODPOWIEDZ_MODELU) as model:
            odp = klient.post("/api/taksa/rozmowa", json={"wiadomosc": "Kupuję mieszkanie za 450 tys."})
        assert odp.status_code == 200
        dane = odp.json()
        assert dane["odpowiedz"].startswith("Przyjąłem")
        assert dane["kalkulacja"]["sumy"]["pcc"] == 9000.0
        assert dane["parametry"]["czynnosci"][0]["rodzaj"] == "sprzedaz_lokalu"
        system, tury, tresc = model.call_args.args[:3]
        assert tury == [] and tresc == "Kupuję mieszkanie za 450 tys."
        assert "sprzedaz_lokalu" in system and "DZIS JEST" in system and "JEDEN OBIEKT JSON" in system.upper()

    def test_historia_idzie_do_modelu_z_wynikiem_kalkulatora(self, klient):
        historia = [
            {"rola": "asystent", "tresc": "Dzień dobry, w czym pomóc?"},            # powitanie ze strony
            {"rola": "uzytkownik", "tresc": "Kupuję mieszkanie za 450 tys."},
            {"rola": "asystent", "tresc": "Przyjąłem bez kredytu.",
             "parametry": {"czynnosci": [{"rodzaj": "sprzedaz_lokalu", "wartosc": 450000}]}},
        ]
        with patch("bedrock.rozmowa_kalkulatora", return_value='{"odpowiedz": "Jasne.", "kalkulacja": null}') as model:
            odp = klient.post("/api/taksa/rozmowa", json={"wiadomosc": "A z kredytem 400 tys.?", "historia": historia})
        assert odp.status_code == 200 and odp.json()["kalkulacja"] is None
        _, tury, tresc = model.call_args.args[:3]
        assert [t["role"] for t in tury] == ["user", "assistant"]
        assert json.loads(tury[1]["content"][0]["text"])["kalkulacja"]["czynnosci"][0]["wartosc"] == 450000
        assert tresc.startswith("WYNIK KALKULATORA") and "RAZEM: 11" in tresc.replace(" ", " ")
        assert tresc.endswith("KLIENT: A z kredytem 400 tys.?")

    def test_dwie_tury_uzytkownika_pod_rzad_sklejone(self, klient):
        historia = [{"rola": "uzytkownik", "tresc": "a"}, {"rola": "asystent", "tresc": "b"},
                    {"rola": "uzytkownik", "tresc": "c"}]
        with patch("bedrock.rozmowa_kalkulatora", return_value='{"odpowiedz": "d", "kalkulacja": null}') as model:
            klient.post("/api/taksa/rozmowa", json={"wiadomosc": "e", "historia": historia})
        _, tury, tresc = model.call_args.args[:3]
        assert [t["role"] for t in tury] == ["user", "assistant"] and tresc == "c\ne"

    def test_zly_json_modelu_to_sam_tekst(self, klient):
        with patch("bedrock.rozmowa_kalkulatora", return_value="Proszę podać wartość mieszkania."):
            odp = klient.post("/api/taksa/rozmowa", json={"wiadomosc": "mieszkanie"})
        assert odp.status_code == 200
        assert odp.json() == {"odpowiedz": "Proszę podać wartość mieszkania.", "kalkulacja": None, "parametry": None}

    def test_kalkulacja_bez_czynnosci_to_brak_kalkulacji(self, klient):
        with patch("bedrock.rozmowa_kalkulatora", return_value='{"odpowiedz": "x", "kalkulacja": {"grupa1": true}}'):
            odp = klient.post("/api/taksa/rozmowa", json={"wiadomosc": "y"})
        assert odp.json()["kalkulacja"] is None and odp.json()["parametry"] is None

    def test_model_nie_wybiera_daty(self, klient):
        stara = json.dumps({"odpowiedz": "x", "kalkulacja": {"data": "2020-01-01", "stale": [{"id": "testament", "wypisy": 0}]}})
        with patch("bedrock.rozmowa_kalkulatora", return_value=stara):
            odp = klient.post("/api/taksa/rozmowa", json={"wiadomosc": "testament"})
        assert odp.json()["kalkulacja"]["tabela"]["id"] == taksa.tabela()["id"]

    def test_pusta_i_za_dluga_wiadomosc(self, klient):
        assert klient.post("/api/taksa/rozmowa", json={"wiadomosc": "   "}).status_code == 400
        assert klient.post("/api/taksa/rozmowa", json={"wiadomosc": "a" * 1501}).status_code == 400

    def test_pulapka_na_automaty_nie_wola_modelu(self, klient):
        with patch("bedrock.rozmowa_kalkulatora") as model:
            odp = klient.post("/api/taksa/rozmowa", json={"wiadomosc": "spam", "strona": "http://x"})
        assert odp.status_code == 200 and not model.called

    def test_limit_na_adres(self, klient, monkeypatch):
        monkeypatch.setattr(kalkulator, "limit_rozmowy", kalkulator.Limit(2, 100))
        with patch("bedrock.rozmowa_kalkulatora", return_value='{"odpowiedz": "ok", "kalkulacja": null}'):
            for _ in range(2):
                assert klient.post("/api/taksa/rozmowa", json={"wiadomosc": "x"}).status_code == 200
            odp = klient.post("/api/taksa/rozmowa", json={"wiadomosc": "x"})
        assert odp.status_code == 429 and "formularza" in odp.json()["detail"]

    def test_limit_dobowy(self, klient, monkeypatch):
        monkeypatch.setattr(kalkulator, "limit_rozmowy", kalkulator.Limit(100, 1))
        with patch("bedrock.rozmowa_kalkulatora", return_value='{"odpowiedz": "ok", "kalkulacja": null}'):
            assert klient.post("/api/taksa/rozmowa", json={"wiadomosc": "x"}, headers={"x-forwarded-for": "1.1.1.1"}).status_code == 200
            assert klient.post("/api/taksa/rozmowa", json={"wiadomosc": "x"}, headers={"x-forwarded-for": "2.2.2.2"}).status_code == 429

    def test_przeciazenie_modelu(self, klient):
        with patch("bedrock.rozmowa_kalkulatora", side_effect=bedrock.Przeciazenie("limit")):
            odp = klient.post("/api/taksa/rozmowa", json={"wiadomosc": "x"})
        assert odp.status_code == 503 and odp.headers["retry-after"] == "60"

    def test_blad_modelu_bez_tresci_w_logu(self, klient, caplog):
        with patch("bedrock.rozmowa_kalkulatora", side_effect=RuntimeError("PESEL 44051401359 Kowalski")):
            odp = klient.post("/api/taksa/rozmowa", json={"wiadomosc": "Jan Kowalski PESEL 44051401359"})
        assert odp.status_code == 502
        assert "44051401359" not in caplog.text and "Kowalski" not in caplog.text and "Kowalski" not in odp.text

    def test_tresc_rozmowy_nie_trafia_do_logu(self, klient, caplog):
        caplog.set_level(logging.INFO, logger="pieczapp.kalkulator")
        with patch("bedrock.rozmowa_kalkulatora", return_value=ODPOWIEDZ_MODELU):
            klient.post("/api/taksa/rozmowa", json={"wiadomosc": "Nazywam się Zenobiusz Przykładowy"})
        assert "Zenobiusz" not in caplog.text and "kalkulator: tura 1" in caplog.text

    def test_wylaczony(self, klient, monkeypatch):
        monkeypatch.setattr(kalkulator, "WLACZONY", False)
        assert klient.post("/api/taksa/rozmowa", json={"wiadomosc": "x"}).status_code == 503


class TestCors:
    def test_preflight_z_notarai_pl(self, klient):
        odp = klient.options("/api/taksa/rozmowa", headers={"Origin": "https://notarai.pl",
                                                            "Access-Control-Request-Method": "POST"})
        assert odp.status_code == 204
        assert odp.headers["access-control-allow-origin"] == "https://notarai.pl"
        assert "POST" in odp.headers["access-control-allow-methods"]

    def test_odpowiedz_niesie_naglowek(self, klient):
        odp = klient.get("/api/taksa", headers={"Origin": "https://www.notarai.pl"})
        assert odp.headers["access-control-allow-origin"] == "https://www.notarai.pl"
        assert odp.headers["vary"] == "Origin"

    def test_obca_domena_bez_cors(self, klient):
        odp = klient.get("/api/taksa", headers={"Origin": "https://zly.example"})
        assert odp.status_code == 200 and "access-control-allow-origin" not in odp.headers

    def test_inne_sciezki_bez_cors(self, klient):
        odp = klient.get("/zdrowie", headers={"Origin": "https://notarai.pl"})
        assert odp.status_code == 200 and "access-control-allow-origin" not in odp.headers


class TestBezLogowania:
    def test_sciezki_otwarte_w_trybie_wielu_kancelarii(self, monkeypatch):
        monkeypatch.setattr(autoryzacja, "MULTI", True)
        app = FastAPI()
        app.middleware("http")(autoryzacja.middleware)
        app.include_router(kalkulator.router)

        @app.get("/api/sprawy")
        def sprawy():
            return []

        klient = TestClient(app)
        assert klient.get("/api/taksa").status_code == 200
        assert klient.post("/api/taksa/oblicz", json={}).status_code == 200
        assert klient.get("/api/sprawy").status_code == 401


PROZA_PRZED_JSON = """

Muszę ustalić kilka rzeczy. Nie powinienem powtarzać danych osobowych.

```json
{
  "odpowiedz": "Rozumiem, sprzedaż domu córce za 800 000 zł.",
  "kalkulacja": {"czynnosci": [{"rodzaj": "sprzedaz_domu", "wartosc": 800000}], "grupa1": true,
                 "oplaty_sadowe": {"wpis_wlasnosci": 1, "wpis_hipoteki": 0}}
}
```"""


class TestOdczytOdpowiedzi:
    def test_proza_przed_json_i_slownik_oplat(self):
        """Tak odpowiedzial Opus 4.6 na zywo (07.11.2026) - musi sie dac odczytac."""
        tekst, parametry = kalkulator._odczytaj(PROZA_PRZED_JSON)
        assert tekst.startswith("Rozumiem") and parametry["grupa1"] is True
        wynik = taksa.oblicz(parametry)
        sad = [p["etykieta"] for p in wynik["pozycje"] if p["rodzaj"] == "sad"]
        assert sad == ["opłata sądowa: wpis prawa własności (użytkowania wieczystego, spółdzielczego prawa)"]

    def test_czysty_json(self):
        tekst, parametry = kalkulator._odczytaj('{"odpowiedz": "ok", "kalkulacja": null}')
        assert tekst == "ok" and parametry is None


class TestModelKalkulatora:
    def test_domyslnie_sonnet_w_ue(self):
        assert kalkulator._model_z_env(None) == "eu.anthropic.claude-sonnet-4-6"

    def test_pusto_znaczy_model_aplikacji(self):
        assert kalkulator._model_z_env("") == "" and kalkulator._model_z_env("  ") == ""

    def test_profil_spoza_ue_odrzucony(self):
        with pytest.raises(RuntimeError, match="profilem EU"):
            kalkulator._model_z_env("global.anthropic.claude-sonnet-4-6")
        with pytest.raises(RuntimeError):
            kalkulator._model_z_env("us.anthropic.claude-sonnet-4-6")

    def test_rozmowa_idzie_na_model_kalkulatora(self, klient, monkeypatch):
        monkeypatch.setattr(kalkulator, "MODEL", "eu.anthropic.claude-haiku-4-5-20251001-v1:0")
        with patch("bedrock.rozmowa_kalkulatora", return_value='{"odpowiedz": "ok", "kalkulacja": null}') as model:
            klient.post("/api/taksa/rozmowa", json={"wiadomosc": "x"})
        assert model.call_args.args[3] == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"


class TestBedrock:
    def test_rozmowa_kalkulatora_bez_myslenia_na_osobnym_modelu(self):
        with patch("bedrock._rozmowa", return_value="{}") as r:
            bedrock.rozmowa_kalkulatora("SYSTEM", [{"role": "user", "content": [{"text": "a"}]},
                                                   {"role": "assistant", "content": [{"text": "b"}]}], "c",
                                        "eu.anthropic.claude-sonnet-4-6")
        assert r.call_args.args[0] == "SYSTEM" and r.call_args.args[1] == [{"text": "c"}]
        assert r.call_args.kwargs["myslenie"] is False and len(r.call_args.kwargs["historia"]) == 2
        assert r.call_args.kwargs["max_tokenow"] == bedrock.MAX_TOKENOW_KALKULATORA
        assert r.call_args.kwargs["model"] == "eu.anthropic.claude-sonnet-4-6"

    def test_model_w_zadaniu_bedrock(self):
        class Strumien:
            def __init__(self):
                self.zadanie = None

            def converse_stream(self, **zadanie):
                self.zadanie = zadanie
                return {"stream": [{"contentBlockDelta": {"delta": {"text": '{"odpowiedz": "x"}'}}},
                                   {"messageStop": {"stopReason": "end_turn"}}]}

        klient = Strumien()
        with patch("bedrock._klient", return_value=klient):
            wynik = bedrock._rozmowa("S", [{"text": "u"}], max_tokenow=10, myslenie=False,
                                     model="eu.anthropic.claude-sonnet-4-6")
        assert wynik == '{"odpowiedz": "x"}'
        assert klient.zadanie["modelId"] == "eu.anthropic.claude-sonnet-4-6"
        assert klient.zadanie["messages"][-1]["role"] == "user"
        assert "thinking" not in klient.zadanie.get("additionalModelRequestFields", {})
        assert klient.zadanie["inferenceConfig"] == {"maxTokens": 10, "temperature": 0}

    def test_domyslny_model_bez_parametru(self):
        class Strumien:
            def __init__(self):
                self.zadanie = None

            def converse_stream(self, **zadanie):
                self.zadanie = zadanie
                return {"stream": [{"contentBlockDelta": {"delta": {"text": "ok"}}}]}

        klient = Strumien()
        with patch("bedrock._klient", return_value=klient):
            assert bedrock._rozmowa("S", [{"text": "u"}], max_tokenow=10, myslenie=True) == "ok"
        import config
        assert klient.zadanie["modelId"] == config.MODEL
