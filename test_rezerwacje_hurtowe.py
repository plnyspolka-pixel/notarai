"""B2B REST and MCP booking tests; only synthetic details, no real parties."""
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import autoryzacja
import config
import magazyn
import rezerwacje_hurtowe as h


@pytest.fixture
def scena(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja, "ADMIN_TOKEN", "test-secret-admin")
    monkeypatch.setattr(autoryzacja, "_CACHE", None)
    monkeypatch.setattr(autoryzacja, "_CACHE_S", 0.0)
    assert magazyn.TRYB == "lokalny"
    autoryzacja._zapisz_rejestr({
        "x": {"id": "biuro-a", "nazwa": "Kancelaria A", "aktywna": True,
              "umowa": {"zaakceptowano": "2026-11-01"}, "przechowywanie": "chmura"},
        "y": {"id": "biuro-b", "nazwa": "Kancelaria B", "aktywna": True,
              "umowa": {"zaakceptowano": "2026-11-01"}, "przechowywanie": "chmura"},
    })
    dzien = (datetime.now(h.STREFA) + timedelta(days=3)).date().isoformat()
    p = {"wlaczone": True, "miasto": "Lublin", "adres": "Testowa 1",
         "godziny": {str(i): ["09:00", "17:00"] for i in range(7)},
         "czas_minut": 60, "wyprzedzenie_godzin": 1, "max_dni": 60}
    for office in ("biuro-a", "biuro-b"):
        with h._WBiurze(office):
            magazyn.zmien_plik_kancelarii("rezerwacje_hurtowe",
                                          lambda aktualne: aktualne.update(p), {})
    import app
    klient = TestClient(app.app)
    administrator = {"Authorization": "Bearer test-secret-admin"}
    def partner(nazwa, biura):
        odp = klient.post("/api/admin/hurtowi", json={"nazwa": nazwa, "kancelarie": biura},
                          headers=administrator)
        assert odp.status_code == 201, odp.text
        return {"Authorization": "Bearer " + odp.json()["api_key"]}, odp.json()["id"]
    return klient, dzien, partner, administrator


def wizyta(dzien, **zmiany):
    return {"kancelaria": "biuro-a", "data": dzien, "godzina": "09:00",
            "rodzaj": "sprzedaż", "uczestnicy": "Jan Testowy",
            "telefon": "600 000 000", "zewnetrzne_id": "K-1020",
            "idempotency_key": "unit-test-appointment-0001",
            "potwierdzam": True, **zmiany}


def test_api_rezerwacje_idempotencja_kolizja_anulowanie(scena):
    client, dzien, dodaj, admin = scena
    a, a_id = dodaj("Hurtownik A", ["biuro-a"])
    b, b_id = dodaj("Hurtownik B", ["biuro-a"])
    c, c_id = dodaj("Inne biuro", ["biuro-b"])

    assert client.get("/api/hurtowe/kancelarie", headers=a).json()[0]["id"] == "biuro-a"
    assert client.get("/api/hurtowe/dostepnosc",
                      params={"kancelaria": "biuro-b", "data": dzien}, headers=a).status_code == 404
    assert client.get("/api/hurtowe/kancelarie", headers=c).json()[0]["id"] == "biuro-b"

    dane = wizyta(dzien)
    brak = client.post("/api/hurtowe/rezerwacje",
                       headers=a, json={**dane, "potwierdzam": False})
    assert brak.status_code == 400
    stworz = client.post("/api/hurtowe/rezerwacje", headers=a, json=dane)
    assert stworz.status_code == 201, stworz.text
    id_w = stworz.json()["id"]
    powtor = client.post("/api/hurtowe/rezerwacje", headers=a, json=dane)
    assert powtor.status_code == 201 and powtor.json()["id"] == id_w
    inny_payload = client.post("/api/hurtowe/rezerwacje", headers=a,
                               json={**dane, "uczestnicy": "Ktoś inny"})
    assert inny_payload.status_code == 409
    kolizja = client.post("/api/hurtowe/rezerwacje", headers=b, json={
        **dane, "idempotency_key": "unit-test-appointment-0002"})
    assert kolizja.status_code == 409
    assert client.get("/api/hurtowe/rezerwacje",
                      params={"kancelaria": "biuro-a"}, headers=b).json() == []

    terminy = client.get("/api/hurtowe/dostepnosc",
                         params={"kancelaria": "biuro-a", "data": dzien},
                         headers=b).json()["terminy"]
    assert "09:00" not in {x["godzina"] for x in terminy}
    przenies = client.put(f"/api/hurtowe/rezerwacje/{id_w}",
                          params={"kancelaria": "biuro-a"},
                          json={"data": dzien, "godzina": "10:00", "potwierdzam": True},
                          headers=a)
    assert przenies.status_code == 200, przenies.text
    assert przenies.json()["godzina"] == "10:00"
    anuluj = client.post(f"/api/hurtowe/rezerwacje/{id_w}/anuluj",
                         params={"kancelaria": "biuro-a"}, json={"potwierdzam": True},
                         headers=a)
    assert anuluj.status_code == 200 and anuluj.json()["status"] == "anulowana"
    znow = client.get("/api/hurtowe/dostepnosc",
                      params={"kancelaria": "biuro-a", "data": dzien}, headers=b)
    assert "10:00" in {x["godzina"] for x in znow.json()["terminy"]}
    with h._WBiurze("biuro-a"):
        assert h.kalendarz.lista() == []   # canceled booking hidden from office UI
        assert len(magazyn.wczytaj_plik_kancelarii("kalendarz", [])) == 1

    lista_admin = client.get("/api/admin/hurtowi", headers=admin).json()
    assert all("hash" not in p and "api_key" not in p for p in lista_admin)
    assert client.delete(f"/api/admin/hurtowi/{a_id}", headers=admin).status_code == 200
    assert client.get("/api/hurtowe/kancelarie", headers=a).status_code == 401


