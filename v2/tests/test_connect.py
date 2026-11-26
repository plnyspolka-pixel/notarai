import json
import subprocess
from types import SimpleNamespace
import pytest
from worker.connect import Router, Result, State
from worker.winapp_adapter import WinApp

class Stub:
    def __init__(self,name,supports,state):
        self.name=name
        self.available=supports
        self.state=state
        self.calls=0
    def supports(self,op):
        return self.available
    def execute(self,op,args):
        self.calls+=1
        return Result(self.state,self.name)

def test_probe_fallback():
    a,b=Stub("a",False,State.VERIFIED),Stub("b",True,State.VERIFIED)
    assert Router([a,b]).run("inspect_window",{}).backend=="b"
    assert (a.calls,b.calls)==(0,1)

@pytest.mark.parametrize("state",[State.UNAVAILABLE,State.UNCERTAIN])
def test_no_retry_after_attempt(state):
    a,b=Stub("a",True,state),Stub("b",True,State.VERIFIED)
    assert Router([a,b]).run("inspect_window",{}).state==State.UNCERTAIN
    assert b.calls==0

def test_write_blocked():
    a=Stub("a",True,State.VERIFIED)
    with pytest.raises(PermissionError):
        Router([a]).run("invoke",{})
    assert a.calls==0

def test_winapp_scoped(tmp_path,monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY","fake")
    def run(argv,**kwargs):
        assert argv[1:]==["ui","inspect","-w","42","--depth","3","--json"]
        assert kwargs["shell"] is False
        assert "AWS_SECRET_ACCESS_KEY" not in kwargs["env"]
        return SimpleNamespace(returncode=0,stdout=json.dumps({"windows":[{"hwnd":42}]}).encode())
    a=WinApp(tmp_path/"winapp.exe",runner=run)
    assert Router([a]).run("inspect_window",{"hwnd":42}).state==State.VERIFIED
    assert Router([a]).run("inspect_window",{"hwnd":"--help"}).state==State.UNCERTAIN

def test_wrong_window(tmp_path):
    a=WinApp(tmp_path/"winapp.exe",runner=lambda *a,**k: SimpleNamespace(returncode=0,stdout=b'{"windows":[{"hwnd":43}]}'))
    assert Router([a]).run("inspect_window",{"hwnd":42}).state==State.UNCERTAIN

def test_timeout(tmp_path):
    def run(*a,**k): raise subprocess.TimeoutExpired("winapp",15)
    a=WinApp(tmp_path/"winapp.exe",runner=run)
    assert Router([a]).run("list_windows",{}).state==State.UNCERTAIN
