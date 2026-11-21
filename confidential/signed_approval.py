"""Versioned, narrowly scoped proof of notary approval (PREVIEW-ONLY R&D).

Not enabled in API, Nitro worker, or real portal adapters. The approval
message is signed by a separately enrolled user-held Ed25519 key; the server
has only a trusted public-key record. A verified signature is NOT an eIDAS
qualified signature or proof of user presence. Production needs WebAuthn or
a comparable user-verification ceremony plus independent document review.

No plaintext form values or customer data belong in this module or its ledger.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import json
import re
import time
from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9_-]{16,80}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_NONCE = re.compile(r"^[0-9a-f]{32}$")
_HOST = re.compile(r"^(?=.{1,253}$)[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?)+$")
_FIELDS = frozenset({
    "version", "tenant_id", "actor_id", "key_id", "job_id", "form_id",
    "action", "origin", "form_digest", "document_digest",
    "nonce", "issued_at", "expires_at",
})
_DOMAIN = b"notarai.confidential.approval.v1\n"


class ApprovalRejected(ValueError):
    """Generic rejection: never embed user data or AWS error text."""


def _valid_origin(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 255:
        return False
    try:
        url = urlsplit(value)
        hostname = url.hostname
        port = url.port
    except ValueError:
        return False
    try:
        ipaddress.ip_address(hostname or "")
    except ValueError:
        pass
    else:
        return False  # no direct IPv4/IPv6 destination, including loopback
    return (
        url.scheme == "https"
        and hostname is not None
        and bool(_HOST.fullmatch(hostname))
        and hostname == hostname.lower()
        and url.username is None and url.password is None
        and not url.path and not url.query and not url.fragment
        and (port is None or port == 443)
        and value == "https://" + hostname + (":443" if port == 443 else "")
    )


@dataclass(frozen=True)
class ApprovalIntent:
    tenant_id: str
    actor_id: str
    key_id: str
    job_id: str
    form_id: str
    action: str
    origin: str
    form_digest: str
    document_digest: str
    nonce: str
    issued_at: int
    expires_at: int

    @classmethod
    def parse(cls, payload: Mapping[str, object]) -> "ApprovalIntent":
        if not isinstance(payload, Mapping) or set(payload) != _FIELDS:
            raise ApprovalRejected("invalid approval fields")
        if type(payload["version"]) is not int or payload["version"] != 1:
            raise ApprovalRejected("unsupported approval version")
        for key in ("tenant_id", "actor_id", "job_id", "form_id"):
            value = payload[key]
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise ApprovalRejected("invalid approval identity")
        key_id = payload["key_id"]
        if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
            raise ApprovalRejected("invalid signing key")
        if payload["action"] != "submit-form":
            raise ApprovalRejected("unsupported operation")
        if not _valid_origin(payload["origin"]):
            raise ApprovalRejected("untrusted destination origin")
        for name in ("form_digest", "document_digest"):
            digest = payload[name]
            if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
                raise ApprovalRejected("invalid content fingerprint")
        nonce = payload["nonce"]
        if not isinstance(nonce, str) or not _NONCE.fullmatch(nonce):
            raise ApprovalRejected("invalid replay nonce")
        issued, expires = payload["issued_at"], payload["expires_at"]
        if (type(issued) is not int or type(expires) is not int or
                issued < 0 or expires <= issued or expires - issued > 300):
            raise ApprovalRejected("invalid approval validity window")
        return cls(
            tenant_id=payload["tenant_id"], actor_id=payload["actor_id"],
            key_id=key_id, job_id=payload["job_id"], form_id=payload["form_id"],
            action="submit-form", origin=payload["origin"],
            form_digest=payload["form_digest"], document_digest=payload["document_digest"],
            nonce=nonce, issued_at=issued, expires_at=expires,
        )

    def canonical_payload(self) -> dict:
        return {"version": 1, **{
            key: getattr(self, key) for key in sorted(_FIELDS - {"version"})
        }}

    def signed_bytes(self) -> bytes:
        return _DOMAIN + json.dumps(
            self.canonical_payload(), ensure_ascii=True, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("ascii")


@dataclass(frozen=True)
class EnrolledCredential:
    """Record supplied ONLY by an independently trusted registry."""

    tenant_id: str
    actor_id: str
    key_id: str
    ed25519_public_key: bytes
    role: str
    active: bool


class CredentialRegistry(Protocol):
    def get(self, tenant_id: str, key_id: str) -> EnrolledCredential | None: ...


class ApprovalLedger(Protocol):
    def consume(self, intent: ApprovalIntent, signature: bytes) -> None: ...


class DynamoCredentialRegistry:
    """Read-only enrollment directory. A signed user request cannot enroll a key.

    A separate, independently authenticated and user-verified enrollment
    ceremony must populate this table. This module never creates credentials.
    """

    def __init__(self, client, *, table_name: str, tenant_id: str):
        if (
            not isinstance(tenant_id, str) or
            not re.fullmatch(r"[a-z0-9]{1,12}", tenant_id) or
            table_name != "notarai-confidential-credentials-" + tenant_id
        ):
            raise ApprovalRejected("invalid credential registry")
        self._ddb = client
        self._table = table_name
        self._tenant = tenant_id

    def get(self, tenant_id: str, key_id: str) -> EnrolledCredential | None:
        if tenant_id != self._tenant or not _KEY_ID.fullmatch(key_id):
            return None
        try:
            record = self._ddb.get_item(
                TableName=self._table,
                Key={"pk": {"S": f"KEY#{tenant_id}#{key_id}"}},
                ConsistentRead=True,
            ).get("Item") or {}
        except Exception:
            raise ApprovalRejected("signing key registry unavailable") from None
        if not record:
            return None
        try:
            pub = base64.b64decode(
                record["ed25519_public_key"]["S"], validate=True
            )
            cred = EnrolledCredential(
                tenant_id=record["tenant_id"]["S"],
                actor_id=record["actor_id"]["S"],
                key_id=record["key_id"]["S"],
                ed25519_public_key=pub,
                role=record["role"]["S"],
                active=record["active"]["BOOL"] is True,
            )
        except (KeyError, TypeError, ValueError, binascii.Error):
            raise ApprovalRejected("invalid registered credential") from None
        if (
            cred.tenant_id != tenant_id or cred.key_id != key_id
            or not _ID.fullmatch(cred.actor_id)
            or len(cred.ed25519_public_key) != 32
        ):
            raise ApprovalRejected("registered credential has invalid scope")
        return cred


def verify_and_consume(
    signed: Mapping[str, object],
    *,
    registry: CredentialRegistry,
    ledger: ApprovalLedger,
    expected_tenant: str,
    expected_actor: str,
    expected_job: str,
    expected_form: str,
    expected_origin: str,
    expected_form_digest: str,
    expected_document_digest: str,
    now: int | None = None,
) -> ApprovalIntent:
    """Atomic one-time approval at an independently trusted execution boundary.

    Never accept a boolean `approved=true`. An enrollment lookup and an
    independent expected document hash are mandatory. The consumer must know
    the same displayed form and document that the notary reviewed.
    """
    if not isinstance(signed, Mapping) or set(signed) != {"intent", "signature"}:
        raise ApprovalRejected("invalid signed approval")
    intent = ApprovalIntent.parse(signed["intent"])
    if not _valid_origin(expected_origin):
        raise ApprovalRejected("untrusted expected destination")
    if (
        intent.tenant_id != expected_tenant
        or intent.actor_id != expected_actor
        or intent.job_id != expected_job
        or intent.form_id != expected_form
        or intent.origin != expected_origin
        or intent.form_digest != expected_form_digest
        or intent.document_digest != expected_document_digest
    ):
        raise ApprovalRejected("approval scope mismatch")
    timestamp = int(time.time()) if now is None else now
    if type(timestamp) is not int or timestamp < intent.issued_at - 60 or timestamp >= intent.expires_at:
        raise ApprovalRejected("approval is not currently valid")
    sig = signed["signature"]
    if not isinstance(sig, str) or len(sig) != 88:
        raise ApprovalRejected("invalid signature format")
    try:
        raw_signature = base64.b64decode(sig, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ApprovalRejected("invalid signature format") from exc
    if len(raw_signature) != 64:
        raise ApprovalRejected("invalid signature size")

    credential = registry.get(intent.tenant_id, intent.key_id)
    if (
        not isinstance(credential, EnrolledCredential)
        or not credential.active
        or credential.role != "notary"
        or credential.tenant_id != intent.tenant_id
        or credential.actor_id != intent.actor_id
        or credential.key_id != intent.key_id
        or not isinstance(credential.ed25519_public_key, bytes)
        or len(credential.ed25519_public_key) != 32
    ):
        raise ApprovalRejected("signing credential not authorized")
    try:
        Ed25519PublicKey.from_public_bytes(
            credential.ed25519_public_key
        ).verify(raw_signature, intent.signed_bytes())
    except (ValueError, InvalidSignature) as exc:
        raise ApprovalRejected("signature verification failed") from exc

    # Must be an atomic, durable reservation BEFORE the irreversible click.
    # On crash/timeout we DO NOT undo it: a partial submission may have happened.
    ledger.consume(intent, raw_signature)
    return intent


class DynamoApprovalLedger:
    """Two conditional writes: reject nonce replay AND repeat job/form/action.

    Table schema: `pk` String partition key only. Uses TransactWriteItems;
    non-success can never authorize a click. No TTL: replays stay blocked
    across delayed messages and later tasks. Retention is an operator decision.
    """

    def __init__(self, client, *, table_name: str, tenant_id: str):
        if (
            not isinstance(table_name, str) or
            not re.fullmatch(r"notarai-confidential-approvals-[a-z0-9]{1,12}", table_name)
            or not isinstance(tenant_id, str) or
            not re.fullmatch(r"[a-z0-9]{1,12}", tenant_id) or
            table_name != "notarai-confidential-approvals-" + tenant_id
        ):
            raise ApprovalRejected("invalid approval table")
        self._client = client
        self._table = table_name
        self._tenant = tenant_id

    def consume(self, intent: ApprovalIntent, signature: bytes) -> None:
        if intent.tenant_id != self._tenant:
            raise ApprovalRejected("approval tenant mismatch")
        intent_hash = hashlib.sha256(intent.signed_bytes()).hexdigest()
        nonce_key = f"N#{self._tenant}#{intent.nonce}"
        operation_key = (
            f"O#{self._tenant}#{intent.job_id}#{intent.form_id}#{intent.action}"
        )
        # No approval values, document text or identifying names stored here.
        writes = []
        for pk in (nonce_key, operation_key):
            writes.append({"Put": {
                "TableName": self._table,
                "Item": {
                    "pk": {"S": pk},
                    "intent_sha256": {"S": intent_hash},
                    "state": {"S": "reserved_before_execution"},
                    "issued_at": {"N": str(intent.issued_at)},
                },
                "ConditionExpression": "attribute_not_exists(pk)",
            }})
        try:
            self._client.transact_write_items(TransactItems=writes)
        except Exception as exc:
            # No plaintext/PII/API request included in logged errors.
            raise ApprovalRejected("approval already used or ledger unavailable") from None


class SignedApprovalGate:
    """Callable adapter for fill_form(..., approve=gate.callback).

    Construct only using independent trusted scope, document fingerprint,
    registry and ledger; never from client-supplied 'expected' fields.
    THIS IS NOT WIRED INTO REAL PORTAL SUBMISSIONS.
    """

    def __init__(
        self, *, signed, registry, ledger, tenant_id, actor_id,
        job_id, form_id, origin, document_digest, now=None,
    ):
        self._signed = signed
        self._registry = registry
        self._ledger = ledger
        self._tenant = tenant_id
        self._actor = actor_id
        self._job = job_id
        self._form = form_id
        self._origin = origin
        self._document = document_digest
        self._now = now

    async def callback(self, job_id: str, form_id: str, form_digest: str) -> bool:
        if job_id != self._job or form_id != self._form:
            raise ApprovalRejected("approval callback scope mismatch")
        verify_and_consume(
            self._signed, registry=self._registry, ledger=self._ledger,
            expected_tenant=self._tenant, expected_actor=self._actor,
            expected_job=job_id, expected_form=form_id,
            expected_origin=self._origin,
            expected_form_digest=form_digest,
            expected_document_digest=self._document,
            now=self._now,
        )
        return True
