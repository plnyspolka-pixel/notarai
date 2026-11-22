from types import SimpleNamespace

import pytest

from computer_use.fallback_router import AutomationRequest, FallbackRouter, Outcome, Risk
from computer_use.native_api import ApiField, ApiProfile, NativeApiStrategy


def request(risk=Risk.READ_ONLY):
    return AutomationRequest(job_id='demo',tenant_id='tenant',app_id='program',
                             action='read_field',risk=risk,payload={'field':'number'})


def profile():
    return ApiProfile('program','https://vendor.example.test/v2/',
                      fields={'number':ApiField('cases/current','data.number')})


class FakeClient:
    def __init__(self, status=200, result=None):
        self.status=status
        self.result=result or {'data':{'number':'A/2026'}}
        self.calls=[]
    def get(self, url, **kwargs):
        self.calls.append((url,kwargs))
        return SimpleNamespace(status_code=self.status,json=lambda:self.result)


def test_api_read_first_priority():
    client=FakeClient()
    result=FallbackRouter([NativeApiStrategy(profile(),client=client)]).execute(request())
    assert result.outcome==Outcome.COMPLETED
    assert result.data['value']=='A/2026'
    assert client.calls==[('https://vendor.example.test/v2/cases/current',
                            {'follow_redirects':False,'timeout':10.0})]


def test_api_unauthorized_stops_without_fallback():
    client=FakeClient(status=403)
    result=FallbackRouter([NativeApiStrategy(profile(),client=client)]).execute(request())
    assert result.outcome==Outcome.DENIED


def test_api_not_found_allows_fallback():
    result=FallbackRouter([NativeApiStrategy(profile(),client=FakeClient(status=404))]).execute(request())
    assert result.outcome==Outcome.UNSUPPORTED


def test_api_never_supports_writes():
    assert NativeApiStrategy(profile(),client=FakeClient()).supports(request(Risk.WRITE)) is False


def test_unsafe_vendor_api_path_rejected():
    for path in ['../admin','//evil.example','cases?query=x','https://evil.test/']:
        with pytest.raises(ValueError):
            ApiField(path,'data.number')


def test_unsafe_vendor_origin_rejected():
    with pytest.raises(ValueError):
        ApiProfile('bad','http://vendor.example.test/v2/')
    with pytest.raises(ValueError):
        ApiProfile('bad','https://user:password@vendor.example.test/v2/')
