from uuid import uuid4

from fastapi.testclient import TestClient

from worker.api import create_app


def test_lokalny_zapis_i_stenogram(tmp_path):
    (tmp_path / "vault.key").write_bytes(b"K" * 32)
    (tmp_path / "api.token").write_text("a" * 48)
    app = create_app(tmp_path, transcriber=lambda data: "Fikcyjna osoba Jan Kowalski, numer 12345.")
    client = TestClient(app, headers={"Authorization": "Bearer " + "a" * 48})
    url = f"/v2/nagrania/{uuid4()}"
    opis = {"sprawa": "Fikcyjna sprawa", "format": "video/webm"}
    assert client.put(url, json=opis).status_code == 200
    assert client.put(url, json=opis).status_code == 200
    assert client.put(url + "/czesci/1", content=b"fragment drugi").status_code == 200
    assert client.put(url + "/koniec", json={"czesci": 2}).status_code == 409
    assert client.put(url + "/czesci/0", content=b"fragment pierwszy").status_code == 200
    assert client.put(url + "/koniec", json={"czesci": 2}).status_code == 200
    assert client.get(url).content == b"fragment pierwszyfragment drugi"
    assert b"fragment pierwszy" not in (tmp_path / "vault.sqlite3").read_bytes()
    wynik = client.post(url + "/stenogram")
    assert wynik.status_code == 200, wynik.text
    assert wynik.json()["tekst"] == "Fikcyjna osoba Jan Kowalski, numer 12345."


def test_kalendarz_wspolnej_sprawy_i_kolizje(tmp_path):
    (tmp_path / "vault.key").write_bytes(b"K" * 32)
    (tmp_path / "api.token").write_text("a" * 48)
    app = create_app(tmp_path, transcriber=lambda data: [
        {"tekst": "Ustalmy odczyt na 14.12.2026 o 10:30.", "sekunda": 42},
        {"tekst": "Proszę dostarczyć pełnomocnictwo.", "sekunda": 55},
    ])
    client = TestClient(app, headers={"Authorization": "Bearer " + "a" * 48})
    base = "/v2/nagrania"

    def dodaj(sprawa):
        id = str(uuid4())
        url = f"{base}/{id}"
        assert client.put(url, json={"sprawa": sprawa, "sprawa_id": sprawa,
                                    "format": "audio/webm", "stanowisko": "sekretariat"}).status_code == 200
        assert client.put(url + "/czesci/0", content=b"synthetic").status_code == 200
        assert client.put(url + "/koniec", json={"czesci": 1}).status_code == 200
        assert client.post(url + "/stenogram").status_code == 200
        return id

    pierwsze = dodaj("sprawa-a")
    drugie = dodaj("sprawa-b")
    code = client.post("/v2/devices/invite", json={"name": "Sekretariat", "scope": "write",
                                                 "cases": ["sprawa-a"]}).json()["code"]
    token = client.post("/v2/devices/redeem", json={"code": code}).json()["token"]
    sekretariat = {"Authorization": "Bearer " + token}
    wpisy = client.get(base + "/kalendarz/wpisy", headers=sekretariat).json()
    assert len(wpisy) == 2
    assert wpisy[0]["id"] == pierwsze and wpisy[0]["sekunda"] == 42
    assert wpisy[0]["termin"] == "2026-12-14T10:30"
    assert wpisy[1]["rodzaj"] == "dokument"
    assert client.get(f"{base}/{pierwsze}", headers=sekretariat).content == b"synthetic"
    assert client.get(f"{base}/{drugie}", headers=sekretariat).status_code == 404
    assert client.post(f"{base}/{pierwsze}/ustalenia/0/zatwierdz", headers=sekretariat).status_code == 200
    assert client.post(f"{base}/{drugie}/ustalenia/0/zatwierdz").status_code == 409
