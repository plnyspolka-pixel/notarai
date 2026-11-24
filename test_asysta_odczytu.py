"""Offline tests: no production records and no AWS calls."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

import asysta_odczytu as a
import autoryzacja
import magazyn


@pytest.fixture
def office(monkeypatch, tmp_path):
    monkeypatch.setattr(a, "ENABLED", True)
    monkeypatch.setattr(a, "REGION", "eu-central-1")
    monkeypatch.setattr(autoryzacja, "MULTI", False)
    monkeypatch.setattr(magazyn, "pobierz_sprawe", lambda path: True)
    monkeypatch.setattr(magazyn, "utrwal_sprawe", lambda path: None)
    monkeypatch.setattr(magazyn, "u_klienta", lambda: False)
    monkeypatch.setattr(a.config, "SPRAWY", tmp_path, raising=False)
    folder = tmp_path / "abc123"
    folder.mkdir()
    (folder / "sprawa.json").write_text('{"id":"abc123"}', "utf-8")
    (folder / "projekt.txt").write_text("Termin wydania: 10 grudnia 2026.", "utf-8")
    return SimpleNamespace(state=SimpleNamespace()), folder


def test_state_is_unmodified(office):
    request, _ = office
    state = a.get_case("abc123", request)
    assert state["formalny_odczyt"] is False
    assert len(state["sha"]) == 64
    assert "10 grudnia" in state["tekst"]


def test_notary_original_is_annotation_only(office):
    request, folder = office
    old = (folder / "projekt.txt").read_text("utf-8")
    req = a.Approval(sprawa="abc123", sha=a.digest(old), tryb="oryginal",
                     przed="10 grudnia", po="15 grudnia", powod="Uzgodnienie stron")
    result = a.approve(req, request)
    assert result["tryb"] == "oryginal"
    assert result["tekst"] == old
    assert not list((folder / "asysta").glob("*.docx"))
    assert (folder / "projekt.txt").read_text("utf-8") == old
    assert a.revisions(folder)[0]["original_modified"] is False


def test_approved_draft_creates_version_without_overwriting(office, monkeypatch):
    request, folder = office
    monkeypatch.setattr(a.dokumenty, "tekst_na_docx",
                        lambda text, path, **kw: path.write_bytes(b"FAKE_DOCX"))
    monkeypatch.setattr(a.ustawienia_kancelarii, "wczytaj", lambda: {"braki": "opis"})
    old = (folder / "projekt.txt").read_text("utf-8")
    req = a.Approval(sprawa="abc123", sha=a.digest(old), tryb="projekt",
                     przed="10 grudnia", po="15 grudnia")
    result = a.approve(req, request)
    assert "15 grudnia" in result["tekst"]
    assert (folder / "projekt.txt").read_text("utf-8") == old
    assert (folder / "asysta" / (result["id"] + ".docx")).is_file()
    assert a.get_case("abc123", request)["sha"] == result["sha"]


def test_revision_conflict_is_rejected(office):
    request, folder = office
    with pytest.raises(HTTPException) as err:
        a.approve(a.Approval(sprawa="abc123", sha="0" * 64,
                             tryb="projekt", przed="10 grudnia", po="15 grudnia"), request)
    assert err.value.status_code == 409
    assert not (folder / "asysta").exists()


def test_duplicate_anchor_is_rejected():
    with pytest.raises(HTTPException) as err:
        a.validate_edit("data data", "data", "termin")
    assert err.value.status_code == 409


def test_failed_model_anchor_never_applied(office, monkeypatch):
    request, folder = office
    monkeypatch.setattr(a, "model_suggestion",
                        lambda text, instruction: {"before": "not there", "after": "changed", "reason": ""})
    sha = a.get_case("abc123", request)["sha"]
    with pytest.raises(HTTPException) as err:
        a.propose(a.Suggestion(sprawa="abc123", sha=sha, polecenie="Zmień termin"), request)
    assert err.value.status_code == 409
    assert not (folder / "asysta").exists()


@pytest.mark.parametrize("origin,host,valid", [
    ("https://app.notarai.pl", "app.notarai.pl", True),
    ("http://localhost:8000", "localhost:8000", True),
    ("https://wrong.example", "app.notarai.pl", False),
    ("null", "app.notarai.pl", False),
    ("", "app.notarai.pl", False),
])
def test_websocket_origin(origin, host, valid):
    assert bool(a.origin_ok(origin, host)) is valid


def test_stream_requires_aws_optout(office, monkeypatch):
    monkeypatch.delenv("PIECZAPP_TRANSCRIBE_OPTOUT", raising=False)
    with pytest.raises(HTTPException) as err:
        a.auth_socket("")
    assert err.value.status_code == 503


def test_notary_only_approval(monkeypatch):
    monkeypatch.setattr(a, "ENABLED", True)
    monkeypatch.setattr(a, "REGION", "eu-central-1")
    monkeypatch.setattr(autoryzacja, "MULTI", True)
    monkeypatch.setattr(autoryzacja, "_osoba_w_kancelarii",
                        lambda *args: {"rola": "czlonek", "stanowisko": "aplikant"})
    monkeypatch.setattr(autoryzacja, "_przechowywanie", lambda *args: "chmura")
    request = SimpleNamespace(state=SimpleNamespace(email="demo@invalid.example",
                                                     kancelaria="demo", serwis=False))
    with pytest.raises(HTTPException) as err:
        a.actor(request, approve=True)
    assert err.value.status_code == 403


def test_eu_only(office, monkeypatch):
    monkeypatch.setattr(a, "REGION", "us-east-1")
    with pytest.raises(HTTPException) as err:
        a.get_case("abc123", office[0])
    assert err.value.status_code == 503
