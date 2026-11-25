"""Syntetyczne regresje PR 143. Bez AWS i bez danych kancelarii."""
import contextvars
import json
import re
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

import bedrock
import bedrock_chroniony as br
import magazyn
import osoby
import pseudonimizacja_lokalna as lokalna
from pseudonimizacja_aktu import (
    Osoba, SesjaPseudonimizacji, Wystapienie, DaneDodatkowe, WymagaWeryfikacji,
)


def przejrzany(tekst, **kw):
    return br.PrzejrzanyTekst(tekst, br.odcisk_tekstu(tekst), **kw)


@pytest.fixture
def sesja():
    s = SesjaPseudonimizacji((
        Osoba("losowy-a", ("Jan", "Adam"), "Kowalski",
              aliasy=("Jana Kowalskiego", "Janowi Kowalskiemu"),
              role=("Zbywca", "Pełnomocnik")),
        Osoba("losowy-b", ("Anna",), "Kowalska-Nowak",
              role=("Nabywca",)),
    ))
    yield s
    s.zamknij()


def test_round_trip_rozne_formy(sesja):
    tekst = "Jan Adam Kowalski, Jan Kowalski, Jana Kowalskiego, Janowi Kowalskiemu. Anna Kowalska-Nowak."
    maska = sesja.pseudonimizuj(tekst)
    assert "Kowalsk" not in maska
    assert len(set(re.findall(r"\[\[NA_[^ ]*?_P001_NAZWA_\d+\]\]", maska))) == 4
    assert "_P002_" in maska
    assert sesja.przywroc(maska) == tekst


def test_rola_wymaga_kontekstu(sesja):
    assert sesja.kandydaci_roli("Pełnomocnik") == ("losowy-a",)
    tekst = "Zbywca"
    token = sesja.pseudonimizuj(tekst, potwierdzone=(Wystapienie(0, len(tekst), "losowy-a", "ROLA"),))
    assert "_P001_ROLA_" in token
    assert sesja.przywroc(token) == tekst
    with pytest.raises(WymagaWeryfikacji, match="ROLE_PERSON_CONFLICT"):
        sesja.pseudonimizuj(tekst, potwierdzone=(Wystapienie(0, len(tekst), "losowy-b", "ROLA"),))


def test_homonimy():
    s = SesjaPseudonimizacji((
        Osoba("a", ("Jan",), "Kowalski", "85031512337"),
        Osoba("b", ("Jan",), "Kowalski"),
    ))
    with pytest.raises(WymagaWeryfikacji, match="AMBIGUOUS"):
        s.pseudonimizuj("Jan Kowalski")
    tekst = "Jan Kowalski"
    assert "_P002_" in s.pseudonimizuj(tekst, potwierdzone=(Wystapienie(0, len(tekst), "b"),))
    with pytest.raises(WymagaWeryfikacji, match="PESEL_PERSON_CONFLICT"):
        s.pseudonimizuj("85031512337", potwierdzone=(Wystapienie(0, 11, "b", "PESEL"),))


def test_nieznane_tokeny_i_iniekcja(sesja):
    maska = sesja.pseudonimizuj("Jan Kowalski")
    obca = SesjaPseudonimizacji(sesja.osoby)
    with pytest.raises(WymagaWeryfikacji, match="UNKNOWN_TOKEN"):
        obca.przywroc(maska)
    with pytest.raises(WymagaWeryfikacji, match="MALFORMED_TOKEN"):
        sesja.przywroc(maska[:-1])
    with pytest.raises(WymagaWeryfikacji, match="TOKEN_IN_SOURCE"):
        sesja.pseudonimizuj(maska)
    with pytest.raises(WymagaWeryfikacji, match="NAME_PERSON_CONFLICT"):
        sesja.pseudonimizuj("Jan Kowalski", potwierdzone=(Wystapienie(0, 12, "losowy-b"),))


def test_legacy_nie_paruje_po_kolejnosci():
    pola = [
        {"nazwa": "aaa: zbywca", "wartosc": "Jan i Ewa małżonkowie Kowalscy"},
        {"nazwa": "+ PESEL zbywcy", "wartosc": "85031512337"},
    ]
    wynik = osoby.osoby_ze_sprawy(pola)
    assert len([o for o in wynik if o["imie_nazwisko"]]) == 2
    assert all(not o["pesel"] for o in wynik if o["imie_nazwisko"])
    assert any(o["pesel"] == "85031512337" and not o["imie_nazwisko"] for o in wynik)


