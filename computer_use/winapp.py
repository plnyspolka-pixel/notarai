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
        if request.app_id != self.profile.app_id or not self.profile.windows_app:
            return False
        if request.action not in {'read_field', 'fill_draft_field', 'navigate_to'}:
            return False
        key = request.payload.get('field')
        el = self.profile.field(key, kind='uia') if isinstance(key, str) else None
        if el is None:
            return False
        if request.action == 'read_field':
            if request.risk is not Risk.READ_ONLY:
                return False
        elif request.action == 'navigate_to':
            expected = request.payload.get('expected_field')
            if not (request.risk is Risk.DRAFT and el.allow_navigation
                    and isinstance(expected, str)
                    and self.profile.field(expected, kind='uia') is not None):
                return False
        elif not (request.risk is Risk.DRAFT and el.allow_draft_fill and el.value_mode == 'input'):
            return False
        if self._installed is None:
            return os.name == 'nt' and shutil.which('winapp') is not None
        return self._installed

    def _call(self, operation, selector, *args):
        cmd = ['winapp', 'ui', operation, selector, *args,
               '-a', self.profile.windows_app, '--json']
        result = self._runner(cmd, shell=False, capture_output=True,
                              text=True, timeout=12, check=False)
        if result.returncode != 0:
            return None
        output = json.loads(result.stdout)
        return output if isinstance(output, dict) else None

    def perform(self, request: AutomationRequest) -> StrategyResult:
        key = request.payload['field']
        el = self.profile.field(key, kind='uia')
        if el is None or not self.profile.windows_app or not self.supports(request):
            return StrategyResult(AttemptStatus.UNAVAILABLE, clean_state_confirmed=True)
        draft = request.action == 'fill_draft_field'
        navigation = request.action == 'navigate_to'
        if draft:
            value = request.payload.get('value')
            if not isinstance(value, str) or len(value) > 2000:
                return StrategyResult(AttemptStatus.POLICY_DENIED, diagnostic_code='invalid_draft_value')
        try:
            if navigation:
                if self._call('invoke', el.selector) is None:
                    return StrategyResult(AttemptStatus.UNKNOWN_EFFECT, diagnostic_code='uia_navigation_effect_unknown')
                expected = self.profile.field(request.payload['expected_field'], kind='uia')
                output = self._call('get-value', expected.selector)
                if output is None or not isinstance(output.get('text'), str):
                    return StrategyResult(AttemptStatus.UNKNOWN_EFFECT, diagnostic_code='uia_navigation_not_verified')
                return StrategyResult(AttemptStatus.SUCCESS, postcondition_verified=True,
                                      data={'target': key, 'expected_field_visible': True})
            if draft and self._call('set-value', el.selector, value) is None:
                # A nonzero return may occur after the UI already changed.
                return StrategyResult(AttemptStatus.UNKNOWN_EFFECT, diagnostic_code='uia_draft_effect_unknown')
            output = self._call('get-value', el.selector)
            if output is None or not isinstance(output.get('text'), str):
                status = AttemptStatus.UNKNOWN_EFFECT if (draft or navigation) else AttemptStatus.RECOVERABLE_FAILURE
                return StrategyResult(status, clean_state_confirmed=not draft,
                                      diagnostic_code='uia_not_readable')
            observed = output['text']
            if draft:
                if observed != value:
                    return StrategyResult(AttemptStatus.UNKNOWN_EFFECT, diagnostic_code='draft_not_verified')
                return StrategyResult(AttemptStatus.SUCCESS, postcondition_verified=True,
                                      data={'field': key, 'value_confirmed': True})
            return StrategyResult(AttemptStatus.SUCCESS, postcondition_verified=True,
                                  data={'field': key, 'value': observed})
        except (ValueError, TypeError, OSError, subprocess.TimeoutExpired):
            status = AttemptStatus.UNKNOWN_EFFECT if draft else AttemptStatus.RECOVERABLE_FAILURE
            return StrategyResult(status, clean_state_confirmed=not draft,
                                  diagnostic_code='uia_operation_failed')
