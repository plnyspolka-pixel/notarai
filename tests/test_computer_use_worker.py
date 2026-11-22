from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

from computer_use.fallback_router import AutomationRequest, Outcome, Risk
from computer_use.profiles import AppProfile, Element
from computer_use.worker import TenantWorker


class Page:
    url = 'https://demo.example.test/'
    def route(self, pattern, callback):
        self.callback = callback
    def goto(self, url, **kw):
        pass
    def locator(self, selector):
        return self
    def count(self):
        return 1
    def text_content(self, **kwargs):
        return 'Fictional case'


@contextmanager
def factory():
    yield Page()


def req(tenant='a', app='case-app'):
    return AutomationRequest(job_id='t1', tenant_id=tenant, app_id=app,
                             action='read_field', risk=Risk.READ_ONLY,
                             payload={'field':'number'})


def worker():
    return TenantWorker(tenant_id='a',
        profiles={'case-app': AppProfile('case-app',
            start_url='https://demo.example.test/',
            fields={'number': Element('css', '#case')})},
        browser_page_factory=factory, winapp_installed=False)


def test_read_case_only_in_own_tenant():
    result = worker().execute(req())
    assert result.outcome == Outcome.COMPLETED
    assert result.data['value'] == 'Fictional case'


def test_cross_tenant_denied_before_any_provider():
    result = worker().execute(req(tenant='b'))
    assert result.outcome == Outcome.DENIED
    assert result.reason == 'tenant_mismatch'


def test_unknown_app_denied():
    result = worker().execute(req(app='other'))
    assert result.outcome == Outcome.DENIED
    assert result.reason == 'app_not_enrolled'


def test_registry_key_mismatch_rejected():
    try:
        TenantWorker(tenant_id='a', profiles={'wrong': AppProfile('right')})
    except ValueError:
        return
    raise AssertionError('registry mismatch accepted')


def test_busy_session_fails_without_dispatch():
    agent = worker()
    agent._exclusive_session.acquire()
    try:
        result = agent.execute(req())
        assert result.outcome == Outcome.FAILED
        assert result.reason == 'session_busy'
    finally:
        agent._exclusive_session.release()


def test_api_is_first_and_browser_not_invoked():
    from computer_use.native_api import ApiField, ApiProfile
    seen=[]
    class API:
        def get(self,url,**kwargs):
            seen.append(url)
            return SimpleNamespace(status_code=200, json=lambda:{'record':{'number':'A/2026'}})
    worker=TenantWorker(tenant_id='a',profiles={
        'case-app':AppProfile('case-app',start_url='https://demo.example.test/',
                              fields={'number':Element('css','#case')})},
        api_profiles={'case-app':ApiProfile('case-app','https://api.example.test/v1/',
                                           fields={'number':ApiField('cases/current','record.number')})},
        api_client_factory=lambda tenant,app: API(),
        browser_page_factory=lambda: (_ for _ in ()).throw(AssertionError('browser should not open')),
        winapp_installed=False)
    result=worker.execute(req())
    assert result.outcome==Outcome.COMPLETED
    assert result.strategy=='native_api'
    assert seen==['https://api.example.test/v1/cases/current']
