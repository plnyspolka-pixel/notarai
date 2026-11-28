"""Testy Klikamy na pulpicie - pomocnik prowadzi program kancelaryjny przez winapp CLI.

Prawdziwego winapp ani Windowsa tu nie ma: atrapa odgrywa okno programu
w ksztalcie odpowiedzi `winapp ui ... --json` (koperta z v0.3.1+, opisana
w references/ui-json-envelope.md repozytorium microsoft/WinAppCli). Model tez jest
atrapa. Sprawdzamy mechanizm: ze blokady trzymaja, gdy model sie pomyli.
"""
import json
import logging
import subprocess

import pytest

from pomocnik import klikamy, pulpit, zadania
from pomocnik.klikamy import prowadz
from pomocnik.pulpit import BladWinapp, OdmowaPulpitu, OknoProgramu, Winapp

DANE_STRONY = "Jan Kowalski"
WPISYWANE = "Anna Nowak-Wisniewska"


def okno_glowne():
    return {
        "hwnd": 1001, "title": "Rejent - Repertorium A", "className": "TFormMain",
        "elements": [{
            "selector": "win-rejent-1a2b", "name": "Rejent - Repertorium A", "type": "Window",
            "children": [
                {"selector": "tb-0001", "type": "TitleBar", "children": [
                    {"selector": "btn-close-0002", "name": "Zamknij", "type": "Button",
                     "isInvokable": True}]},
                {"selector": "NowaCzynnosc", "name": "Nowa czynność", "type": "Button",
                 "isInvokable": True, "isEnabled": True},
                {"selector": "txt-strona-0003", "name": "Strona", "type": "Edit",
                 "isEditable": True, "value": DANE_STRONY},
                {"selector": "txt-haslo-0004", "name": "Hasło", "type": "Edit",
                 "isEditable": True},
                {"selector": "btn-zamknijrok-0005", "name": "Zamknij rok", "type": "Button",
                 "isInvokable": True},
                {"selector": "btn-wyslij-0006", "name": "Wyślij do GIIF", "type": "Button",
                 "isInvokable": True},
                {"selector": "btn-off-0007", "name": "Nieaktywny", "type": "Button",
                 "isInvokable": True, "isEnabled": False},
                {"selector": "btn-ukryty-0008", "name": "Ukryty", "type": "Button",
                 "isInvokable": True, "isOffscreen": True},
                {"selector": "lbl-rok-0009", "name": "Repertorium A 2026", "type": "Text"},
            ],
        }],
    }


def dialog_usuwania():
    return {
        "hwnd": 2002, "title": "Potwierdzenie", "className": "#32770",
        "elements": [{
            "selector": "win-potw-0010", "name": "Potwierdzenie", "type": "Window",
            "children": [
                {"selector": "lbl-pyt-0011", "type": "Text",
                 "name": "Czy na pewno usunąć akt Rep. A 123/2026?"},
                {"selector": "btn-tak-0012", "name": "Tak", "type": "Button",
                 "isInvokable": True},
                {"selector": "btn-nie-0013", "name": "Nie", "type": "Button",
                 "isInvokable": True},
            ],
        }],
    }


class AtrapaWinapp:
    """Odpowiada jak `winapp ui <polecenie> --json` dla jednego procesu."""

    def __init__(self, okna=None, proces="Rejent", hasla=("txt-haslo-0004",),
                 wlasciwosci_padaja=False):
        self.okna = okna if okna is not None else [okno_glowne()]
        self.proces = proces
        self.hasla = set(hasla)
        self.wlasciwosci_padaja = wlasciwosci_padaja
        self.wywolania = []

    def __call__(self, polecenie, *opcje, pozycyjne=()):
        self.wywolania.append((polecenie, tuple(map(str, opcje)), tuple(pozycyjne)))
        if polecenie == "status":
            return {"processId": 4321, "processName": self.proces, "hwnd": 1001}
        if polecenie == "inspect":
            return {"depth": 12, "windows": self.okna}
        if polecenie == "get-property":
            if self.wlasciwosci_padaja:
                raise BladWinapp("element_not_found")
            haslo = pozycyjne[0] in self.hasla
            return {"elementId": pozycyjne[0], "properties": {"IsPassword": str(haslo)}}
        if polecenie == "yield":
            return {"released": True}
        return {"elementId": pozycyjne[0] if pozycyjne else ""}

    def czynnosci(self, rodzaj):
        return [w for w in self.wywolania if w[0] == rodzaj]


