"""Samonaprawa: wykrywanie bledow, zgloszenia bez danych osobowych, bramki, workflow.

Agent naprawczy nie moze zmienic tego pliku (strefa zakazana w bramkach).
"""
from __future__ import annotations

import importlib.util
import json
import logging
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from botocore.exceptions import ClientError, ParamValidationError

import samonaprawa

KORZEN = Path(__file__).parent
NARZ = KORZEN / "scripts" / "samonaprawa"


def _modul(nazwa: str):
    spec = importlib.util.spec_from_file_location(f"sn_{nazwa}", NARZ / f"{nazwa}.py")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


zgl = _modul("zgloszenie")
sys.modules.setdefault("zgloszenie", zgl)
obs = _modul("obserwacja")
gh = _modul("github")
bramki = _modul("bramki")


@pytest.fixture(autouse=True)
def _czysto(monkeypatch):
    samonaprawa._reset_do_testow()
    monkeypatch.delenv("PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("PIECZAPP_WERSJA", "abc123def456")
    monkeypatch.setenv("GITHUB_REPOSITORY", "plnyspolka-pixel/notarai")
    yield
    samonaprawa._reset_do_testow()


def _rzuc(funkcja):
    try:
        funkcja()
    except Exception as e:  # noqa: BLE001
        return e
    raise AssertionError("nie rzucono")


def _blad_w_funkcji_a():
    raise ValueError("Jan Kowalski PESEL 85010112345 jan@kowalski.pl skan_Kowalski.pdf")


def _blad_w_funkcji_b():
    raise ValueError("inna tresc")


def _throttling():
    raise ClientError({"Error": {"Code": "ThrottlingException", "Message": "Too many"}}, "ConverseStream")


def _cachepoint():
    raise ParamValidationError(report='Unknown parameter in messages[0].content[1]: "cachePoint"')


# ------------------------------------------------------------------ aplikacja

class TestOdcisk:
    def test_ten_sam_blad_ten_sam_odcisk_mimo_innej_tresci(self):
        a1 = _rzuc(_blad_w_funkcji_a)
        a2 = _rzuc(_blad_w_funkcji_a)
        assert samonaprawa.odcisk(a1) == samonaprawa.odcisk(a2)
        assert len(samonaprawa.odcisk(a1)) == 12

    def test_inne_miejsce_inny_odcisk(self):
        assert samonaprawa.odcisk(_rzuc(_blad_w_funkcji_a)) != samonaprawa.odcisk(_rzuc(_blad_w_funkcji_b))

    def test_rodzaje(self):
        assert samonaprawa.rodzaj(_rzuc(_throttling)) == "przejsciowy"
        assert samonaprawa.rodzaj(_rzuc(_cachepoint)) == "kod"
        from fastapi import HTTPException
        assert samonaprawa.rodzaj(HTTPException(400, "zly plik")) == "pomijany"


class TestZgloszenieBezDanychOsobowych:
    def test_tresc_wyjatku_nie_trafia_do_zgloszenia_ani_logu(self, caplog):
        caplog.set_level(logging.ERROR)
        z = samonaprawa.zglos(_rzuc(_blad_w_funkcji_a))
        calosc = json.dumps(z, ensure_ascii=False) + caplog.text
        for dane in ("Kowalski", "85010112345", "jan@kowalski.pl", "skan_"):
            assert dane not in calosc
        assert z["typ"] == "ValueError" and z["rodzaj"] == "kod"
        assert any("_blad_w_funkcji_a" in m for m in z["miejsca"])

    def test_znacznik_w_logu_czyta_workflow(self, caplog):
        caplog.set_level(logging.ERROR)
        z = samonaprawa.zglos(_rzuc(_cachepoint))
        wpis = zgl.odczytaj_znacznik(caplog.records[-1].getMessage())
        assert wpis["odcisk"] == z["odcisk"] and wpis["wersja"] == "abc123def456"
        assert wpis["rodzaj"] == "kod"

    def test_pomijany_nie_jest_zglaszany(self):
        from fastapi import HTTPException
        assert samonaprawa.zglos(HTTPException(404, "brak")) is None


class TestWysylkaDoGithuba:
    def test_bez_tokenu_nie_wysyla(self):
        with patch("httpx.post") as post:
            samonaprawa.zglos(_rzuc(_cachepoint))
        post.assert_not_called()

    def test_z_tokenem_wysyla_raz_na_odcisk(self, monkeypatch):
        monkeypatch.setenv("PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN", "github_pat_test")
        wyslane = []
        monkeypatch.setattr(samonaprawa, "_wyslij", wyslane.append)
        monkeypatch.setattr(samonaprawa.threading, "Thread",
                            lambda target, args, **kw: MagicMock(start=lambda: target(*args)))
        samonaprawa.zglos(_rzuc(_cachepoint))
        samonaprawa.zglos(_rzuc(_cachepoint))
        assert len(wyslane) == 1
        assert samonaprawa.stan()["odciski"][wyslane[0]["odcisk"]] == 2

    def test_przejsciowy_nie_budzi_agenta(self, monkeypatch):
        monkeypatch.setenv("PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN", "github_pat_test")
        wyslane = []
        monkeypatch.setattr(samonaprawa, "_wyslij", wyslane.append)
        samonaprawa.zglos(_rzuc(_throttling))
        assert wyslane == []

    def test_wysylka_nigdy_nie_rzuca(self, monkeypatch):
        monkeypatch.setenv("PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN", "github_pat_test")
        with patch("httpx.post", side_effect=OSError("siec")):
            samonaprawa._wyslij({"odcisk": "abc"})   # bez wyjatku

    def test_ladunek_do_githuba(self, monkeypatch):
        monkeypatch.setenv("PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN", "github_pat_test")
        with patch("httpx.post") as post:
            post.return_value.status_code = 204
            samonaprawa._wyslij({"odcisk": "abc123def456"})
        kw = post.call_args.kwargs
        assert post.call_args.args[0].endswith("/repos/plnyspolka-pixel/notarai/dispatches")
        assert kw["json"]["event_type"] == "samonaprawa"
        assert kw["timeout"] <= 10


class TestWychwytywanie:
    def test_log_error_w_except_zglasza_blad(self):
        logger = logging.getLogger("pieczapp.test_samonaprawa")
        samonaprawa.zainstaluj(logging.getLogger("pieczapp"))
        try:
            _cachepoint()
        except ParamValidationError:
            logger.error("blad generowania")
        assert sum(samonaprawa.stan()["odciski"].values()) == 1

    def test_ten_sam_wyjatek_liczony_raz(self):
        blad = _rzuc(_cachepoint)
        samonaprawa.zglos(blad)
        samonaprawa.zglos(blad)
        assert sum(samonaprawa.stan()["odciski"].values()) == 1

    def test_nieobsluzony_wyjatek_endpointu(self):
        import asyncio
        from starlette.requests import Request
        import app as aplikacja
        zadanie = Request({"type": "http", "method": "POST", "path": "/api/sprawy/x/projekt",
                           "headers": [], "query_string": b""})
        odp = asyncio.run(aplikacja._nieobsluzony(zadanie, _rzuc(_cachepoint)))
        assert odp.status_code == 500
        assert sum(samonaprawa.stan()["odciski"].values()) == 1


# ------------------------------------------------------------------ zgloszenie

class TestOczyszczanieZgloszenia:
    def test_tylko_znane_pola_i_bezpieczne_znaki(self):
        z = zgl.oczysc({"odcisk": "ABC123DEF456", "typ": "ValueError$(rm -rf /)`x`",
                        "miejsca": ["bedrock.py:10 f", "zle; rm -rf", 5], "obce": "x"})
        assert z["odcisk"] == "abc123def456"
        assert "$" not in z["typ"] and "`" not in z["typ"]
        assert z["miejsca"] == ["bedrock.py:10 f"]
        assert "obce" not in z

    def test_bez_odcisku_odrzucone(self):
        with pytest.raises(ValueError):
            zgl.oczysc({"odcisk": "../../etc"})

    def test_zgloszenie_reczne_dostaje_odcisk(self):
        z = zgl.oczysc({"uwagi": "Sporządź projekt: Błąd modelu (ParamValidationError)"})
        assert len(z["odcisk"]) == 12 and z["rodzaj"] == "reczne"

    def test_kandydaci_z_logow(self):
        klient = MagicMock()
        linia = lambda o, r: f'2026 ERROR pieczapp.samonaprawa: samonaprawa {{"odcisk": "{o}", "rodzaj": "{r}"}}'
        klient.filter_log_events.return_value = {"events": [
            {"message": linia("aaaaaaaaaaaa", "kod"), "timestamp": 1},
            {"message": linia("bbbbbbbbbbbb", "kod"), "timestamp": 2},
            {"message": linia("bbbbbbbbbbbb", "kod"), "timestamp": 3},
            {"message": linia("cccccccccccc", "przejsciowy"), "timestamp": 4},
        ]}
        wynik = zgl.kandydaci(40, klient=klient)
        assert [w["odcisk"] for w in wynik] == ["bbbbbbbbbbbb", "aaaaaaaaaaaa"]
        assert wynik[0]["wystapien"] == 2


# ------------------------------------------------------------------ obserwacja

class TestObserwacja:
    def test_czysto(self):
        assert obs.ocen("aaaaaaaaaaaa", "v2", [], [])["werdykt"] == "ok"

    def test_nawrot_w_nowej_wersji_cofa(self):
        po = [{"odcisk": "aaaaaaaaaaaa", "wersja": "v2", "rodzaj": "kod"}]
        assert obs.ocen("aaaaaaaaaaaa", "v2", [], po)["werdykt"] == "cofnij"

    def test_stara_wersja_w_trakcie_podmiany_nie_cofa(self):
        po = [{"odcisk": "aaaaaaaaaaaa", "wersja": "v1", "rodzaj": "kod"}]
        assert obs.ocen("aaaaaaaaaaaa", "v2", [], po)["werdykt"] == "ok"

    def test_nowy_blad_po_wdrozeniu_cofa(self):
        po = [{"odcisk": "nnnnnnnnnnnn", "wersja": "v2", "rodzaj": "kod"}] * obs.PROG_NOWYCH
        assert obs.ocen("aaaaaaaaaaaa", "v2", [], po)["werdykt"] == "cofnij"
        znany = [{"odcisk": "nnnnnnnnnnnn"}]
        assert obs.ocen("aaaaaaaaaaaa", "v2", znany, po)["werdykt"] == "ok"


# ------------------------------------------------------------------ decyzja (GitHub)

class TestDecyzja:
    Z = {"odcisk": "abc123def456", "rodzaj": "kod", "typ": "ValueError", "kod_aws": "",
         "opis": "x", "miejsca": [], "endpoint": "", "wersja": "v1", "czas": "", "uwagi": ""}

    def _api(self, issue=None, komentarze=(), prs=(), zamkniete=()):
        wywolania = []

        def api(metoda, sciezka, dane=None):
            wywolania.append((metoda, sciezka, dane))
            if metoda == "GET" and "/issues?" in sciezka:
                return [issue] if issue else []
            if metoda == "GET" and sciezka.endswith("/comments?per_page=100"):
                return list(komentarze)
            if metoda == "GET" and "pulls?state=open" in sciezka:
                return list(prs)
            if metoda == "GET" and "pulls?state=closed" in sciezka:
                return list(zamkniete)
            if metoda == "POST" and sciezka.endswith("/issues"):
                return {"number": 7, "labels": [], "state": "open"}
            return {}
        return api, wywolania

    def test_nowy_blad_zaklada_zgloszenie_i_naprawia(self, monkeypatch):
        api, wyw = self._api()
        monkeypatch.setattr(gh, "api", api)
        d = gh.decyzja(dict(self.Z), "auto")
        assert d["dzialanie"] == "napraw" and d["tryb"] == "auto" and d["issue"] == 7 and d["nowe"]
        assert any(m == "POST" and s.endswith("/issues") for m, s, _ in wyw)

    def test_eskalacja_po_dwoch_probach(self, monkeypatch):
        issue = {"number": 3, "title": "[samonaprawa] abc123def456 x", "labels": [], "state": "open"}
        proba = {"body": gh.ZNACZNIK_PROBY + " nieudana"}
        api, _ = self._api(issue=issue, komentarze=[proba] * gh.MAX_PROB)
        monkeypatch.setattr(gh, "api", api)
        assert gh.decyzja(dict(self.Z), "auto")["dzialanie"] == "eskaluj"

    def test_po_eskalacji_bez_kolejnych_prob(self, monkeypatch):
        issue = {"number": 3, "title": "[samonaprawa] abc123def456", "state": "open",
                 "labels": [{"name": gh.ETYKIETA_ESKALACJA}]}
        api, _ = self._api(issue=issue)
        monkeypatch.setattr(gh, "api", api)
        assert gh.decyzja(dict(self.Z), "auto")["dzialanie"] == "tylko_zglos"

    def test_limit_dobowy_przelacza_na_pr(self, monkeypatch):
        from datetime import datetime, timezone
        teraz = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        scalone = [{"merged_at": teraz, "labels": [{"name": gh.ETYKIETA_AUTO}]}] * gh.MAX_AUTO_NA_DOBE
        api, _ = self._api(zamkniete=scalone)
        monkeypatch.setattr(gh, "api", api)
        d = gh.decyzja(dict(self.Z), "auto")
        assert d["dzialanie"] == "napraw" and d["tryb"] == "pr"

    def test_wylaczona_i_przejsciowy_tylko_zglaszaja(self, monkeypatch):
        api, _ = self._api()
        monkeypatch.setattr(gh, "api", api)
        assert gh.decyzja(dict(self.Z), "wylaczona")["dzialanie"] == "tylko_zglos"
        assert gh.decyzja(dict(self.Z, rodzaj="przejsciowy"), "auto")["dzialanie"] == "tylko_zglos"

    def test_czekajaca_poprawka_blokuje_druga(self, monkeypatch):
        issue = {"number": 3, "title": "[samonaprawa] abc123def456", "labels": [], "state": "open"}
        api, _ = self._api(issue=issue, prs=[{"head": {"ref": "samonaprawa/abc123def456-99"}}])
        monkeypatch.setattr(gh, "api", api)
        assert gh.decyzja(dict(self.Z), "auto")["dzialanie"] == "tylko_zglos"


class TestCzekanieNaWdrozenie:
    """23.11.2026: anulowane (zdublowane) wdrozenie wziete za awarie -> falszywe cofniecie."""
    P = {"updated_at": "2026-11-23T13:40:00Z", "html_url": "u"}

    def test_anulowane_zdublowane_to_nie_awaria(self):
        przebiegi = [dict(self.P, head_sha="abc", status="completed", conclusion="cancelled"),
                     dict(self.P, head_sha="abc", status="in_progress", conclusion=None)]
        assert gh.ocen_przebiegi("abc", przebiegi, zawiera=lambda g: True) is None
        przebiegi[1].update(status="completed", conclusion="success")
        assert gh.ocen_przebiegi("abc", przebiegi, zawiera=lambda g: True)["wynik"] == "success"

    def test_pozniejsza_wersja_z_poprawka_liczy_sie(self):
        przebiegi = [dict(self.P, head_sha="nowszy", status="completed", conclusion="success"),
                     dict(self.P, head_sha="abc", status="completed", conclusion="cancelled")]
        wynik = gh.ocen_przebiegi("abc", przebiegi, zawiera=lambda g: g in ("abc", "nowszy"))
        assert wynik["wynik"] == "success" and wynik["sha"] == "nowszy"

    def test_starsza_wersja_bez_poprawki_nie_liczy_sie(self):
        przebiegi = [dict(self.P, head_sha="starszy", status="completed", conclusion="success")]
        assert gh.ocen_przebiegi("abc", przebiegi, zawiera=lambda g: g == "abc") is None

    def test_porazka_dopiero_gdy_nic_juz_nie_trwa(self):
        przebiegi = [dict(self.P, head_sha="abc", status="completed", conclusion="failure"),
                     dict(self.P, head_sha="abc", status="queued", conclusion=None)]
        assert gh.ocen_przebiegi("abc", przebiegi, zawiera=lambda g: True) is None
        assert gh.ocen_przebiegi("abc", przebiegi[:1], zawiera=lambda g: True)["wynik"] == "failure"


# ------------------------------------------------------------------ bramki

@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Male repozytorium: modul z bledem i test. Bramki dzialaja na nim jak na notarai."""
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q", "-b", "master")
    git("config", "user.email", "t@t"); git("config", "user.name", "t")
    (tmp_path / "liczby.py").write_text("def dodaj(a, b):\n    return a - b\n")
    (tmp_path / "test_liczby.py").write_text(
        "from liczby import dodaj\n\ndef test_zero():\n    assert dodaj(0, 0) == 0\n")
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -q\n")
    git("add", "-A"); git("commit", "-qm", "baza")
    baza = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True,
                          text=True, check=True).stdout.strip()
    monkeypatch.setattr(bramki, "KORZEN", tmp_path)

    def zatwierdz(pliki: dict[str, str | None]):
        for nazwa, tresc in pliki.items():
            if tresc is None:
                (tmp_path / nazwa).unlink()
            else:
                (tmp_path / nazwa).parent.mkdir(parents=True, exist_ok=True)
                (tmp_path / nazwa).write_text(textwrap.dedent(tresc))
        git("add", "-A"); git("commit", "-qm", "poprawka")
    return baza, zatwierdz


DOBRA_POPRAWKA = "def dodaj(a, b):\n    return a + b\n"
TEST_REGRESJI = ("from liczby import dodaj\n\ndef test_zero():\n    assert dodaj(0, 0) == 0\n\n"
                 "def test_dodaje():\n    assert dodaj(2, 3) == 5\n")
RAPORT = {"testy_regresji": ["test_liczby.py::test_dodaje"], "ryzyko": "niskie"}


class TestBramki:
    def test_poprawka_z_dowodem_przechodzi_automatem(self, repo):
        baza, zatwierdz = repo
        zatwierdz({"liczby.py": DOBRA_POPRAWKA, "test_liczby.py": TEST_REGRESJI})
        wynik = bramki.ocen(baza, RAPORT)
        assert wynik["werdykt"] == "auto", wynik

    def test_test_ktory_nie_oblewa_starego_kodu_nie_jest_dowodem(self, repo):
        baza, zatwierdz = repo
        nic_nie_sprawdza = TEST_REGRESJI.replace("dodaj(2, 3) == 5", "True")
        zatwierdz({"liczby.py": DOBRA_POPRAWKA, "test_liczby.py": nic_nie_sprawdza})
        wynik = bramki.ocen(baza, RAPORT)
        assert wynik["werdykt"] == "odrzuc"
        assert "nie oblewa" in " ".join(wynik["odrzucenie"])

    def test_brak_testu_regresji(self, repo):
        baza, zatwierdz = repo
        zatwierdz({"liczby.py": DOBRA_POPRAWKA})
        assert bramki.ocen(baza, {"ryzyko": "niskie"})["werdykt"] == "odrzuc"

    def test_usuniety_test_odrzuca(self, repo):
        baza, zatwierdz = repo
        zatwierdz({"liczby.py": DOBRA_POPRAWKA,
                   "test_liczby.py": "from liczby import dodaj\n\ndef test_dodaje():\n    assert dodaj(2, 3) == 5\n"})
        wynik = bramki.ocen(baza, RAPORT)
        assert wynik["werdykt"] == "odrzuc" and "usuniete testy" in " ".join(wynik["odrzucenie"])

    def test_wyciszenie_testu_odrzuca(self, repo):
        baza, zatwierdz = repo
        zatwierdz({"liczby.py": DOBRA_POPRAWKA,
                   "test_liczby.py": "import pytest\n" + TEST_REGRESJI.replace(
                       "def test_zero", "@pytest.mark.skip\ndef test_zero")})
        assert bramki.ocen(baza, RAPORT)["werdykt"] == "odrzuc"

    def test_strefa_zakazana_tylko_pr(self, repo):
        baza, zatwierdz = repo
        zatwierdz({"liczby.py": DOBRA_POPRAWKA, "test_liczby.py": TEST_REGRESJI,
                   "prompty.py": "X = 1\n"})
        wynik = bramki.ocen(baza, RAPORT)
        assert wynik["werdykt"] == "pr" and "prompty.py" in " ".join(wynik["tylko_pr"])

    def test_ryzyko_wysokie_tylko_pr(self, repo):
        baza, zatwierdz = repo
        zatwierdz({"liczby.py": DOBRA_POPRAWKA, "test_liczby.py": TEST_REGRESJI})
        assert bramki.ocen(baza, dict(RAPORT, ryzyko="wysokie"))["werdykt"] == "pr"

    @pytest.mark.parametrize("sciezka", [
        "scripts/samonaprawa/bramki.py", ".github/workflows/ci.yml", "conftest.py", "infra/x.yaml",
        "test_samonaprawa.py", "CLAUDE.md", "dziennik.py", "magazyn.py",
    ])
    def test_strefy_zakazane(self, sciezka):
        assert bramki.w_strefie_zakazanej(sciezka)

    @pytest.mark.parametrize("sciezka", ["autoryzacja.py", "logowanie.py", "rejestracja.py",
                                         "urzadzenia.py", "platnosci.py", "tokenomia.py"])
    def test_logowanie_i_platnosci_calkowicie_poza_samonaprawa(self, sciezka):
        assert bramki.w_strefie_wykluczonej(sciezka)

    @pytest.mark.parametrize("sciezka", ["prompty.py", "zasady.py", "taksa.py", "klauzule.py", "osoby.py"])
    def test_tresc_prawna_taksa_dane_to_strefa_notariusza(self, sciezka):
        assert bramki.w_strefie_notariusza(sciezka) and not bramki.w_strefie_zakazanej(sciezka)

    def test_logowanie_odrzucone_nawet_na_prosbe(self, repo):
        baza, zatwierdz = repo
        zatwierdz({"liczby.py": DOBRA_POPRAWKA, "test_liczby.py": TEST_REGRESJI, "logowanie.py": "X = 1\n"})
        wynik = bramki.ocen(baza, RAPORT, prosba=True)
        assert wynik["werdykt"] == "odrzuc" and "logowanie" in " ".join(wynik["odrzucenie"])

    def test_tresc_prawna_na_prosbe_notariusza_wchodzi_automatem(self, repo):
        baza, zatwierdz = repo
        zatwierdz({"liczby.py": DOBRA_POPRAWKA, "test_liczby.py": TEST_REGRESJI, "prompty.py": "X = 1\n"})
        assert bramki.ocen(baza, RAPORT, prosba=True)["werdykt"] == "auto"

    def test_zwykly_kod_poza_strefa(self):
        assert not bramki.w_strefie_zakazanej("bedrock.py")
        assert not bramki.w_strefie_zakazanej("test_bedrock.py")


# ------------------------------------------------------------------ workflow i infrastruktura

class TestWorkflow:
    W = yaml.safe_load((KORZEN / ".github/workflows/samonaprawa.yml").read_text(encoding="utf-8"))
    KROKI = W["jobs"]["naprawa"]["steps"]

    def _krok(self, nazwa):
        return next(k for k in self.KROKI if k.get("name", "").startswith(nazwa))

    def test_jedna_naprawa_naraz_bez_przerywania(self):
        assert self.W["concurrency"]["cancel-in-progress"] is False

    def test_tylko_z_master(self):
        assert "refs/heads/master" in self.W["jobs"]["naprawa"]["if"]

    def test_agent_bez_tokenow(self):
        checkout = self.KROKI[0]
        assert checkout["with"]["persist-credentials"] is False
        for nazwa in ("Agent naprawczy", "Agent recenzent"):
            skrypt = self._krok(nazwa)["run"]
            for zmienna in ("GH_TOKEN", "GITHUB_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_RUNTIME_TOKEN"):
                assert f"-u {zmienna}" in skrypt, (nazwa, zmienna)
            assert "poswiadczenia.sh\" agent" in skrypt

    def test_bramki_z_kopii_sprzed_zmian_agenta(self):
        nazwy = [k.get("name", "") for k in self.KROKI]
        kopia = nazwy.index("Narzedzia samonaprawy z master (agent ich nie podmieni)")
        assert kopia < nazwy.index("Agent naprawczy")
        assert '"$NARZ/bramki.py"' in self._krok("Commit poprawki")["run"]

    def test_recenzent_nie_zmienia_plikow(self):
        skrypt = self._krok("Agent recenzent")["run"]
        assert "Edit,Write" in skrypt and "git status --porcelain" in skrypt

    def test_cofniecie_po_nawrocie(self):
        krok = self._krok("Cofniecie")
        assert "OBSERWACJA == 'cofnij'" in krok["if"] and "git revert" in krok["run"]

    def test_poprawka_nie_utyka_gdy_pr_nie_powstanie(self):
        """Bez PR (np. repo nie pozwala Actions zakladac PR) "auto" scala sie gitem, "pr" dostaje link."""
        pr = self._krok("Pull request")["run"]
        assert "PR=0" in pr and "compare/master..." in pr
        scal = self._krok("Scalenie i wdrozenie")["run"]
        assert "git merge --no-ff" in scal and 'HEAD:refs/heads/master' in scal
        assert '"$(git rev-parse origin/master)" != "$BAZA"' in scal      # tylko na przetestowany kod
        assert "wyzwol --workflow wdrozenie.yml" in scal                   # GITHUB_TOKEN nie odpala CI

    def test_nieudane_scalenie_powiadamia_a_nie_cofa(self):
        assert "nie_scalono" in self._krok("Nie scalono")["if"]
        assert "env.SCALONY != ''" in self._krok("Cofniecie")["if"]

    def test_tryb_testu_wdrozenia_bez_agenta_tylko_docs(self):
        assert self.W[True]["workflow_dispatch"]["inputs"]["test_wdrozenia"]["default"] is False
        for nazwa in ("Agent naprawczy", "Commit poprawki", "Agent recenzent", "Werdykt"):
            assert "TEST_WDROZENIA != 'true'" in self._krok(nazwa)["if"], nazwa
        test = self._krok("Test wdrozenia")["run"]
        assert "git add docs/samonaprawa-testy-wdrozenia.md" in test and "git add -A" not in test

    def test_prosba_notariusza_i_wlaczenie_po_zbudowaniu(self):
        assert "--prosba" in self._krok("Commit poprawki")["run"]
        assert "WLACZ=" in self._krok("Werdykt")["run"]

    def test_przeglad_mozna_wyzwolic_recznie(self):
        """Zastepczo, dopoki GitHub nie odpali harmonogramu: workflow_dispatch z przeglad=true."""
        assert self.W[True]["workflow_dispatch"]["inputs"]["przeglad"]["default"] is False
        assert "github.event.inputs.przeglad" in self._krok("Zgloszenie")["run"]

    def test_bramki_bez_tokenow_w_srodowisku(self):
        """Bramki uruchamiaja testy napisane przez agenta - nie moga widziec GH_TOKEN ani OIDC."""
        krok = self._krok("Commit poprawki")["run"]
        for zmienna in ("GH_TOKEN", "GITHUB_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_RUNTIME_TOKEN"):
            assert f"-u {zmienna}" in krok
        assert "poswiadczenia.sh" not in krok

    def test_postep_dla_notariusza_na_kazdym_etapie(self):
        calosc = "\n".join(k.get("run", "") for k in self.KROKI)
        for etap in ("przyjete", "analiza", "kontrola", "recenzja", "wdrazanie", "obserwacja",
                     "gotowe", "do_decyzji", "cofniete"):
            assert f"postep.sh\" {etap}" in calosc or f"postep.sh {etap}" in calosc, etap

    def test_model_w_ue(self):
        assert self.W["env"]["AWS_REGION"] == "eu-central-1"
        assert "eu.anthropic." in self.W["env"]["MODEL_AGENTA"]


class TestInfrastruktura:
    @staticmethod
    def _yaml(nazwa):
        class Ladowacz(yaml.SafeLoader):
            pass
        for tag in ("!Ref", "!Sub", "!GetAtt", "!If", "!Not", "!Equals", "!Join", "!Select"):
            Ladowacz.add_constructor(tag, lambda l, n: l.construct_scalar(n) if isinstance(n, yaml.ScalarNode)
                                     else l.construct_sequence(n))
        return yaml.load((KORZEN / "infra" / nazwa).read_text(encoding="utf-8"), Ladowacz)

    def test_rola_samonaprawy_tylko_z_master(self):
        rola = self._yaml("notarai-github.yaml")["Resources"]["RolaSamonaprawy"]["Properties"]
        warunek = rola["AssumeRolePolicyDocument"]["Statement"][0]["Condition"]["StringEquals"]
        assert "ref:refs/heads/${Galaz}" in warunek["token.actions.githubusercontent.com:sub"]
        akcje = [a for s in rola["Policies"][0]["PolicyDocument"]["Statement"]
                 for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])]
        # bez budowania, wdrazania i zmian w stosach
        assert not [a for a in akcje if a.split(":")[0] in ("cloudformation", "ecs", "codebuild", "iam", "s3")]

    def test_aplikacja_ma_wersje_i_token_warunkowo(self):
        szablon = (KORZEN / "infra/notarai-aplikacja.yaml").read_text(encoding="utf-8")
        assert "PIECZAPP_WERSJA" in szablon
        assert "PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN" in szablon
        assert "Condition: MamySamonaprawe" in szablon


def test_znacznik_brak_w_sekrecie_to_nie_token(monkeypatch):
    """Sekret notarai/samonaprawa-github ma "brak", dopoki wlasciciel nie wklei tokenu."""
    monkeypatch.setenv("PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN", "brak")
    assert samonaprawa._token() == ""
    monkeypatch.setenv("PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN", "github_pat_abc")
    assert samonaprawa._token() == "github_pat_abc"
