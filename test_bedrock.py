"""Testy przepływu z atrapa Bedrock.

NIE wywolujemy prawdziwego modelu w testach.
Mockujemy boto3.client i symulujemy odpowiedzi.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
import bedrock


def _jako_strumien(odpowiedz: dict) -> dict:
    """Odpowiedz w ksztalcie `converse` zamieniona na zdarzenia `converse_stream`."""
    zdarzenia = [{"contentBlockDelta": {"delta": {"text": c.get("text", "")}}}
                 for c in odpowiedz["output"]["message"]["content"]]
    zdarzenia.append({"messageStop": {"stopReason": odpowiedz.get("stopReason", "end_turn")}})
    zdarzenia.append({"metadata": {"usage": odpowiedz.get("usage", {})}})
    return {"stream": iter(zdarzenia)}


@pytest.fixture
def mock_bedrock_client():
    """Atrapa klienta Bedrock.

    Testy ustawiaja `converse.return_value` jak dla zwyklego wywolania;
    `converse_stream`, ktorego uzywa aplikacja, przekazuje do niego argumenty
    i zwraca te sama odpowiedz jako strumien. Dzieki temu asercje na
    `converse.call_args` dalej widza parametry wywolania.
    """
    with patch("bedrock._klient") as mock:
        klient = MagicMock()
        klient.converse_stream.side_effect = lambda **kw: _jako_strumien(klient.converse(**kw))
        mock.return_value = klient
        yield klient


class TestOdczytajDane:
    """Testy przeplywu ekstrakcji danych ze skanow."""

    def test_odczyt_podstawowy(self, mock_bedrock_client):
        # Przygotuj odpowiedz modelu
        odpowiedz_json = {
            "pola": [
                {
                    "nazwa": "imie",
                    "wartosc": "Jan",
                    "zrodlo": "test.pdf, str. 1",
                    "pewnosc": "wysoka",
                    "uwaga": ""
                },
                {
                    "nazwa": "nazwisko",
                    "wartosc": "Kowalski",
                    "zrodlo": "test.pdf, str. 1",
                    "pewnosc": "wysoka",
                    "uwaga": ""
                }
            ],
            "braki": [],
            "rozbieznosci": []
        }

        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": json.dumps(odpowiedz_json, ensure_ascii=False)}]
                }
            },
            "usage": {"inputTokens": 100, "outputTokens": 50}
        }

        # Przygotuj dane wejsciowe
        strony = [
            {
                "dokument": "test.pdf",
                "strona": 1,
                "png": b"fake-png-data"
            }
        ]
        pola = ["imie", "nazwisko"]
        opis = "Umowa sprzedazy"

        # Wywolaj funkcje
        wynik = bedrock.odczytaj_dane(strony, pola, opis)

        # Sprawdz wynik
        assert "pola" in wynik
        assert len(wynik["pola"]) == 2
        assert wynik["pola"][0]["nazwa"] == "imie"
        assert wynik["pola"][0]["wartosc"] == "Jan"
        assert wynik["pola"][1]["nazwa"] == "nazwisko"
        assert wynik["pola"][1]["wartosc"] == "Kowalski"

        # Sprawdz czy converse zostalo wywolane
        mock_bedrock_client.converse.assert_called_once()
        call_args = mock_bedrock_client.converse.call_args
        assert "modelId" in call_args.kwargs
        assert "messages" in call_args.kwargs

    def test_odczyt_z_brakami(self, mock_bedrock_client):
        odpowiedz_json = {
            "pola": [
                {
                    "nazwa": "pesel",
                    "wartosc": None,
                    "zrodlo": "",
                    "pewnosc": "niska",
                    "uwaga": "Nie znaleziono numeru PESEL"
                }
            ],
            "braki": ["numer PESEL"],
            "rozbieznosci": []
        }

        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": json.dumps(odpowiedz_json)}]
                }
            },
            "usage": {"inputTokens": 100, "outputTokens": 30}
        }

        strony = [{"dokument": "test.pdf", "strona": 1, "png": b"data"}]
        wynik = bedrock.odczytaj_dane(strony, ["pesel"], "")

        assert len(wynik["braki"]) == 1
        assert "numer PESEL" in wynik["braki"]
        assert wynik["pola"][0]["wartosc"] is None

    def test_odczyt_z_rozbieznosciami(self, mock_bedrock_client):
        odpowiedz_json = {
            "pola": [
                {
                    "nazwa": "cena",
                    "wartosc": "500000",
                    "zrodlo": "umowa.pdf, str. 2",
                    "pewnosc": "niska",
                    "uwaga": "W umowie 500000, w akcie 550000"
                }
            ],
            "braki": [],
            "rozbieznosci": ["Rozna cena w dokumentach"]
        }

        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": json.dumps(odpowiedz_json)}]
                }
            },
            "usage": {"inputTokens": 200, "outputTokens": 80}
        }

        strony = [{"dokument": "test.pdf", "strona": 1, "png": b"data"}]
        wynik = bedrock.odczytaj_dane(strony, ["cena"], "")

        assert len(wynik["rozbieznosci"]) == 1
        assert wynik["pola"][0]["pewnosc"] == "niska"

    def test_odczyt_json_z_markdown(self, mock_bedrock_client):
        # Model czasami zwraca JSON w znacznikach markdown
        odpowiedz_json = {
            "pola": [{"nazwa": "test", "wartosc": "wartosc", "zrodlo": "src", "pewnosc": "wysoka", "uwaga": ""}],
            "braki": [],
            "rozbieznosci": []
        }
        tekst_z_markdown = f"```json\n{json.dumps(odpowiedz_json)}\n```"

        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": tekst_z_markdown}]
                }
            },
            "usage": {"inputTokens": 100, "outputTokens": 50}
        }

        strony = [{"dokument": "test.pdf", "strona": 1, "png": b"data"}]
        wynik = bedrock.odczytaj_dane(strony, ["test"], "")

        assert wynik["pola"][0]["nazwa"] == "test"

    def test_odczyt_wiele_stron(self, mock_bedrock_client):
        odpowiedz_json = {
            "pola": [
                {"nazwa": "pole1", "wartosc": "wartosc1", "zrodlo": "dok1.pdf, str. 1", "pewnosc": "wysoka", "uwaga": ""},
                {"nazwa": "pole2", "wartosc": "wartosc2", "zrodlo": "dok2.pdf, str. 1", "pewnosc": "wysoka", "uwaga": ""}
            ],
            "braki": [],
            "rozbieznosci": []
        }

        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": json.dumps(odpowiedz_json)}]
                }
            },
            "usage": {"inputTokens": 300, "outputTokens": 100}
        }

        strony = [
            {"dokument": "dok1.pdf", "strona": 1, "png": b"data1"},
            {"dokument": "dok2.pdf", "strona": 1, "png": b"data2"},
            {"dokument": "dok2.pdf", "strona": 2, "png": b"data3"}
        ]
        wynik = bedrock.odczytaj_dane(strony, ["pole1", "pole2"], "Opis")

        # Sprawdz czy wszystkie strony zostaly przekazane
        call_args = mock_bedrock_client.converse.call_args
        messages = call_args.kwargs["messages"]
        content = messages[0]["content"]
        # content powinien zawierac wpisy dla kazdej strony


class TestSporzadzProjekt:
    """Testy przeplywu generowania projektu dokumentu."""

    def test_generowanie_podstawowe(self, mock_bedrock_client):
        projekt_tekst = """AKT NOTARIALNY

