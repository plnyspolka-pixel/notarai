"""Synthetic signed-approval verification and atomic replay tests.

No notary credentials, official submissions, customer documents, or AWS calls.
"""
import asyncio
import base64
import copy
import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from confidential.signed_approval import (
    ApprovalIntent, ApprovalRejected, DynamoApprovalLedger, EnrolledCredential,
    SignedApprovalGate, verify_and_consume,
)
from confidential.form_engine import BlockedAction, fill_form
from test_confidential import Page, form


TENANT = "pilot01"
ACTOR = "notary_demo"
KEY = "demo_public_key_0001"
JOB = "synthetic_job"
FORM = "fixture"
ORIGIN = "https://forms.example.test"
DOC = "f" * 64
TIME = 1800000060


def form_digest(values=None):
    values = values or {"name": "FICTIONAL PERSON"}
    body = json.dumps(
        {"job_id": JOB, "form_id": FORM, "fields": values},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def payload(**updates):
    result = {
        "version": 1, "tenant_id": TENANT, "actor_id": ACTOR, "key_id": KEY,
        "job_id": JOB, "form_id": FORM, "action": "submit-form",
        "origin": ORIGIN, "form_digest": form_digest(), "document_digest": DOC,
        "nonce": "0" * 32, "issued_at": 1800000000, "expires_at": 1800000300,
    }
    result.update(updates)
    return result


class Registry:
    def __init__(self, key):
        self.record = EnrolledCredential(
            tenant_id=TENANT, actor_id=ACTOR, key_id=KEY,
            ed25519_public_key=key.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw
            ),
            role="notary", active=True,
        )

    def get(self, tenant, key_id):
        if (tenant, key_id) == (self.record.tenant_id, self.record.key_id):
            return self.record
        return None


class Conflict(Exception):
    pass


