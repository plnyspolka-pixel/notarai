"""Offline v2 encryption: office-held key, per-document DEK, and cross-office denial."""
import copy
import json
import pytest
from cryptography.exceptions import InvalidTag
from notarai_sealed_v2 import make_office_key,seal_bytes,open_envelope,grant_recipient,write_new

PASS="This is a fictional recovery password 2026, kept offline"
TENANT="office-fictional-1"

def key(office=TENANT):
    return make_office_key(office,PASS)

def test_each_document_uses_random_dek_and_office_keeps_key():
    public,private=key()
    one=seal_bytes(b"Fictional secret document",TENANT,[public])
    two=seal_bytes(b"Fictional secret document",TENANT,[public])
    assert one["ciphertext"]!=two["ciphertext"]
    assert "privateKey" not in json.dumps(one)
    assert "Fictional" not in json.dumps(one)
    assert open_envelope(one,private,PASS)==b"Fictional secret document"

def test_multiple_recipients_and_office_bound_keys():
    p1,k1=key()
    p2,k2=key()
    foreign,_=key("another-office")
    env=seal_bytes(b"test-only",TENANT,[p1,p2])
    assert open_envelope(env,k1,PASS)==b"test-only"
    assert open_envelope(env,k2,PASS)==b"test-only"
    with pytest.raises(ValueError):
        seal_bytes(b"test-only",TENANT,[p1,foreign])
    with pytest.raises(ValueError):
        seal_bytes(b"test-only",TENANT,[p1,p1])

def test_guest_cannot_read_until_authorized_offline_grant():
    p1,k1=key()
    p2,k2=key()
    original=seal_bytes(b"Fictional content",TENANT,[p1])
    with pytest.raises(ValueError):
        open_envelope(original,k2,PASS)
    shared=grant_recipient(original,k1,PASS,p2)
    assert shared["ciphertext"]==original["ciphertext"]
    assert len(original["recipients"])==1
    assert open_envelope(shared,k2,PASS)==b"Fictional content"

def test_tampering_rejected_by_aead():
    p1,k1=key()
    env=seal_bytes(b"fictional",TENANT,[p1])
    altered=copy.deepcopy(env)
    altered["documentId"]="123e4567-e89b-42d3-a456-426614174000"
    with pytest.raises((InvalidTag,ValueError)):
        open_envelope(altered,k1,PASS)
    altered=copy.deepcopy(env)
    altered["ciphertext"]=altered["ciphertext"][:-2]+"AA"
    with pytest.raises((InvalidTag,ValueError)):
        open_envelope(altered,k1,PASS)
    altered=copy.deepcopy(env)
    altered["tenantRef"]="other-office"
    with pytest.raises(ValueError):
        open_envelope(altered,k1,PASS)

def test_private_key_is_encrypted_and_new_file_does_not_overwrite(tmp_path):
    p,k=key()
    assert "ENCRYPTED PRIVATE KEY" in k["privateKeyPem"]
    assert "PRIVATE KEY-----" not in k["privateKeyPem"].split("ENCRYPTED")[0]
    dest=tmp_path/"key.json"
    write_new(str(dest),json.dumps(k).encode(),private=True)
    with pytest.raises(FileExistsError):
        write_new(str(dest),b"replaced")