Dnia 2026-07-24 przed notariuszem Anną Kowalską stawil sie Jan Nowak, PESEL 85031512337.

Strony uzgodnily cene w kwocie 500000.00 zl."""

        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": projekt_tekst}]
                }
            },
            "usage": {"inputTokens": 500, "outputTokens": 200}
        }

        wzor = "Dnia {{data}} przed notariuszem {{notariusz}} stawil sie {{imie}} {{nazwisko}}, PESEL {{pesel}}."
        dane = [
            {"nazwa": "data", "wartosc": "2026-07-24"},
            {"nazwa": "notariusz", "wartosc": "Anna Kowalska"},
            {"nazwa": "imie", "wartosc": "Jan"},
            {"nazwa": "nazwisko", "wartosc": "Nowak"},
            {"nazwa": "pesel", "wartosc": "85031512337"}
        ]
        opis = "Przygotuj akt sprzedazy"

        wynik = bedrock.sporzadz_projekt(wzor, dane, opis)

        assert "AKT NOTARIALNY" in wynik
        assert "Jan Nowak" in wynik
        assert "85031512337" in wynik
        mock_bedrock_client.converse.assert_called_once()

    def test_generowanie_z_brakami(self, mock_bedrock_client):
        projekt_tekst = """Dnia 2026-07-24 stawil sie <<BRAK: imie>> <<BRAK: nazwisko>>."""

        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": projekt_tekst}]
                }
            },
            "usage": {"inputTokens": 200, "outputTokens": 50}
        }

        wzor = "Dnia {{data}} stawil sie {{imie}} {{nazwisko}}."
        dane = [
            {"nazwa": "data", "wartosc": "2026-07-24"},
            {"nazwa": "imie", "wartosc": None},
            {"nazwa": "nazwisko", "wartosc": None}
        ]

        wynik = bedrock.sporzadz_projekt(wzor, dane, "")

        assert "<<BRAK: imie>>" in wynik
        assert "<<BRAK: nazwisko>>" in wynik


class TestWczytajJson:
    """Testy parsowania JSON z odpowiedzi modelu."""

    def test_czysty_json(self):
        tekst = '{"klucz": "wartosc"}'
        wynik = bedrock._wczytaj_json(tekst)
        assert wynik == {"klucz": "wartosc"}

    def test_json_z_markdown(self):
        tekst = '```json\n{"klucz": "wartosc"}\n```'
        wynik = bedrock._wczytaj_json(tekst)
        assert wynik == {"klucz": "wartosc"}

    def test_json_z_tekstem_przed_i_po(self):
        tekst = 'Oto odpowiedz:\n{"klucz": "wartosc"}\nKoniec'
        wynik = bedrock._wczytaj_json(tekst)
        assert wynik == {"klucz": "wartosc"}

    def test_json_bez_nawiasu(self):
        tekst = '"klucz": "wartosc"'
        with pytest.raises(ValueError, match="nie zwrocil poprawnego JSON"):
            bedrock._wczytaj_json(tekst)

    def test_pusty_tekst(self):
        with pytest.raises(ValueError):
            bedrock._wczytaj_json("")

    def test_json_zagniezdzone(self):
        tekst = '{"outer": {"inner": "value"}}'
        wynik = bedrock._wczytaj_json(tekst)
        assert wynik["outer"]["inner"] == "value"

    def test_cudzyslow_z_tresci_dokumentu(self):
        # Tak wygladala usterka, przez ktora 23.10.2026 przepadla duza sprawa.
        tekst = '{"pola": [{"nazwa": "kupujacy", "wartosc": "Spolka "Zalesie" sp. z o.o.", "pewnosc": "wysoka"}]}'
        wynik = bedrock._wczytaj_json(tekst)
        assert wynik["pola"][0]["wartosc"] == 'Spolka "Zalesie" sp. z o.o.'
        assert wynik["pola"][0]["pewnosc"] == "wysoka"

    def test_surowa_nowa_linia_w_wartosci(self):
        wynik = bedrock._wczytaj_json('{"cytat": "Dzial II\nwlasciciel: Sobczak Jan"}')
        assert wynik["cytat"] == "Dzial II\nwlasciciel: Sobczak Jan"

    def test_poprawne_cudzyslowy_bez_zmian(self):
        tekst = '{"a": "x \\"y\\" z", "b": ["1", "2"], "c": {"d": ""}}'
        assert bedrock._napraw_cudzyslowy(tekst) == tekst

    def test_nienaprawialny_to_niepoprawny_json(self):
        with pytest.raises(bedrock.NiepoprawnyJson):
            bedrock._wczytaj_json('{"a": "1" "b": "2"}')


def _odpowiedz(tekst: str, powod: str = "end_turn") -> dict:
    return {"output": {"message": {"content": [{"text": tekst}]}},
            "usage": {"inputTokens": 1, "outputTokens": 1}, "stopReason": powod}


ZLY_JSON = '{"pola": [{"nazwa": "a" "wartosc": "1"}], "braki": []}'
DOBRY_JSON = '{"pola": [{"nr": 1, "nazwa": "a", "wartosc": "1"}], "braki": [], "rozbieznosci": []}'


class TestZestawienieNiePrzepada:
    """Blad na koncu odczytu nie moze przekreslac przepisanych juz stron."""

    def test_model_poprawia_skladnie(self, mock_bedrock_client):
        mock_bedrock_client.converse.side_effect = [_odpowiedz(ZLY_JSON), _odpowiedz(DOBRY_JSON)]
        wynik = bedrock.odczytaj_dane([], ["a"], "")
        assert wynik["pola"][0]["wartosc"] == "1"
        naprawa = mock_bedrock_client.converse.call_args_list[1].kwargs
        assert naprawa["system"][0]["text"] == bedrock.prompty.NAPRAWA_JSON
        assert "thinking" not in naprawa.get("additionalModelRequestFields", {})
        assert ZLY_JSON in naprawa["messages"][0]["content"][0]["text"]

    def test_ponawia_zestawienie_gdy_naprawa_zawiedzie(self, mock_bedrock_client):
        mock_bedrock_client.converse.side_effect = [
            _odpowiedz(ZLY_JSON), _odpowiedz(ZLY_JSON),  # zestawienie i nieudana poprawka
            _odpowiedz(DOBRY_JSON),                       # drugie zestawienie
        ]
        wynik = bedrock.odczytaj_dane([], ["a"], "")
        assert wynik["pola"][0]["nazwa"] == "a"
        systemy = [c.kwargs["system"][0]["text"] for c in mock_bedrock_client.converse.call_args_list]
        assert systemy == [bedrock.prompty.EKSTRAKCJA, bedrock.prompty.NAPRAWA_JSON,
                           bedrock.prompty.EKSTRAKCJA]

    def test_przeczekuje_limit_zapytan(self, mock_bedrock_client, monkeypatch):
        from botocore.exceptions import ClientError
        czekanie = []
        monkeypatch.setattr(bedrock.time, "sleep", czekanie.append)
        limit = ClientError({"Error": {"Code": "ThrottlingException", "Message": "limit"}}, "ConverseStream")
        mock_bedrock_client.converse.side_effect = [limit, _odpowiedz(DOBRY_JSON)]
        wynik = bedrock.odczytaj_dane([], ["a"], "")
        assert wynik["pola"][0]["wartosc"] == "1" and czekanie == [60]

    def test_po_wszystkich_probach_czytelny_blad(self, mock_bedrock_client):
        mock_bedrock_client.converse.return_value = _odpowiedz(ZLY_JSON)
        with pytest.raises(bedrock.NiepoprawnyJson, match="niepoprawny JSON"):
            bedrock.odczytaj_dane([], ["a"], "")
        assert mock_bedrock_client.converse.call_count == 2 * bedrock.PROB_ZESTAWIENIA

    def test_ucieta_odpowiedz_nie_jest_ponawiana(self, mock_bedrock_client):
        mock_bedrock_client.converse.return_value = _odpowiedz('{"pola": [', "max_tokens")
        with pytest.raises(ValueError, match="ucieta"):
            bedrock.odczytaj_dane([], ["a"], "")
        assert mock_bedrock_client.converse.call_count == 1


class TestRozmowa:
    """Testy podstawowego mechanizmu rozmowy z modelem."""

    def test_rozmowa_struktura_wywolania(self, mock_bedrock_client):
        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "Odpowiedz testowa"}]
                }
            },
            "usage": {"inputTokens": 50, "outputTokens": 10}
        }

        system = "Jestes asystentem"
        tresc = [{"text": "Pytanie"}]
        max_tokenow = 1000

        wynik = bedrock._rozmowa(system, tresc, max_tokenow)

        assert wynik == "Odpowiedz testowa"
        mock_bedrock_client.converse.assert_called_once()

        call_kwargs = mock_bedrock_client.converse.call_args.kwargs
        assert call_kwargs["system"] == [{"text": system}]
        assert call_kwargs["messages"][0]["content"] == tresc
        assert call_kwargs["inferenceConfig"]["maxTokens"] == max_tokenow

    def test_myslenie_i_limity_dla_opus_4_6(self, mock_bedrock_client, monkeypatch):
        import config
        monkeypatch.setattr(config, "MODEL", "eu.anthropic.claude-opus-4-6-v1")
        monkeypatch.setattr(config, "MYSLENIE", True)
        mock_bedrock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "ok"}]}}, "usage": {}}
        bedrock._rozmowa("s", [{"text": "t"}])
        kw = mock_bedrock_client.converse.call_args.kwargs
        assert kw["inferenceConfig"] == {"maxTokens": config.MAX_WYJSCIE}  # bez temperature przy mysleniu
        dodatkowe = kw["additionalModelRequestFields"]
        assert dodatkowe["thinking"] == {"type": "adaptive"}
        assert dodatkowe["output_config"] == {"effort": config.WYSILEK}
        assert "context-1m-2025-08-07" in dodatkowe["anthropic_beta"]

    def test_bez_myslenia_temperatura_zero(self, mock_bedrock_client, monkeypatch):
        import config
        monkeypatch.setattr(config, "MODEL", "eu.anthropic.claude-sonnet-4-5-20250929-v1:0")
        mock_bedrock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "ok"}]}}, "usage": {}}
        bedrock._rozmowa("s", [{"text": "t"}], 1000, myslenie=False)
        kw = mock_bedrock_client.converse.call_args.kwargs
        assert kw["inferenceConfig"]["temperature"] == 0
        assert "additionalModelRequestFields" not in kw

    def test_starszy_model_dostaje_budzet_myslenia(self, mock_bedrock_client, monkeypatch):
        import config
        monkeypatch.setattr(config, "MODEL", "eu.anthropic.claude-sonnet-4-5-20250929-v1:0")
        mock_bedrock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "ok"}]}}, "usage": {}}
        bedrock._rozmowa("s", [{"text": "t"}], 8000, myslenie=True)
        dodatkowe = mock_bedrock_client.converse.call_args.kwargs["additionalModelRequestFields"]
        assert dodatkowe == {"thinking": {"type": "enabled", "budget_tokens": 4000}}

    def test_rozmowa_wiele_czesci_odpowiedzi(self, mock_bedrock_client):
        # Model moze zwrocic odpowiedz w wielu czesciach
        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [
                        {"text": "Czesc 1 "},
                        {"text": "Czesc 2 "},
                        {"text": "Czesc 3"}
                    ]
                }
            },
            "usage": {"inputTokens": 50, "outputTokens": 30}
        }

        wynik = bedrock._rozmowa("system", [{"text": "test"}], 1000)
        assert wynik == "Czesc 1 Czesc 2 Czesc 3"

    def test_rozmowa_obcinanie_bialych_znakow(self, mock_bedrock_client):
        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "  \n  Odpowiedz  \n  "}]
                }
            },
            "usage": {"inputTokens": 50, "outputTokens": 10}
        }

        wynik = bedrock._rozmowa("system", [{"text": "test"}], 1000)
        assert wynik == "Odpowiedz"


class TestBezpieczenstwoOdpowiedzi:
    """Ucieta odpowiedz i zly JSON nie moga wyciekac do logow."""

    def test_ucieta_odpowiedz_zglasza_blad(self, mock_bedrock_client):
        mock_bedrock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"pola": [{"nazwa": "x", "wartosc": "1'}]}},
            "usage": {"inputTokens": 1, "outputTokens": 8000},
            "stopReason": "max_tokens",
        }
        with pytest.raises(ValueError, match="ucieta"):
            bedrock.odczytaj_dane([], ["x"], "")

    def test_zly_json_nie_trafia_do_logow(self, mock_bedrock_client, caplog):
        tajne = "ZXC987654"
        mock_bedrock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"pola": [{"nazwa": "dowod", "wartosc": "' + tajne + '"'}]}},
            "usage": {"inputTokens": 1, "outputTokens": 1},
            "stopReason": "end_turn",
        }
        with pytest.raises(ValueError):
            bedrock.odczytaj_dane([], ["dowod"], "")
        assert tajne not in caplog.text


class TestPrzypisanieNazw:
    """Numer pola z odpowiedzi modelu jest rozstrzygajacy."""

    POLA = ["??1: Dnia __ przed", "ggg: nr kw", "??2: PESEL __ ,"]

    def test_numer_nadpisuje_nazwe(self):
        wynik = bedrock._przypisz_nazwy([{"nr": 2, "nazwa": "numer ksiegi", "wartosc": "x"}], self.POLA)
        assert wynik[0]["nazwa"] == "ggg: nr kw"

    def test_dodatkowe_pole_dostaje_prefiks(self):
        wynik = bedrock._przypisz_nazwy([{"nr": 0, "nazwa": "stan cywilny", "wartosc": "x"}], self.POLA)
        assert wynik[0]["nazwa"] == "+ stan cywilny"

    def test_numer_spoza_zakresu_traktowany_jak_dodatek(self):
        wynik = bedrock._przypisz_nazwy([{"nr": 99, "nazwa": "cos", "wartosc": "x"}], self.POLA)
        assert wynik[0]["nazwa"] == "+ cos"

    def test_dokladna_nazwa_bez_numeru_zachowana(self):
        wynik = bedrock._przypisz_nazwy([{"nazwa": "ggg: nr kw", "wartosc": "x"}], self.POLA)
        assert wynik[0]["nazwa"] == "ggg: nr kw"

    def test_smieci_pomijane(self):
        assert bedrock._przypisz_nazwy(["tekst", None], self.POLA) == []


class TestOczyszczanieProjektu:
    def test_usuwa_naglowki_markdown_i_ogrodzenia(self):
        tekst = "# PROJEKT DO WERYFIKACJI\n```\nAKT NOTARIALNY\n\nDnia 1.1.2026\n```\n"
        assert bedrock._oczysc_projekt(tekst) == "AKT NOTARIALNY\n\nDnia 1.1.2026"

    def test_nie_rusza_paragrafow(self):
        tekst = "§1. Tresc\n- pozycja\n"
        assert bedrock._oczysc_projekt(tekst) == "§1. Tresc\n- pozycja"


class TestPolaStale:
    def test_pola_stale_dolaczone_i_mapowane(self, mock_bedrock_client):
        import prompty
        n = 2 + len(prompty.POLA_STALE)
        mock_bedrock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": json.dumps({"pola": [{"nr": 3, "nazwa": "x", "wartosc": "Zalesie"}], "braki": [], "rozbieznosci": []})}]}},
            "usage": {"inputTokens": 1, "outputTokens": 1}, "stopReason": "end_turn",
        }
        wynik = bedrock.odczytaj_dane([], ["a", "b"], "")
        prompt = mock_bedrock_client.converse.call_args.kwargs["messages"][0]["content"][-1]["text"]
        assert f"[{n}]" in prompt and "STALE: miejscowosc" in prompt
        assert wynik["pola"][0]["nazwa"] == prompty.POLA_STALE[0]


class TestWyborProfiluAWS:
    """Skad biora sie poswiadczenia.

    W kontenerze (App Runner, ECS) nie ma zadnych profili AWS - poswiadczenia
    daje rola instancji. Wymuszenie nazwy profilu wywrocilo by tam start
    aplikacji, wiec domyslnie nie podajemy jej wcale.
    """

    @pytest.fixture(autouse=True)
    def _nowy_klient(self, monkeypatch):
        # Klient jest tworzony raz i wspoldzielony przez watki odczytu.
        monkeypatch.setattr(bedrock, "_klient_bedrock", None)

    def test_bez_profilu_zwykly_lancuch_poswiadczen(self, monkeypatch):
        monkeypatch.setattr(bedrock.config, "PROFIL_AWS", "")
        with patch("bedrock.boto3.Session") as sesja:
            bedrock._klient()
        assert "profile_name" not in sesja.call_args.kwargs
        assert sesja.call_args.kwargs["region_name"] == bedrock.config.REGION

    def test_nazwany_profil_gdy_ustawiony(self, monkeypatch):
        monkeypatch.setattr(bedrock.config, "PROFIL_AWS", "inny-profil")
        with patch("bedrock.boto3.Session") as sesja:
            bedrock._klient()
        assert sesja.call_args.kwargs["profile_name"] == "inny-profil"

    def test_domyslna_konfiguracja_nie_wymusza_profilu(self):
        """Domyslnie pusto - inaczej obraz nie wstanie w chmurze."""
        import importlib
        import config as modul_config
        importlib.reload(modul_config)
        assert modul_config.PROFIL_AWS == ""