def test_bramka_blokuje_istniejace_sciezki(monkeypatch):
    monkeypatch.setenv("PIECZAPP_BEDROCK_CHRONIONY", "1")
    raw = Mock()
    monkeypatch.setattr(bedrock, "_klient_bedrock", raw)
    for metoda in ("converse", "converse_stream", "invoke_model"):
        with pytest.raises(WymagaWeryfikacji):
            getattr(bedrock._klient(), metoda)(messages=[{"text": "surowe"}])
    with pytest.raises(WymagaWeryfikacji):
        bedrock._strumien({"messages": [{"content": [{"image": {"source": {"bytes": b"scan"}}}]}]})
    with pytest.raises(WymagaWeryfikacji):
        bedrock.tura_z_narzedziami("surowe", [], [])
    assert not raw.mock_calls


def test_bramka_tekstowa_integracja(monkeypatch, sesja, caplog):
    monkeypatch.setenv("PIECZAPP_BEDROCK_CHRONIONY", "1")
    monkeypatch.setattr(bedrock.config, "MODEL", "eu.anthropic.claude-sonnet-4-6")
    monkeypatch.setattr(bedrock.tokenomia, "dolicz", lambda *a: None)
    raw = Mock()
    monkeypatch.setattr(bedrock, "_klient_bedrock", raw)
    tekst = "Jan Kowalski, adres Testowa 10."
    a = tekst.index("Testowa")
    def echo(**zadanie):
        assert "Jan Kowalski" not in json.dumps(zadanie)
        assert "Testowa" not in json.dumps(zadanie)
        from conftest import sprawdz_zgodnosc_z_api_bedrock
        # Walidacja SDK istniejąca w repo jest również wykonywana przez główną suite.
        return {"stopReason": "end_turn", "usage": {}, "output": {"message": {
            "content": [{"text": zadanie["messages"][0]["content"][0]["text"]}]}}}
    raw.converse.side_effect = echo
    assert bedrock.rozmowa_chroniona(sesja, przejrzany("Odpowiedz."),
        [("user", przejrzany(tekst, dodatkowe=(DaneDodatkowe(a, len(tekst)-1, "ADRES"),)))]) == tekst
    assert raw.converse.call_count == 1
    assert "Jan Kowalski" not in caplog.text
    with pytest.raises(WymagaWeryfikacji):
        bedrock._klient().converse(messages=[])
    assert raw.converse.call_count == 1


def test_stara_wersja_i_cross_tenant(monkeypatch, sesja):
    monkeypatch.setenv("PIECZAPP_BEDROCK_CHRONIONY", "1")
    raw = Mock()
    with pytest.raises(WymagaWeryfikacji, match="REVIEW_STALE"):
        br.rozmowa(raw, sesja, przejrzany("System"),
                   [("user", br.PrzejrzanyTekst("Nowa", br.odcisk_tekstu("Stara")))],
                   model="eu.test", max_tokenow=10)
    assert not raw.mock_calls
    zadanie = {"messages": []}
    with br._zezwol("converse", zadanie):
        br.sprawdz("converse", zadanie)
        with pytest.raises(WymagaWeryfikacji):
            br.sprawdz("converse", {"messages": ["zmiana"]})
        t = magazyn.kancelaria_var.set("inna-kancelaria")
        try:
            with pytest.raises(WymagaWeryfikacji):
                br.sprawdz("converse", zadanie)
        finally:
            magazyn.kancelaria_var.reset(t)
        with ThreadPoolExecutor(max_workers=1) as pool:
            ctx = contextvars.copy_context()
            with pytest.raises(WymagaWeryfikacji):
                pool.submit(ctx.run, br.sprawdz, "converse", zadanie).result()


def test_ocr_brak_binarnego_fallbacku(monkeypatch):
    def brak(*a, **kw):
        raise FileNotFoundError()
    monkeypatch.setattr(lokalna.subprocess, "run", brak)
    with pytest.raises(WymagaWeryfikacji, match="LOCAL_OCR_FAILED"):
        lokalna.ocr_png(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(WymagaWeryfikacji, match="OCR_INVALID_PNG"):
        lokalna.ocr_png(b"pdf")


def test_lokalne_propozycje():
    tekst = "kontakt@example.test; LU1I/00012345/6; ABC 123456"
    assert {x.typ for x in lokalna.propozycje(tekst)} >= {"EMAIL", "KW", "DOWOD"}