class FakeDynamo:
    def __init__(self):
        self.keys = set()
        self.calls = []
        self.raise_error = False

    def transact_write_items(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_error:
            raise RuntimeError("SYNTHETIC unavailable")
        writes = kwargs["TransactItems"]
        assert len(writes) == 2
        pending = set()
        for write in writes:
            assert write["Put"]["ConditionExpression"] == "attribute_not_exists(pk)"
            pk = write["Put"]["Item"]["pk"]["S"]
            assert pk not in pending
            if pk in self.keys:
                raise Conflict("simulated conditional conflict")
            pending.add(pk)
        self.keys.update(pending)


def signing():
    private = Ed25519PrivateKey.generate()
    return private, Registry(private), FakeDynamo()


def sign(private, data=None):
    value = data or payload()
    message = ApprovalIntent.parse(value).signed_bytes()
    return {
        "intent": value, "signature": base64.b64encode(
            private.sign(message)
        ).decode("ascii")
    }


def attempt(signed, registry, ddb, *, now=TIME, expected_doc=DOC, expected_form_digest=None):
    return verify_and_consume(
        signed, registry=registry,
        ledger=DynamoApprovalLedger(
            ddb, table_name=f"notarai-confidential-approvals-{TENANT}",
            tenant_id=TENANT,
        ),
        expected_tenant=TENANT, expected_actor=ACTOR, expected_job=JOB,
        expected_form=FORM, expected_origin=ORIGIN,
        expected_form_digest=expected_form_digest or form_digest(),
        expected_document_digest=expected_doc, now=now,
    )


def test_valid_notary_signature_consumes_nonce_and_operation_once():
    private, registry, ddb = signing()
    approval = sign(private)
    intent = attempt(approval, registry, ddb)
    assert intent.job_id == JOB and intent.document_digest == DOC
    assert len(ddb.keys) == 2
    assert all(k.startswith(("N#pilot01#", "O#pilot01#")) for k in ddb.keys)
    items = [item["Put"]["Item"] for item in ddb.calls[0]["TransactItems"]]
    assert all(item["state"]["S"] == "reserved_before_execution" for item in items)
    assert not any("signature" in item or "plaintext" in item for item in items)
    with pytest.raises(ApprovalRejected, match="used"):
        attempt(approval, registry, ddb)


def test_document_or_field_change_invalidates_approval_before_ledger():
    private, registry, ddb = signing()
    signed = sign(private)
    with pytest.raises(ApprovalRejected, match="scope"):
        attempt(signed, registry, ddb, expected_doc="e" * 64)
    with pytest.raises(ApprovalRejected, match="scope"):
        attempt(signed, registry, ddb, expected_form_digest="a" * 64)
    assert ddb.keys == set()


def test_expiration_future_and_maximum_window():
    private, registry, ddb = signing()
    signed = sign(private)
    for clock in (1799999900, 1800000300, 1800003000):
        with pytest.raises(ApprovalRejected, match="valid"):
            attempt(signed, registry, ddb, now=clock)
    with pytest.raises(ApprovalRejected):
        ApprovalIntent.parse(payload(expires_at=1800010000))
    assert not ddb.keys


@pytest.mark.parametrize("changes", [
    {"actor_id": "other_person"},
    {"tenant_id": "other_tenant"},
    {"job_id": "other_job"},
    {"form_id": "other_form"},
    {"origin": "https://evil.example.test"},
    {"origin": "http://forms.example.test"},
    {"origin": "https://forms.example.test.evil.org"},
    {"action": "approve-all"},
    {"form_digest": "a" * 64},
    {"document_digest": "a" * 64},
    {"nonce": "../bad"},
    {"version": True},
    {"issued_at": 1800000200, "expires_at": 1800000100},
])
def test_invalid_or_wrongly_scoped_messages_are_denied(changes):
    private, registry, ddb = signing()
    candidate = payload(**changes)
    if changes.get("action") == "approve-all" or changes.get("nonce") == "../bad" or (
        changes.get("version") is True
    ) or changes.get("origin", "").startswith("http:") or (
        changes.get("issued_at") == 1800000200
    ):
        with pytest.raises(ApprovalRejected):
            sign(private, candidate)
    else:
        with pytest.raises(ApprovalRejected):
            attempt(sign(private, candidate), registry, ddb)
    assert not ddb.keys


def test_attacker_cannot_modify_valid_signed_payload():
    private, registry, ddb = signing()
    good = sign(private)
    forged = copy.deepcopy(good)
    forged["intent"]["document_digest"] = "e" * 64
    with pytest.raises(ApprovalRejected, match="signature"):
        attempt(forged, registry, ddb, expected_doc="e" * 64)
    assert not ddb.keys


def test_unregistered_revoked_or_wrong_role_credentials_are_denied():
    private, registry, ddb = signing()
    signed = sign(private)
    previous = registry.record
    for change in ({"active": False}, {"role": "assistant"},
                   {"actor_id": "other_actor"}):
        registry.record = EnrolledCredential(**{**previous.__dict__, **change})
        with pytest.raises(ApprovalRejected):
            attempt(signed, registry, ddb)
    registry.record = previous
    registry.record = EnrolledCredential(
        **{**previous.__dict__, "ed25519_public_key": b"0" * 32}
    )
    with pytest.raises(ApprovalRejected):
        attempt(signed, registry, ddb)
    assert not ddb.keys


def test_same_operation_with_new_nonce_cannot_execute_twice():
    private, registry, ddb = signing()
    attempt(sign(private), registry, ddb)
    distinct_nonce = sign(private, payload(nonce="1" * 32))
    with pytest.raises(ApprovalRejected):
        attempt(distinct_nonce, registry, ddb)
    assert len(ddb.keys) == 2


def test_ledger_failure_blocks_all_executions():
    private, registry, ddb = signing()
    ddb.raise_error = True
    with pytest.raises(ApprovalRejected, match="ledger"):
        attempt(sign(private), registry, ddb)


def test_signed_callback_binds_exact_browser_values_and_prevents_replay():
    private, registry, ddb = signing()
    data = {"name": "FICTIONAL PERSON"}
    signed = sign(private)
    gate = SignedApprovalGate(
        signed=signed, registry=registry,
        ledger=DynamoApprovalLedger(
            ddb, table_name=f"notarai-confidential-approvals-{TENANT}",
            tenant_id=TENANT,
        ),
        tenant_id=TENANT, actor_id=ACTOR, job_id=JOB,
        form_id=FORM, origin=ORIGIN, document_digest=DOC, now=TIME,
    )

    async def run():
        p1 = Page()
        result = await fill_form(
            p1, form(), data, job_id=JOB, submit=True, approve=gate.callback
        )
        assert result.submitted is True and p1.clicks == ["#submit"]
        p2 = Page()
        with pytest.raises(ApprovalRejected, match="used"):
            await fill_form(
                p2, form(), data, job_id=JOB, submit=True, approve=gate.callback
            )
        assert p2.clicks == []
        p3 = Page()
        with pytest.raises(ApprovalRejected, match="scope"):
            await fill_form(
                p3, form(), {"name": "CHANGED"}, job_id=JOB,
                submit=True, approve=gate.callback
            )
        assert p3.clicks == []
    asyncio.run(run())


def test_canonical_encoding_and_validation_are_deterministic():
    intent = ApprovalIntent.parse(payload())
    assert intent.signed_bytes().startswith(b"notarai.confidential.approval.v1\n")
    assert intent.signed_bytes() == ApprovalIntent.parse(
        json.loads(json.dumps(intent.canonical_payload()))
    ).signed_bytes()
    with pytest.raises(ApprovalRejected):
        ApprovalIntent.parse({**payload(), "extra": True})


def test_invalid_table_scope_rejected():
    with pytest.raises(ApprovalRejected):
        DynamoApprovalLedger(FakeDynamo(), table_name="notarai-users", tenant_id=TENANT)
