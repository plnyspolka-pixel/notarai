"""Sealed v2 API isolated tenant/auth schema tests."""
import base64
import importlib
import json
import sys
import types
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

def encode(v:bytes)->str:
    return base64.urlsafe_b64encode(v).decode().rstrip("=")

@pytest.fixture()
def vault(monkeypatch):
    office={"id":"office-a","local":False}
    state={}
    stub=types.ModuleType("magazyn")
    stub.kancelaria=lambda:office["id"]
    stub.u_klienta=lambda:office["local"]
    stub.wczytaj_plik_kancelarii=lambda _n,_d:state.get(office["id"],{"documents":{}})
    def write(_n,callback,_default):
        obj=state.setdefault(office["id"],{"documents":{}})
        return callback(obj)
    stub.zmien_plik_kancelarii=write
    monkeypatch.setitem(sys.modules,"magazyn",stub)
    import sealed_vault_v2
    importlib.reload(sealed_vault_v2)
    return sealed_vault_v2,office,state

def doc(v):
    return v.SealedDocument.model_validate({
        "schema":"notarai.sealed.v2","documentId":str(uuid.uuid4()),
        "tenantRef":"office-a","algorithm":"AES-256-GCM",
        "keyWrap":"X25519-HKDF-SHA256-AES256GCM",
        "nonce":encode(bytes(range(12))),
        "ciphertext":encode(bytes(range(17))),
        "recipients":[{
            "keyId":"a"*40,"ephemeralPublic":encode(bytes(range(32))),
            "salt":encode(bytes(range(32))),"nonce":encode(bytes(range(12))),
            "wrappedKey":encode(bytes(range(48)))
        }]
    })

def test_ciphertext_only_envelope_is_registered_for_single_tenant(vault):
    v,office,state=vault
    e=doc(v)
    r=v.register(e)
    assert r["created"]
    assert v.register(e)["created"] is False
    data=v.get_document(e.documentId)
    assert data["schema"]=="notarai.sealed.v2"
    assert data["recipients"][0]["keyId"]=="a"*40
    assert "passphrase" not in json.dumps(state)

def test_wrong_tenant_unexpected_plaintext_and_duplicate_recipient_rejected(vault):
    v,office,state=vault
    e=doc(v)
    office["id"]="office-b"
    with pytest.raises(HTTPException) as caught:v.register(e)
    assert caught.value.status_code==403
    office["id"]="office-a"
    data=e.model_dump(by_alias=True,mode="json")
    data["plaintext"]="act text should not be submitted"
    with pytest.raises(ValidationError):v.SealedDocument.model_validate(data)
    data=e.model_dump(by_alias=True,mode="json")
    data["recipients"].append(data["recipients"][0])
    with pytest.raises(HTTPException) as err:v.register(v.SealedDocument.model_validate(data))
    assert err.value.status_code==422

def test_replay_or_metadata_changes_cannot_overwrite(vault):
    v,office,state=vault
    e=doc(v)
    v.register(e)
    d=e.model_dump(by_alias=True,mode="json")
    d["nonce"]=encode(bytes([1]*12))
    with pytest.raises(HTTPException) as error:v.register(v.SealedDocument.model_validate(d))
    assert error.value.status_code==409

def test_local_only_office_does_not_upload(vault):
    v,office,state=vault
    office["local"]=True
    with pytest.raises(HTTPException) as error:v.register(doc(v))
    assert error.value.status_code==409

def test_role_policy_is_notary_only():
    import stanowiska
    import ast
    from pathlib import Path
    for method in ("GET","POST","PUT","DELETE"):
        assert stanowiska.wymagane(method,"/api/sealed/v2/documents")=="kancelaria"
    node=ast.parse(Path("autoryzacja.py").read_text("utf-8"))
    block=next(n for n in node.body if isinstance(n,ast.Assign)
               and any(isinstance(t,ast.Name) and t.id=="_POZA_SERWISEM" for t in n.targets))
    assert "/api/sealed" in ast.literal_eval(block.value)