def polacz(atrapa=None, dozwolone=frozenset({"rejent"})):
    atrapa = atrapa or AtrapaWinapp()
    return OknoProgramu.polacz("Rejent", winapp=atrapa, dozwolone=set(dozwolone)), atrapa


def model_ze_scenariusza(*akcje):
    kolejka = list(akcje)

    def model(cel, stan, kroki):
        return kolejka.pop(0) if kolejka else {"akcja": "koniec", "podsumowanie": "koniec"}
    return model


def nr(okno, opis):
    return next(e["nr"] for e in okno.elementy() if e["opis"] == opis)


class TestKtorymProgramemWolno:
    def test_program_spoza_listy_tego_komputera(self):
        atrapa = AtrapaWinapp()
        with pytest.raises(OdmowaPulpitu, match="nie zezwolono"):
            OknoProgramu.polacz("Rejent", winapp=atrapa, dozwolone=set())
        assert atrapa.wywolania == []  # nawet nie pytamy systemu o okna

    @pytest.mark.parametrize("program", ["cmd", "powershell.exe", "chrome", "outlook",
                                         "szafir", "explorer", "notarai-pomocnik"])
    def test_zakazane_nawet_gdy_notariusz_je_dopisal(self, program):
        with pytest.raises(OdmowaPulpitu, match="nie steruje"):
            OknoProgramu.polacz(program, winapp=AtrapaWinapp(proces=program),
                                dozwolone={pulpit.nazwa_programu(program)})

    def test_okno_ktore_tylko_nazywa_sie_jak_program(self):
        # -a dopasowuje tez tytul okna: karta przegladarki "Rejent" to nie Rejent.
        with pytest.raises(OdmowaPulpitu, match="Nie znalazlem"):
            OknoProgramu.polacz("Rejent", winapp=AtrapaWinapp(proces="chrome"),
                                dozwolone={"rejent"})

    def test_dalej_celujemy_w_pid_a_nie_w_nazwe(self):
        okno, atrapa = polacz()
        okno.elementy()
        polecenie, opcje, _ = atrapa.czynnosci("inspect")[0]
        assert opcje[opcje.index("--app") + 1] == "4321"

    def test_nazwa_z_exe_i_wielkimi_literami(self):
        assert pulpit.nazwa_programu("  Rejent.EXE ") == "rejent"
        assert pulpit.nazwa_programu("rejent; del *") == ""


class TestOdczytOkna:
    def test_tylko_aktywne_widoczne_kontrolki_bez_paska_tytulu(self):
        okno, _ = polacz()
        opisy = [e["opis"] for e in okno.elementy()]
        assert "Nowa czynność" in opisy and "Strona" in opisy
        assert "Zamknij" not in opisy          # pasek tytulu programu
        assert "Nieaktywny" not in opisy and "Ukryty" not in opisy
        assert [e["nr"] for e in okno.elementy()] == list(range(1, len(opisy) + 1))

    def test_tekst_okna_dla_modelu(self):
        okno, _ = polacz()
        okno.elementy()
        tekst = okno.tekst_strony()
        assert "Repertorium A 2026" in tekst and f"Strona: {DANE_STRONY}" in tekst

    def test_adres_to_nazwa_programu_nie_tytul_okna(self):
        okno, _ = polacz()
        assert okno.url == "pulpit://rejent/"
        assert klikamy._host(okno.url) == "rejent"

    def test_kontekst_tylko_dla_przyciskow_bez_znaczenia(self):
        okno, _ = polacz(AtrapaWinapp(okna=[okno_glowne(), dialog_usuwania()]))
        elementy = {e["opis"]: e for e in okno.elementy()}
        assert "usunąć akt" in elementy["Tak"]["kontekst"]
        assert elementy["Nowa czynność"]["kontekst"] == ""
        assert elementy["Tak"]["rola"] == "Button w oknie 2"

    def test_limit_elementow(self):
        wiele = {"hwnd": 1001, "title": "Rejent", "elements": [
            {"selector": f"btn-{i}", "name": f"P{i}", "type": "Button", "isInvokable": True}
            for i in range(400)]}
        okno, _ = polacz(AtrapaWinapp(okna=[wiele]))
        assert len(okno.elementy()) == pulpit.MAKS_ELEMENTOW


