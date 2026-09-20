"""Dobieranie wartosci pol formularza z tresci aktu. Model zastapiony atrapa."""
import pytest

from formularze.silnik import Mapowanie, PoleFormularza
from formularze.dopasowanie import dopasuj


def _mapowanie(pola=None) -> Mapowanie:
    return Mapowanie(
        system="rejestr_testowy", opis="Rejestr testowy", adres="https://",
        status="gotowe", gotowosc="#formularz", przycisk_wysylki="#wyslij",
        pola=pola or [
            PoleFormularza(nazwa="Numer PESEL", zrodlo="pesel", selektor="#pesel",
                           transformacja="cyfry", wymagane=True,
                           opis="PESEL zbywcy"),
            PoleFormularza(nazwa="Numer ksiegi wieczystej", zrodlo="nr kw",
                           selektor="#kw", opis="KW nieruchomosci"),
        ],
    )


AKT = (
    "AKT NOTARIALNY\n\n"
    "Stawil sie TOMASZ PIOTR SOBCZAK, PESEL 85031512337, zamieszkaly w Zalesiu, "
    "i oswiadczyl, ze sprzedaje dzialke nr 12/3, objeta ksiega wieczysta "
    "KR1K/00012345/7, za cene 50 000 zl."
)


def _model_z_aktu(tekst, pola):
    """Atrapa modelu: zwraca to, co prawdziwy model powinien znalezc."""
    gotowe = {
        "Numer PESEL": {"wartosc": "85031512337", "cytat": "PESEL 85031512337",
                        "pewnosc": "wysoka"},
        "Numer ksiegi wieczystej": {"wartosc": "KR1K/00012345/7",
                                    "cytat": "ksiega wieczysta KR1K/00012345/7",
                                    "pewnosc": "wysoka"},
    }
    return [dict({"pole": p["nazwa"]}, **gotowe.get(p["nazwa"], {})) for p in pola]


class TestZrodlaWartosci:
    def test_pole_sprawy_ma_pierwszenstwo_przed_aktem(self):
        wynik = dopasuj(_mapowanie(), AKT, {"pesel": "44051401359"}, model=_model_z_aktu)
        pesel = next(w for w in wynik["wpisy"] if w["pole"] == "Numer PESEL")
        assert pesel["wartosc"] == "44051401359"
        assert pesel["skad"] == "pole sprawy"
        assert pesel["cytat"] == "", "wartosc z pola sprawy nie potrzebuje cytatu"

    def test_brakujace_pole_bierzemy_z_tresci_aktu(self):
        wynik = dopasuj(_mapowanie(), AKT, {}, model=_model_z_aktu)
        kw = next(w for w in wynik["wpisy"] if w["pole"] == "Numer ksiegi wieczystej")
        assert kw["wartosc"] == "KR1K/00012345/7"
        assert kw["skad"] == "tresc aktu"
        assert "KR1K/00012345/7" in kw["cytat"], "notariusz musi widziec, skad to sie wzielo"

    def test_bez_aktu_i_bez_pol_zostaje_brak(self):
        wynik = dopasuj(_mapowanie(), "", {}, model=_model_z_aktu)
        assert all(w["wartosc"] is None for w in wynik["wpisy"])
        assert all(w["skad"] == "brak" for w in wynik["wpisy"])
        assert wynik["dane"] == {}

    def test_dane_trafiaja_do_silnika_pod_kluczem_zrodla(self):
        """Silnik formularzy szuka wartosci po nazwie zrodla, nie po nazwie pola."""
        wynik = dopasuj(_mapowanie(), AKT, {}, model=_model_z_aktu)
        assert wynik["dane"] == {"pesel": "85031512337", "nr kw": "KR1K/00012345/7"}

    def test_kolejnosc_jak_w_formularzu(self):
        wynik = dopasuj(_mapowanie(), AKT, {}, model=_model_z_aktu)
        assert [w["pole"] for w in wynik["wpisy"]] == [
            "Numer PESEL", "Numer ksiegi wieczystej"]


