"""Trusted, declarative selectors rather than a custom adapter per vendor.

Profiles must be authored, reviewed and signed by a trusted deployer; never
parse arbitrary browser URLs / selectors from LLM instructions as profiles.
"""
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Element:
    kind: str  # css, role, uia, visual
    selector: str
    role: str | None = None
    value_mode: str = 'text'  # text or input
    allow_draft_fill: bool = False  # only after a verified non-persistent test
    allow_navigation: bool = False  # reviewed, non-destructive UI navigation only

    def __post_init__(self):
        if self.kind not in {'css', 'role', 'uia', 'visual'} or not self.selector or len(self.selector) > 256:
            raise ValueError('invalid approved selector')
        if self.value_mode not in {'text', 'input'}:
            raise ValueError('invalid value mode')
        if self.kind == 'role' and not self.role:
            raise ValueError('role selector needs explicit role')
        if self.selector.startswith('-') or '\x00' in self.selector:
            raise ValueError('unsafe selector')


@dataclass(frozen=True)
class AppProfile:
    app_id: str
    # HTTPS origin+path for browser apps, or None for desktop-only apps.
    start_url: str | None = None
    # Actual Windows target allowed for -a, chosen by trusted provisioner.
    windows_app: str | None = None
    fields: Mapping[str, Element | tuple[Element, ...]] = field(default_factory=dict)
    allow_http_loopback: bool = False  # test fixture only

    def __post_init__(self):
        if not self.app_id or len(self.app_id) > 128:
            raise ValueError('invalid app id')
        if self.windows_app and (self.windows_app.startswith('-') or len(self.windows_app) > 128):
            raise ValueError('invalid Windows app target')
        if self.start_url and not self.is_allowed_url(self.start_url):
            raise ValueError('unsafe start URL')

    def is_allowed_url(self, url: str) -> bool:
        url_parts = urlsplit(url)
        if url_parts.username or url_parts.password:
            return False
        if url_parts.scheme == 'https':
            valid = bool(url_parts.hostname)
        else:
            valid = (self.allow_http_loopback and url_parts.scheme == 'http'
                     and url_parts.hostname in {'127.0.0.1', 'localhost'})
        if not valid:
            return False
        if self.start_url:
            base = urlsplit(self.start_url)
            return (url_parts.scheme, url_parts.hostname, url_parts.port) == (base.scheme, base.hostname, base.port)
        return True

    def field(self, key: str, *, kind: str) -> Element | None:
        defined = self.fields.get(key)
        options = (defined,) if isinstance(defined, Element) else (defined or ())
        allowed_kinds = {'css', 'role'} if kind == 'browser' else ({'uia'} if kind == 'uia' else {'visual'})
        return next((item for item in options if item.kind in allowed_kinds), None)
