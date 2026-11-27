import hashlib
import pytest
from scripts.pakiet_dowodowy_indeks import index, REQUIRED

def plan():
    return [{"id":i,"status":"NIEZWERYFIKOWANE","next_step":"Verify evidence","files":[]} for i in REQUIRED]

def test_index(tmp_path):
    (tmp_path/"report.txt").write_bytes(b"verified report")
    p=plan()
    p[0].update(status="GOTOWE",files=["report.txt"])
    r=index(tmp_path,p)
    assert r["items"][0]["evidence"][0]["sha256"]==hashlib.sha256(b"verified report").hexdigest()
    assert r["unresolved"]==list(REQUIRED[1:])

def test_ready_requires_evidence(tmp_path):
    p=plan()
    p[0]["status"]="GOTOWE"
    with pytest.raises(ValueError):
        index(tmp_path,p)

def test_unresolved_requires_action(tmp_path):
    p=plan()
    p[0]["next_step"]=""
    with pytest.raises(ValueError):
        index(tmp_path,p)

def test_missing_or_duplicate_item(tmp_path):
    p=plan()
    p[0]["id"]=p[1]["id"]
    with pytest.raises(ValueError):
        index(tmp_path,p)

def test_path_traversal(tmp_path):
    p=plan()
    p[0]["files"]=["../outside"]
    with pytest.raises(ValueError):
        index(tmp_path,p)

def test_symlink(tmp_path):
    (tmp_path/"original").write_text("x")
    (tmp_path/"link").symlink_to(tmp_path/"original")
    p=plan()
    p[0]["files"]=["link"]
    with pytest.raises(ValueError):
        index(tmp_path,p)