class TestCzegoPomocnikNieZrobiWProgramie:
    def test_tak_pod_pytaniem_o_usuniecie(self):
        okno, atrapa = polacz(AtrapaWinapp(okna=[okno_glowne(), dialog_usuwania()]))
        przebieg = prowadz("potwierdz", okno, model_ze_scenariusza(
            {"akcja": "kliknij", "nr": nr(okno, "Tak")}))
        assert atrapa.czynnosci("invoke") == []
        assert "Nie kliknę" in przebieg.pytanie

    def test_nie_pod_pytaniem_o_usuniecie_jest_dozwolone(self):
        okno, atrapa = polacz(AtrapaWinapp(okna=[okno_glowne(), dialog_usuwania()]))
        prowadz("nie usuwaj", okno, model_ze_scenariusza(
            {"akcja": "kliknij", "nr": nr(okno, "Nie")}))
        assert [w[2] for w in atrapa.czynnosci("invoke")] == [("btn-nie-0013",)]

    def test_zamkniecie_roku_nigdy(self):
        okno, atrapa = polacz()
        przebieg = prowadz("zamknij rok", okno, model_ze_scenariusza(
            {"akcja": "kliknij", "nr": nr(okno, "Zamknij rok")}))
        assert atrapa.czynnosci("invoke") == []
        assert "nie da sie cofnac" in przebieg.pytanie

    def test_wysylka_do_urzedu_bez_zgody(self):
        okno, atrapa = polacz()
        przebieg = prowadz("wyslij", okno, model_ze_scenariusza(
            {"akcja": "kliknij", "nr": nr(okno, "Wyślij do GIIF")}))
        assert atrapa.czynnosci("invoke") == []
        assert "wysłać" in przebieg.pytanie

    def test_haslo(self):
        okno, atrapa = polacz()
        przebieg = prowadz("zaloguj", okno, model_ze_scenariusza(
            {"akcja": "wpisz", "nr": nr(okno, "Hasło"), "tekst": "tajne"}))
        assert atrapa.czynnosci("set-value") == []
        assert "hasla" in przebieg.pytanie.lower()

    def test_gdy_nie_wiadomo_czy_to_haslo_tez_nie_wpisujemy(self):
        okno, atrapa = polacz(AtrapaWinapp(wlasciwosci_padaja=True))
        przebieg = prowadz("wpisz", okno, model_ze_scenariusza(
            {"akcja": "wpisz", "nr": nr(okno, "Strona"), "tekst": WPISYWANE}))
        assert atrapa.czynnosci("set-value") == []
        assert "Nie umiem sprawdzic" in przebieg.pytanie

    def test_adresow_nie_otwiera(self):
        okno, atrapa = polacz()
        przebieg = prowadz("otworz", okno, model_ze_scenariusza(
            {"akcja": "otworz", "adres": "pulpit://rejent/cokolwiek"}))
        assert "adresow tu nie otwieram" in przebieg.pytanie
        przebieg = prowadz("otworz", okno, model_ze_scenariusza(
            {"akcja": "otworz", "adres": "https://bank.example.pl"}))
        assert "Nie wejde" in przebieg.pytanie

    def test_nieczytelna_nazwa_przycisku(self):
        glowne = okno_glowne()
        glowne["elements"][0]["children"].append(
            {"selector": "btn-zle-0099", "name": "Usu\ufffd", "type": "Button",
             "isInvokable": True})
        okno, atrapa = polacz(AtrapaWinapp(okna=[glowne]))
        prowadz("klik", okno, model_ze_scenariusza(
            {"akcja": "kliknij", "nr": nr(okno, "Usu\ufffd")}))
        assert atrapa.czynnosci("invoke") == []

    def test_element_spoza_odczytanego_okna(self):
        okno, _ = polacz()
        okno.elementy()
        with pytest.raises(OdmowaPulpitu):
            okno.kliknij("1001|Button|btn-wymyslony")


