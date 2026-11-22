"""Windows UI Automation backend via Microsoft WinApp CLI (read-only MVP).

Runs INSIDE the dedicated Windows user's interactive session. No shell,
no unbounded commands, no pass-through of arbitrary model-supplied selectors.
"""
import json
import os
import shutil
import subprocess

from .fallback_router import AutomationRequest, AttemptStatus, Risk, StrategyResult
from .profiles import AppProfile


class WinAppStrategy:
    name = 'windows_uia'

    def __init__(self, profile: AppProfile, *, runner=None, installed=None):
        self.profile = profile
        self._runner = runner or subprocess.run
        self._installed = installed

    def supports(self, request: AutomationRequest) -> bool:
        if request.app_id != self.profile.app_id or request.risk is not Risk.READ_ONLY:
            return False
        if not self.profile.windows_app or request.action != 'read_field':
            return False
        key = request.payload.get('field')
        if not isinstance(key, str) or self.profile.field(key, kind='uia') is None:
            return False
        if self._installed is None:
            return os.name == 'nt' and shutil.which('winapp') is not None
        return self._installed

    def perform(self, request: AutomationRequest) -> StrategyResult:
        key = request.payload['field']
        el = self.profile.field(key, kind='uia')
        if el is None or not self.profile.windows_app:
            return StrategyResult(AttemptStatus.UNAVAILABLE, clean_state_confirmed=True)
        cmd = ['winapp', 'ui', 'get-value', el.selector, '-a', self.profile.windows_app, '--json']
        try:
            result = self._runner(cmd, shell=False, capture_output=True,
                                  text=True, timeout=12, check=False)
            if result.returncode != 0:
                return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                      clean_state_confirmed=True, diagnostic_code='uia_not_available')
            payload = json.loads(result.stdout)
            value = payload.get('text')
            if not isinstance(value, str):
                return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                      clean_state_confirmed=True, diagnostic_code='invalid_uia_envelope')
            return StrategyResult(AttemptStatus.SUCCESS, postcondition_verified=True,
                                  data={'field': key, 'value': value})
        except (ValueError, TypeError, OSError, subprocess.TimeoutExpired):
            return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                  clean_state_confirmed=True, diagnostic_code='uia_read_failed')
