"""Duze sprawy: dzielenie stron na pasy, grupowanie stron w ksiegi wieczyste,
rownolegla transkrypcja. Bez wywolan Bedrock, dane fikcyjne."""
import io
from unittest.mock import patch

import fitz
import pytest
from PIL import Image

import bedrock
import config
import dokumenty


def _png_wymiary(dane: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(dane)).size


class TestPasy:
    def test_strona_a4_w_pasach_bez_dalszego_pomniejszania(self):
        strona = Image.new("L", (2480, 3508), 255)  # A4 w 300 dpi
        pasy = dokumenty._pasy(strona)
        assert len(pasy) >= 3
        for pas in pasy:
            szer, wys = dokumenty._dopasuj(pas).size
            assert szer <= config.MAX_BOK and wys <= config.MAX_BOK
            assert szer * wys <= config.MAX_PIKSELI
            assert pas.width == strona.width  # pas na cala szerokosc - wiersze tabel w calosci
        # pasy pokrywaja cala strone i zachodza na siebie
        assert pasy[-1].height == pasy[0].height

    def test_pasy_daja_wyzsza_rozdzielczosc_niz_cala_strona(self):
        strona = Image.new("L", (2480, 3508), 255)
        calosc = dokumenty._dopasuj(strona)
        pas = dokumenty._dopasuj(dokumenty._pasy(strona)[0])
        assert pas.width > calosc.width * 1.5

    def test_mala_strona_bez_pasow(self):
        assert dokumenty._pasy(Image.new("L", (800, 1000), 255)) == []

    def test_strona_pozioma(self):
        pasy = dokumenty._pasy(Image.new("L", (3508, 2480), 255))
        assert len(pasy) >= 2