class TestZwyklaPraca:
    def test_klik_i_wpis_celuja_w_okno_i_typ(self):
        okno, atrapa = polacz()
        przebieg = prowadz("nowa czynnosc dla strony", okno, model_ze_scenariusza(
            {"akcja": "kliknij", "nr": nr(okno, "Nowa czynność")},
            {"akcja": "wpisz", "nr": nr(okno, "Strona"), "tekst": WPISYWANE},
            {"akcja": "koniec", "podsumowanie": "Dodalem czynnosc."}))
        assert przebieg.podsumowanie == "Dodalem czynnosc." and not przebieg.pytanie
        _, opcje, pozycyjne = atrapa.czynnosci("invoke")[0]
        assert opcje == ("--window", "1001", "--type", "Button")  # bez przeskoku do rodzica
        assert pozycyjne == ("NowaCzynnosc",)
        _, opcje, pozycyjne = atrapa.czynnosci("set-value")[0]
        assert opcje == ("--window", "1001", "--type", "Edit")
        assert pozycyjne == ("txt-strona-0003", WPISYWANE)

    def test_wybor_z_listy_przez_rozwiniecie(self):
        glowne = okno_glowne()
        glowne["elements"][0]["children"].append(
            {"selector": "cmb-rodzaj-0020", "name": "Rodzaj czynności", "type": "ComboBox",
             "isInvokable": True})

        class ZLista(AtrapaWinapp):
            def __call__(self, polecenie, *opcje, pozycyjne=()):
                if polecenie == "set-value":
                    self.wywolania.append((polecenie, opcje, pozycyjne))
                    raise BladWinapp("pattern_not_supported")
                if polecenie == "search":
                    self.wywolania.append((polecenie, opcje, pozycyjne))
                    return {"matchCount": 2, "matches": [
                        {"selector": "itm-umowa-0021", "name": "Umowa sprzedaży"},
                        {"selector": "itm-umowa-0022", "name": "Umowa sprzedaży lokalu"}]}
                return super().__call__(polecenie, *opcje, pozycyjne=pozycyjne)

        okno, atrapa = polacz(ZLista(okna=[glowne]))
        okno.elementy()
        okno.wybierz("1001|ComboBox|cmb-rodzaj-0020", "umowa sprzedaży")
        assert atrapa.czynnosci("invoke")[-1] == (
            "invoke", ("--window", "1001", "--type", "ListItem", "--action", "select"),
            ("itm-umowa-0021",))

    def test_zgoda_dotyczy_przycisku_w_programie(self):
        okno, atrapa = polacz()
        zgody = []
        prowadz("wyslij do GIIF", okno, model_ze_scenariusza(
            {"akcja": "kliknij", "nr": nr(okno, "Wyślij do GIIF")}),
            zatwierdz_wysylke=lambda host, etykieta: zgody.append((host, etykieta)) or True)
        assert zgody == [("rejent", "Wyślij do GIIF")]
        assert [w[2] for w in atrapa.czynnosci("invoke")] == [("btn-wyslij-0006",)]


class Wynik:
    def __init__(self, kod=0, stdout=b"{}", stderr=b""):
        self.returncode, self.stdout, self.stderr = kod, stdout, stderr


