"""Testy potoku samonaprawy w AWS (bez sieci i bez AWS: wszystko po stronie zewnetrznej jest atrapa).

Ten plik jest w scripts/samonaprawa/*, wiec zalicza sie do strefy zakazanej bramek:
agent naprawczy nie zmieni testow wlasnego potoku.
"""
from __future__ import annotations

import base64
import io
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml

NARZ = Path(__file__).resolve().parent
KORZEN = NARZ.parents[1]
sys.path.insert(0, str(NARZ))

import agent as ag  # noqa: E402
import potok as pt  # noqa: E402
import stan as st  # noqa: E402
import straznik_poprawek as sp  # noqa: E402
import synchronizacja as sync  # noqa: E402
import wdroz as wz  # noqa: E402
import zatwierdz as zat  # noqa: E402
import zglos as zg  # noqa: E402

PROD = "aaaaaaaaaaaa"
ODCISK = "abc123def456"
Z = {"odcisk": ODCISK, "rodzaj": "kod", "typ": "ValueError", "kod_aws": "", "opis": "x",
     "miejsca": ["app_modul.py:1 f"], "endpoint": "", "wersja": PROD, "czas": "2026-11-25T10:00:00Z", "uwagi": ""}


def git(katalog, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=katalog,
                          capture_output=True, text=True, check=True).stdout


# ---------------------------------------------------------------- stan (DynamoDB)

class TestStanDecyzja:
    def _stan(self, teraz=None):
        return st.Stan(st.TabelaPamiec(), teraz=teraz)

    def test_nowy_blad_zaklada_rekord_i_naprawia(self):
        s = self._stan()
        d = s.decyzja(dict(Z), "auto")
        assert d["dzialanie"] == "napraw" and d["tryb"] == "auto" and d["nowe"] and d["proby"] == 0
        assert s.pobierz(ODCISK)["status"] == st.NOWE

    def test_eskalacja_po_dwoch_probach(self):
        s = self._stan()
        s.decyzja(dict(Z), "auto")
        for _ in range(st.MAX_PROB):
            s.komentarz(ODCISK, st.ZNACZNIK_PROBY + " nieudana")
        assert s.decyzja(dict(Z), "auto")["dzialanie"] == "eskaluj"

    def test_komentarz_bez_znacznika_nie_liczy_proby(self):
        s = self._stan()
        s.decyzja(dict(Z), "auto")
        s.komentarz(ODCISK, "zwykly komentarz")
        assert s.pobierz(ODCISK)["proby"] == 0

    def test_po_eskalacji_bez_kolejnych_prob(self):
        s = self._stan()
        s.decyzja(dict(Z), "auto")
        s.etykieta(ODCISK, st.ETYKIETA_ESKALACJA)
        assert s.decyzja(dict(Z), "auto")["dzialanie"] == "tylko_zglos"
        assert s.pobierz(ODCISK)["status"] == st.ESKALACJA

    def test_wylaczona_i_przejsciowy_tylko_zglaszaja(self):
        s = self._stan()
        assert s.decyzja(dict(Z), "wylaczona")["dzialanie"] == "tylko_zglos"
        assert s.decyzja(dict(Z, rodzaj="przejsciowy"), "auto")["dzialanie"] == "tylko_zglos"

    def test_limit_dobowy_przelacza_na_pr(self):
        s = self._stan()
        for i in range(st.MAX_AUTO_NA_DOBE):
            s.zapisz_wdrozenie(f"{i:012x}", "sn-x", "auto")
        d = s.decyzja(dict(Z), "auto")
        assert d["dzialanie"] == "napraw" and d["tryb"] == "pr"

    def test_wdrozenia_zatwierdzone_i_starsze_niz_doba_nie_licza_sie_do_limitu(self):
        t = [datetime(2026, 11, 25, 12, tzinfo=timezone.utc)]
        s = self._stan(teraz=lambda: t[0])
        s.zapisz_wdrozenie("a" * 12, "sn-a", "auto")
        t[0] += timedelta(hours=25)
        s.zapisz_wdrozenie("b" * 12, "sn-b", "zatwierdzone")
        s.zapisz_wdrozenie("c" * 12, "sn-c", "auto")
        assert s.auto_w_dobie() == 1

    def test_poprawka_czekajaca_blokuje_druga(self):
        s = self._stan()
        s.decyzja(dict(Z), "auto")
        s.ustaw(ODCISK, status=st.CZEKA)
        assert s.decyzja(dict(Z), "auto")["dzialanie"] == "tylko_zglos"

    def test_poprawka_do_zsynchronizowania_blokuje_druga_probe(self):
        s = self._stan()
        s.decyzja(dict(Z), "auto")
        s.zarejestruj_poprawke(ODCISK, "sn-x", PROD, "poprawki/x.patch")
        assert s.decyzja(dict(Z), "auto")["dzialanie"] == "tylko_zglos"

    def test_nawrot_po_zamknieciu_otwiera_ponownie_i_zachowuje_proby(self):
        s = self._stan()
        s.decyzja(dict(Z), "auto")
        s.komentarz(ODCISK, st.ZNACZNIK_PROBY)
        s.zamknij(ODCISK)
        assert s.pobierz(ODCISK)["status"] == st.NAPRAWIONE and not s.pobierz(ODCISK)["otwarte"]
        d = s.decyzja(dict(Z), "auto")
        assert d["proby"] == 1 and not d["nowe"] and s.pobierz(ODCISK)["otwarte"]

    def test_wybierz(self):
        s = self._stan()
        a, b, c = (dict(Z, odcisk=x * 12) for x in "abc")
        assert s.wybierz([a, b]) == a                       # nowy blad
        s.decyzja(a, "auto"); s.etykieta(a["odcisk"], st.ETYKIETA_ESKALACJA)
        s.decyzja(b, "auto"); s.ustaw(b["odcisk"], status=st.CZEKA)
        assert s.wybierz([a, b]) is None                    # eskalacja i czekajaca poprawka pomijane
        s.decyzja(c, "auto"); s.zamknij(c["odcisk"])
        assert s.wybierz([a, b, c]) == c                    # zamkniety, ale wrocil

    def test_historia_komentarzy_ma_limit(self):
        s = self._stan()
        s.decyzja(dict(Z), "auto")
        for i in range(st.KOMENTARZY_MAX + 10):
            s.komentarz(ODCISK, f"k{i}")
        k = s.pobierz(ODCISK)["komentarze"]
        assert len(k) == st.KOMENTARZY_MAX and k[-1]["tresc"] == f"k{st.KOMENTARZY_MAX + 9}"

    def test_zgloszenie_sprzed_naprawy_to_duplikat(self):
        s = self._stan()
        s.decyzja(dict(Z), "auto")
        s.zamknij(ODCISK)
        zamkniecie = s.pobierz(ODCISK)["czas_zamkniecia"]
        assert s.zamkniete_po(ODCISK, "2000-01-01T00:00:00Z")
        assert not s.zamkniete_po(ODCISK, "2999-01-01T00:00:00Z")
        assert zamkniecie

    def test_rejestr_poprawek_w_kolejnosci_i_bez_kasowania(self):
        t = [datetime(2026, 11, 25, 12, tzinfo=timezone.utc)]
        s = self._stan(teraz=lambda: t[0])
        p1 = s.zarejestruj_poprawke("a" * 12, "sn-1", PROD, "poprawki/1.patch")
        t[0] += timedelta(minutes=5)
        p2 = s.zarejestruj_poprawke("b" * 12, "sn-2", "sn-1", "poprawki/2.patch")
        assert [p["id"] for p in s.poprawki_do_synchronizacji()] == [p1, p2]
        s.status_poprawki(p1, st.ZSYNCHRONIZOWANE)
        assert [p["id"] for p in s.poprawki_do_synchronizacji()] == [p2]
        assert s.poprawka(p1)["status"] == st.ZSYNCHRONIZOWANE      # wpis zostaje


class TestTabelaDynamo:
    def test_aktualizacja_buduje_set_i_remove(self):
        zasob = MagicMock()
        t = st.TabelaDynamo(zasob=zasob)
        t.aktualizuj("p", "s", {"a": 1, "b": None, "c": [1]})
        arg = zasob.Table.return_value.update_item.call_args.kwargs
        assert arg["UpdateExpression"] == "SET #k0 = :v0, #k1 = :v1 REMOVE #d0"
        assert arg["ExpressionAttributeValues"] == {":v0": 1, ":v1": [1]}
        assert arg["ExpressionAttributeNames"]["#d0"] == "b"

    def test_odczyt_zamienia_decimal(self):
        from decimal import Decimal
        zasob = MagicMock()
        zasob.Table.return_value.get_item.return_value = {"Item": {"proby": Decimal("2"), "l": [Decimal("1")]}}
        assert st.TabelaDynamo(zasob=zasob).pobierz("p", "s") == {"proby": 2, "l": [1]}


# ---------------------------------------------------------------- werdykt

@pytest.mark.parametrize("naprawione,bramki,recenzja,tryb,zmieniona,oczekiwany", [
    (True, "auto", "przepusc", "auto", False, "auto"),
    (False, "auto", "przepusc", "auto", False, "odrzuc"),
    (True, "odrzuc", "przepusc", "auto", False, "odrzuc"),
    (True, "auto", "odrzuc", "auto", False, "odrzuc"),
    (True, "pr", "przepusc", "auto", False, "pr"),
    (True, "auto", "do_wlasciciela", "auto", False, "pr"),
    (True, "auto", "przepusc", "pr", False, "pr"),
    (True, "auto", "przepusc", "auto", True, "pr"),       # produkcja uciekla od bazy
    (True, "odrzuc", "do_wlasciciela", "pr", True, "odrzuc"),
])
def test_tabela_werdyktu(naprawione, bramki, recenzja, tryb, zmieniona, oczekiwany):
    assert pt.werdykt(naprawione, bramki, recenzja, tryb, zmieniona) == oczekiwany


