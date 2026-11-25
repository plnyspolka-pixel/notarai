import hashlib
import zipfile
import pytest
from scripts.rznp_kontrakt_audyt import inventory

NAME="rejestr-zastrzezen-proxy-contract.yml"

def make(tmp_path, entries):
    p=tmp_path/"contract.zip"
    with zipfile.ZipFile(p,"w") as z:
        for name, data in entries:
            z.writestr(name,data)
    return p

def test_inventory(tmp_path):
    p=make(tmp_path,[(NAME,b"openapi: 3.0.3"),("stub.jar",b"not executed")])
    r=inventory(p)
    assert r["status"]=="INVENTORY_ONLY"
    assert r["sha256"]==hashlib.sha256(p.read_bytes()).hexdigest()
    assert r["files"][0]["sha256"]==hashlib.sha256(b"openapi: 3.0.3").hexdigest()

@pytest.mark.parametrize("name",["../evil","/evil","a/../../evil","C:/evil",chr(92)+"evil"])
def test_unsafe_member(tmp_path,name):
    with pytest.raises(ValueError):
        inventory(make(tmp_path,[(NAME,b"x"),(name,b"x")]))

def test_missing_contract(tmp_path):
    with pytest.raises(ValueError):
        inventory(make(tmp_path,[("stub.jar",b"x")]))

def test_ambiguous_contract(tmp_path):
    with pytest.raises(ValueError):
        inventory(make(tmp_path,[(NAME,b"x"),("other/"+NAME,b"x")]))