def test_mcp_nowoczesny_protokol_i_izolacja(scena):
    client, dzien, dodaj, _ = scena
    a, _ = dodaj("Hurtownik A", ["biuro-a"])
    def rpc(method, params=None, *, headers=None):
        params = {"_meta": {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {}}, **(params or {})}
        hds = {**a, "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": method,
               **({"Mcp-Name": params["name"]} if method == "tools/call" else {}),
               **(headers or {})}
        return client.post("/mcp", headers=hds,
                           json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    assert rpc("server/discover").json()["result"]["supportedVersions"] == ["2026-07-28"]
    tools = rpc("tools/list").json()["result"]["tools"]
    assert "wolne_terminy" in {x["name"] for x in tools}
    odp = rpc("tools/call", {"name": "wolne_terminy",
                              "arguments": {"kancelaria": "biuro-a", "data": dzien}})
    assert odp.status_code == 200 and not odp.json()["result"]["isError"]
    assert json.loads(odp.json()["result"]["content"][0]["text"])["terminy"]
    assert rpc("tools/list", headers={"Origin": "https://zly.example"}).status_code == 403
    assert rpc("tools/list", headers={"MCP-Protocol-Version": "2025-06-18"}).status_code == 400
    assert rpc("tools/call", {"name": "wolne_terminy",
               "arguments": {"kancelaria": "biuro-b", "data": dzien}}).json()["result"]["isError"]


def test_polityka_wymaga_zgody_i_jest_scisla(scena):
    client, dzien, dodaj, _ = scena
    a, _ = dodaj("Hurtownik A", ["biuro-a"])
    with h._WBiurze("biuro-a"):
        magazyn.zmien_plik_kancelarii("rezerwacje_hurtowe",
                                      lambda p: p.update({"wlaczone": False}), {})
    assert client.get("/api/hurtowe/kancelarie", headers=a).json() == []
    assert client.post("/api/hurtowe/rezerwacje", headers=a, json=wizyta(dzien)).status_code == 404
    # Settings may be changed by office owner in SaaS, not by anonymous request.
    assert client.put("/api/rezerwacje-hurtowe/ustawienia", json={
        "wlaczone": True, "miasto": "Lublin", "adres": "Testowa 1",
        "godziny": {"0": ["09:00", "17:00"]}}).status_code == 403
    with pytest.raises(Exception):
        h._popraw_polityke(h.Polityka(wlaczone=True, miasto="Lublin", adres="",
                                      godziny={"0": ["09:00", "17:00"]}))


def test_portal_b2b_i_link_na_stronie(scena):
    client, _, _, _ = scena
    portal = client.get("/hurtowe")
    assert portal.status_code == 200
    assert "Otwórz terminarz" in portal.text
    assert "/static/hurtowe.js" in portal.text
    assert client.get("/static/hurtowe.js").status_code == 200
    assert client.get("/api/hurtowe/kancelarie").status_code == 401
    from pathlib import Path
    strona = (Path(__file__).parent / "strona" / "index.html").read_text("utf-8")
    assert "https://app.notarai.pl/hurtowe" in strona
    assert "Rezerwacje B2B" in strona


def test_rezerwacja_niestandardowej_czynnosci(scena):
    client, dzien, nowy, _ = scena
    klucz, _ = nowy("Partner z testem", ["biuro-a"])
    dane = wizyta(dzien, rodzaj="inne", rodzaj_inny="Umowa spółki",
                  idempotency_key="niestandardowa-czynnosc-001")
    odp = client.post("/api/hurtowe/rezerwacje", json=dane, headers=klucz)
    assert odp.status_code == 201, odp.text
    with h._WBiurze("biuro-a"):
        wpis = h.kalendarz.lista()[0]
        assert wpis["rodzaj_inny"] == "Umowa spółki"