def test_ladunek_json_i_base64():
    assert pt.odkoduj_ladunek('{"a": 1}') == {"a": 1}
    b = base64.b64encode(json.dumps({"zdarzenie": "przeglad"}).encode()).decode()
    assert pt.odkoduj_ladunek(b) == {"zdarzenie": "przeglad"}
    with pytest.raises(Exception):
        pt.odkoduj_ladunek("%%%")


# ---------------------------------------------------------------- srodowisko agenta

class TestIzolacjaAgenta:
    def test_polityka_sesji_tylko_bedrock(self):
        akcje = ag.POLITYKA_SESJI["Statement"][0]["Action"]
        assert sorted(akcje) == sorted(["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream",
                                        "bedrock:GetInferenceProfile", "bedrock:ListInferenceProfiles"])
        assert all(a.startswith("bedrock:") for a in akcje)

    def test_assume_role_z_polityka_sesji_i_krotka_sesja(self):
        sts = MagicMock()
        sts.assume_role.return_value = {"Credentials": {"AccessKeyId": "AK", "SecretAccessKey": "SK", "SessionToken": "ST"}}
        wynik = ag.sesja_agenta(sts, nazwa="samonaprawa-naprawa")
        arg = sts.assume_role.call_args.kwargs
        assert arg["RoleArn"].endswith(":role/notarai-samonaprawa-agent") and arg["DurationSeconds"] <= 3600
        assert json.loads(arg["Policy"]) == ag.POLITYKA_SESJI
        assert wynik == {"AWS_ACCESS_KEY_ID": "AK", "AWS_SECRET_ACCESS_KEY": "SK", "AWS_SESSION_TOKEN": "ST"}

    def test_proces_agenta_dostaje_tylko_poswiadczenia_sesji(self):
        potok_env = {"PATH": "/usr/bin", "AWS_ACCESS_KEY_ID": "ROLA-CB", "AWS_SECRET_ACCESS_KEY": "x", "AWS_SESSION_TOKEN": "x",
                     "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/abc", "GH_TOKEN": "ghp_x",
                     "GITHUB_TOKEN": "x", "CODEBUILD_BUILD_ID": "b", "SN_LADUNEK": "x", "TOKEN_SYNC": "x"}
        sesja = {"AWS_ACCESS_KEY_ID": "AK", "AWS_SECRET_ACCESS_KEY": "SK", "AWS_SESSION_TOKEN": "ST"}
        env = ag.srodowisko_agenta(sesja, "/tmp/dom", "eu.anthropic.claude-opus-4-6-v1",
                                   {"SAMONAPRAWA_RAPORT": "/x"}, bazowe=potok_env)
        assert env["AWS_ACCESS_KEY_ID"] == "AK" and env["CLAUDE_CODE_USE_BEDROCK"] == "1"
        for obce in ("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", "GH_TOKEN", "GITHUB_TOKEN", "CODEBUILD_BUILD_ID",
                     "SN_LADUNEK", "TOKEN_SYNC"):
            assert obce not in env
        assert env["HOME"] == "/tmp/dom" and env["ANTHROPIC_MODEL"].startswith("eu.anthropic.")

    def test_bramki_bez_zadnych_poswiadczen_aws(self):
        env = ag.srodowisko_czyste("/tmp/dom", bazowe={"PATH": "/bin", "AWS_ACCESS_KEY_ID": "x",
                                                         "AWS_CONTAINER_CREDENTIALS_FULL_URI": "http://x"})
        assert not [k for k in env if k.startswith("AWS_") and k not in ("AWS_REGION", "AWS_DEFAULT_REGION",
                                                                          "AWS_EC2_METADATA_DISABLED")]
        assert env["AWS_EC2_METADATA_DISABLED"] == "true"

    def test_uruchomienie_agenta_flagi_i_uzytkownik(self, monkeypatch, tmp_path):
        wywolania = []

        def uruchom(arg, **kw):
            wywolania.append((arg, kw))
            return SimpleNamespace(returncode=0)
        monkeypatch.setenv("SN_AGENT_UZYTKOWNIK", "snagent")
        monkeypatch.setattr(ag.os, "geteuid", lambda: 0)
        kod = ag.uruchom_agenta("polecenie", {"HOME": "/x"}, tmp_path, tmp_path / "w.json",
                                ag.NARZEDZIA_ZABRONIONE_RECENZJA, 60, 25, uruchom=uruchom)
        arg, kw = wywolania[0]
        assert kod == 0 and arg[0] == "claude" and "--max-turns" in arg and arg[arg.index("--max-turns") + 1] == "60"
        assert "Edit,Write" in arg[arg.index("--disallowedTools") + 1]
        assert kw["user"] == "snagent" and kw["timeout"] == 25 * 60 and kw["env"] == {"HOME": "/x"}

    def test_przekroczenie_czasu_to_blad(self, tmp_path):
        def uruchom(arg, **kw):
            raise subprocess.TimeoutExpired(arg, 1)
        assert ag.uruchom_agenta("p", {}, tmp_path, tmp_path / "w", "x", 1, 1, uruchom=uruchom) == -1


