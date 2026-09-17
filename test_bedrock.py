"""Testy przepływu z atrapa Bedrock.

NIE wywolujemy prawdziwego modelu w testach.
Mockujemy boto3.client i symulujemy odpowiedzi.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
import bedrock


@pytest.fixture
def mock_bedrock_client():
    """Atrapa klienta Bedrock."""
    with patch("bedrock._klient") as mock:
        klient = MagicMock()
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
        assert call_kwargs["inferenceConfig"]["temperature"] == 0

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