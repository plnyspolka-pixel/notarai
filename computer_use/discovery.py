"""Read-only, privacy-minimized UIA discovery for unknown Windows apps.

Runs locally with WinApp CLI, never logs raw inspect JSON or window text.
Only stable-looking AutomationIds are returned as profile candidates; they
must be manually validated before being enabled as actions.
"""
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from .profiles import AppProfile

SAFE_ID = re.compile(r'^(?=.{2,64}$)(?=.*[A-Za-z])[A-Za-z][A-Za-z0-9_-]*$')
CONTROL_TYPES = {'Edit', 'Document', 'Button', 'ComboBox', 'Table', 'DataGrid', 'List', 'Tab'}


@dataclass(frozen=True)
class Candidate:
    automation_id: str
    control_type: str


@dataclass(frozen=True)
class Discovery:
    app_id: str
    candidates: tuple[Candidate, ...]
    examined_elements: int
    truncated: bool


class WinAppDiscovery:
    def __init__(self, profile: AppProfile, *, runner=None, installed=None):
        self.profile = profile
        self.runner = runner or subprocess.run
        self.installed = installed

    def run(self) -> Discovery:
        if not self.profile.windows_app:
            raise ValueError('app has no approved Windows target')
        if self.installed is False or (self.installed is None and
                (os.name != 'nt' or not shutil.which('winapp'))):
            raise RuntimeError('winapp unavailable on this worker')
        proc = self.runner(
            ['winapp', 'ui', 'inspect', '-a', self.profile.windows_app,
             '--interactive', '--json'],
            shell=False, capture_output=True, text=True, timeout=20, check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError('UIA inspection unavailable')
        try:
            result = json.loads(proc.stdout)
        except (ValueError, TypeError) as exc:
            raise RuntimeError('invalid UIA inspection envelope') from exc
        if not isinstance(result, dict) or not isinstance(result.get('windows'), list):
            raise RuntimeError('invalid UIA inspection shape')
        stack = []
        for win in result['windows'][:16]:
            if isinstance(win, dict) and isinstance(win.get('elements'), list):
                stack.extend((node, 0) for node in win['elements'])
        count = 0
        candidates = []
        seen = set()
        max_elements = 500
        while stack and count < max_elements:
            node, depth = stack.pop()
            if not isinstance(node, dict):
                continue
            count += 1
            control_type = node.get('type')
            automation_id = node.get('automationId')
            if (control_type in CONTROL_TYPES and isinstance(automation_id, str)
                    and SAFE_ID.fullmatch(automation_id)
                    and automation_id not in seen):
                candidates.append(Candidate(automation_id, control_type))
                seen.add(automation_id)
            if depth < 20 and isinstance(node.get('children'), list):
                stack.extend((child, depth + 1) for child in node['children'])
        return Discovery(self.profile.app_id, tuple(sorted(candidates, key=lambda c: c.automation_id)), count, bool(stack))
