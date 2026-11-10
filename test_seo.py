"""Strona notarai.pl z kodu: baza kancelarii, strony miejscowosci, blog."""
import json
from pathlib import Path

import pytest

from seo import baza, blog, generuj, strona


class TestBaza:
    def test_naprawa_kodowania(self):
        assert baza.napraw_kodowanie("ul. PawÅ\x82a II 3") == "ul. Pawła II 3"
        assert baza.napraw_kodowanie("ul. DÄ brÃ³wki 17, 39 â\x80\x93 300") == "ul. Dąbrówki 17, 39 – 300"
        assert baza.napraw_kodowanie("ul. Żabia 3") == "ul. Żabia 3"
        assert baza.napraw_kodowanie(None) == ""

    def test_slug(self):
        assert baza.slug("Nowy Sącz") == "nowy-sacz" and baza.slug("Łódź") == "lodz"
        assert baza.slug("Ostrów Mazowiecka") == "ostrow-mazowiecka"

    def test_telefony(self):
        assert baza.telefony("(87) 643-74-05") == ["87 643 74 05"]
        assert baza.telefony("509-627-532 / (87) 643-05-73") == ["509 627 532", "87 643 05 73"]
        assert baza.telefony("Tel./Fax 58 346 27 88; 506-251-469 / (58) 346-27-88") == ["506 251 469", "58 346 27 88"]
        assert baza.telefony("+48 896740174") == ["89 674 01 74"]
        assert baza.telefony("Fax 54 288 24 35") == []
        assert baza.telefony(None) == [] and baza.telefony(226286467) == ["22 628 64 67"]

    def test_adres(self):
        assert baza.adres("MICKIEWICZA 40 11-010 BARCZEWO, BIAŁYSTOK, POLAND", "Barczewo", "Białymstoku") == "Mickiewicza 40 11-010 Barczewo"
        assert baza.adres("ul. Jana PawÅ\x82a II 23, 37-500; ul. Jana Pawła II 23, Jarosław", "Jarosław", "Rzeszowie") == "ul. Jana Pawła II 23, 37-500, Jarosław"
        assert baza.adres("ul. Dzierżoniowska 5, Strzelin, Polska", "Strzelin", "Wrocławiu") == "ul. Dzierżoniowska 5, Strzelin"
        assert baza.adres(None, "X", "Lublinie") == ""

    def test_nazwa_kancelarii(self):
        assert baza.nazwa_kancelarii("Kisiel Małgorzata", "") == "Kancelaria Notarialna Małgorzata Kisiel"
        assert baza.nazwa_kancelarii("Harajda Alicja, Mikłaszewicz-Reszko Monika", "spółka cywilna") == "Kancelaria Notarialna Alicja Harajda, Monika Mikłaszewicz-Reszko s.c."
        assert baza.nazwa_kancelarii("Łoboda Agnieszka Dorota", "spółka partnerska").endswith("Agnieszka Dorota Łoboda sp.p.")

    def test_normalizacja_laczy_literowki(self):
        wiersze = [["ID", "Izba notarialna", "Notariusz / notariusze", "Miejscowość", "Forma prowadzenia", "Adres kancelarii",
                    "Telefon", "E-mail", "Strona WWW / profil", "Status weryfikacji"],
                   [1, "Krakowie", "Nowak Anna", "Nowy Sącz", None, "ul. A 1", "18 000 00 00", "a@x.test", None, "kontakt publiczny — katalog izby notarialnej"],
                   [2, "Krakowie", "Kowal Jan", "Nowy Sacz", None, None, None, None, None, "brak publicznych danych w użytych katalogach"],
                   [3, "Warszawie", "Zielona Ewa", "ZIelonka", None, "ul. B 2", None, None, "https://notaries-directory.eu/en/x", "kontakt publiczny — oficjalny katalog notarialny"],
                   [4, "Warszawie", "Biała Ola", "Zielonka", None, None, None, None, None, "brak publicznych danych w użytych katalogach"]]
        d = baza.normalizuj(wiersze)
        assert [m["nazwa"] for m in d["miejscowosci"]] == ["Nowy Sącz", "Zielonka"]
        assert d["miejscowosci"][0]["liczba"] == 2 and d["miejscowosci"][1]["liczba"] == 2
        k = {x["id"]: x for x in d["kancelarie"]}
        assert k[2]["brak_kontaktu"] and not k[2]["zweryfikowany"] and k[1]["zweryfikowany"]
        assert k[3]["profil"].startswith("https://notaries-directory") and k[3]["www"] == ""
        assert k[1]["email"] == "a@x.test" and k[2]["adres"] == ""

    def test_json_w_repozytorium(self):
        d = baza.wczytaj_json()
        assert len(d["kancelarie"]) == 3501 and len(d["miejscowosci"]) == 602
        assert {m["slug"] for m in d["miejscowosci"]} == {k["slug"] for k in d["kancelarie"]}
        assert all(k["izba"] in baza.IZBY for k in d["kancelarie"])


