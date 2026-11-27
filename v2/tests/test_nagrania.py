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