def test_zmiany_agenta_przenoszone_bez_jego_git(tmp_path):
    zrodlo, cel = tmp_path / "praca", tmp_path / "kandydat"
    for k in (zrodlo / ".git" / "hooks", cel / ".git"):
        k.mkdir(parents=True)
    (zrodlo / ".git" / "config").write_text("[core]\n\tfsmonitor = ./zlosliwe\n")
    (zrodlo / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n")
    (zrodlo / "a.py").write_text("nowe")
    (zrodlo / "__pycache__").mkdir()
    (zrodlo / "__pycache__" / "x.pyc").write_text("x")
    (cel / "a.py").write_text("stare")
    (cel / "usunieta.py").write_text("x")
    pt.przenies_zmiany(zrodlo, cel)
    assert (cel / "a.py").read_text() == "nowe" and not (cel / "usunieta.py").exists()
    assert not (cel / ".git" / "config").exists() and not (cel / "__pycache__").exists()


def test_hash_drzewa_wykrywa_zmiane(tmp_path):
    (tmp_path / "a").write_text("1")
    h = pt.hash_drzewa(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x").write_text("ignorowane")
    assert pt.hash_drzewa(tmp_path) == h
    (tmp_path / "a").write_text("2")
    assert pt.hash_drzewa(tmp_path) != h


# ---------------------------------------------------------------- orkiestracja potoku

DRZEWO = {
    "app_modul.py": "x = 1\n",
    "requirements.txt": "boto3==1.44.9\n",
    "scripts/samonaprawa/polecenie.md": "napraw\n",
    "scripts/samonaprawa/recenzja.md": "zrecenzuj\n",
    "infra/notarai-aplikacja.yaml": "AWSTemplateFormatVersion: '2010-09-09'\n",
    "docs/samonaprawa-testy-wdrozenia.md": "# testy\n",
}


def zip_drzewa(drzewo=DRZEWO) -> bytes:
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w") as z:
        for nazwa, tresc in drzewo.items():
            z.writestr(nazwa, tresc)
    return bufor.getvalue()


class AtrapaWdroz:
    def __init__(self, tagi=(PROD,), tag_stosu=PROD, wynik_wdrozenia=None, wolny=True, budowanie_pada=False):
        self.tagi, self.n = list(tagi), 0
        self.stos = tag_stosu
        self.wolny = wolny
        self.wyniki = list(wynik_wdrozenia or [{"wynik": "success", "powod": "", "koniec_ms": 111}])
        self.budowanie_pada = budowanie_pada
        self.pobrane, self.zbudowane, self.wdrozone = [], [], []
        self.wywolania = []

    def aktualny_tag(self):
        wynik = self.tagi[min(self.n, len(self.tagi) - 1)]
        self.n += 1
        return wynik

    def tag_stosu(self):
        return self.stos

    def czekaj_na_stos(self, minut):
        self.wywolania.append("czekaj")
        return self.wolny

    def pobierz_zrodla(self, tag, cel, bucket):
        self.pobrane.append(tag)
        Path(cel).write_bytes(zip_drzewa())

    def zbuduj_obraz(self, tag, zip_sciezka, bucket=""):
        if self.budowanie_pada:
            raise wz.BladWdrozenia("docker nie dziala")
        self.zbudowane.append((tag, zipfile.ZipFile(zip_sciezka).namelist()))

    def wdroz(self, tag, szablon, drzewo):
        self.wdrozone.append((tag, Path(szablon).name, Path(drzewo).name))
        wynik = self.wyniki.pop(0) if len(self.wyniki) > 1 else self.wyniki[0]
        if wynik["wynik"] == "success":
            self.stos = tag
        return wynik


class Srodowisko:
    """Zaleznosci potoku z atrapami; zapisuje, co sie stalo."""

    def __init__(self, tmp_path, wdroz=None, tryb="auto", agent="dobry", bramki="auto", recenzja="przepusc",
                 obserwacja=None, sync_pada=False, recenzent_psuje=False):
        self.s3, self.powiadomienia, self.postepy, self.agenci, self.bramki_wywolania = {}, [], [], [], []
        self.synchronizacje = 0
        self.obs_wywolania = []
        self.wdroz = wdroz or AtrapaWdroz()
        self.stan = st.Stan(st.TabelaPamiec())
        self.testy = []

        def uruchom_agenta(rodzaj, env, cwd, wyjscie, polecenie):
            self.agenci.append((rodzaj, env, Path(cwd).name, polecenie))
            if rodzaj == "naprawa":
                (Path(cwd) / ".git" / "config").write_text("[core]\n\tfsmonitor = ./zlosliwe\n")
                if agent == "dobry":
                    (Path(cwd) / "app_modul.py").write_text("x = 2\n")
                    Path(env["SAMONAPRAWA_RAPORT"]).write_text(json.dumps({
                        "naprawione": True, "przyczyna": "zly x", "poprawka": "x = 2", "ryzyko": "niskie",
                        "testy_regresji": ["test_x.py::test_x"], "dla_wlasciciela": "Naprawiono x.",
                        "sprawdz_w_aplikacji": "otworz x", "ustawienie": {"klucz": "k", "wartosc": "w"}}))
                elif agent == "nic":
                    Path(env["SAMONAPRAWA_RAPORT"]).write_text(json.dumps({"naprawione": False, "przyczyna": "nie wiem"}))
            else:
                if recenzent_psuje:
                    (Path(cwd) / "app_modul.py").write_text("x = 666\n")
                Path(env["SAMONAPRAWA_RECENZJA"]).write_text(json.dumps({"werdykt": recenzja, "powody": []}))
            return 0

        def uruchom_bramki(repo, baza, raport, wynik, prosba):
            self.bramki_wywolania.append((Path(repo).name, baza, prosba))
            Path(wynik).write_text(json.dumps({"werdykt": bramki, "odrzucenie": [] if bramki != "odrzuc" else ["czerwone"],
                                               "tylko_pr": [], "pliki": ["app_modul.py"], "linie": 2}))
            return 0

        def synchronizuj():
            self.synchronizacje += 1
            if sync_pada:
                raise RuntimeError("GitHub nie dziala")
            return []

        def obserwuj(odcisk, tag, od_ms):
            self.obs_wywolania.append((odcisk, tag, od_ms))
            return obserwacja or {"werdykt": "ok", "powody": []}

        self.zal = pt.Zaleznosci(
            stan=self.stan, wdroz=self.wdroz,
            powiadom=lambda t, m: self.powiadomienia.append((t, m)),
            postep=lambda odcisk, etap, opis="", wlacz=None: self.postepy.append((etap, opis, wlacz)),
            s3_wyslij=lambda k, plik: self.s3.__setitem__(k, Path(plik).read_bytes().decode("utf-8", "replace")),
            s3_pobierz=lambda k: self.s3[k], tryb=lambda: tryb, sesja_agenta=lambda r: {},
            uruchom_agenta=uruchom_agenta, uruchom_bramki=uruchom_bramki,
            uruchom_testy=lambda repo: (self.testy.append(Path(repo).name), 0)[1],
            obserwuj=obserwuj, kandydaci=lambda m: [], historia=lambda o: {"wystapien_7_dni": 3},
            synchronizuj=synchronizuj, zainstaluj=lambda d: None, daj_agentowi=lambda p: None,
            sn=tmp_path / "sn", bucket_wlasny="bucket-poprawek", przebieg="build-1",
            teraz=lambda: 1_700_000_000.0)

    def potok(self, test=False):
        return pt.Potok(self.zal, test=test)

    def tematy(self):
        return [t for t, _ in self.powiadomienia]


class TestPotokAuto:
    def test_zrodlem_jest_wersja_z_produkcji_a_nie_master(self, tmp_path):
        e = Srodowisko(tmp_path, wdroz=AtrapaWdroz(tagi=("f" * 12,), tag_stosu="f" * 12))
        e.potok().uruchom(dict(Z))
        assert e.wdroz.pobrane == ["f" * 12]
        # BAZA to commit z paczki, a agent pracowal na jej kopii
        assert git(tmp_path / "sn" / "zrodlo", "log", "--format=%s").startswith("BAZA ffffffffffff")

    def test_pelna_sciezka_naprawa_wdrozenie_obserwacja(self, tmp_path):
        e = Srodowisko(tmp_path)
        wynik = e.potok().uruchom(dict(Z))
        assert wynik["werdykt"] == "auto" and wynik["wdrozenie"] == "success"
        tag = wynik["tag"]
        assert tag.startswith("sn-") and len(tag) == 15
        assert e.wdroz.zbudowane[0][0] == tag and "app_modul.py" in e.wdroz.zbudowane[0][1]
        assert e.wdroz.wdrozone == [(tag, "notarai-aplikacja.yaml", "kandydat")]
        assert e.obs_wywolania == [(ODCISK, tag, 111)]
        rec = e.stan.pobierz(ODCISK)
        assert rec["status"] == st.NAPRAWIONE and not rec["otwarte"]
        assert e.tematy() == ["notarai: blad naprawiony automatycznie"]
        assert "Naprawiono x." in e.powiadomienia[0][1]
        assert [p[0] for p in e.postepy][:5] == ["przyjete", "analiza", "kontrola", "recenzja", "wdrazanie"]
        assert e.postepy[-1][0] == "gotowe" and e.postepy[-1][2] == {"klucz": "k", "wartosc": "w"}
        assert e.synchronizacje == 1

    def test_agent_i_bramki_dzialaja_na_kopiach_a_nie_na_czystym_repozytorium(self, tmp_path):
        e = Srodowisko(tmp_path)
        e.potok().uruchom(dict(Z))
        assert [a[2] for a in e.agenci] == ["praca", "recenzja"]
        assert e.bramki_wywolania[0][0] == "testy"
        # agent wpisal do swojego .git zlosliwa konfiguracje - kandydat (czyste repozytorium) jej nie ma
        assert "fsmonitor" not in (tmp_path / "sn" / "kandydat" / ".git" / "config").read_text()
        assert "fsmonitor" not in (tmp_path / "sn" / "zrodlo" / ".git" / "config").read_text()

    def test_narzedzia_skopiowane_z_bazy_przed_agentem(self, tmp_path):
        e = Srodowisko(tmp_path)
        e.potok().uruchom(dict(Z))
        assert (tmp_path / "sn" / "narzedzia" / "polecenie.md").read_text() == "napraw\n"
        assert e.agenci[0][3] == "napraw\n" and e.agenci[1][3] == "zrecenzuj\n"
        assert (tmp_path / "sn" / "szablon-baza.yaml").exists()

    def test_poprawka_trafia_do_rejestru_z_patchem_wzgledem_bazy(self, tmp_path):
        e = Srodowisko(tmp_path)
        wynik = e.potok().uruchom(dict(Z))
        wpisy = e.stan.t.zapytaj("NAPRAWA")
        assert len(wpisy) == 1 and wpisy[0]["status"] == st.DO_ZSYNCHRONIZOWANIA   # synchronizacja atrapa nic nie zmienia
        assert wpisy[0]["tag"] == wynik["tag"] and wpisy[0]["tag_bazowy"] == PROD
        patch = e.s3[wpisy[0]["patch_klucz"]]
        assert "-x = 1" in patch and "+x = 2" in patch and patch.startswith("From ")
        # patch daje sie nalozyc na czyste drzewo wersji z produkcji
        czyste = tmp_path / "czyste"
        czyste.mkdir()
        for n, t in DRZEWO.items():
            (czyste / n).parent.mkdir(parents=True, exist_ok=True)
            (czyste / n).write_text(t)
        git(czyste, "init", "-q"); git(czyste, "add", "-A"); git(czyste, "commit", "-qm", "x")
        (tmp_path / "p.patch").write_text(patch)
        git(czyste, "apply", "--check", str(tmp_path / "p.patch"))

    def test_limit_dobowy_zapisuje_wdrozenie(self, tmp_path):
        e = Srodowisko(tmp_path)
        e.potok().uruchom(dict(Z))
        assert e.stan.auto_w_dobie() == 1

    def test_blad_synchronizacji_nie_psuje_potoku(self, tmp_path):
        e = Srodowisko(tmp_path, sync_pada=True)
        wynik = e.potok().uruchom(dict(Z))
        assert wynik["wdrozenie"] == "success" and e.stan.pobierz(ODCISK)["status"] == st.NAPRAWIONE
        assert any("synchronizacja z GitHub nieudana" in l for l in e.zal.dziennik)

    def test_obserwacja_cofnij_wdraza_poprzedni_tag_z_szablonem_bazy(self, tmp_path):
        e = Srodowisko(tmp_path, obserwacja={"werdykt": "cofnij", "powody": ["blad wrocil"]})
        wynik = e.potok().uruchom(dict(Z))
        assert wynik["wdrozenie"] == "cofnieto"
        assert [w[0] for w in e.wdroz.wdrozone][-1] == PROD
        assert e.wdroz.wdrozone[-1][1:] == ("szablon-baza.yaml", "zrodlo")
        assert e.tematy() == ["notarai: samonaprawa cofnieta"]
        assert e.stan.pobierz(ODCISK)["proby"] == 1                         # jedna nieudana proba
        assert e.stan.t.zapytaj("NAPRAWA")[0]["status"] == st.WYCOFANA     # straznik wdrozen jej juz nie dolaczy
        assert e.stan.pobierz(ODCISK)["otwarte"] and e.stan.pobierz(ODCISK)["status"] == st.COFNIETE
        assert e.synchronizacje == 0                                        # nic do zapisu w repozytorium
        assert e.postepy[-1][0] == "cofniete"

    def test_blad_wdrozenia_stosu_tez_cofa(self, tmp_path):
        wdr = AtrapaWdroz(wynik_wdrozenia=[{"wynik": "blad", "powod": "smoke test produkcji nie przeszedl", "koniec_ms": 5},
                                           {"wynik": "success", "powod": "", "koniec_ms": 6}])
        e = Srodowisko(tmp_path, wdroz=wdr)
        wdr_stos_po = []
        wynik = e.potok().uruchom(dict(Z))
        assert wynik["wdrozenie"] in ("cofnieto", "cofniecie_pominiete")
        assert e.obs_wywolania == [] and e.stan.pobierz(ODCISK)["proby"] == 1
        assert e.stan.t.zapytaj("NAPRAWA") == []        # nie zarejestrowano: poprawki nie ma na produkcji
        assert wdr_stos_po == []

    def test_blad_wdrozenia_cofa_gdy_stos_ma_nasz_tag(self, tmp_path):
        class W(AtrapaWdroz):
            def wdroz(self, tag, szablon, drzewo):
                r = super().wdroz(tag, szablon, drzewo)
                if len(self.wdrozone) == 1:
                    self.stos = tag             # stos zdazyl zmienic tag, potem padl smoke
                return r
        wdr = W(wynik_wdrozenia=[{"wynik": "blad", "powod": "smoke", "koniec_ms": 5},
                                 {"wynik": "success", "powod": "", "koniec_ms": 6}])
        e = Srodowisko(tmp_path, wdroz=wdr)
        assert e.potok().uruchom(dict(Z))["wdrozenie"] == "cofnieto"
        assert [w[0] for w in wdr.wdrozone][-1] == PROD and e.tematy() == ["notarai: samonaprawa cofnieta"]

    def test_cofniecie_nieudane_alarmuje(self, tmp_path):
        wdr = AtrapaWdroz(wynik_wdrozenia=[{"wynik": "success", "powod": "", "koniec_ms": 1},
                                           {"wynik": "blad", "powod": "cfn padl", "koniec_ms": 2}])
        e = Srodowisko(tmp_path, wdroz=wdr, obserwacja={"werdykt": "cofnij", "powody": ["nawrot"]})
        assert e.potok().uruchom(dict(Z))["wdrozenie"] == "cofniecie_nieudane"
        assert "COFNIECIE NIE POWIODLO SIE" in e.tematy()[0]

    def test_cofniecie_pomijane_gdy_ktos_wdrozyl_inna_wersje(self, tmp_path):
        class W(AtrapaWdroz):
            def tag_stosu(self):
                return "inny" if self.wdrozone else self.stos
        e = Srodowisko(tmp_path, wdroz=W(), obserwacja={"werdykt": "cofnij", "powody": ["nawrot"]})
        assert e.potok().uruchom(dict(Z))["wdrozenie"] == "cofniecie_pominiete"
        assert len(e.wdroz.wdrozone) == 1 and "produkcja zmieniona" in e.tematy()[0]

    def test_wdrozenie_wyprzedzone_nie_cofa_w_ciemno(self, tmp_path):
        wdr = AtrapaWdroz(wynik_wdrozenia=[{"wynik": "wyprzedzone", "powod": "ECS uzywa x", "koniec_ms": 1}])
        e = Srodowisko(tmp_path, wdroz=wdr)
        assert e.potok().uruchom(dict(Z))["wdrozenie"] == "wyprzedzone"
        assert len(wdr.wdrozone) == 1 and e.stan.t.zapytaj("NAPRAWA") == []

    def test_budowanie_obrazu_pada_bez_wdrozenia(self, tmp_path):
        e = Srodowisko(tmp_path, wdroz=AtrapaWdroz(budowanie_pada=True))
        assert e.potok().uruchom(dict(Z))["wdrozenie"] == "blad"
        assert e.wdroz.wdrozone == [] and e.stan.pobierz(ODCISK)["proby"] == 1

    def test_stos_zajety_dluzej_niz_75_min_idzie_do_zatwierdzenia(self, tmp_path):
        e = Srodowisko(tmp_path, wdroz=AtrapaWdroz(wolny=False))
        wynik = e.potok().uruchom(dict(Z))
        assert wynik["wdrozenie"] == "nie_wdrozono" and e.wdroz.wdrozone == []
        assert e.stan.pobierz(ODCISK)["status"] == st.CZEKA

    def test_produkcja_zmienila_sie_w_trakcie_naprawy_poprawka_czeka(self, tmp_path):
        e = Srodowisko(tmp_path, wdroz=AtrapaWdroz(tagi=(PROD, "b" * 12)))
        wynik = e.potok().uruchom(dict(Z))
        assert wynik["werdykt"] == "pr" and e.wdroz.wdrozone == []
        assert e.stan.pobierz(ODCISK)["status"] == st.CZEKA

    def test_ktos_wdrozyl_tuz_przed_wdrozeniem(self, tmp_path):
        # kolejne odczyty: start, przed werdyktem, po czekaniu na stos, po zbudowaniu obrazu
        e = Srodowisko(tmp_path, wdroz=AtrapaWdroz(tagi=(PROD, PROD, PROD, "b" * 12)))
        wynik = e.potok().uruchom(dict(Z))
        assert wynik["wdrozenie"] == "nie_wdrozono" and e.wdroz.wdrozone == []
        assert e.stan.pobierz(ODCISK)["status"] == st.CZEKA

    def test_tryb_pr_zawsze_czeka_na_zatwierdzenie(self, tmp_path):
        e = Srodowisko(tmp_path, tryb="pr")
        wynik = e.potok().uruchom(dict(Z))
        rec = e.stan.pobierz(ODCISK)
        assert wynik["werdykt"] == "pr" and rec["status"] == st.CZEKA and rec["patch_klucz"] in e.s3
        assert e.wdroz.wdrozone == [] and e.tematy() == ["notarai: poprawka bledu czeka na decyzje"]
        assert f"zatwierdz.py {ODCISK}" in e.powiadomienia[0][1]
        assert e.postepy[-1][0] == "do_decyzji"

    def test_strefa_zakazana_bramki_pr(self, tmp_path):
        e = Srodowisko(tmp_path, bramki="pr")
        assert e.potok().uruchom(dict(Z))["werdykt"] == "pr"

    def test_bramki_odrzucaja_bez_recenzenta(self, tmp_path):
        e = Srodowisko(tmp_path, bramki="odrzuc")
        wynik = e.potok().uruchom(dict(Z))
        assert wynik["werdykt"] == "odrzuc" and [a[0] for a in e.agenci] == ["naprawa"]
        rec = e.stan.pobierz(ODCISK)
        assert rec["proby"] == 1 and rec["status"] == st.ODRZUCONE and e.wdroz.wdrozone == []

    def test_agent_nie_naprawil(self, tmp_path):
        e = Srodowisko(tmp_path, agent="nic")
        assert e.potok().uruchom(dict(Z))["werdykt"] == "odrzuc"
        assert e.stan.pobierz(ODCISK)["proby"] == 1 and e.bramki_wywolania == []

    def test_agent_bez_raportu_to_odrzucenie(self, tmp_path):
        e = Srodowisko(tmp_path, agent="cisza")
        assert e.potok().uruchom(dict(Z))["werdykt"] == "odrzuc"

    def test_recenzja_odrzuca(self, tmp_path):
        e = Srodowisko(tmp_path, recenzja="odrzuc")
        assert e.potok().uruchom(dict(Z))["werdykt"] == "odrzuc" and e.stan.pobierz(ODCISK)["proby"] == 1

    def test_recenzent_zmienia_pliki_recenzja_niewazna(self, tmp_path):
        e = Srodowisko(tmp_path, recenzent_psuje=True)
        wynik = e.potok().uruchom(dict(Z))
        assert wynik["werdykt"] == "pr" and e.wdroz.wdrozone == []

    def test_recenzent_do_wlasciciela_to_pr(self, tmp_path):
        assert Srodowisko(tmp_path, recenzja="do_wlasciciela").potok().uruchom(dict(Z))["werdykt"] == "pr"

    def test_niepoprawny_wynik_bramek_to_odrzucenie(self, tmp_path):
        e = Srodowisko(tmp_path, bramki="wszystko_dobrze")
        assert e.potok().uruchom(dict(Z))["werdykt"] == "odrzuc"

    def test_prosba_notariusza_przekazana_bramkom(self, tmp_path):
        e = Srodowisko(tmp_path)
        e.potok().uruchom(dict(Z, rodzaj="reczne", uwagi="zmien x"))
        assert e.bramki_wywolania[0][2] is True


class TestPotokPozaNaprawa:
    def test_eskalacja_po_dwoch_probach(self, tmp_path):
        e = Srodowisko(tmp_path)
        e.stan.decyzja(dict(Z), "auto")
        for _ in range(st.MAX_PROB):
            e.stan.komentarz(ODCISK, st.ZNACZNIK_PROBY)
        wynik = e.potok().uruchom(dict(Z))
        assert wynik["dzialanie"] == "eskaluj" and e.agenci == []
        assert e.tematy() == ["notarai: samonaprawa potrzebuje czlowieka"]
        assert st.ETYKIETA_ESKALACJA in e.stan.pobierz(ODCISK)["etykiety"]

    def test_nowy_blad_bez_naprawy_mail_raz(self, tmp_path):
        e = Srodowisko(tmp_path, tryb="wylaczona")
        e.potok().uruchom(dict(Z))
        e.potok().uruchom(dict(Z))
        assert e.tematy() == ["notarai: nowy blad na produkcji"] and e.agenci == []

    def test_duplikat_zdarzenia_po_naprawie_jest_pomijany(self, tmp_path):
        e = Srodowisko(tmp_path)
        e.stan.decyzja(dict(Z), "auto")
        e.stan.zamknij(ODCISK)
        wynik = e.potok().uruchom(dict(Z, czas="2000-01-01T00:00:00Z"))
        assert wynik["dzialanie"] == "brak" and e.agenci == []

    def test_przeglad_bez_kandydatow(self, tmp_path):
        e = Srodowisko(tmp_path)
        assert e.potok().uruchom({"zdarzenie": "przeglad"})["dzialanie"] == "brak"
        assert e.synchronizacje == 1            # przeglad ponawia zapis poprawek w repozytorium

    def test_przeglad_bierze_pierwszy_blad_bez_eskalacji(self, tmp_path):
        e = Srodowisko(tmp_path)
        a, b = dict(Z, odcisk="a" * 12, wystapien=5), dict(Z, odcisk="b" * 12, wystapien=2)
        e.stan.decyzja(a, "auto"); e.stan.etykieta(a["odcisk"], st.ETYKIETA_ESKALACJA)
        e.zal.kandydaci = lambda m: [a, b]
        wynik = e.potok().uruchom({"zdarzenie": "przeglad"})
        assert wynik["odcisk"] == "b" * 12 and wynik["werdykt"] == "auto"

    def test_zdarzenie_z_ladunkiem_base64(self, tmp_path):
        e = Srodowisko(tmp_path, tryb="wylaczona")
        szczegoly = dict(Z, ladunek_b64=base64.b64encode(json.dumps(Z).encode()).decode())
        assert e.potok().uruchom(szczegoly)["odcisk"] == ODCISK


class TestZatwierdzenie:
    def _czeka(self, tmp_path, **kw):
        e = Srodowisko(tmp_path, tryb="pr", **kw)
        e.potok().uruchom(dict(Z))
        return e

    def test_bez_flagi_nic_nie_wdraza(self, tmp_path):
        e = self._czeka(tmp_path)
        wynik = e.potok().uruchom({"zdarzenie": "zatwierdzenie", "odcisk": ODCISK})
        assert wynik["dzialanie"] == "brak" and e.wdroz.wdrozone == []

    def test_sfalszowane_zdarzenie_dla_nieistniejacej_poprawki(self, tmp_path):
        e = Srodowisko(tmp_path)
        assert e.potok().uruchom({"zdarzenie": "zatwierdzenie", "odcisk": "f" * 12})["dzialanie"] == "brak"

    def test_zatwierdzona_poprawka_przechodzi_testy_i_wdrozenie(self, tmp_path):
        e = self._czeka(tmp_path)
        ev = MagicMock(); ev.put_events.return_value = {"FailedEntryCount": 0}
        zat.zatwierdz(ODCISK, e.stan, ev, "arn:aws:iam::1:user/wlasciciel")
        wpis = ev.put_events.call_args.kwargs["Entries"][0]
        assert wpis["DetailType"] == "zatwierdzenie" and "ladunek_b64" in json.loads(wpis["Detail"])
        wynik = e.potok().uruchom({"zdarzenie": "zatwierdzenie", "odcisk": ODCISK})
        assert wynik["dzialanie"] == "zatwierdzone" and wynik["wdrozenie"] == "success"
        assert e.testy == ["testy"]
        assert (tmp_path / "sn" / "kandydat" / "app_modul.py").read_text() == "x = 2\n"
        assert e.stan.t.zapytaj("WDROZENIE")[0]["tryb"] == "zatwierdzone" and e.stan.auto_w_dobie() == 0
        assert e.stan.pobierz(ODCISK)["status"] == st.NAPRAWIONE
        assert e.stan.t.zapytaj("NAPRAWA")[0]["patch_klucz"] in e.s3            # swiezy patch w rejestrze

    def test_czerwone_testy_po_zatwierdzeniu_blokuja_wdrozenie(self, tmp_path):
        e = self._czeka(tmp_path)
        zat.zatwierdz(ODCISK, e.stan, MagicMock(put_events=MagicMock(return_value={})), "x")
        e.zal.uruchom_testy = lambda repo: 1
        assert e.potok().uruchom({"zdarzenie": "zatwierdzenie", "odcisk": ODCISK})["dzialanie"] == "testy_nieudane"
        assert e.wdroz.wdrozone == []

    def test_patch_niepasujacy_do_biezacej_produkcji(self, tmp_path):
        e = self._czeka(tmp_path)
        zat.zatwierdz(ODCISK, e.stan, MagicMock(put_events=MagicMock(return_value={})), "x")

        class Inny(AtrapaWdroz):
            def pobierz_zrodla(self, tag, cel, bucket):
                Path(cel).write_bytes(zip_drzewa(DRZEWO | {"app_modul.py": "x = 5\ny = 7\n"}))
        e.zal.wdroz = Inny()
        assert e.potok().uruchom({"zdarzenie": "zatwierdzenie", "odcisk": ODCISK})["dzialanie"] == "konflikt"
        assert "nie pasuje" in e.tematy()[-1]

    def test_zatwierdz_odmawia_gdy_nic_nie_czeka(self):
        s = st.Stan(st.TabelaPamiec())
        with pytest.raises(ValueError):
            zat.zatwierdz(ODCISK, s, MagicMock())


class TestTrybTestowy:
    def test_nieszkodliwa_zmiana_bez_agentow_z_wdrozeniem(self, tmp_path):
        e = Srodowisko(tmp_path, tryb="pr")      # tryb z parametru jest ignorowany w tescie
        wynik = e.potok(test=True).uruchom({"uwagi": "Test sciezki wdrozenia", "rodzaj": "reczne"})
        assert wynik["wdrozenie"] == "success" and e.agenci == [] and e.bramki_wywolania == []
        linie = (tmp_path / "sn" / "kandydat" / "docs" / "samonaprawa-testy-wdrozenia.md").read_text()
        assert "przebieg build-1: test sciezki wdrozenia (AWS)" in linie
        assert e.tematy() == ["notarai: test wdrozenia samonaprawy udany"]
        assert len(e.obs_wywolania) == 1

    def test_tryb_testowy_tez_cofa(self, tmp_path):
        e = Srodowisko(tmp_path, obserwacja={"werdykt": "cofnij", "powody": ["x"]})
        wynik = e.potok(test=True).uruchom({"uwagi": "Test sciezki wdrozenia", "rodzaj": "reczne"})
        assert wynik["wdrozenie"] == "cofnieto" and e.wdroz.wdrozone[-1][0] == PROD


# ---------------------------------------------------------------- Wdrozenie (boto3)

def _wdroz(**klienci):
    uruchom = MagicMock(return_value=SimpleNamespace(returncode=0, stderr="", stdout=""))
    w = wz.Wdrozenie(klienci={k: v for k, v in klienci.items()}, uruchom=uruchom, spij=lambda s: None)
    return w, uruchom


def _cfn(parametry, status="UPDATE_COMPLETE"):
    cfn = MagicMock()
    stos = {"StackStatus": status, "Parameters": [{"ParameterKey": k, "ParameterValue": v} for k, v in parametry.items()],
            "Outputs": [{"OutputKey": "RepozytoriumUri", "OutputValue": "127621462971.dkr.ecr.eu-central-1.amazonaws.com/notarai"},
                        {"OutputKey": "BucketZrodel", "OutputValue": "notarai-zrodla-1"},
                        {"OutputKey": "ProjektBudowania", "OutputValue": "notarai-obraz"}]}
    cfn.describe_stacks.return_value = {"Stacks": [stos]}
    return cfn


class TestWdrozenieAws:
    REPO = "127621462971.dkr.ecr.eu-central-1.amazonaws.com/notarai"

    def test_tag_z_obrazu(self):
        assert wz.tag_z_obrazu(f"{self.REPO}:abc123") == "abc123"
        assert wz.tag_z_obrazu("repo:5000/obraz") == ""

    def test_biezacy_tag_z_definicji_zadania_ecs(self):
        ecs = MagicMock()
        ecs.describe_services.return_value = {"services": [{"taskDefinition": "arn:td"}]}
        ecs.describe_task_definition.return_value = {"taskDefinition": {"containerDefinitions": [{"image": f"{self.REPO}:{PROD}"}]}}
        w, _ = _wdroz(ecs=ecs)
        assert w.aktualny_tag() == PROD
        ecs.describe_services.assert_called_with(cluster="notarai", services=["notarai"])

    def test_parametry_wdrozenia_z_biezacego_stosu(self):
        sm = MagicMock()
        sm.describe_secret.return_value = {"ARN": "arn:sekret"}
        cfn = _cfn({"EmailAlarmowy": "", "Administratorzy": "a@x.pl, b@x.pl", "Cpu": "1024", "Pamiec": "4096", "LiczbaKopii": "2"})
        w, _ = _wdroz(cloudformation=cfn, secretsmanager=sm)
        p = w.parametry_wdrozenia("sn-abcdef012345")
        assert p == ["TagObrazu=sn-abcdef012345", "Tokenomia=true", "EmailAlarmowy=a@x.pl", "SamonaprawaSekretArn=arn:sekret",
                     "Cpu=1024", "Pamiec=4096", "LiczbaKopii=2"]

    def test_aktualizacja_stosu_przez_role_cloudformation(self):
        cfn = _cfn({"EmailAlarmowy": "a@x.pl", "SamonaprawaSekretArn": "arn:s"})
        w, uruchom = _wdroz(cloudformation=cfn)
        w.aktualizuj_stos("sn-abcdef012345", Path("infra/notarai-aplikacja.yaml"))
        cmd = uruchom.call_args.args[0]
        assert cmd[:3] == ["aws", "cloudformation", "deploy"] and "--stack-name" in cmd
        assert cmd[cmd.index("--role-arn") + 1] == "arn:aws:iam::127621462971:role/notarai-cloudformation"
        assert "CAPABILITY_NAMED_IAM" in cmd and "--no-fail-on-empty-changeset" in cmd
        assert "TagObrazu=sn-abcdef012345" in cmd and "SamonaprawaSekretArn=arn:s" in cmd

    def test_deploy_cli_pada(self):
        w, uruchom = _wdroz(cloudformation=_cfn({}))
        uruchom.return_value = SimpleNamespace(returncode=255, stderr="boom", stdout="")
        with pytest.raises(wz.BladWdrozenia):
            w.aktualizuj_stos("sn-abcdef012345", Path("x.yaml"))

    def test_czekanie_na_stos_w_toku(self):
        cfn = MagicMock()
        cfn.describe_stacks.side_effect = [{"Stacks": [{"StackStatus": "UPDATE_IN_PROGRESS"}]},
                                           {"Stacks": [{"StackStatus": "UPDATE_COMPLETE"}]}]
        w, _ = _wdroz(cloudformation=cfn)
        assert w.czekaj_na_stos(75) is True and cfn.describe_stacks.call_count == 2

    def test_czekanie_na_stos_timeout(self):
        cfn = MagicMock()
        cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "UPDATE_IN_PROGRESS"}]}
        czas = iter(range(0, 10_000_000, 2000))
        w = wz.Wdrozenie(klienci={"cloudformation": cfn}, spij=lambda s: None, teraz=lambda: next(czas))
        assert w.czekaj_na_stos(75) is False

    def _pelne(self, obraz_po, tag_stosu_po, smoke=True):
        ecs = MagicMock()
        ecs.describe_services.return_value = {"services": [{"taskDefinition": "td"}]}
        ecs.describe_task_definition.return_value = {"taskDefinition": {"containerDefinitions": [{"image": obraz_po}]}}
        cfn = _cfn({"TagObrazu": tag_stosu_po})
        w, uruchom = _wdroz(ecs=ecs, cloudformation=cfn)
        wywolania = []

        def wykonaj(cmd, **kw):
            wywolania.append(cmd)
            kod = 0 if (cmd[0] == "aws" or smoke) else 1
            return SimpleNamespace(returncode=kod, stderr="", stdout="")
        w._uruchom = wykonaj
        return w, wywolania

    def test_wdrozenie_udane_z_smoke_testem(self):
        w, cmds = self._pelne(f"{self.REPO}:sn-abcdef012345", "sn-abcdef012345")
        wynik = w.wdroz("sn-abcdef012345", Path("s.yaml"), Path("."))
        assert wynik["wynik"] == "success" and ["python3", "scripts/smoke_public_demo.py"] in cmds

    def test_smoke_nie_przeszedl(self):
        w, _ = self._pelne(f"{self.REPO}:sn-abcdef012345", "sn-abcdef012345", smoke=False)
        assert w.wdroz("sn-abcdef012345", Path("s.yaml"), Path("."))["wynik"] == "blad"

    def test_inny_obraz_i_inny_tag_stosu_to_wyprzedzenie(self):
        w, _ = self._pelne(f"{self.REPO}:cccccccccccc", "cccccccccccc")
        assert w.wdroz("sn-abcdef012345", Path("s.yaml"), Path("."))["wynik"] == "wyprzedzone"

    def test_inny_obraz_przy_naszym_tagu_stosu_to_blad(self):
        w, _ = self._pelne(f"{self.REPO}:cccccccccccc", "sn-abcdef012345")
        assert w.wdroz("sn-abcdef012345", Path("s.yaml"), Path("."))["wynik"] == "blad"

    def test_zrodla_z_paczki_budowania_albo_kopii_samonaprawy(self, tmp_path):
        s3 = MagicMock()
        s3.download_file.side_effect = [Exception("404"), None]
        w, _ = _wdroz(s3=s3, cloudformation=_cfn({}))
        assert w.pobierz_zrodla(PROD, tmp_path / "z.zip", "bucket-sn").endswith(f"bucket-sn/zrodla/{PROD}.zip")
        assert s3.download_file.call_args_list[0].args[:2] == ("notarai-zrodla-1", f"notarai/zrodla-{PROD}.zip")

    def test_brak_paczki_zrodel_czytelny_blad(self, tmp_path):
        s3 = MagicMock()
        s3.download_file.side_effect = Exception("404")
        w, _ = _wdroz(s3=s3, cloudformation=_cfn({}))
        with pytest.raises(wz.BladWdrozenia, match="wygasaja"):
            w.pobierz_zrodla(PROD, tmp_path / "z.zip")

    def test_obraz_juz_w_ecr_nie_jest_budowany(self, tmp_path):
        w, _ = _wdroz(ecr=MagicMock(), cloudformation=_cfn({}), codebuild=MagicMock())
        w.zbuduj_obraz("sn-abcdef012345", tmp_path / "x.zip")
        w._k("codebuild").start_build.assert_not_called()

    def test_budowanie_obrazu_projekt_z_wyjscia_stosu(self, tmp_path):
        ecr, cb, s3 = MagicMock(), MagicMock(), MagicMock()
        ecr.describe_images.side_effect = type("ImageNotFoundException", (Exception,), {})()
        cb.start_build.return_value = {"build": {"id": "b1"}}
        cb.batch_get_builds.return_value = {"builds": [{"buildStatus": "SUCCEEDED"}]}
        w, _ = _wdroz(ecr=ecr, codebuild=cb, s3=s3, cloudformation=_cfn({}))
        w.zbuduj_obraz("sn-abcdef012345", tmp_path / "x.zip", "bucket-sn")
        arg = cb.start_build.call_args.kwargs
        assert arg["projectName"] == "notarai-obraz" and arg["sourceLocationOverride"] == "notarai-zrodla-1/notarai/zrodla-sn-abcdef012345.zip"
        assert arg["environmentVariablesOverride"][0]["value"] == "sn-abcdef012345"
        assert s3.upload_file.call_count == 2           # bucket budowania i kopia w buckecie samonaprawy


