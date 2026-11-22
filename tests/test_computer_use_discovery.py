import json
from types import SimpleNamespace

import pytest

from computer_use.discovery import WinAppDiscovery
from computer_use.profiles import AppProfile


def test_read_only_inspection_removes_window_text_and_values():
    data = {'windows': [{'title':'Confidential Client', 'elements': [
        {'type':'Edit','name':'Client PESEL 12345678901','value':'PRIVATE DATA',
         'automationId':'SearchBox', 'children': [
             {'type':'Text', 'name':'SENSITIVE CLIENT', 'automationId':'12345678901'}]},
        {'type':'Button','name':'Save','automationId':'SaveButton'},
        {'type':'Edit','name':'Client','automationId':'SearchBox'},
    ]}]}
    seen = []
    def runner(cmd, **kwargs):
        seen.append(cmd)
        return SimpleNamespace(returncode=0, stdout=json.dumps(data))
    inv = WinAppDiscovery(AppProfile('app', windows_app='notepad'),
                          runner=runner, installed=True).run()
    assert [(c.automation_id,c.control_type) for c in inv.candidates] == [
        ('SaveButton','Button'), ('SearchBox','Edit')]
    assert 'PRIVATE DATA' not in str(inv)
    assert 'SENSITIVE CLIENT' not in str(inv)
    assert seen[0][0:3] == ['winapp','ui','inspect']
    assert '--interactive' in seen[0]
    assert '--json' in seen[0]


def test_inspection_is_unavailable_without_winapp():
    with pytest.raises(RuntimeError):
        WinAppDiscovery(AppProfile('test', windows_app='notepad'), installed=False).run()


def test_invalid_response_is_not_exposed():
    inv = WinAppDiscovery(AppProfile('test', windows_app='notepad'), installed=True,
        runner=lambda *a,**kw: SimpleNamespace(returncode=0,stdout='secret raw data'))
    with pytest.raises(RuntimeError, match='invalid UIA inspection'):
        inv.run()