class TestStrony:
    def test_odmiana(self):
        assert strona.odmiana(1, "kancelaria", "kancelarie", "kancelarii") == "1 kancelaria"
        assert strona.odmiana(3, "kancelaria", "kancelarie", "kancelarii") == "3 kancelarie"
        assert strona.odmiana(12, "kancelaria", "kancelarie", "kancelarii") == "12 kancelarii"
        assert strona.odmiana(22, "kancelaria", "kancelarie", "kancelarii") == "22 kancelarie"
        assert strona.odmiana(402, "kancelaria", "kancelarie", "kancelarii") == "402 kancelarie"

    def test_markdown(self):
        html = strona.markdown("## Tytuł\n\nAkapit z **pogrubieniem** i [linkiem](/kalkulator/).\n\n- a\n- b\n\n1. x\n2. y\n\n| k | w |\n|---|---|\n| 1 | 2 |\n\n> cytat\n")
        assert "<h2>Tytuł</h2>" in html and "<strong>pogrubieniem</strong>" in html and '<a href="/kalkulator/">linkiem</a>' in html
        assert "<ul><li>a</li><li>b</li></ul>" in html.replace("\n", "") and "<ol><li>x</li><li>y</li></ol>" in html.replace("\n", "")
        assert "<th>k</th>" in html and "<td>2</td>" in html and "<blockquote>cytat</blockquote>" in html
        assert "<script" not in strona.markdown("<script>alert(1)</script>") and "&lt;script&gt;" in strona.markdown("<script>alert(1)</script>")

    def test_generator_na_probce(self, tmp_path):
        dane = {"izby": baza.IZBY, "miejscowosci": [
            {"slug": "lublin", "nazwa": "Lublin", "izba": "Lublinie", "liczba": 2},
            {"slug": "pulawy", "nazwa": "Puławy", "izba": "Lublinie", "liczba": 1}],
            "kancelarie": [
                {"id": 1, "slug": "lublin", "miejscowosc": "Lublin", "izba": "Lublinie", "nazwa": "Kancelaria Notarialna Anna Testowa",
                 "notariusze": "Testowa Anna", "adres": "ul. Próbna 1, Lublin", "telefony": ["81 000 00 00"], "email": "tajny@kancelaria.test",
                 "www": "https://kancelaria.test", "profil": "", "zweryfikowany": True, "brak_kontaktu": False, "forma": ""},
                {"id": 2, "slug": "lublin", "miejscowosc": "Lublin", "izba": "Lublinie", "nazwa": "Kancelaria Notarialna Jan Cichy",
                 "notariusze": "Cichy Jan", "adres": "", "telefony": [], "email": "", "www": "", "profil": "", "zweryfikowany": False, "brak_kontaktu": True, "forma": ""},
                {"id": 3, "slug": "pulawy", "miejscowosc": "Puławy", "izba": "Lublinie", "nazwa": "Kancelaria Notarialna Ewa Nowa",
                 "notariusze": "Nowa Ewa", "adres": "ul. Druga 2, Puławy", "telefony": ["81 111 11 11"], "email": "e@n.test",
                 "www": "", "profil": "", "zweryfikowany": True, "brak_kontaktu": False, "forma": ""}]}
        wynik = generuj.generuj(dane, tmp_path)
        assert wynik == {"miejscowosci": 2, "kancelarie": 3}
        lublin = (tmp_path / "notariusz" / "lublin" / "index.html").read_text("utf-8")
        assert "<title>Notariusz Lublin: 2 kancelarie, koszty aktu, umów wizytę</title>" in lublin
        assert "Anna Testowa" in lublin and "81 000 00 00" in lublin and "tajny@kancelaria.test" not in lublin
        assert 'data-umow="1"' in lublin and 'data-umow="2"' not in lublin   # bez kontaktu = bez przycisku
        # .przycisk ma display: inline-block w style.css - bez tej reguly hidden nie dziala
        assert "[hidden] { display: none !important; }" in lublin
        # Neutralnosc: bez przesuwania kancelarii z notarai na gore listy i bez odznaki.
        assert "lista.prepend" not in lublin and "Korzysta z notarai" not in lublin
        assert "Brak danych kontaktowych" in lublin
        assert '"@type": "Notary"' in lublin and '"@type": "FAQPage"' in lublin and 'rel="canonical" href="https://notarai.pl/notariusz/lublin/"' in lublin
        assert "/notariusz/pulawy/" in lublin and "11 387,69" in lublin   # okolice i przyklad kosztow
        assert "/api/wizyty/zgloszenie" in lublin
        hub = (tmp_path / "notariusz" / "index.html").read_text("utf-8")
        assert "Puławy" in hub and "3 kancelarii" in hub and "Izba Notarialna w Lublinie" in hub
        mapa = (tmp_path / "sitemap.xml").read_text("utf-8")
        assert "https://notarai.pl/notariusz/pulawy/" in mapa and "https://notarai.pl/kalkulator/" in mapa
        assert "Sitemap: https://notarai.pl/sitemap.xml" in (tmp_path / "robots.txt").read_text("utf-8")

    def test_strony_wygenerowane_bez_emaili(self):
        katalog = Path("strona/notariusz")
        if not katalog.exists():
            pytest.skip("strony nie wygenerowane")
        tekst = (katalog / "lublin" / "index.html").read_text("utf-8")
        for swoj in ("@context", "@type", "@media", "kontakt@notarai.pl"):
            tekst = tekst.replace(swoj, "")
        assert "@" not in tekst