class TestWywolaniaWinapp:
    def test_argumenty_srodowisko_i_brak_powloki(self):
        zapis = {}

        def uruchom(argumenty, **opcje):
            zapis["argumenty"], zapis["opcje"] = argumenty, opcje
            return Wynik(stdout=b'{"elementId": "x"}')

        winapp = Winapp(sciezka="C:/winapp/winapp.exe", uruchom=uruchom)
        assert winapp("set-value", "--window", 1001, "--type", "Edit",
                      pozycyjne=("txt-1", "-rm wartosc")) == {"elementId": "x"}
        assert zapis["argumenty"] == ["C:/winapp/winapp.exe", "ui", "set-value", "--window",
                                      "1001", "--type", "Edit", "--json", "--", "txt-1",
                                      "-rm wartosc"]
        assert zapis["opcje"]["env"]["WINAPP_CLI_TELEMETRY_OPTOUT"] == "1"
        assert zapis["opcje"]["env"]["WINAPP_UI_WORKFLOW_ID"].startswith("notarai-pomocnik-")
        assert "shell" not in zapis["opcje"] and zapis["opcje"]["stdin"] == subprocess.DEVNULL

    def test_blad_niesie_tylko_kod(self, caplog):
        koperta = json.dumps({"error": {"code": "element_not_found",
                                        "message": f"No element '{DANE_STRONY}'",
                                        "selector": DANE_STRONY}}).encode()
        winapp = Winapp(sciezka="winapp", uruchom=lambda a, **k: Wynik(2, b"", koperta))
        with caplog.at_level(logging.DEBUG), pytest.raises(BladWinapp) as blad:
            winapp("invoke", pozycyjne=(DANE_STRONY,))
        assert blad.value.kod == "element_not_found"
        assert DANE_STRONY not in str(blad.value) and DANE_STRONY not in caplog.text

    def test_brak_trafien_w_search_to_wynik(self):
        winapp = Winapp(sciezka="winapp",
                        uruchom=lambda a, **k: Wynik(1, b'{"matchCount": 0, "matches": []}'))
        assert winapp("search", pozycyjne=("x",))["matchCount"] == 0

    def test_bez_winapp(self):
        with pytest.raises(BladWinapp) as blad:
            Winapp(sciezka="")("status")
        assert blad.value.kod == "brak_winapp"

        def brak(*a, **k):
            raise FileNotFoundError
        with pytest.raises(BladWinapp, match="nie ma winapp"):
            Winapp(sciezka="winapp", uruchom=brak)("status")

    def test_nigdy_przez_nakladke_cmd(self, tmp_path, monkeypatch):
        # Nakladka npm przepuszcza argumenty przez cmd.exe - "&" w nazwisku
        # stalby sie poleceniem. Bierzemy prawdziwy winapp.exe obok niej.
        nakladka = tmp_path / "winapp.cmd"
        nakladka.write_text("@node cli.js %*", encoding="utf-8")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "brak"))
        monkeypatch.setenv("NOTARAI_WINAPP", str(nakladka))
        monkeypatch.setattr(pulpit.shutil, "which", lambda nazwa: None)
        assert pulpit.znajdz_winapp() is None
        exe = tmp_path / "node_modules/@microsoft/winappcli/bin/win-x64/winapp.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"MZ")
        monkeypatch.setattr(pulpit, "_architektura", lambda: "win-x64")
        assert pulpit.znajdz_winapp() == str(exe)

    def test_przekroczony_czas(self):
        def wolno(*a, **k):
            raise subprocess.TimeoutExpired("winapp", 30)
        with pytest.raises(BladWinapp) as blad:
            Winapp(sciezka="winapp", uruchom=wolno)("inspect")
        assert blad.value.kod == "timeout"

    def test_strona_kodowa_zamiast_utf8(self):
        tresc = '{"name": "Usuń"}'.encode("cp1250")
        winapp = Winapp(sciezka="winapp", uruchom=lambda a, **k: Wynik(stdout=tresc))
        assert winapp("get-property")["name"] == "Usuń"


class TestZgodaNaKomputerze:
    def test_zezwol_i_cofnij(self, tmp_path):
        plik = tmp_path / "pomocnik.json"
        plik.write_text('{"token": "t"}', encoding="utf-8")
        assert pulpit.zezwol_na_program("Rejent.exe", plik) == "rejent"
        assert pulpit.dozwolone_programy(plik) == {"rejent"}
        assert json.loads(plik.read_text(encoding="utf-8"))["token"] == "t"
        pulpit.cofnij_zgode("REJENT", plik)
        assert pulpit.dozwolone_programy(plik) == set()

    def test_zakazanego_nie_dopisze(self, tmp_path):
        with pytest.raises(ValueError):
            pulpit.zezwol_na_program("powershell", tmp_path / "pomocnik.json")
        assert not (tmp_path / "pomocnik.json").exists()

    def test_flaga_w_wierszu_polecen(self, tmp_path, monkeypatch):
        from pomocnik import __main__ as wejscie
        plik = tmp_path / "pomocnik.json"
        monkeypatch.setattr(pulpit, "_plik_ustawien", lambda: plik)
        komunikat = wejscie.zezwol_z_wiersza(["exe", "--zezwol-program", "Rejent"])
        assert "rejent" in komunikat and pulpit.dozwolone_programy(plik) == {"rejent"}
        assert "Nie dopisano" in wejscie.zezwol_z_wiersza(["exe", "--zezwol-program"])


class AtrapaNotarai:
    def __init__(self, *akcje):
        self.model = model_ze_scenariusza(*akcje)
        self.stany = []

    def krok_klikania(self, zlecenie, cel, stan, kroki):
        self.stany.append(stan)
        return self.model(cel, stan, kroki)


