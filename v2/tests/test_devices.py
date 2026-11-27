import base64
import sqlite3
import uuid
import pytest
from fastapi.testclient import TestClient
from worker.api import create_app
from worker.devices import DeviceRegistry
from worker.sync import plan

@pytest.fixture
def setup(tmp_path):
    (tmp_path/"vault.key").write_bytes(b"K"*32)
    (tmp_path/"api.token").write_text("t"*48)
    return TestClient(create_app(tmp_path)),{"Authorization":"Bearer "+"t"*48},tmp_path

def pair(client,admin,scope):
    r=client.post("/v2/devices/invite",headers=admin,json={"name":"synthetic phone","scope":scope})
    assert r.status_code==200
    code=r.json()["code"]
    r=client.post("/v2/devices/redeem",json={"code":code})
    assert r.status_code==200
    assert client.post("/v2/devices/redeem",json={"code":code}).status_code==403
    return r.json()

def headers(device):
    return {"Authorization":"Bearer "+device["token"]}

def test_read_only_and_revoke(setup):
    c,a,home=setup
    d=pair(c,a,"read")
    h=headers(d)
    assert c.get("/v2/documents",headers=h).status_code==200
    assert c.post("/v2/documents",headers=h,json={"name":"a.txt","expected_version":0,"content_b64":"YQ=="}).status_code==403
    assert c.get("/v2/devices",headers=h).status_code==403
    assert c.post("/v2/bedrock/smoke",headers=h).status_code==403
    assert d["token"].encode() not in (home/"devices.sqlite3").read_bytes()
    assert c.delete("/v2/devices/"+d["id"],headers=a).status_code==200
    assert c.get("/v2/documents",headers=h).status_code==401

def test_write_and_sync(setup):
    c,a,_=setup
    h=headers(pair(c,a,"write"))
    p={"name":"a.txt","expected_version":0,"content_b64":"YQ=="}
    r=c.post("/v2/documents",headers=h,json=p)
    assert r.status_code==200
    i=r.json()["id"]
    assert c.post("/v2/sync/plan",headers=h,json={"items":[]}).json()["download"]==[{"id":i,"version":1}]
    assert c.post("/v2/documents",headers=h,json={**p,"id":i,"expected_version":1}).status_code==200
    assert c.post("/v2/documents",headers=h,json={**p,"id":i,"expected_version":1}).status_code==409

def test_expired_invitation(setup):
    c,a,home=setup
    code=c.post("/v2/devices/invite",headers=a,json={"name":"phone"}).json()["code"]
    with sqlite3.connect(home/"devices.sqlite3") as db:
        db.execute("UPDATE invitations SET expires=0")
    assert c.post("/v2/devices/redeem",json={"code":code}).status_code==403

def test_sync_never_deletes():
    i,j=str(uuid.uuid4()),str(uuid.uuid4())
    p=plan([{"id":i,"version":3}],[{"id":i,"version":4},{"id":j,"version":1}])
    assert len(p["review"])==2
    assert p["download"]==[]
    with pytest.raises(ValueError):
        plan([], [{"id":i,"version":1},{"id":i,"version":2}])

def test_pocket_and_validation(setup):
    c,a,_=setup
    r=c.get("/v2/pocket")
    assert r.status_code==200
    assert r.headers["cache-control"]=="no-store"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert c.get("/v2/pocket.js").status_code==200
    assert c.get("/v2/pocket",headers={"Host":"evil.example"}).status_code==403
    r=c.post("/v2/documents",headers=a,json={"name":"SENSITIVE-SYNTHETIC","expected_version":"not-int","content_b64":"YQ=="})
    assert r.status_code==422
    assert "SENSITIVE-SYNTHETIC" not in r.text


def test_document_history_for_paired_devices(setup):
    client, admin, _ = setup
    writer = headers(pair(client, admin, "write"))
    reader = headers(pair(client, admin, "read"))
    payload = {"name": "Pierwsza.txt", "expected_version": 0, "content_b64": "YQ=="}
    doc_id = client.post("/v2/documents", headers=writer, json=payload).json()["id"]
    path = "/v2/documents/" + doc_id
    second_revision = {**payload, "id": doc_id, "expected_version": 1,
                       "name": "Druga.txt", "content_b64": "Yg=="}
    assert client.post("/v2/documents", headers=writer, json=second_revision).status_code == 200

    assert client.get(path + "/versions").status_code == 401
    history = client.get(path + "/versions", headers=reader)
    assert history.json() == [2, 1]
    assert history.headers["cache-control"] == "no-store"
    assert client.get("/v2/documents", headers=reader).json() == [{"id": doc_id, "version": 2}]
    listed = client.get("/v2/documents?include_names=true", headers=reader).json()
    assert len(listed) == 1 and listed[0].pop("created") > 0
    assert listed == [{"id": doc_id, "version": 2, "name": "Druga.txt", "size": 1, "case": None}]
    assert client.get(path + "?version=1", headers=reader).json() == {
        "id": doc_id, "version": 1, "name": "Pierwsza.txt", "content_b64": "YQ=="
    }
    assert client.get(path + "?version=3", headers=reader).status_code == 404
    assert client.get("/v2/documents/invalid/versions", headers=reader).status_code == 404


def test_the_window_on_this_computer_reopens_without_a_code(setup):
    c,a,home=setup
    local={"Host":"127.0.0.1:47000"}
    r=c.post("/v2/admin/reopen",headers=local)
    assert r.status_code==200
    session=c.post("/v2/devices/redeem",json={"code":r.json()["code"]}).json()
    assert session["scope"]=="admin" if "scope" in session else session["device"]["scope"]=="admin"
    # other websites, other hosts and a page that is not the window itself get nothing
    assert c.post("/v2/admin/reopen",headers={**local,"Origin":"https://evil.example"}).status_code==403
    assert c.post("/v2/admin/reopen",headers={**local,"Sec-Fetch-Site":"cross-site"}).status_code==403
    assert c.post("/v2/admin/reopen",headers={"Host":"notarai.example"}).status_code==403
    assert c.post("/v2/admin/reopen",headers={**local,"Origin":"http://127.0.0.1:47000","Sec-Fetch-Site":"same-origin"}).status_code==200
