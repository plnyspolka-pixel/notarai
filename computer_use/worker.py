"""Isolated execution facade for a single NotarAI kancelaria tenant.

IMPORTANT: This class does not authenticate a network request. The cloud
control plane must authenticate the user and cryptographically bind a job to
the tenant before it reaches the worker. Profiles are trusted deployment config.
"""
from threading import Lock
from typing import Callable, Mapping

from .browser import WebDomStrategy
from .fallback_router import (ApprovalVerifier, AutomationRequest,
                              AutomationResponse, FallbackRouter, Outcome)
from .profiles import AppProfile
from .native_api import ApiProfile, NativeApiStrategy
from .winapp import WinAppStrategy


class TenantWorker:
    def __init__(self, *, tenant_id: str, profiles: Mapping[str, AppProfile],
                 browser_page_factory: Callable | None = None,
                 approval_verifier: ApprovalVerifier | None = None,
                 winapp_runner=None, winapp_installed=None,
                 api_profiles: Mapping[str, ApiProfile] | None = None,
                 api_client_factory: Callable | None = None):
        if not tenant_id:
            raise ValueError('tenant_id must come from authenticated runtime')
        if any(app_id != profile.app_id for app_id, profile in profiles.items()):
            raise ValueError('profile registry key must match app_id')
        if any(app_id != profile.app_id for app_id, profile in (api_profiles or {}).items()):
            raise ValueError('API registry key must match app_id')
        self._tenant_id = tenant_id
        self._profiles = dict(profiles)
        self._api_profiles = dict(api_profiles or {})
        self._api_client_factory = api_client_factory
        self._page_factory = browser_page_factory
        self._approval = approval_verifier
        self._winapp_runner = winapp_runner
        self._winapp_installed = winapp_installed
        self._exclusive_session = Lock()

    def execute(self, request: AutomationRequest) -> AutomationResponse:
        if request.tenant_id != self._tenant_id:
            return AutomationResponse(Outcome.DENIED, reason='tenant_mismatch')
        profile = self._profiles.get(request.app_id)
        api_profile = self._api_profiles.get(request.app_id)
        if profile is None and api_profile is None:
            return AutomationResponse(Outcome.DENIED, reason='app_not_enrolled')
        if not self._exclusive_session.acquire(blocking=False):
            return AutomationResponse(Outcome.FAILED, reason='session_busy')
        try:
            browser_opts = ({'page_factory': self._page_factory}
                            if self._page_factory is not None else {})
            strategies = []
            if api_profile is not None and self._api_client_factory is not None:
                # The factory is supplied by the authenticated worker runtime.
                client = self._api_client_factory(self._tenant_id, request.app_id)
                strategies.append(NativeApiStrategy(api_profile, client=client))
            if profile is not None:
                strategies.extend([
                    WebDomStrategy(profile, **browser_opts),
                    WinAppStrategy(profile, runner=self._winapp_runner,
                                   installed=self._winapp_installed),
                ])
            return FallbackRouter(strategies,
                                  approval_verifier=self._approval).execute(request)
        finally:
            self._exclusive_session.release()
