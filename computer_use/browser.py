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
            context = browser.new_context(accept_downloads=False, service_workers='block')
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
        if request.app_id != self.profile.app_id or not self.profile.start_url:
            return False
        if request.action not in {'read_field', 'fill_draft_field'}:
            return False
        key = request.payload.get('field')
        definition = self.profile.field(key, kind='browser') if isinstance(key, str) else None
        if definition is None:
            return False
        if request.action == 'read_field':
            return request.risk is Risk.READ_ONLY
        return request.risk is Risk.DRAFT and definition.allow_draft_fill and definition.value_mode == 'input'

    def perform(self, request: AutomationRequest) -> StrategyResult:
        key = request.payload['field']
        definition = self.profile.field(key, kind='browser')
        if definition is None or self.profile.start_url is None or not self.supports(request):
            return StrategyResult(AttemptStatus.UNAVAILABLE, clean_state_confirmed=True)
        draft = request.action == 'fill_draft_field'
        if draft:
            value = request.payload.get('value')
            if not isinstance(value, str) or len(value) > 2000:
                return StrategyResult(AttemptStatus.POLICY_DENIED, diagnostic_code='invalid_draft_value')
        try:
            with self.page_factory() as page:
                # Prevent redirects/subresources to unapproved origins BEFORE
                # they reach the network. Production also uses network egress ACL.
                def guard(route):
                    if self.profile.is_allowed_url(route.request.url):
                        route.continue_()
                    else:
                        route.abort()
                page.route('**/*', guard)
                page.goto(self.profile.start_url, wait_until='domcontentloaded', timeout=15000)
                if not self.profile.is_allowed_url(page.url):
                    return StrategyResult(AttemptStatus.POLICY_DENIED, diagnostic_code='cross_origin_redirect')
                locator = (page.locator(definition.selector) if definition.kind == 'css'
                           else page.get_by_role(definition.role, name=definition.selector, exact=True))
                if locator.count() != 1:
                    return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                          clean_state_confirmed=True, diagnostic_code='non_unique_locator')
                if draft:
                    locator.fill(value, timeout=5000)
                    observed = locator.input_value(timeout=5000)
                    if observed != value or not self.profile.is_allowed_url(page.url):
                        return StrategyResult(AttemptStatus.UNKNOWN_EFFECT, diagnostic_code='draft_not_verified')
                    return StrategyResult(AttemptStatus.SUCCESS, postcondition_verified=True,
                                          data={'field': key, 'value_confirmed': True})
                observed = (locator.input_value(timeout=5000) if definition.value_mode == 'input'
                            else locator.text_content(timeout=5000))
                if not isinstance(observed, str):
                    return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                          clean_state_confirmed=True, diagnostic_code='missing_text')
                if not self.profile.is_allowed_url(page.url):
                    return StrategyResult(AttemptStatus.POLICY_DENIED, diagnostic_code='origin_changed')
                return StrategyResult(AttemptStatus.SUCCESS, postcondition_verified=True,
                                      data={'field': key, 'value': observed})
        except Exception:
            # A fill may have changed UI or autosaved before the error; never retry.
            if draft:
                return StrategyResult(AttemptStatus.UNKNOWN_EFFECT, diagnostic_code='draft_effect_unknown')
            return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                  clean_state_confirmed=True, diagnostic_code='browser_read_failed')