class TestOpisStron:
    def test_pdf_liczony_bez_renderowania(self, tmp_path):
        pdf = fitz.open()
        for _ in range(3):
            pdf.new_page()
        sciezka = tmp_path / "kw.pdf"
        pdf.save(sciezka)
        strony = dokumenty.opisz_strony([sciezka])
        assert [s["strona"] for s in strony] == [1, 2, 3]
        assert "png" not in strony[0]

    def test_limit_stron(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MAX_STRON", 2)
        pdf = fitz.open()
        for _ in range(3):
            pdf.new_page()
        sciezka = tmp_path / "duzy.pdf"
        pdf.save(sciezka)
        with pytest.raises(ValueError, match="Za duzo stron"):
            dokumenty.opisz_strony([sciezka])

    def test_obrazy_strony_z_warstwa_tekstowa(self, tmp_path):
        pdf = fitz.open()
        s = pdf.new_page()
        for i in range(20):
            s.insert_text((72, 72 + i * 12), f"Wypis z rejestru gruntow, wiersz {i}", fontsize=8)
        sciezka = tmp_path / "wypis.pdf"
        pdf.save(sciezka)
        obrazy = dokumenty.obrazy_strony({"dokument": "wypis.pdf", "strona": 1, "sciezka": sciezka})
        assert "Wypis z rejestru" in obrazy["tekst"]
        assert len(obrazy["pasy"]) >= 3
        szer, wys = _png_wymiary(obrazy["calosc"])
        assert szer * wys <= config.MAX_PIKSELI


class TestNaglowekTranskrypcji:
    def test_rozbior(self):
        surowa = ("TYP: ksiega wieczysta - wydruk\nNR_KW: AB1C/00012345/6\n"
                  "POCZATEK_DOKUMENTU: tak\nNUMERACJA: Strona 1 z 4\nDZIAL: I-O\n---\n"
                  "| Nr dzialki | Obreb | Pow. |\n| 12/3 | Zalesie | 0,5100 |")
        t = bedrock._naglowek_transkrypcji(surowa)
        assert t["nr_kw"] == "AB1C/00012345/6" and t["poczatek"] is True
        assert t["dzial"] == "I-O" and t["tresc"].startswith("| Nr dzialki")

    def test_brak_kw(self):
        t = bedrock._naglowek_transkrypcji("TYP: x\nNR_KW: brak\nPOCZATEK_DOKUMENTU: nie\n---\ntresc")
        assert t["nr_kw"] is None and t["poczatek"] is False

    def test_bez_separatora_calosc_to_tresc(self):
        t = bedrock._naglowek_transkrypcji("sama tresc strony")
        assert t["tresc"] == "sama tresc strony" and t["typ"] == "nieustalony"


def _t(plik, nr, kw=None, poczatek=False, numeracja=None, tresc=""):
    return {"dokument": plik, "strona": nr, "typ": "ksiega wieczysta", "nr_kw": kw,
            "poczatek": poczatek, "numeracja": numeracja, "dzial": None, "tresc": tresc}


class TestGrupowanie:
    def test_strony_bez_numeru_naleza_do_swojej_ksiegi(self):
        strony = [
            _t("kw.pdf", 1, "AB1C/00000001/1", True), _t("kw.pdf", 2), _t("kw.pdf", 3),
            _t("kw.pdf", 4, "AB1C/00000002/2", True), _t("kw.pdf", 5),
        ]
        grupy = bedrock.pogrupuj_dokumenty(strony)
        assert [g["nr_kw"] for g in grupy] == ["AB1C/00000001/1", "AB1C/00000002/2"]
        assert [len(g["strony"]) for g in grupy] == [3, 2]

    def test_inny_numer_kw_bez_flagi_poczatku_zaczyna_nowa_ksiege(self):
        strony = [_t("kw.pdf", 1, "AB1C/00000001/1"), _t("kw.pdf", 2),
                  _t("kw.pdf", 3, "AB1C/00000002/2")]
        assert len(bedrock.pogrupuj_dokumenty(strony)) == 2

    def test_ten_sam_numer_w_innym_zapisie_to_ta_sama_ksiega(self):
        strony = [_t("kw.pdf", 1, "AB1C/00000001/1"), _t("kw.pdf", 2, "AB1C 00000001 1")]
        assert len(bedrock.pogrupuj_dokumenty(strony)) == 1

    def test_strona_1_z_n_zaczyna_dokument(self):
        strony = [_t("a.pdf", 1, numeracja="Strona 1 z 2"), _t("a.pdf", 2, numeracja="Strona 2 z 2"),
                  _t("a.pdf", 3, numeracja="Strona 1 z 3")]
        assert len(bedrock.pogrupuj_dokumenty(strony)) == 2

    def test_nowy_plik_to_nowy_dokument(self):
        assert len(bedrock.pogrupuj_dokumenty([_t("a.pdf", 1), _t("b.pdf", 1)])) == 2

    def test_tresc_dla_ekstrakcji_przypisuje_kw_stronom_bez_numeru(self):
        strony = [_t("kw.pdf", 1, "AB1C/00000001/1", True, tresc="Dzial I-O"),
                  _t("kw.pdf", 2, tresc="Dzial II: Sobczak Jan")]
        tekst = "\n".join(c["text"] for c in bedrock._tresc_z_transkrypcji(strony))
        assert "strona nalezy do KW AB1C/00000001/1" in tekst
        assert "MAPA DOKUMENTOW" in tekst and "KONIEC DOKUMENTU 1" in tekst


def _wynik(strona, tresc="ok"):
    return {"dokument": strona["dokument"], "strona": strona["strona"], "tresc": tresc}


class TestPaczki:
    def test_paczki_po_kolei_w_obrebie_pliku(self, monkeypatch):
        monkeypatch.setattr(config, "STRON_W_PACZCE", 3)
        strony = ([{"dokument": "a.pdf", "strona": n} for n in range(1, 6)]
                  + [{"dokument": "b.pdf", "strona": 1}])
        paczki = bedrock._paczki(strony)
        assert [[(s["dokument"], s["strona"]) for s in p] for p in paczki] == [
            [("a.pdf", 1), ("a.pdf", 2), ("a.pdf", 3)], [("a.pdf", 4), ("a.pdf", 5)], [("b.pdf", 1)]]

    def test_podzial_odpowiedzi_na_strony(self):
        surowa = ("=== STRONA 1 ===\nTYP: x\n---\npierwsza\n"
                  "=== STRONA 2 ===\nTYP: y\nNR_KW: AB1C/00000001/1\n---\ndruga")
        czesci = bedrock._podziel_na_strony(surowa, 2)
        assert bedrock._naglowek_transkrypcji(czesci[1])["tresc"] == "pierwsza"
        assert bedrock._naglowek_transkrypcji(czesci[2])["nr_kw"] == "AB1C/00000001/1"

    def test_pojedyncza_strona_bez_znacznika(self):
        assert bedrock._podziel_na_strony("TYP: x\n---\ntresc", 1) == {1: "TYP: x\n---\ntresc"}

    def test_paczka_przekracza_limit_obrazow_dzieli_sie(self, monkeypatch):
        strony = [{"dokument": "a.pdf", "strona": n} for n in range(1, 5)]
        monkeypatch.setattr(dokumenty, "obrazy_strony",
                            lambda s: {"calosc": b"x", "pasy": [b"p"] * 6, "tekst": ""})
        wywolania = []

        def model(system, tresc, **kw):
            n = sum(1 for c in tresc if "image" in c)
            wywolania.append(n)
            ile = sum(1 for c in tresc if c.get("text", "").startswith("=== STRONA"))
            return "\n".join(f"=== STRONA {i} ===\nTYP: t\n---\nstrona {i}" for i in range(1, ile + 1))

        with patch("bedrock._rozmowa", side_effect=model):
            wynik = bedrock.transkrybuj_paczke(strony)
        assert all(n <= bedrock.MAX_OBRAZOW for n in wywolania)
        assert [w["strona"] for w in wynik] == [1, 2, 3, 4]

    def test_strona_pominieta_czytana_osobno(self):
        paczka = [{"dokument": "a.pdf", "strona": n} for n in (1, 2)]
        odp = [[_wynik(paczka[0]), {"dokument": "a.pdf", "strona": 2, "brak": True}],
               [_wynik(paczka[1], "dopiero teraz")]]
        with patch("bedrock.transkrybuj_paczke", side_effect=odp) as atrapa:
            wynik = bedrock._transkrybuj_z_ponowieniem(paczka)
        assert wynik[1]["tresc"] == "dopiero teraz" and atrapa.call_count == 2


class TestRownoleglaTranskrypcja:
    def test_kolejnosc_zachowana_i_postep(self):
        strony = [{"dokument": "a.pdf", "strona": n} for n in range(1, 11)]
        postep = []
        with patch("bedrock.transkrybuj_paczke", side_effect=lambda p, w=None: [_wynik(s) for s in p]):
            wynik = bedrock.transkrybuj_strony(strony, lambda g, w: postep.append((g, w)))
        assert [w["strona"] for w in wynik] == list(range(1, 11))
        assert postep[-1] == (10, 10)

    def test_ponowienie_po_dlawieniu(self):
        from botocore.exceptions import ClientError
        dlawienie = ClientError({"Error": {"Code": "ThrottlingException"}}, "ConverseStream")
        s = {"dokument": "a", "strona": 1}
        with patch("bedrock.transkrybuj_paczke", side_effect=[dlawienie, [_wynik(s)]]):
            assert bedrock._transkrybuj_z_ponowieniem([s])[0]["tresc"] == "ok"

    def test_blad_walidacji_bez_ponowien(self):
        from botocore.exceptions import ClientError
        blad = ClientError({"Error": {"Code": "ValidationException"}}, "ConverseStream")
        with patch("bedrock.transkrybuj_paczke", side_effect=blad) as atrapa:
            with pytest.raises(ClientError):
                bedrock._transkrybuj_z_ponowieniem([{"dokument": "a", "strona": 1}])
        assert atrapa.call_count == 1


class TestWysilek:
    def test_wybor_z_przelacznika_zastepuje_domyslny(self, monkeypatch):
        monkeypatch.setattr(config, "MODEL", "eu.anthropic.claude-opus-4-6-v1")
        _, dodatkowe = bedrock._parametry_modelu(1000, True, "high")
        assert dodatkowe["output_config"] == {"effort": "high"}
        _, dodatkowe = bedrock._parametry_modelu(1000, True)
        assert dodatkowe["output_config"] == {"effort": config.WYSILEK}

    def test_wysilek_dochodzi_do_kazdej_paczki(self, monkeypatch):
        monkeypatch.setattr(config, "STRON_W_PACZCE", 1)
        strony = [{"dokument": "a.pdf", "strona": n} for n in (1, 2)]
        with patch("bedrock.transkrybuj_paczke", side_effect=lambda p, w=None: [_wynik(s) for s in p]) as atrapa:
            bedrock.transkrybuj_strony(strony, None, "medium")
        assert {c.args[1] for c in atrapa.call_args_list} == {"medium"}
