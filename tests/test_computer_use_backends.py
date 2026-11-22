"""No network calls, secrets, user records or Windows installation needed."""
import json
import unittest
from contextlib import contextmanager
from types import SimpleNamespace

from computer_use.browser import WebDomStrategy
from computer_use.deployment import Capabilities, Runtime, choose_runtime
from computer_use.fallback_router import AutomationRequest, FallbackRouter, Outcome, Risk
from computer_use.profiles import AppProfile, Element
from computer_use.winapp import WinAppStrategy


class FakeLocator:
    def __init__(self, text='Fictional case', count=1):
        self._text = text
        self._count = count
    def count(self):
        return self._count
    def text_content(self, **kwargs):
        return self._text
    def input_value(self, **kwargs):
        return self._text


class FakePage:
    def __init__(self, *, final_url='https://cases.example.test/sprawy', locator=None):
        self.url = final_url
        self.element = locator or FakeLocator()
        self.goto_calls = []
    def goto(self, url, **kwargs):
        self.goto_calls.append(url)
    def locator(self, css):
        assert css == '#case'
        return self.element
    def get_by_role(self, role, name, exact):
        assert (role, name, exact) == ('textbox', 'Case number', True)
        return self.element


@contextmanager
def page_factory(page):
    yield page


def request(app_id='desktop', field='case', risk=Risk.READ_ONLY):
    return AutomationRequest(job_id='test-01', tenant_id='tenant-bound',
                             app_id=app_id, action='read_field', risk=risk,
                             payload={'field': field})


class TestBackends(unittest.TestCase):
    def setUp(self):
        self.web = AppProfile('web', start_url='https://cases.example.test/sprawy',
                              fields={'case': Element('css', '#case')})
        self.desktop = AppProfile('desktop', windows_app='Notepad',
                                  fields={'case': Element('uia', 'CaseField')})

    def test_01_web_read(self):
        page = FakePage()
        out = FallbackRouter([WebDomStrategy(self.web, page_factory=lambda: page_factory(page))]).execute(request('web'))
        self.assertEqual(out.outcome, Outcome.COMPLETED)
        self.assertEqual(out.data['value'], 'Fictional case')
        self.assertEqual(page.goto_calls, ['https://cases.example.test/sprawy'])

    def test_02_role_locator_input(self):
        profile = AppProfile('web', start_url='https://cases.example.test/sprawy',
                             fields={'case': Element('role', 'Case number', 'textbox', 'input')})
        out = FallbackRouter([WebDomStrategy(profile, page_factory=lambda: page_factory(FakePage()))]).execute(request('web'))
        self.assertEqual(out.outcome, Outcome.COMPLETED)

    def test_03_mismatched_tenant_app_not_supported(self):
        out = FallbackRouter([WebDomStrategy(self.web, page_factory=lambda: page_factory(FakePage()))]).execute(request('foreign-app'))
        self.assertEqual(out.outcome, Outcome.UNSUPPORTED)

    def test_04_cross_origin_redirect_denied(self):
        page = FakePage(final_url='https://evil.example.test/path')
        out = FallbackRouter([WebDomStrategy(self.web, page_factory=lambda: page_factory(page))]).execute(request('web'))
        self.assertEqual(out.outcome, Outcome.DENIED)

    def test_05_ambiguous_dom_falls_through(self):
        page = FakePage(locator=FakeLocator(count=2))
        out = FallbackRouter([WebDomStrategy(self.web, page_factory=lambda: page_factory(page))]).execute(request('web'))
        self.assertEqual(out.outcome, Outcome.UNSUPPORTED)

    def test_06_windows_read_via_cli(self):
        calls = []
        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return SimpleNamespace(returncode=0, stdout=json.dumps({'elementId':'ok','text':'A/123'}))
        backend = WinAppStrategy(self.desktop, runner=fake_run, installed=True)
        out = FallbackRouter([backend]).execute(request())
        self.assertEqual(out.outcome, Outcome.COMPLETED)
        self.assertEqual(out.data, {'field':'case', 'value':'A/123'})
        self.assertEqual(calls[0][0], ['winapp','ui','get-value','CaseField','-a','Notepad','--json'])
        self.assertIs(calls[0][1]['shell'], False)

    def test_07_windows_invalid_json_falls_through(self):
        backend = WinAppStrategy(self.desktop, runner=lambda *a,**k: SimpleNamespace(returncode=0, stdout='bad'), installed=True)
        out = FallbackRouter([backend]).execute(request())
        self.assertEqual(out.outcome, Outcome.UNSUPPORTED)

    def test_08_windows_missing_is_not_supported(self):
        backend = WinAppStrategy(self.desktop, installed=False)
        self.assertFalse(backend.supports(request()))

    def test_09_web_and_windows_read_only_no_mutating_commands(self):
        out = FallbackRouter([WebDomStrategy(self.web, page_factory=lambda: page_factory(FakePage()))]).execute(request('web', risk=Risk.DRAFT))
        self.assertNotEqual(out.outcome, Outcome.COMPLETED)
        self.assertFalse(WinAppStrategy(self.desktop, installed=True).supports(request(risk=Risk.WRITE)))

    def test_10_reject_remote_http_and_password(self):
        for url in ('http://external.example.test/sprawy', 'https://user:secret@example.test/',
                    'file:///etc/passwd'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                AppProfile('bad', start_url=url)

    def test_11_reject_shell_option_in_selector_and_program(self):
        with self.assertRaises(ValueError):
            Element('uia', '--help')
        with self.assertRaises(ValueError):
            AppProfile('bad', windows_app='-x')

    def test_12_cloud_browser_before_vm(self):
        c = Capabilities(web_app=True, reachable_from_cloud=True, desktop_app=True,
                         windows_vm_licensed=True, database_reachable_from_hosted_vm=True)
        self.assertEqual(choose_runtime(c).runtime, Runtime.CLOUD_BROWSER)

    def test_13_api_before_browser(self):
        c = Capabilities(authorized_remote_api=True, web_app=True, reachable_from_cloud=True)
        self.assertEqual(choose_runtime(c).runtime, Runtime.REMOTE_API)

    def test_14_onprem_only_for_local_database(self):
        c = Capabilities(desktop_app=True, windows_vm_licensed=True,
                         database_reachable_from_hosted_vm=False, on_prem_vm_available=True)
        self.assertEqual(choose_runtime(c).runtime, Runtime.ON_PREM_VM)

    def test_15_fallback_to_manual_when_no_access(self):
        self.assertEqual(choose_runtime(Capabilities()).runtime, Runtime.HUMAN_SETUP)

    def test_16_local_connector_after_vm(self):
        c = Capabilities(desktop_app=True, narrow_connector_permitted=True)
        self.assertEqual(choose_runtime(c).runtime, Runtime.LOCAL_CONNECTOR)

    def test_17_web_unsupported_field(self):
        self.assertFalse(WebDomStrategy(self.web).supports(request('web', 'unapproved_field')))

    def test_18_web_http_loopback_test_only(self):
        good = AppProfile('demo', start_url='http://localhost:8055/demo', allow_http_loopback=True)
        self.assertTrue(good.is_allowed_url('http://localhost:8055/next'))
        self.assertFalse(good.is_allowed_url('http://127.0.0.1:8055/next'))


if __name__ == '__main__':
    unittest.main()
