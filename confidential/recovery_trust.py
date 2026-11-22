"""Custodian/trustee recovery signers pinned in an independently approved guest image.

Recovery signatures are worthless if the caller supplies both public keys.
The guest must load exactly the custodian-approved two public keys from its
immutable PCR/image-measured release. Without this root, all migrations fail.
The root itself does not prove independent AWS custody or genuine PCR policy.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import time
from pathlib import Path

from confidential.zk_recovery import RecoveryDenied

_ROOT_PATH = Path(__file__).resolve().with_name("trusted-recovery-root.json")
_KEYS = frozenset({
    "schema", "tenant_id", "old_key_arn", "old_key_pin",
    "custodian_public_key_b64", "trustee_public_key_b64", "expires_at",
})
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_KEY = re.compile(r"^arn:aws:kms:eu-central-1:[0-9]{12}:key/[A-Za-z0-9-]+$")
_PIN = re.compile(r"^[A-Za-z0-9+/]{43}=$")
_MAX_ROOT = 2048


def _no_dupes(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise RecoveryDenied("duplicate recovery trust field")
        data[key] = value
    return data


def _public_key(value):
    try:
        if not isinstance(value, str) or len(value) != 44:
            raise ValueError("invalid key encoding")
        raw = base64.b64decode(value, validate=True)
        if len(raw) != 32:
            raise ValueError("invalid Ed25519 key")
        return raw
    except (ValueError, TypeError, binascii.Error):
        raise RecoveryDenied("invalid recovery trust signing key") from None


def load_recovery_trust_root(*, tenant: str, old_key_arn: str,
                             old_key_pin: str, now: int | None = None):
    if (not isinstance(tenant, str) or not _TENANT.fullmatch(tenant)
            or not isinstance(old_key_arn, str) or not _KEY.fullmatch(old_key_arn)
            or not isinstance(old_key_pin, str) or not _PIN.fullmatch(old_key_pin)):
        raise RecoveryDenied("invalid recovery trust scope")
    if now is None:
        now = int(time.time())
    if type(now) is not int:
        raise RecoveryDenied("invalid recovery verification clock")
    try:
        with _ROOT_PATH.open("rb") as fd:
            body = fd.read(_MAX_ROOT + 1)
    except OSError:
        raise RecoveryDenied("external recovery trust root not provisioned") from None
    if len(body) > _MAX_ROOT:
        raise RecoveryDenied("oversized recovery trust root")
    try:
        root = json.loads(body.decode("ascii"), object_pairs_hook=_no_dupes)
    except (ValueError, UnicodeError):
        raise RecoveryDenied("invalid recovery trust root") from None
    if (not isinstance(root, dict) or set(root) != _KEYS
            or root.get("schema") != "notarai.recovery-root.v1"
            or root.get("tenant_id") != tenant
            or root.get("old_key_arn") != old_key_arn
            or root.get("old_key_pin") != old_key_pin
            or type(root.get("expires_at")) is not int
            or not now < root["expires_at"] < 4102444800):
        raise RecoveryDenied("recovery root not approved for this document")
    custodian = _public_key(root["custodian_public_key_b64"])
    trustee = _public_key(root["trustee_public_key_b64"])
    if custodian == trustee:
        raise RecoveryDenied("recovery trust requires distinct signers")
    return custodian, trustee
