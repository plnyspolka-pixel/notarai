"""Codzienna praca bez powtarzania tych samych czynnosci. Bez sieci, dane fikcyjne."""
from unittest.mock import patch

from test_bez_zapisu import _przywroc_moduly, _skan, _wzor, klient  # noqa: F401

ODCZYT = {"pola": [{"nr": 1, "nazwa": "zbywca", "wartosc": "Ewa Pawlak"}],
          "braki": [], "rozbieznosci": []}


def _nowa(klient, **kw):
    with patch("bedrock.odczytaj_dane", return_value=ODCZYT), \
         patch("bedrock.rozmawiaj", return_value="Czego brakuje?"):
        return klient.post("/api/sprawy", **kw)


class TestWzorZPoprzedniejSprawy:
    def test_druga_sprawa_bez_wgrywania_wzoru(self, klient, tmp_path):
        pierwsza = _nowa(klient, files={"wzor": _wzor(), "skany": _skan()}).json()["id"]
        odp = _nowa(klient, files={"skany": _skan()}, data={"wzor_ze_sprawy": pierwsza})
        assert odp.status_code == 200, odp.text
        druga = odp.json()["id"]
        assert druga != pierwsza
        assert (tmp_path / druga / "wzor.docx").read_bytes() == \
            (tmp_path / pierwsza / "wzor.docx").read_bytes()

    def test_bez_wzoru_czytelny_blad(self, klient, tmp_path):
        odp = _nowa(klient, files={"skany": _skan()})
        assert odp.status_code == 400 and "wzor" in odp.json()["detail"]
        assert not any(tmp_path.iterdir()), "nieudana proba nie zostawia pustej sprawy"

    def test_nieznana_sprawa(self, klient, tmp_path):
        assert _nowa(klient, files={"skany": _skan()},
                     data={"wzor_ze_sprawy": "nieistnieje1"}).status_code == 404
        assert _nowa(klient, files={"skany": _skan()},
                     data={"wzor_ze_sprawy": "../inna"}).status_code == 400
        assert not any(tmp_path.iterdir())


def test_ustawienia_mowia_czy_dziala_mikrofon(klient):
    with patch("transkrypcja.dostepna", return_value=False):
        assert klient.get("/api/ustawienia").json()["transkrypcja"] is False
    with patch("transkrypcja.dostepna", return_value=True):
        assert klient.get("/api/ustawienia").json()["transkrypcja"] is True