class TestZlecenieDlaPomocnika:
    def test_jest_wsrod_wykonawcow(self):
        assert zadania.WYKONAWCY["pulpit"] is zadania.pulpit

    def test_caly_przebieg_bez_danych_w_raporcie_i_logach(self, caplog):
        atrapa = AtrapaWinapp()
        notarai = AtrapaNotarai(
            {"akcja": "wpisz", "nr": 2, "tekst": WPISYWANE},
            {"akcja": "koniec", "podsumowanie": "Wpisalem strone."})
        with caplog.at_level(logging.DEBUG):
            raport = zadania.pulpit(
                {"id": "z1", "tresc": {"cel": "wpisz strone", "program": "Rejent"}},
                notarai=notarai, winapp=atrapa, dozwolone={"rejent"})
        assert raport["podsumowanie"] == "Wpisalem strone." and raport["bledy"] == []
        assert atrapa.czynnosci("set-value")[0][2] == ("txt-strona-0003", WPISYWANE)
        assert atrapa.czynnosci("yield")  # pulpit oddany po pracy
        assert notarai.stany[0]["adres"] == "pulpit://rejent/"
        for tekst in (json.dumps(raport, ensure_ascii=False), caplog.text):
            assert WPISYWANE not in tekst and DANE_STRONY not in tekst

    def test_program_bez_zgody(self):
        raport = zadania.pulpit({"id": "z1", "tresc": {"cel": "x", "program": "Rejent"}},
                                notarai=AtrapaNotarai(), winapp=AtrapaWinapp(),
                                dozwolone=set())
        assert "nie zezwolono" in raport["bledy"][0]

    def test_program_zamkniety_w_trakcie(self):
        class Zamkniety(AtrapaWinapp):
            def __call__(self, polecenie, *opcje, pozycyjne=()):
                if polecenie == "inspect":
                    raise BladWinapp("no_target")
                return super().__call__(polecenie, *opcje, pozycyjne=pozycyjne)

        raport = zadania.pulpit({"id": "z1", "tresc": {"cel": "x", "program": "Rejent"}},
                                notarai=AtrapaNotarai(), winapp=Zamkniety(),
                                dozwolone={"rejent"})
        assert raport["bledy"] == ["Nie znalazlem okna programu."]


class TestPolecenieDlaModelu:
    def test_model_wie_ze_to_program(self):
        stan = {"adres": "pulpit://rejent/", "elementy": [], "tekst": ""}
        assert "nie uzywaj akcji otworz" in klikamy.polecenie_dla_modelu("x", stan, [])
        stan["adres"] = "https://krz.ms.gov.pl/"
        assert "nie uzywaj akcji otworz" not in klikamy.polecenie_dla_modelu("x", stan, [])


@pytest.fixture
def serwer(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import app as aplikacja
    import config
    import zlecenia

    monkeypatch.setattr(config, "SPRAWY", tmp_path)
    (tmp_path / "abc123").mkdir()
    monkeypatch.setattr(zlecenia, "dostepne", lambda: True)
    monkeypatch.setattr(aplikacja, "_pomocnik_pod_reka", lambda: True)
    zlozone = []
    monkeypatch.setattr(zlecenia, "zloz", lambda rodzaj, sprawa, tresc: zlozone.append(
        {"rodzaj": rodzaj, "tresc": tresc}) or {"id": "z1"})
    return TestClient(aplikacja.app), zlozone, monkeypatch, aplikacja


class TestSerwer:
    def test_sklada_zlecenie_pulpitu(self, serwer):
        http, zlozone, _, _ = serwer
        odp = http.post("/api/sprawy/abc123/pulpit",
                        json={"cel": "dodaj czynnosc", "program": "Rejent.exe"})
        assert odp.status_code == 202 and odp.json()["zlecenie"] == "z1"
        assert zlozone == [{"rodzaj": "pulpit",
                            "tresc": {"cel": "dodaj czynnosc", "program": "rejent"}}]

    @pytest.mark.parametrize("dane", [{"cel": " ", "program": "Rejent"},
                                      {"cel": "x", "program": "rejent && calc"}])
    def test_zle_dane(self, serwer, dane):
        http, zlozone, _, _ = serwer
        assert http.post("/api/sprawy/abc123/pulpit", json=dane).status_code == 400
        assert zlozone == []

    def test_bez_pomocnika(self, serwer):
        http, zlozone, monkeypatch, aplikacja = serwer
        monkeypatch.setattr(aplikacja, "_pomocnik_pod_reka", lambda: False)
        odp = http.post("/api/sprawy/abc123/pulpit", json={"cel": "x", "program": "Rejent"})
        assert odp.status_code == 409 and zlozone == []

    def test_rodzaj_znany_kolejce(self):
        import zlecenia
        assert "pulpit" in zlecenia.RODZAJE