# ---------------------------------------------------------------- synchronizacja z repozytorium

class FakeGithub:
    def __init__(self, master=None, merge_pada=False, patch_zly=False):
        self.pliki = master if master is not None else {"app_modul.py": "x = 1\n"}
        self.wywolania, self.merge_pada = [], merge_pada

    def api(self, metoda, sciezka, dane=None):
        self.wywolania.append((metoda, sciezka, dane))
        if sciezka == "/git/ref/heads/master":
            return {"object": {"sha": "m" * 40}}
        if sciezka.startswith("/git/commits/") and metoda == "GET":
            return {"tree": {"sha": "t" * 40}}
        if sciezka.startswith("/contents/"):
            nazwa = sciezka.split("/contents/")[1].split("?")[0]
            if nazwa not in self.pliki:
                raise RuntimeError("404")
            return {"content": base64.b64encode(self.pliki[nazwa].encode()).decode()}
        if sciezka == "/git/blobs":
            return {"sha": "b" * 40}
        if sciezka == "/git/trees":
            return {"sha": "r" * 40}
        if sciezka == "/git/commits":
            return {"sha": "c" * 40}
        if sciezka == "/pulls":
            return {"number": 77}
        if sciezka.endswith("/merge"):
            if self.merge_pada:
                raise RuntimeError("HTTP 405")
            return {"merged": True}
        return {}


