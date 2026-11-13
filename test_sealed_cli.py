"""Offline Python/JS interoperable Sealed envelope roundtrip tests."""
import copy

import pytest
from cryptography.exceptions import InvalidTag

import notarai_sealed_cli as sealed

PASSWORD="This is a long demonstrator passphrase"
TENANT="office-demo"
CONTENT=b"Fictional document, no personal data"


def test_seal_roundtrip_and_no_plaintext():
    envelope=sealed.seal_bytes(CONTENT,PASSWORD,TENANT)
    assert envelope["schema"]=="notarai.sealed.v1"
    assert "Fictional" not in repr(envelope)
    assert sealed.open_envelope(envelope,PASSWORD,expected_office=TENANT)==CONTENT


def test_wrong_password_and_tampering_fail():
    env=sealed.seal_bytes(CONTENT,PASSWORD,TENANT)
    with pytest.raises(InvalidTag):
        sealed.open_envelope(env,"Completely different passphrase")
    changed=copy.deepcopy(env)
    changed["tenantRef"]="different-office"
    with pytest.raises(InvalidTag):
        sealed.open_envelope(changed,PASSWORD)
    changed=copy.deepcopy(env)
    changed["nonce"]=sealed._encoded(b"\x00"*12)
    with pytest.raises(InvalidTag):
        sealed.open_envelope(changed,PASSWORD)


def test_office_binding_and_overwrite_guard(tmp_path):
    env=sealed.seal_bytes(CONTENT,PASSWORD,TENANT)
    with pytest.raises(ValueError):
        sealed.open_envelope(env,PASSWORD,expected_office="another")
    target=tmp_path/"already"
    target.write_bytes(b"untouched")
    with pytest.raises(FileExistsError):
        sealed._write_new(target,b"something")
    assert target.read_bytes()==b"untouched"


def test_weak_passphrase_and_big_file_are_rejected():
    with pytest.raises(ValueError):
        sealed.seal_bytes(CONTENT,"short",TENANT)
    with pytest.raises(ValueError):
        sealed.seal_bytes(b"x"*(sealed.LIMIT+1),PASSWORD,TENANT)
