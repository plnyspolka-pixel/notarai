"""Rozszerzenie przegladarki (rozszerzenie/): panel z polem polecenia obok strony.

Trzy rzeczy pilnowane tutaj:
  - serwerowa polowa: zlecenie skladane przez panel nie trafia do kolejki
    pomocnika (.exe) i nie zapala przycisku "pomocnik pod reka",
  - manifest: rozszerzenie nie prosi o wiecej, niz potrzebuje,
  - silnik w JavaScripcie: jego wlasne testy (node --test) przechodza.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import bedrock
import zlecenia

KATALOG = Path(__file__).parent / "rozszerzenie"


@pytest.fixture
def klient(monkeypatch):
    from fastapi.testclient import TestClient
    import app as aplikacja

    monkeypatch.setattr(zlecenia, "dostepne", lambda: True)
    odnotowane = []
    monkeypatch.setattr(aplikacja, "_odnotuj_pomocnika",
                        lambda *a, **k: odnotowane.append(1))
    baza = {}

    def zloz(rodzaj, sprawa, tresc, stan="czeka"):
        baza["z1"] = {"id": "z1", "rodzaj": rodzaj, "sprawa": sprawa,
                      "tresc": tresc, "stan": stan}
        return baza["z1"]

    def zapisz_wynik(identyfikator, raport):
        baza[identyfikator].update(stan="wykonane", raport=raport, tresc={})
        return baza[identyfikator]

    monkeypatch.setattr(zlecenia, "zloz", zloz)
    monkeypatch.setattr(zlecenia, "wynik", lambda identyfikator: baza.get(identyfikator))
    monkeypatch.setattr(zlecenia, "zapisz_wynik", zapisz_wynik)
    return TestClient(aplikacja.app), baza, odnotowane


class TestZleceniaZPanelu:
    def test_panel_sklada_zlecenie_ktorego_pomocnik_nie_odbierze(self, klient):
        http, baza, _ = klient
        odp = http.post("/api/pomocnik/klikamy",
                        json={"cel": "znajdz dzialke 123/4", "host": "Mapy.Geoportal.gov.pl"})
        assert odp.status_code == 201 and odp.json() == {"zlecenie": "z1"}
        assert baza["z1"]["stan"] == "w_toku"          # kolejka oddaje tylko "czeka"
        assert baza["z1"]["tresc"]["dozwolone_hosty"] == ["mapy.geoportal.gov.pl"]

    def test_pusty_cel_to_blad(self, klient):
        http, baza, _ = klient
        assert http.post("/api/pomocnik/klikamy", json={"cel": "  "}).status_code == 400
        assert baza == {}

    def test_kroki_panelu_nie_udaja_obecnosci_pomocnika(self, klient, monkeypatch):
        """Rozszerzenie nie odbiera zlecen KRZ - przycisk nie moze sie przez nie zapalic."""
        http, _, odnotowane = klient
        monkeypatch.setattr(bedrock, "nastepny_krok", lambda cel, stan, kroki: {"akcja": "czytaj"})
        http.post("/api/pomocnik/klikamy", json={"cel": "x"})
        odp = http.post("/api/pomocnik/klikamy/z1/krok",
                        json={"cel": "x", "stan": {"adres": "https://a.gov.pl/", "tekst": "",
                                                   "elementy": []}, "kroki": []})
        assert odp.status_code == 200 and odp.json() == {"akcja": "czytaj"}
        assert odnotowane == []

    def test_koniec_zapisuje_liczby_a_nie_tresc(self, klient):
        http, baza, _ = klient
        http.post("/api/pomocnik/klikamy", json={"cel": "wpisz PESEL 44051401359"})
        odp = http.post("/api/pomocnik/klikamy/z1/koniec", json={"krokow": 4, "wynik": "pytanie"})
        assert odp.status_code == 200
        assert baza["z1"]["raport"] == {"krokow": 4, "wynik": "pytanie"}
        assert "44051401359" not in json.dumps(baza["z1"])

    def test_koniec_tylko_dla_zlecenia_panelu(self, klient):
        http, baza, _ = klient
        baza["z2"] = {"id": "z2", "stan": "czeka"}
        assert http.post("/api/pomocnik/klikamy/z2/koniec", json={}).status_code == 404
        assert http.post("/api/pomocnik/klikamy/nie-ma/koniec", json={}).status_code == 404

    def test_nieznany_wynik_nie_trafia_do_zapisu(self, klient):
        http, baza, _ = klient
        http.post("/api/pomocnik/klikamy", json={"cel": "x"})
        http.post("/api/pomocnik/klikamy/z1/koniec", json={"krokow": 1, "wynik": "Jan Kowalski"})
        assert baza["z1"]["raport"]["wynik"] == "przerwano"


class TestKolejki:
    def test_stan_w_toku_jest_dozwolony_a_inny_nie(self, monkeypatch):
        zapisane = []
        monkeypatch.setattr(zlecenia, "_zapisz", lambda kancelaria, z: zapisane.append(z))
        monkeypatch.setattr(zlecenia.magazyn, "kancelaria", lambda: "k1")
        assert zlecenia.zloz("klikamy", "", {"cel": "x"}, stan="w_toku")["stan"] == "w_toku"
        assert zlecenia.zloz("klikamy", "", {"cel": "x"})["stan"] == "czeka"
        with pytest.raises(ValueError):
            zlecenia.zloz("klikamy", "", {}, stan="cokolwiek")


class TestManifestu:
    def _manifest(self):
        return json.loads((KATALOG / "manifest.json").read_text("utf-8"))

    def test_bez_debuggera_i_bez_stalego_dostepu_do_wszystkich_stron(self):
        manifest = self._manifest()
        assert manifest["manifest_version"] == 3
        assert "debugger" not in manifest["permissions"]
        assert "<all_urls>" not in json.dumps(manifest)
        # Staly dostep tylko do notarai; do stron urzedow - za zgoda, strona po stronie.
        assert manifest["host_permissions"] == ["https://app.notarai.pl/*"]
        assert "https://*/*" in manifest["optional_host_permissions"]

    def test_pliki_z_manifestu_istnieja(self):
        manifest = self._manifest()
        sciezki = [manifest["side_panel"]["default_path"],
                   manifest["background"]["service_worker"], *manifest["icons"].values()]
        for sciezka in sciezki:
            assert (KATALOG / sciezka).is_file(), sciezka

    def test_obraz_serwera_nie_niesie_rozszerzenia(self):
        wpisy = (Path(__file__).parent / ".dockerignore").read_text("utf-8").split()
        assert "rozszerzenie/" in wpisy


class TestZlecenZKolejki:
    """KRZ i formularze: serwer zleca, rozszerzenie wykonuje w przegladarce notariusza."""

    @pytest.fixture
    def sprawa(self, klient, tmp_path, monkeypatch):
        import app as aplikacja
        import config
        import formularze

        http, baza, _ = klient
        monkeypatch.setattr(config, "SPRAWY", tmp_path)
        (tmp_path / "abc123").mkdir()
        monkeypatch.setattr(formularze.silnik, "czy_mozna_sterowac", lambda: False)
        monkeypatch.setattr(aplikacja, "_pomocnik_pod_reka", lambda: True)
        return http, baza, monkeypatch, aplikacja

    def _mapowanie(self, status):
        from formularze.silnik import Mapowanie, PoleFormularza
        return Mapowanie(
            system="probny", opis="", adres="https://rejestr.example.gov.pl/formularz",
            status=status, gotowosc="#pesel", przycisk_wysylki="#wyslij",
            pola=[PoleFormularza("Numer PESEL", "pesel", "#pesel", transformacja="cyfry"),
                  PoleFormularza("Uwagi", "uwagi", "#uwagi")])

    def _zlec(self, http):
        return http.post("/api/sprawy/abc123/formularze/probny", json={
            "pola": [{"nazwa": "pesel", "wartosc": "440 514 01359"}],
            "tryb": "faktyczny", "potwierdzam": True})

    def test_zlecenie_krz_niesie_opis_portalu(self, sprawa):
        import krz_portal
        http, baza, _, _ = sprawa
        odp = http.post("/api/sprawy/abc123/krz", json={
            "osoby": [{"pesel": "44051401359", "etykieta": "zbywca"}], "potwierdzam": True})
        assert odp.status_code == 202
        assert baza["z1"]["tresc"]["portal"] == krz_portal.opis_portalu()
        assert baza["z1"]["stan"] == "czeka"

    def test_formularz_gotowy_trafia_do_kolejki_z_krokami(self, sprawa):
        http, baza, monkeypatch, aplikacja = sprawa
        monkeypatch.setattr(aplikacja.formularze, "wczytaj_mapowanie",
                            lambda system: self._mapowanie("gotowe"))
        odp = self._zlec(http)
        assert odp.status_code == 202 and odp.json() == {"zlecenie": "z1", "stan": "czeka"}
        tresc = baza["z1"]["tresc"]
        assert baza["z1"]["rodzaj"] == "formularz" and tresc["tryb"] == "faktyczny"
        assert tresc["przycisk_wysylki"] == "#wyslij" and tresc["status_mapowania"] == "gotowe"
        assert tresc["kroki"][0] == {"pole": "Numer PESEL", "selektor": "#pesel",
                                     "typ": "tekst", "wartosc": "44051401359"}
        assert tresc["kroki"][1]["wartosc"] is None

    def test_szkic_nie_trafia_do_kolejki(self, sprawa):
        http, baza, monkeypatch, aplikacja = sprawa
        monkeypatch.setattr(aplikacja.formularze, "wczytaj_mapowanie",
                            lambda system: self._mapowanie("szkic"))
        odp = self._zlec(http)
        assert odp.status_code == 200 and "szkic" in odp.json()["bledy"][0]
        assert baza == {}

    def test_bez_odbiorcy_nie_skladamy_zlecenia(self, sprawa):
        http, baza, monkeypatch, aplikacja = sprawa
        monkeypatch.setattr(aplikacja.formularze, "wczytaj_mapowanie",
                            lambda system: self._mapowanie("gotowe"))
        monkeypatch.setattr(aplikacja, "_pomocnik_pod_reka", lambda: False)
        assert self._zlec(http).status_code == 409
        assert baza == {}

    def test_raport_formularza_bez_wartosci_pol(self, sprawa):
        http, baza, monkeypatch, aplikacja = sprawa
        monkeypatch.setattr(aplikacja.formularze, "wczytaj_mapowanie",
                            lambda system: self._mapowanie("gotowe"))
        self._zlec(http)
        odp = http.post("/api/pomocnik/zlecenia/z1/wynik", json={
            "kroki": [{"pole": "Numer PESEL", "wykonano": True, "uwaga": "",
                       "wartosc": "44051401359"},
                      {"pole": "Uwagi", "wykonano": False, "uwaga": "brak wartości"}],
            "bledy": []})
        assert odp.status_code == 200
        raport = baza["z1"]["raport"]
        assert raport["kroki"][0] == {"pole": "Numer PESEL", "wykonano": True, "uwaga": ""}
        assert raport["system"] == "probny" and raport["tryb"] == "faktyczny"
        assert "44051401359" not in json.dumps(baza["z1"])     # tresc zlecenia tez wyczyszczona
        stan = http.get("/api/sprawy/abc123/zlecenia/z1").json()
        assert stan["stan"] == "wykonane" and len(stan["raport"]["kroki"]) == 2

    def test_drugi_raport_do_tego_samego_zlecenia_nic_nie_dopisuje(self, sprawa):
        """Kolejke moga odpytywac naraz pomocnik (.exe) i rozszerzenie."""
        http, baza, monkeypatch, aplikacja = sprawa
        zapisane = []
        monkeypatch.setattr(aplikacja.rejestry, "zapisz_sprawdzenie",
                            lambda sprawa, wynik: zapisane.append(wynik))
        monkeypatch.setattr(aplikacja.magazyn, "utrwal_sprawe", lambda katalog: None)
        http.post("/api/sprawy/abc123/krz", json={
            "osoby": [{"pesel": "44051401359", "etykieta": "zbywca"}], "potwierdzam": True})
        raport = {"sprawdzenia": [{"rejestr": "KRZ", "pesel": "44051401359",
                                   "status": "brak_wpisu", "szczegoly": "zbywca - brak",
                                   "etykieta": "zbywca", "zrodlo": "https://krz.ms.gov.pl/"}]}
        assert http.post("/api/pomocnik/zlecenia/z1/wynik", json=raport).json()["zapisano"] == 1
        assert http.post("/api/pomocnik/zlecenia/z1/wynik", json=raport).json()["zapisano"] == 0
        assert len(zapisane) == 1


def test_opis_portalu_krz_w_testach_rozszerzenia_jest_aktualny():
    """Testy JavaScriptu rozpoznaja wynik wzorcami z serwera - musza miec te same."""
    import krz_portal
    zapisany = json.loads((KATALOG / "testy" / "portal-krz.json").read_text("utf-8"))
    assert zapisany == krz_portal.opis_portalu(), \
        "Zmienil sie krz_portal: odswiez rozszerzenie/testy/portal-krz.json"


@pytest.mark.skipif(not shutil.which("node"), reason="brak Node.js")
def test_silnik_rozszerzenia_przechodzi_wlasne_testy():
    wynik = subprocess.run(["node", "--test", "testy/silnik.test.mjs", "testy/kolejka.test.mjs"], cwd=KATALOG,
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert wynik.returncode == 0, wynik.stdout[-3000:] + wynik.stderr[-2000:]