class TestOstrzezenia:
    def test_bledna_suma_kontrolna_nie_kasuje_wartosci_tylko_ja_oznacza(self):
        def model(tekst, pola):
            return [{"pole": "Numer PESEL", "wartosc": "85031512331",
                     "cytat": "PESEL 85031512331", "pewnosc": "wysoka"},
                    {"pole": "Numer ksiegi wieczystej", "wartosc": None, "cytat": ""}]
        wynik = dopasuj(_mapowanie(), AKT, {}, model=model)
        pesel = next(w for w in wynik["wpisy"] if w["pole"] == "Numer PESEL")
        assert pesel["wartosc"] == "85031512331", "decyzje podejmuje notariusz"
        assert pesel["ostrzezenie"], "ale musi zobaczyc, ze suma kontrolna sie nie zgadza"

    def test_brak_wymaganego_pola_jest_oznaczony(self):
        def model(tekst, pola):
            return [{"pole": p["nazwa"], "wartosc": None, "cytat": ""} for p in pola]
        wynik = dopasuj(_mapowanie(), AKT, {}, model=model)
        pesel = next(w for w in wynik["wpisy"] if w["pole"] == "Numer PESEL")
        assert "wymagane" in pesel["ostrzezenie"].lower()

    def test_pole_niewymagane_bez_wartosci_nie_alarmuje(self):
        def model(tekst, pola):
            return [{"pole": p["nazwa"], "wartosc": None, "cytat": ""} for p in pola]
        wynik = dopasuj(_mapowanie(), AKT, {}, model=model)
        kw = next(w for w in wynik["wpisy"] if w["pole"] == "Numer ksiegi wieczystej")
        assert kw["ostrzezenie"] == ""


class TestOdpornoscNaModel:
    def test_model_moze_pominac_pole(self):
        wynik = dopasuj(_mapowanie(), AKT, {}, model=lambda t, p: [])
        assert len(wynik["wpisy"]) == 2
        assert all(w["wartosc"] is None for w in wynik["wpisy"])

    def test_model_moze_dopisac_pole_spoza_formularza(self):
        def model(tekst, pola):
            return [{"pole": "Cena", "wartosc": "50 000", "cytat": "za cene 50 000 zl"},
                    {"pole": "Numer PESEL", "wartosc": "85031512337", "cytat": "PESEL"}]
        wynik = dopasuj(_mapowanie(), AKT, {}, model=model)
        assert [w["pole"] for w in wynik["wpisy"]] == [
            "Numer PESEL", "Numer ksiegi wieczystej"], "obce pola nie trafiaja do formularza"

    def test_cytat_jest_przycinany(self):
        def model(tekst, pola):
            return [{"pole": p["nazwa"], "wartosc": "85031512337", "cytat": "x" * 500}
                    for p in pola]
        wynik = dopasuj(_mapowanie(), AKT, {}, model=model)
        assert all(len(w["cytat"]) <= 200 for w in wynik["wpisy"])


class TestOdpowiedziModelu:
    """bedrock.wyciagnij_do_formularza tlumaczy odpowiedz modelu na wpisy."""

    def test_odrzuca_pola_spoza_listy_i_uzupelnia_brakujace(self, monkeypatch):
        import bedrock
        monkeypatch.setattr(bedrock, "_rozmowa", lambda *a, **k: (
            '{"pola": [{"pole": "Numer PESEL", "wartosc": "85031512337", '
            '"cytat": "PESEL 85031512337", "pewnosc": "wysoka"}, '
            '{"pole": "Zmyslone pole", "wartosc": "x", "cytat": ""}]}'
        ))
        wynik = bedrock.wyciagnij_do_formularza(
            AKT, [{"nazwa": "Numer PESEL", "opis": ""},
                  {"nazwa": "Numer ksiegi wieczystej", "opis": ""}])
        assert [w["pole"] for w in wynik] == ["Numer PESEL", "Numer ksiegi wieczystej"]
        assert wynik[0]["wartosc"] == "85031512337"
        assert wynik[1]["wartosc"] is None, "pole bez odpowiedzi zostaje puste"

    def test_pusta_lista_pol_nie_wola_modelu(self, monkeypatch):
        import bedrock
        def nie_wolaj(*a, **k):
            raise AssertionError("model nie powinien byc wywolany")
        monkeypatch.setattr(bedrock, "_rozmowa", nie_wolaj)
        assert bedrock.wyciagnij_do_formularza(AKT, []) == []
