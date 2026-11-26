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