def _patch_x2(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    (r / "app_modul.py").write_text("x = 1\n")
    git(r, "init", "-q"); git(r, "add", "-A"); git(r, "commit", "-qm", "b")
    (r / "app_modul.py").write_text("x = 2\n")
    git(r, "commit", "-qam", "Samonaprawa: x")
    return git(r, "format-patch", "-1", "--stdout")


class TestSynchronizacja:
    def test_pr_i_scalenie_z_skip_ci(self, tmp_path):
        gh = FakeGithub()
        wynik = sync.synchronizuj_poprawke(gh, {"odcisk": ODCISK, "tag": "sn-1"}, _patch_x2(tmp_path))
        assert wynik["wynik"] == "zsynchronizowane" and wynik["pr"] == 77
        scalenie = next(w for w in gh.wywolania if w[1].endswith("/merge"))
        assert "[skip ci]" in scalenie[2]["commit_title"] and "[skip ci]" in scalenie[2]["commit_message"]
        commit = next(w for w in gh.wywolania if w[1] == "/git/commits" and w[0] == "POST")
        assert "[skip ci]" in commit[2]["message"] and commit[2]["parents"] == ["m" * 40]
        assert any(w[1] == "/pulls" for w in gh.wywolania)
        assert any(w[2] and w[2].get("labels") == ["samonaprawa"] for w in gh.wywolania)

    def test_juz_w_master_wykrywane_reverse_check(self, tmp_path):
        gh = FakeGithub(master={"app_modul.py": "x = 2\n"})
        assert sync.synchronizuj_poprawke(gh, {"odcisk": ODCISK}, _patch_x2(tmp_path))["wynik"] == "juz"
        assert not any(w[1] == "/pulls" for w in gh.wywolania)

    def test_konflikt_z_master(self, tmp_path):
        gh = FakeGithub(master={"app_modul.py": "x = 9\nz = 3\n"})
        wynik = sync.synchronizuj_poprawke(gh, {"odcisk": ODCISK}, _patch_x2(tmp_path))
        assert wynik["wynik"] == "blad" and "konflikt" in wynik["powod"]

    def test_scalenie_odmowione_zostawia_pr(self, tmp_path):
        wynik = sync.synchronizuj_poprawke(FakeGithub(merge_pada=True), {"odcisk": ODCISK}, _patch_x2(tmp_path))
        assert wynik["wynik"] == "pr_otwarty" and wynik["pr"] == 77

    def test_synchronizuj_wszystkie_oznacza_i_nie_kasuje(self, tmp_path):
        s = st.Stan(st.TabelaPamiec())
        p1 = s.zarejestruj_poprawke(ODCISK, "sn-1", PROD, "poprawki/1.patch")
        patch = _patch_x2(tmp_path)
        maile = []
        wynik = sync.synchronizuj_wszystkie(s, lambda k: patch, lambda: FakeGithub(), lambda t, m: maile.append(t))
        assert wynik[0]["wynik"] == "zsynchronizowane" and s.poprawka(p1)["status"] == st.ZSYNCHRONIZOWANE and maile == []

    def test_brak_tokenu_mail_raz_i_wpis_zostaje(self):
        s = st.Stan(st.TabelaPamiec())
        p1 = s.zarejestruj_poprawke(ODCISK, "sn-1", PROD, "poprawki/1.patch")
        maile = []
        for _ in range(3):
            sync.synchronizuj_wszystkie(s, lambda k: "", lambda: None, lambda t, m: maile.append((t, m)))
        assert s.poprawka(p1)["status"] == st.DO_ZSYNCHRONIZOWANIA and s.poprawka(p1)["proby_synchronizacji"] == 3
        assert len(maile) == 1 and "nie zapisana w repozytorium" in maile[0][0]
        assert "nadpisze" not in maile[0][1]       # straznik w wdrozenie.yml dolacza poprawke

    def test_porazka_pierwszej_zatrzymuje_kolejne(self):
        s = st.Stan(st.TabelaPamiec())
        s.zarejestruj_poprawke("a" * 12, "sn-1", PROD, "p1")
        s.zarejestruj_poprawke("b" * 12, "sn-2", "sn-1", "p2")

        def pobierz(k):
            raise OSError("s3")
        wynik = sync.synchronizuj_wszystkie(s, pobierz, lambda: FakeGithub(), lambda t, m: None)
        assert len(wynik) == 1 and len(s.poprawki_do_synchronizacji()) == 2

    def test_token_z_sekretu(self):
        sm = MagicMock()
        sm.get_secret_value.return_value = {"SecretString": json.dumps({"token": "github_pat_abc"})}
        assert sync.token_z_sekretu(sm) == "github_pat_abc"
        sm.get_secret_value.return_value = {"SecretString": json.dumps({"token": "brak"})}
        assert sync.token_z_sekretu(sm) == ""
        sm.get_secret_value.side_effect = Exception("AccessDenied")
        assert sync.token_z_sekretu(sm) == ""


# ---------------------------------------------------------------- straznik wdrozen z GitHuba

def _item(sk, klucz, status="do_zsynchronizowania", odcisk=ODCISK):
    return {"pk": {"S": "NAPRAWA"}, "sk": {"S": sk}, "status": {"S": status}, "patch_klucz": {"S": klucz},
            "odcisk": {"S": odcisk}, "proby_synchronizacji": {"N": "0"}}


class AtrapaAws:
    def __init__(self, items=None, blad_dynamo=None, patche=None):
        self.items, self.blad, self.patche, self.sns = items or [], blad_dynamo, patche or {}, []

    def __call__(self, cmd, **kw):
        if cmd[0] != "aws":
            return subprocess.run(cmd, **kw)
        if cmd[1] == "dynamodb":
            if self.blad:
                return SimpleNamespace(returncode=254, stdout="", stderr=self.blad)
            return SimpleNamespace(returncode=0, stdout=json.dumps({"Items": self.items}), stderr="")
        if cmd[1] == "s3":
            klucz = cmd[3].split("/", 3)[3]
            if klucz not in self.patche:
                return SimpleNamespace(returncode=1, stdout=b"", stderr=b"NoSuchKey")
            return SimpleNamespace(returncode=0, stdout=self.patche[klucz].encode(), stderr=b"")
        if cmd[1] == "sns":
            self.sns.append(cmd)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(cmd)


def _master(tmp_path, tresc="x = 1\n"):
    r = tmp_path / "master"
    r.mkdir()
    (r / "app_modul.py").write_text(tresc)
    git(r, "init", "-q"); git(r, "add", "-A"); git(r, "commit", "-qm", "master")
    return r


class TestStraznik:
    def test_naklada_poprawki_w_kolejnosci_i_zmienia_tag(self, tmp_path):
        patch = _patch_x2(tmp_path)
        aws = AtrapaAws([_item("2026-11-25T10:00:00Z#a", "poprawki/a.patch")], patche={"poprawki/a.patch": patch})
        repo = _master(tmp_path)
        tag, zastosowane, pominiete = sp.zastosuj(repo, "1" * 12, aws)
        assert zastosowane == ["2026-11-25T10:00:00Z#a"] and (repo / "app_modul.py").read_text() == "x = 2\n"
        assert tag == f"{'1' * 12}-sn{sp.skrot_poprawek(zastosowane)}" and tag != "1" * 12
        assert "Poprawki samonaprawy" in git(repo, "log", "-1", "--format=%s")   # commit lokalny, bez pusha

    def test_poprawka_juz_w_master_jest_pomijana(self, tmp_path):
        patch = _patch_x2(tmp_path)
        aws = AtrapaAws([_item("s#a", "poprawki/a.patch")], patche={"poprawki/a.patch": patch})
        tag, zastosowane, pominiete = sp.zastosuj(_master(tmp_path, "x = 2\n"), "1" * 12, aws)
        assert tag == "1" * 12 and zastosowane == [] and pominiete == ["s#a"]

    def test_zsynchronizowane_i_wycofane_nie_sa_stosowane(self, tmp_path):
        aws = AtrapaAws([_item("s#a", "p", status="zsynchronizowane"), _item("s#b", "p", status="wycofana")])
        assert sp.oczekujace(aws) == []

    def test_kolejnosc_wedlug_sk(self):
        aws = AtrapaAws([_item("2026-11-25T11:00:00Z#b", "b"), _item("2026-11-25T10:00:00Z#a", "a")])
        assert [p["patch_klucz"] for p in sp.oczekujace(aws)] == ["a", "b"]

    def test_patch_sie_nie_stosuje_glosna_porazka_i_mail(self, tmp_path, capsys):
        patch = _patch_x2(tmp_path)
        aws = AtrapaAws([_item("s#a", "poprawki/a.patch")], patche={"poprawki/a.patch": patch})
        repo = _master(tmp_path, "x = 9\nz = 3\n")
        plik_env = tmp_path / "env"
        kod = sp.main(["--tag", "1" * 12, "--repo", str(repo), "--zapisz-env", str(plik_env)], aws)
        assert kod == 1 and not plik_env.exists()
        assert len(aws.sns) == 1 and "ZATRZYMANE" in aws.sns[0][aws.sns[0].index("--message") + 1]
        assert "notarai-alarmy" in aws.sns[0][aws.sns[0].index("--topic-arn") + 1]
        assert "::error::" in capsys.readouterr().out

    def test_brak_patcha_w_s3_tez_glosna_porazka(self, tmp_path):
        aws = AtrapaAws([_item("s#a", "poprawki/brak.patch")])
        assert sp.main(["--tag", "1" * 12, "--repo", str(_master(tmp_path))], aws) == 1

    def test_brak_tabeli_to_brak_poprawek(self, tmp_path):
        aws = AtrapaAws(blad_dynamo="An error occurred (ResourceNotFoundException)")
        plik_env = tmp_path / "env"
        assert sp.main(["--tag", "1" * 12, "--repo", str(_master(tmp_path)), "--zapisz-env", str(plik_env)], aws) == 0
        assert plik_env.read_text() == f"TAG={'1' * 12}\n"

    def test_brak_uprawnien_nie_jest_cicho_pomijany(self, tmp_path):
        aws = AtrapaAws(blad_dynamo="AccessDeniedException")
        assert sp.main(["--tag", "1" * 12, "--repo", str(_master(tmp_path))], aws) == 1

    def test_tag_z_poprawkami_przechodzi_wzorzec_szablonu(self, tmp_path):
        patch = _patch_x2(tmp_path)
        aws = AtrapaAws([_item("s#a", "poprawki/a.patch")], patche={"poprawki/a.patch": patch})
        tag, _, _ = sp.zastosuj(_master(tmp_path), "0123456789ab", aws)
        wzorzec = yaml.safe_load(_szablon_tekst("notarai-aplikacja.yaml").replace("!Sub", "").replace("!Ref", "")
                                 .replace("!GetAtt", "").replace("!If", "").replace("!Not", "").replace("!Equals", "")
                                 .replace("!Select", "").replace("!Join", ""))["Parameters"]["TagObrazu"]["AllowedPattern"]
        import re
        assert re.fullmatch(wzorzec, tag) and re.fullmatch(wzorzec, "sn-0123456789ab") and re.fullmatch(wzorzec, "0123456789ab")
        assert not re.fullmatch(wzorzec, "latest") and not re.fullmatch(wzorzec, "sn-xyz")


# ---------------------------------------------------------------- zdarzenia, CLI

class TestZdarzenia:
    def test_zglos_i_aplikacja_buduja_ten_sam_ksztalt(self):
        import samonaprawa
        dane = {"odcisk": ODCISK, "rodzaj": "kod", "typ": "ValueError", "opis": "x"}
        a, b = samonaprawa.wpis_zdarzenia(dane), zg.wpis_zdarzenia("zgloszenie", dane)
        assert a == b

    def test_zglos_reczne(self):
        ev = MagicMock(); ev.put_events.return_value = {"FailedEntryCount": 0}
        assert zg.main(["Sporzadz projekt: blad modelu"], {"events": ev}) == 0
        wpis = ev.put_events.call_args.kwargs["Entries"][0]
        szczegoly = json.loads(wpis["Detail"])
        assert wpis["DetailType"] == "zgloszenie" and szczegoly["rodzaj"] == "reczne" and len(szczegoly["odcisk"]) == 12
        assert json.loads(base64.b64decode(szczegoly["ladunek_b64"]))["uwagi"].startswith("Sporzadz")

    def test_zglos_przeglad(self):
        ev = MagicMock(); ev.put_events.return_value = {"FailedEntryCount": 0}
        assert zg.main(["--przeglad"], {"events": ev}) == 0
        szczegoly = json.loads(ev.put_events.call_args.kwargs["Entries"][0]["Detail"])
        assert json.loads(base64.b64decode(szczegoly["ladunek_b64"])) == {"zdarzenie": "przeglad"}

    def test_zglos_test_startuje_build_z_trybem_testowym(self):
        cb = MagicMock(); cb.start_build.return_value = {"build": {"id": "notarai-samonaprawa:1"}}
        assert zg.main(["--test"], {"codebuild": cb}) == 0
        arg = cb.start_build.call_args.kwargs
        env = {e["name"]: e["value"] for e in arg["environmentVariablesOverride"]}
        assert arg["projectName"] == "notarai-samonaprawa" and env["SN_TEST_WDROZENIA"] == "1"
        assert pt.odkoduj_ladunek(env["SN_LADUNEK"])["rodzaj"] == "reczne"

    def test_zglos_bez_opisu_to_blad(self):
        with pytest.raises(SystemExit):
            zg.main([], {"events": MagicMock()})


# ---------------------------------------------------------------- infrastruktura i workflow

def _szablon_tekst(nazwa):
    return (KORZEN / "infra" / nazwa).read_text(encoding="utf-8")


class _L(yaml.SafeLoader):
    pass


_L.add_multi_constructor("!", lambda l, tag, n: (l.construct_scalar(n) if isinstance(n, yaml.ScalarNode)
                                                 else l.construct_sequence(n) if isinstance(n, yaml.SequenceNode)
                                                 else l.construct_mapping(n)))


def _szablon(nazwa):
    return yaml.load(_szablon_tekst(nazwa), _L)


def _akcje(rola):
    wynik = []
    for s in rola["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]:
        wynik += [s["Action"]] if isinstance(s["Action"], str) else s["Action"]
    return wynik


class TestInfraSamonaprawy:
    S = _szablon("notarai-samonaprawa.yaml")
    R = S["Resources"]

    def test_buildspec_w_szablonie_jest_taki_sam_jak_plik(self):
        wbudowany = yaml.safe_load(self.R["ProjektSamonaprawy"]["Properties"]["Source"]["BuildSpec"])
        assert wbudowany == yaml.safe_load((KORZEN / "infra" / "buildspec-samonaprawa.yml").read_text(encoding="utf-8"))
        polecenia = json.dumps(wbudowany)
        assert "potok.py" in polecenia and "notarai-budowanie" in polecenia and "zrodla-" in polecenia
        assert "git clone" not in polecenia and "github.com" not in polecenia

    def test_projekt_jedna_naprawa_naraz_180_minut_logi_30_dni(self):
        p = self.R["ProjektSamonaprawy"]["Properties"]
        assert p["Name"] == "notarai-samonaprawa" and p["ConcurrentBuildLimit"] == 1 and p["TimeoutInMinutes"] == 180
        assert p["Source"]["Type"] == "NO_SOURCE" and p["Environment"]["PrivilegedMode"] is False
        assert self.R["LogiPotoku"]["Properties"]["RetentionInDays"] == 30
        assert self.R["LogiPotoku"]["Properties"]["LogGroupName"] == "/aws/codebuild/notarai-samonaprawa"

    def test_tabela_dynamodb(self):
        p = self.R["Tabela"]["Properties"]
        assert p["TableName"] == "notarai-samonaprawa" and p["BillingMode"] == "PAY_PER_REQUEST"
        assert p["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is True
        assert p["SSESpecification"] == {"SSEEnabled": True, "SSEType": "KMS"}     # klucz zarzadzany AWS
        assert self.R["Tabela"]["DeletionPolicy"] == "Retain"

    def test_bucket_prywatny_szyfrowany_90_dni(self):
        p = self.R["BucketPoprawek"]["Properties"]
        assert all(p["PublicAccessBlockConfiguration"].values())
        assert p["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"
        assert p["LifecycleConfiguration"]["Rules"][0]["ExpirationInDays"] == 90
        assert "notarai-samonaprawa-" in p["BucketName"]

    def test_rola_agenta_tylko_bedrock_i_ufa_roli_potoku(self):
        r = self.R["RolaAgenta"]
        assert r["Properties"]["RoleName"] == "notarai-samonaprawa-agent" and r["DependsOn"] == "RolaPotoku"
        assert r["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]["Principal"]["AWS"].endswith("role/notarai-samonaprawa-codebuild")
        assert all(a.startswith("bedrock:") for a in _akcje(r))

    def test_rola_potoku_najmniejsze_uprawnienia(self):
        r = self.R["RolaPotoku"]
        stmts = r["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        akcje = _akcje(r)
        assert "*" not in akcje and not [a for a in akcje if a.endswith(":*")]
        assert not [a for a in akcje if a.startswith(("iam:", "ec2:", "kms:")) and a != "iam:PassRole"]
        passrole = next(s for s in stmts if s["Action"] == "iam:PassRole")
        assert passrole["Resource"].endswith("role/notarai-cloudformation")
        assert passrole["Condition"]["StringEquals"]["iam:PassedToService"] == "cloudformation.amazonaws.com"
        sekret = next(s for s in stmts if s["Sid"] == "TokenSynchronizacji")
        assert sekret["Resource"].endswith("secret:notarai/samonaprawa-github-??????")
        assert next(s for s in stmts if s["Sid"] == "StosAplikacji")["Resource"].endswith("stack/notarai-aplikacja/*")
        assert next(s for s in stmts if s["Sid"] == "Budowanie")["Resource"].endswith("project/notarai-obraz")
        assert next(s for s in stmts if s["Sid"] == "SesjaAgenta")["Resource"].endswith("role/notarai-samonaprawa-agent")
        assert not [a for a in akcje if a.startswith("bedrock:")]          # model tylko przez sesje agenta
        assert "secretsmanager:BatchGetSecretValue" not in akcje

    def test_reguly_eventbridge(self):
        z, a, p = self.R["RegulaZgloszen"]["Properties"], self.R["RegulaZatwierdzen"]["Properties"], self.R["RegulaPrzegladu"]["Properties"]
        assert z["EventPattern"]["source"] == ["notarai.samonaprawa"] and z["EventPattern"]["detail-type"] == ["zgloszenie"]
        assert a["EventPattern"]["detail-type"] == ["zatwierdzenie"]
        assert self.S["Parameters"]["HarmonogramPrzegladu"]["Default"] == "rate(30 minutes)" and p["ScheduleExpression"] == "HarmonogramPrzegladu"
        for regula in (z, a):
            cel = regula["Targets"][0]
            assert cel["InputTransformer"]["InputPathsMap"] == {"ladunek": "$.detail.ladunek_b64"}
            szablon_wejscia = json.loads(cel["InputTransformer"]["InputTemplate"].replace("<ladunek>", "QQ=="))
            assert szablon_wejscia["environmentVariablesOverride"][0]["name"] == "SN_LADUNEK"
        stale = json.loads(p["Targets"][0]["Input"])["environmentVariablesOverride"][0]["value"]
        assert pt.odkoduj_ladunek(stale) == {"zdarzenie": "przeglad"}

    def test_prefiks_i_brak_pauz_w_nazwach_zasobow(self):
        for zasob in self.R.values():
            for klucz in ("TableName", "RoleName", "Name", "BucketName", "AlarmName", "LogGroupName"):
                wartosc = zasob["Properties"].get(klucz)
                if isinstance(wartosc, str) and not wartosc.startswith("/aws"):
                    assert "notarai-" in wartosc
        assert "—" not in _szablon_tekst("notarai-samonaprawa.yaml") and "–" not in _szablon_tekst("notarai-samonaprawa.yaml")

    def test_alarm_na_bledy_potoku(self):
        assert self.R["AlarmPotoku"]["Properties"]["MetricName"] == "FailedBuilds"


class TestInfraAplikacjiIGithub:
    def test_rola_zadania_ma_tylko_put_events_na_domyslna_szyne(self):
        rola = _szablon("notarai-aplikacja.yaml")["Resources"]["RolaZadania"]["Properties"]["Policies"]
        pol = next(p for p in rola if isinstance(p, dict) and p.get("PolicyName") == "zdarzenia-samonaprawy")
        s = pol["PolicyDocument"]["Statement"][0]
        assert s["Action"] == "events:PutEvents" and s["Resource"].endswith("event-bus/default")

    def test_aplikacja_nie_czyta_juz_sekretu_github(self):
        szablon = _szablon_tekst("notarai-aplikacja.yaml")
        assert "Name: PIECZAPP_SAMONAPRAWA_GITHUB_TOKEN" not in szablon and "PolicyName: sekret-samonaprawy" not in szablon

    def test_rola_wdrozen_github_tylko_odczyt_rejestru_i_patchy(self):
        rola = _szablon("notarai-github.yaml")["Resources"]["RolaGithub"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        rejestr = next(s for s in rola if s.get("Sid") == "RejestrPoprawekSamonaprawy")
        assert sorted(rejestr["Action"]) == ["dynamodb:GetItem", "dynamodb:Query"] and rejestr["Resource"].endswith("table/notarai-samonaprawa")
        patche = next(s for s in rola if s.get("Sid") == "PatchePoprawekSamonaprawy")
        assert patche["Action"] == "s3:GetObject" and patche["Resource"].endswith("-${AWS::Region}/poprawki/*")
        assert next(s for s in rola if s.get("Sid") == "PowiadomienieStraznika")["Action"] == "sns:Publish"

    def test_paczki_zrodel_zyja_dluzej_niz_14_dni(self):
        reguly = _szablon("notarai-budowanie.yaml")["Resources"]["BucketZrodel"]["Properties"]["LifecycleConfiguration"]["Rules"]
        assert reguly[0]["ExpirationInDays"] >= 90


class TestWorkflowy:
    def test_straznik_przed_budowaniem_obrazu(self):
        w = yaml.safe_load((KORZEN / ".github/workflows/wdrozenie.yml").read_text(encoding="utf-8"))
        nazwy = [k["name"] for k in w["jobs"]["wdrozenie"]["steps"]]
        straznik = next(n for n in nazwy if "straznik" in n)
        assert nazwy.index("Sprawdz konto") < nazwy.index(straznik) < nazwy.index("Obraz w CodeBuild")
        krok = next(k for k in w["jobs"]["wdrozenie"]["steps"] if k["name"] == straznik)
        assert "straznik_poprawek.py" in krok["run"] and "$GITHUB_ENV" in krok["run"]

    def test_stary_workflow_tylko_recznie(self):
        tekst = (KORZEN / ".github/workflows/samonaprawa.yml").read_text(encoding="utf-8")
        w = yaml.safe_load(tekst)
        assert list(w[True]) == ["workflow_dispatch"]
        assert "wylaczony: samonaprawa dziala w AWS (docs/samonaprawa.md)" in tekst and "reczny awaryjny" in tekst

    def test_claude_md_wskazuje_potok_aws(self):
        tekst = (KORZEN / "CLAUDE.md").read_text(encoding="utf-8")
        assert "WYŁĄCZNIE przez potok AWS" in tekst and "notarai-samonaprawa" in tekst
        assert "WYŁĄCZNIE przez ten\n  workflow" not in tekst


def test_skrypt_postepu_bez_kopii_narzedzi_bierze_skrypt_z_paczki(tmp_path):
    """Regresja z proby 25.11.2026: postep.sh nie istnial w /tmp/sn/narzedzia przed pierwsza naprawa."""
    brak = tmp_path / "narzedzia"                        # kopia jeszcze nie powstala
    sciezka = pt.skrypt_postepu(brak)
    assert sciezka.name == "postep.sh" and sciezka.exists()
    assert sciezka.parent == Path(pt.__file__).resolve().parent
    brak.mkdir()
    (brak / "postep.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    assert pt.skrypt_postepu(brak) == brak / "postep.sh"   # kopia sprzed agenta ma pierwszenstwo