class TestBlog:
    def test_zapis_i_odczyt_artykulu(self, tmp_path, monkeypatch):
        monkeypatch.setattr(blog, "KATALOG_SZKICOW", tmp_path / "szkice")
        plik = blog.zapisz_szkic({"tytul": "Ile kosztuje testament", "opis": "Opis.", "slug": "Ile Kosztuje Testament!",
                                  "tresc": "## Sekcja\n\nTreść."}, "temat", "model-x")
        assert plik.name == "ile-kosztuje-testament.md"
        a = blog.wczytaj_artykul(plik)
        assert a["tytul"] == "Ile kosztuje testament" and a["tresc"] == "## Sekcja\n\nTreść." and a["temat"] == "temat"

    def test_budowa_bloga(self, tmp_path, monkeypatch):
        katalog = tmp_path / "artykuly"
        katalog.mkdir()
        (katalog / "a.md").write_text("---\ntytul: A\nopis: Opis A\ndata: 2026-11-07\n---\n\n## X\n\nTekst **a**.\n", encoding="utf-8")
        (katalog / "b.md").write_text("---\ntytul: B\nopis: Opis B\ndata: 2026-11-01\n---\n\nTekst b.\n", encoding="utf-8")
        monkeypatch.setattr(blog, "KATALOG_ARTYKULOW", katalog)
        assert blog.zbuduj(tmp_path) == 2
        a = (tmp_path / "blog" / "a" / "index.html").read_text("utf-8")
        assert "<h1>A</h1>" in a and "<strong>a</strong>" in a and '"@type": "Article"' in a and "/blog/b/" in a
        indeks = (tmp_path / "blog" / "index.html").read_text("utf-8")
        assert indeks.index("/blog/a/") < indeks.index("/blog/b/")   # najnowszy pierwszy

    def test_fakty_zawieraja_kwoty_z_kalkulatora(self):
        f = blog.fakty()
        assert "11 387,69" in f and "Dz.U. 2026 poz. 1370" in f and "sprzedaz_lokalu" in f and "PESEL" not in f.split("DOKUMENTY")[0]

    def test_opublikowane_artykuly_maja_naglowki(self):
        for plik in blog.KATALOG_ARTYKULOW.glob("*.md"):
            a = blog.wczytaj_artykul(plik)
            assert a["tytul"] and a["opis"] and "## " in a["tresc"] and "/kalkulator/" in a["tresc"]
