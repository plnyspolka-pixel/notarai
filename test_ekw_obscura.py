"""Offline tests: Obscura MCP protocol is mocked; never contacts the EKW website."""
import json

import httpx
import pytest

import ekw
import ekw_obscura
import ekw_polecenia
import magazyn

KW = "WA4M/00160286/2"
TOOLS = ("browser_navigate", "browser_fill_form", "browser_evaluate", "browser_close")


class AtrapaMCP:
    def __init__(self, blocked=False, incomplete=False):
        self.stage = "start"
        self.section = ""
        self.blocked = blocked
        self.incomplete = incomplete
        self.calls = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        payload = json.loads(req.content)
        self.calls.append(payload)
        assert req.headers["authorization"] == "Bearer unit-test-placeholder"
        if payload["method"] == "tools/list":
            result = {"tools": [{"name": x} for x in TOOLS]}
        else:
            name = payload["params"]["name"]
            args = payload["params"]["arguments"]
            if name == "browser_navigate":
                assert args["url"] == ekw_obscura.PORTAL
                self.stage = "search"
                value = "ok"
            elif name == "browser_fill_form":
                assert [x["value"] for x in args["fields"]] == ["WA4M", "00160286", "2"]
                value = "ok"
            elif name == "browser_evaluate":
                expr = args["expression"]
                if "location.href" in expr:
                    text = {
                        "search": "Wyszukiwanie księgi wieczystej",
                        "choice": "Przeglądanie aktualnej treści",
                        "main": f"TREŚĆ KSIĘGI WIECZYSTEJ NR {KW}",
                        "section": f"TREŚĆ KSIĘGI WIECZYSTEJ NR {KW} Dział {self.section}",
                    }.get(self.stage, "")
                    if self.blocked:
                        text = "Error 15 - Access Denied - Incapsula"
                    tables = ("BRAK WPISÓW" if self.section == "IV" else
                              f"Dział {self.section} | rubryka | wpis testowy | {self.section}00")
                    if self.incomplete:
                        tables = "x"
                        text = "x"
                    value = json.dumps({"url": ekw_obscura.PORTAL, "title": "EKW",
                                        "text": text, "tables": tables if self.stage == "section" else ""},
                                       ensure_ascii=False)
                elif '"kind": "search"' in expr:
                    self.stage = "choice"
                    value = "CLICKED"
                elif '"kind": "current"' in expr:
                    self.stage = "main"
                    value = "CLICKED"
                elif '"kind": "section"' in expr:
                    self.stage = "section"
                    self.section = expr.split('"label": "Dzial ', 1)[1].split('"', 1)[0]
                    value = "CLICKED"
                else:
                    raise AssertionError("Unknown DOM operation")
            elif name == "browser_close":
                value = "closed"
            else:
                raise AssertionError(name)
            result = {"content": [{"type": "text", "text": value}], "isError": False}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": result})


@pytest.fixture
def ustawienia(monkeypatch):
    monkeypatch.setenv("PIECZAPP_OBSCURA_MCP_URL", "http://127.0.0.1:13000/mcp")
    monkeypatch.setenv("PIECZAPP_OBSCURA_MCP_TOKEN", "unit-test-placeholder")
    monkeypatch.setenv("PIECZAPP_OBSCURA_KANCELARIA", "lokalna")
    token = magazyn.kancelaria_var.set("lokalna")
    yield
    magazyn.kancelaria_var.reset(token)


def test_obscura_provider_and_five_sections(ustawienia):
    assert ekw.dostawca() == "obscura"
    stub = AtrapaMCP()
    with httpx.Client(transport=httpx.MockTransport(stub)) as client:
        result = ekw.pobierz_obscura(KW, client)
    assert result["dostawca"] == "obscura"
    assert len(result["dzialy"]) == 5
    assert [x["oznaczenie"] for x in result["dzialy"]] == ["I-O", "I-Sp", "II", "III", "IV"]
    assert result["dzialy"][-1]["pusty"] is True
    assert sum(x["pusty"] for x in result["dzialy"]) == 1
    assert any(x.get("params", {}).get("name") == "browser_close" for x in stub.calls)


def test_imperva_denied_never_returns_book(ustawienia):
    with httpx.Client(transport=httpx.MockTransport(AtrapaMCP(blocked=True))) as client:
        with pytest.raises(ekw.BladEKW) as error:
            ekw.pobierz_obscura(KW, client)
    assert error.value.kod == "blokada"


def test_incomplete_sections_fail_closed(ustawienia):
    with httpx.Client(transport=httpx.MockTransport(AtrapaMCP(incomplete=True))) as client:
        with pytest.raises(ekw.BladEKW) as error:
            ekw.pobierz_obscura(KW, client)
    assert error.value.kod == "niepelny"


def test_cannot_share_mcp_between_offices(ustawienia):
    token = magazyn.kancelaria_var.set("inna_kancelaria")
    try:
        assert not ekw_obscura.dostepne()
        assert ekw.dostawca() != "obscura"
    finally:
        magazyn.kancelaria_var.reset(token)


def test_mcp_endpoint_must_be_private_or_https(ustawienia, monkeypatch):
    monkeypatch.setenv("PIECZAPP_OBSCURA_MCP_URL", "http://obscura.example.com/mcp")
    with httpx.Client(transport=httpx.MockTransport(AtrapaMCP())) as client:
        with pytest.raises(ekw_obscura.ProblemObscura) as error:
            ekw_obscura.pobierz(KW, client)
    assert error.value.kod == "konfiguracja"


def test_natural_language_explicit_request(ustawienia):
    assert ekw_polecenia.rozpoznaj(f"Sprawdź księgę wieczystą {KW}", "") == (True, KW, "")
    assert ekw_polecenia.rozpoznaj("Sprawdź hipotekę", f"Dokument: {KW}") == (True, KW, "")
    assert ekw_polecenia.rozpoznaj(f"Numer księgi {KW}", "")[0] is False
    assert ekw_polecenia.rozpoznaj("Sprawdź KW", "")[1] is None
    assert ekw_polecenia.rozpoznaj("Sprawdź KW", f"{KW} oraz WA4M/00160286/2")[1] == KW
