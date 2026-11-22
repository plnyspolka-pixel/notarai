"""Generic read-only provider for officially supported vendor HTTP APIs.

All URLs and field paths come from trusted deployment configuration, never
from a model or page content. Authentication client is supplied by the tenant
runtime. HTTPS and no redirects are required; separate egress ACL still needed.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlsplit

from .fallback_router import AutomationRequest, AttemptStatus, Risk, StrategyResult

API_PATH = re.compile(r'^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*$')
JSON_PATH = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$')


@dataclass(frozen=True)
class ApiField:
    relative_path: str
    json_path: str

    def __post_init__(self):
        if not API_PATH.fullmatch(self.relative_path) or not JSON_PATH.fullmatch(self.json_path):
            raise ValueError('unsafe API field mapping')


@dataclass(frozen=True)
class ApiProfile:
    app_id: str
    base_url: str
    fields: Mapping[str, ApiField] = field(default_factory=dict)

    def __post_init__(self):
        url = urlsplit(self.base_url)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or not self.app_id):
            raise ValueError('API base must be a clean HTTPS URL')
        if not self.base_url.endswith('/'):
            raise ValueError('API base URL must end in /')


class NativeApiStrategy:
    name = 'native_api'

    def __init__(self, profile: ApiProfile, *, client: Any):
        self.profile = profile
        self.client = client  # trusted authenticated tenant-scoped HTTP client

    def supports(self, request: AutomationRequest) -> bool:
        return (self.client is not None and request.risk is Risk.READ_ONLY
                and request.action == 'read_field'
                and request.app_id == self.profile.app_id
                and isinstance(request.payload.get('field'), str)
                and request.payload['field'] in self.profile.fields)

    def perform(self, request: AutomationRequest) -> StrategyResult:
        if not self.supports(request):
            return StrategyResult(AttemptStatus.UNAVAILABLE, clean_state_confirmed=True)
        key = request.payload['field']
        definition = self.profile.fields[key]
        url = self.profile.base_url + definition.relative_path
        try:
            response = self.client.get(url, follow_redirects=False, timeout=10.0)
            code = response.status_code
            if code in (401, 403) or 300 <= code < 400:
                return StrategyResult(AttemptStatus.POLICY_DENIED, diagnostic_code='api_access_denied')
            if code < 200 or code >= 300:
                return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                      clean_state_confirmed=True, diagnostic_code='api_read_not_available')
            value = response.json()
            for part in definition.json_path.split('.'):
                if not isinstance(value, dict) or part not in value:
                    return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                          clean_state_confirmed=True, diagnostic_code='missing_api_field')
                value = value[part]
            if not isinstance(value, (str, int, float, bool)) and value is not None:
                return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                      clean_state_confirmed=True, diagnostic_code='non_scalar_api_result')
            return StrategyResult(AttemptStatus.SUCCESS, postcondition_verified=True,
                                  data={'field': key, 'value': value})
        except Exception:
            # GET only; no credential/body/exception details in audit.
            return StrategyResult(AttemptStatus.RECOVERABLE_FAILURE,
                                  clean_state_confirmed=True, diagnostic_code='api_read_failed')
