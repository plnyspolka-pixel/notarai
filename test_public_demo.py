"""Regression tests for the public capability; no AWS or real tenant data."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import autoryzacja
import logowanie
import public_demo


def test_public_demo_isolated(monkeypatch):
    monkeypatch.setenv("NOTARAI_PUBLIC_DEMO", "1")
    monkeypatch.setattr(autoryzacja, "MULTI", True)
    monkeypatch.setattr(logowanie, "wlaczone", lambda: True)
    def forbidden(*args, **kwargs):
        raise AssertionError("demo reached production authentication/storage")
    monkeypatch.setattr(logowanie, "zaloguj", forbidden)
    monkeypatch.setattr(autoryzacja, "_wczytaj_rejestr", forbidden)
    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    app.include_router(autoryzacja.router_logowania)
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def production(path: str):
        raise AssertionError("demo reached production handler")
    client = TestClient(app)
    login = client.post("/api/logowanie", json={"email": "test", "haslo": "test"})
    assert login.status_code == 200
    assert login.json()["demo"] is True
    assert "Max-Age=0" in login.headers["set-cookie"]
    headers = {"Authorization": "Bearer " + login.json()["token"]}
    paired = client.post("/api/urzadzenia/rozszerzenie", headers=headers,
                         json={"nazwa": "Chrome - NotarAI"})
    assert paired.status_code == 200
    assert paired.json()["token"] == public_demo.HELPER_TOKEN
    helper = {"Authorization": "Bearer " + paired.json()["token"]}
    assert client.get("/api/pomocnik/zlecenia?wersja=r0.2", headers=helper).json() == []
    assert client.post("/api/pomocnik/odlacz", headers=helper, json={}).status_code == 200
    assert client.post("/api/pomocnik/klikamy", headers=helper, json={}).status_code == 403
    assert client.post("/api/logowanie", json={"email":"test","haslo":"wrong"}).status_code == 401
    assert client.get("/api/ustawienia", headers=headers).json()["kancelaria"] == public_demo.TENANT
    cases = client.get("/api/sprawy", headers=headers).json()
    assert len(cases) == 1 and cases[0]["id"] == public_demo.CASE
    assert client.get("/api/sprawy/"+public_demo.CASE, headers=headers).status_code == 200
    assert client.get("/api/sprawy/real-tenant-case", headers=headers).status_code == 403
    assert client.get("/api/sprawy", headers={**headers,"X-Serwis-Kancelaria":"other"}).status_code == 403
    for method, path in [
        ("GET","/api/admin"), ("GET","/api/hurtowe"), ("POST","/mcp"),
        ("POST","/api/finyou/platnosc"), ("POST","/api/kredyty/pakiet"),
        ("POST","/api/sprawy"), ("DELETE","/api/sprawy/"+public_demo.CASE),
        ("POST","/api/agent-glosowy"), ("POST","/api/pulpit-ai/glos"),
        ("POST","/api/pulpit-ai/samonaprawa/zglos"), ("POST","/api/pomocnik/parowanie"),
        ("GET","/api/korespondencja/oauth/powrot"), ("POST","/api/giif"),
        ("GET","/api/logowanie/odnow"), ("POST","/api/zespol"),
    ]:
        assert client.request(method,path,headers=headers).status_code == 403, path
    chat = client.post("/api/pulpit-ai/rozmowa", headers=headers, json={"wiadomosc":"kalendarz"})
    assert chat.status_code == 200 and "DEMO" in chat.json()["odpowiedz"]
    assert client.post("/api/pulpit-ai/rozmowa",headers=headers,content=b"x"*9000).status_code == 413
    monkeypatch.setenv("NOTARAI_PUBLIC_DEMO", "0")
    assert client.get("/api/sprawy",headers=headers).status_code == 403
    assert client.post("/api/logowanie",json={"email":"test","haslo":"test"}).status_code == 401
