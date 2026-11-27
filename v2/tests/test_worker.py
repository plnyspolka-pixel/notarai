import base64
import sqlite3
import pytest
from fastapi.testclient import TestClient
from cryptography.exceptions import InvalidTag
from worker.api import create_app
from worker.vault import Vault, Conflict
from worker.bedrock import smoke_test

@pytest.fixture
def setup(tmp_path):
    key = b"K"*32
    token = "t"*48
    (tmp_path/"vault.key").write_bytes(key)
    (tmp_path/"api.token").write_text(token)
    return tmp_path, Vault(tmp_path,key), TestClient(create_app(tmp_path)), {"Authorization":"Bearer "+token}

def test_auth(setup):
    _,_,client,headers = setup
    assert client.get("/v2/health").status_code == 401
    assert client.get("/v2/health",headers=headers).status_code == 200
    assert client.get("/v2/health",headers={**headers,"Host":"evil.example"}).status_code == 403

def test_revision_and_conflict(setup):
    _,vault,_,_ = setup
    i,v = vault.put(None,0,"synthetic.txt",b"first")
    assert v == 1
    assert vault.put(i,1,"synthetic.txt",b"second") == (i,2)
    with pytest.raises(Conflict):
        vault.put(i,1,"synthetic.txt",b"stale")
    assert vault.get(i,1)[2] == b"first"
    assert vault.get(i)[2] == b"second"

def test_encrypted_and_tamper(setup):
    home,vault,_,_ = setup
    i,_ = vault.put(None,0,"SYNTHETIC-NAME-12345",b"SYNTHETIC-SECRET-12345")
    assert b"SYNTHETIC-SECRET-12345" not in (home/"vault.sqlite3").read_bytes()
    assert b"SYNTHETIC-NAME-12345" not in (home/"vault.sqlite3").read_bytes()
    with sqlite3.connect(home/"vault.sqlite3") as db:
        payload = db.execute("SELECT payload FROM revisions").fetchone()[0]
        db.execute("UPDATE revisions SET payload=?", (payload[:-1]+bytes([payload[-1]^1]),))
    with pytest.raises(InvalidTag):
        vault.get(i)

def test_api_roundtrip(setup):
    _,_,client,headers = setup
    content = base64.b64encode(b"synthetic").decode()
    payload = {"name":"a.txt","expected_version":0,"content_b64":content}
    result = client.post("/v2/documents",headers=headers,json=payload)
    assert result.status_code == 200
    i = result.json()["id"]
    assert client.get("/v2/documents/"+i,headers=headers).json()["content_b64"] == content
    assert client.post("/v2/documents",headers=headers,json={**payload,"id":i}).status_code == 409

def test_bedrock_disabled(monkeypatch):
    monkeypatch.delenv("NOTARAI_V2_BEDROCK_SYNTHETIC",raising=False)
    with pytest.raises(PermissionError):
        smoke_test()

def test_bedrock_region(monkeypatch):
    monkeypatch.setenv("NOTARAI_V2_BEDROCK_SYNTHETIC","1")
    monkeypatch.setenv("NOTARAI_V2_BEDROCK_REGION","us-east-1")
    with pytest.raises(ValueError):
        smoke_test()

def test_bedrock_no_document_payload(monkeypatch):
    monkeypatch.setenv("NOTARAI_V2_BEDROCK_SYNTHETIC","1")
    monkeypatch.setenv("NOTARAI_V2_BEDROCK_REGION","eu-central-1")
    monkeypatch.setenv("NOTARAI_V2_BEDROCK_MODEL","anthropic.synthetic-test")
    class Fake:
        def get_model_invocation_logging_configuration(self):
            return {}
        def converse(self,**kwargs):
            assert kwargs["messages"][0]["content"][0]["text"] == "Synthetic test only. Reply with OK."
            return {"stopReason":"end_turn"}
    assert smoke_test(lambda *args,**kwargs: Fake())["ok"]

def test_nagranie_zaszyfrowane_fragmenty_i_ponowienie(setup):
    from uuid import uuid4

    home, _, client, headers = setup
    url = f"/v2/nagrania/{uuid4()}"
    opis = {"sprawa": "FIKCYJNA SPRAWA 123", "format": "video/webm"}
    pierwszy = b"FIKCYJNY DZWIEK I OBRAZ 123"
    drugi = b"FIKCYJNY FRAGMENT 456"
    assert client.put(url, json=opis).status_code == 401
    assert client.put(url, headers=headers, json=opis).status_code == 200
    assert client.put(url, headers=headers, json=opis).status_code == 200
    assert client.put(url + "/czesci/1", headers=headers, content=drugi).status_code == 200
    assert client.put(url + "/koniec", headers=headers, json={"czesci": 2}).status_code == 409
    assert client.get(url, headers=headers).status_code == 409
    assert client.put(url + "/czesci/0", headers=headers, content=pierwszy).status_code == 200
    assert client.put(url + "/czesci/0", headers=headers, content=pierwszy).status_code == 200
    assert client.put(url + "/czesci/0", headers=headers, content=drugi).status_code == 409
    assert client.put(url + "/koniec", headers=headers, json={"czesci": 2}).status_code == 200
    assert client.put(url + "/czesci/2", headers=headers, content=drugi).status_code == 409
    assert client.get(url, headers=headers).content == pierwszy + drugi
    dysk = (home / "vault.sqlite3").read_bytes()
    assert pierwszy not in dysk and drugi not in dysk and opis["sprawa"].encode() not in dysk
