"""Functional ciphertext-only API tests, isolated from AWS/Bedrock and real office data."""
import base64
import importlib
import json
import sys
import types
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError


def enc(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


@pytest.fixture()
def vault(monkeypatch):
    office={"id":"office-test-001", "local":False}
    records={}
    stub=types.ModuleType("magazyn")
    stub.kancelaria=lambda:office["id"]
    stub.u_klienta=lambda:office["local"]
    def read(name, defaults):
        return records.get(office["id"], {"documents":{}})
    def write(name, mutate, defaults):
        state=records.setdefault(office["id"], {"documents":{}})
        return mutate(state)
    stub.wczytaj_plik_kancelarii=read
    stub.zmien_plik_kancelarii=write
    monkeypatch.setitem(sys.modules, "magazyn",stub)
    import sealed_vault
    importlib.reload(sealed_vault)
    return sealed_vault, office, records


def demo(v, document_id=None, ciphertext=None):
    return v.SealedEnvelope.model_validate({
        "schema":"notarai.sealed.v1",
        "documentId":str(document_id or uuid.uuid4()),
        "tenantRef":"office-test-001", "algorithm":"AES-256-GCM",
        "kdf":"PBKDF2-SHA256", "iterations":600000,
        "salt":enc(bytes(range(16))),"nonce":enc(bytes(range(12))),
        "ciphertext":enc(ciphertext or bytes(range(17))),
    })


def test_store_only_ciphertext_and_roundtrip(vault):
    v,office,records=vault
    env=demo(v)
    saved=v.store_document(env)
    assert saved["created"] is True
    doc=v.load_document(env.documentId)
    assert doc["schema"]=="notarai.sealed.v1"
    assert doc["ciphertext"]==env.ciphertext
    assert "passphrase" not in json.dumps(records).lower()
    assert v.store_document(env)["created"] is False


def test_same_document_id_cannot_overwrite_an_existing_ciphertext(vault):
    v,office,records=vault
    env=demo(v)
    v.store_document(env)
    changed=demo(v,document_id=env.documentId,ciphertext=b"a"*17)
    with pytest.raises(HTTPException) as exc:
        v.store_document(changed)
    assert exc.value.status_code==409


def test_cross_office_replay_is_rejected(vault):
    v,office,records=vault
    env=demo(v)
    office["id"]="other-office"
    with pytest.raises(HTTPException) as exc:
        v.store_document(env)
    assert exc.value.status_code==403


def test_malformed_metadata_is_rejected(vault):
    v,office,records=vault
    from pydantic import ValidationError
    for changes in ({"salt":enc(b"short")},{"nonce":enc(b"short")}):
        data=demo(v).model_dump(by_alias=True, mode="json")
        data.update(changes)
        with pytest.raises(ValidationError):
            v.SealedEnvelope.model_validate(data)
    for changes in ({"iterations":1},{"schema":"other-version"}):
        data=demo(v).model_dump(by_alias=True, mode="json")
        data.update(changes)
        with pytest.raises(HTTPException) as exc:
            v.store_document(v.SealedEnvelope.model_validate(data))
        assert exc.value.status_code==422


def test_local_only_policy_blocks_cloud_vault(vault):
    v,office,records=vault
    office["local"]=True
    with pytest.raises(HTTPException) as exc:
        v.store_document(demo(v))
    assert exc.value.status_code==409


def test_forbids_unknown_fields_that_could_contain_plaintext(vault):
    v, office, records = vault
    data=demo(v).model_dump(by_alias=True, mode="json")
    data["plaintext"]="should-never-be-accepted"
    with pytest.raises(ValidationError):
        v.SealedEnvelope.model_validate(data)
    assert records=={}


def test_nonce_change_cannot_be_treated_as_idempotent_reupload(vault):
    v, office, records = vault
    envelope=demo(v)
    v.store_document(envelope)
    modified=demo(v,document_id=envelope.documentId)
    modified.nonce=enc(bytes(range(1,13)))
    with pytest.raises(HTTPException) as error:
        v.store_document(modified)
    assert error.value.status_code==409
