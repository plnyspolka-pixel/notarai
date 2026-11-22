"""Playwright strategy for read-only access to approved browser-app fields.

A live caller provides an authorized, tenant-isolated page/context factory.
No credentials are sourced from request payloads, URLs are allowlisted and
no arbitrary JavaScript, clicks, page screenshots or exports are exposed.
"""
from contextlib import contextmanager

from .fallback_router import AutomationRequest, AttemptStatus, Risk, StrategyResult
from .profiles import AppProfile


@contextmanager
def isolated_playwright_page():
    """Demo-only unauthenticated browser; production injects tenant context."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(accept_downloads=False)
            try:
                yield context.new_page()
            finally:
                context.close()
        finally:
            browser.close()


class WebDomStrategy:
    name = 'web_dom'

    def __init__(self, profile: AppProfile, *, page_factory=isolated_playwright_page):
        self.profile = profile
        self.page_factory = page_factory

    def supports(self, request: AutomationRequest) -> bool:
        if request.app_id != self.profile.app_id or request.risk is not Risk.READ_ONLY:
            return False
        if not self.profile.start_url or request.action != 'read_field':
            return False
        key = request.payload.get('field')
        return isinstance(key, str) and self.profile.field(key, kind='browser') is not None

    def perform(self, request: AutomationRequest) -> StrategyResult:
        key = request.payload['field']
        definition = self.profile.field(key, kind='browser')
        if definition is None or self.profile.start_url is None:
            return StrategyResult(AttemptStatus.UNAVAILABLE, clean_state_confirmed=True)
        try:
            with self.page_factory() as page:
                page.goto(self.profile.start_url, wait_until='domcontentloaded', timeout=15000)
                if not self.profile.is_allowed_url(page.url):
                    return StrategyResult(AttemptStatus.POLICY_DENIED, diagnostic_code='cross_origin_redirect')
                locator = (page.locator(definition.selector) if definition.kind == 'css'
                           else page.get_by_role(definition.role, name=definition.selector, exact=True))
                if locator.count() != 1:
                    return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                          clean_state_confirmed=True, diagnostic_code='non_unique_locator')
                value = locator.input_value(timeout=5000) if definition.value_mode == 'input' else locator.text_content(timeout=5000)
                if not isinstance(value, str):
                    return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                          clean_state_confirmed=True, diagnostic_code='missing_text')
                if not self.profile.is_allowed_url(page.url):
                    return StrategyResult(AttemptStatus.POLICY_DENIED, diagnostic_code='origin_changed')
                return StrategyResult(AttemptStatus.SUCCESS, postcondition_verified=True,
                                      data={'field': key, 'value': value})
        except Exception:
            # This backend NEVER issues persistent writes or submits forms.
            return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                  clean_state_confirmed=True, diagnostic_code='browser_read_failed')
