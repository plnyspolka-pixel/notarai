"""Load trusted, tenant-bound app profiles without per-vendor Python code.

The HMAC verification key is injected from a protected runtime (e.g. KMS-backed
secret). Profile files, LLM replies, web pages and uploads are never trusted.
"""
import hashlib
import hmac
import json
from dataclasses import dataclass

from .profiles import AppProfile, Element


class ProfileRejected(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedProfile:
    tenant_id: str
    revision: int
    app: AppProfile


def load_verified_profile(raw: bytes, signature: str, key: bytes, *, tenant_id: str) -> VerifiedProfile:
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= 32768:
        raise ProfileRejected('invalid_profile_size')
    if not isinstance(signature, str) or len(signature) != 64:
        raise ProfileRejected('invalid_signature')
    if not isinstance(key, bytes) or len(key) < 32:
        raise ProfileRejected('weak_signing_key')
    expected = hmac.new(key, raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ProfileRejected('signature_mismatch')
    try:
        item = json.loads(raw.decode('utf-8'))
        if set(item) != {'tenant_id', 'revision', 'app'}:
            raise ProfileRejected('invalid_profile_schema')
        if item['tenant_id'] != tenant_id or not tenant_id:
            raise ProfileRejected('tenant_mismatch')
        if type(item['revision']) is not int or item['revision'] < 1:
            raise ProfileRejected('invalid_revision')
        source = item['app']
        if set(source) != {'app_id', 'start_url', 'windows_app', 'fields'}:
            raise ProfileRejected('invalid_app_schema')
        if not isinstance(source['fields'], dict) or len(source['fields']) > 128:
            raise ProfileRejected('invalid_fields')
        fields = {}
        for key_name, definitions in source['fields'].items():
            if not isinstance(key_name, str) or not key_name or len(key_name) > 128:
                raise ProfileRejected('invalid_field_name')
            nodes = definitions if isinstance(definitions, list) else [definitions]
            if not 1 <= len(nodes) <= 3:
                raise ProfileRejected('invalid_field_options')
            values = []
            for d in nodes:
                if not isinstance(d, dict) or not set(d).issubset(
                    {'kind', 'selector', 'role', 'value_mode', 'allow_draft_fill', 'allow_navigation'}):
                    raise ProfileRejected('invalid_element_schema')
                values.append(Element(**d))
            fields[key_name] = values[0] if len(values) == 1 else tuple(values)
        profile = AppProfile(app_id=source['app_id'],
                             start_url=source['start_url'],
                             windows_app=source['windows_app'],
                             fields=fields)
    except (TypeError, AttributeError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileRejected('malformed_profile') from exc
    return VerifiedProfile(item['tenant_id'], item['revision'], profile)
