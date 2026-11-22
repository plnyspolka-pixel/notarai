"""AUTO is default for all confidential preview work, never a submit authority.

These tests use no AWS account, no customer data and no real official portal.
"""
import asyncio
import json
import sys
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.datastructures import QueryParams

from confidential.auto_mode import DEFAULT_AUTO, UnsafeAutoRequest, validate_preview_options
from confidential.form_engine import BlockedAction, fill_form
from confidential.router import automatic_policy, queue_preview, preview_status
from test_confidential_job_ledger import FakeDdb
from test_confidential import Page, Route, form


def run(coro):
    return asyncio.run(coro)


def test_auto_is_immutable_default_with_thinking_off():
    policy = DEFAULT_AUTO
    assert policy.mode == "auto"
    assert not policy.thinking_enabled
    assert not policy.can_submit
    assert not policy.can_sign
    assert not policy.external_writes_enabled
    assert policy.requires_human_for_external_effect
    assert "send_application" in policy.public()["blocked_stages"]
    with pytest.raises(FrozenInstanceError):
        policy.can_submit = True


@pytest.mark.parametrize("query", [
    "mode=supervised", "mode=manual", "mode=auto&mode=auto",
    "submit=true", "approved=true", "thinking=true",
    "mode=auto&submit=false", "operation=send", "mode=",
])
def test_auto_api_rejects_unknown_or_dangerous_parameters(query):
    with pytest.raises(UnsafeAutoRequest):
        validate_preview_options(QueryParams(query), has_body=False)


def test_auto_api_accepts_only_empty_or_explicit_auto_mode():
    for query in ("", "mode=auto"):
        assert validate_preview_options(
            QueryParams(query), has_body=False
        ) is DEFAULT_AUTO
        with pytest.raises(UnsafeAutoRequest):
            validate_preview_options(QueryParams(query), has_body=True)


def test_automatic_form_fill_does_not_click_submit():
    async def scenario():
        page = Page()
        result = await fill_form(
            page, form(), {"name": "FICTIONAL"},
            job_id="synthetic_job",
        )
        assert not result.submitted
        assert page.clicks == []
        assert page.context.init_script is not None
        assert "preventDefault" in page.context.init_script
        assert page.context.websocket_filter is not None
        get = Route("https://forms.example.test/assets.js", "GET")
        post = Route("https://forms.example.test/api/save", "POST")
        put = Route("https://forms.example.test/api/save", "PUT")
        delete = Route("https://forms.example.test/api/delete", "DELETE")
        external = Route("https://evil.example.org/x", "GET")
        for item in (get, post, put, delete, external):
            await page.filter(item)
        assert get.action == "continue"
        assert all(item.action == "abort" for item in
                   (post, put, delete, external))
        class Socket:
            closed = False
            async def close(self):
                self.closed = True
        ws = Socket()
        await page.context.websocket_filter(ws)
        assert ws.closed
    run(scenario())


def test_signed_approval_cannot_upgrade_default_auto_to_submit():
    async def scenario():
        page = Page()
        called = []
        async def approve(*args):
            called.append(args)
            return True
        with pytest.raises(BlockedAction, match="never submits"):
            await fill_form(
                page, form(), {"name": "FICTIONAL"}, job_id="pilot",
                submit=True, approve=approve,
            )
        assert not called and not page.clicks
        assert page.fills == []
    run(scenario())


def test_unexpected_browser_mode_or_missing_safety_controls_fails_closed():
    async def scenario():
        with pytest.raises(BlockedAction, match="mode"):
            await fill_form(
                Page(), form(), {"name": "FICTIONAL"},
                job_id="pilot", execution_mode="unsafe",
            )
        page = Page()
        page.context = None
        with pytest.raises(BlockedAction, match="controls"):
            await fill_form(
                page, form(), {"name": "FICTIONAL"}, job_id="pilot",
            )
        assert not page.fills
    run(scenario())


class RequestFake:
    def __init__(self, query="", body=b""):
        self.state = SimpleNamespace(
            email="notary@example.test", serwis=False, kancelaria="pilot01"
        )
        self.query_params = QueryParams(query)
        self.body_bytes = body
    async def stream(self):
        yield self.body_bytes


def setup_tenant(monkeypatch):
    monkeypatch.setitem(sys.modules, "autoryzacja", SimpleNamespace(MULTI=True))
    monkeypatch.setitem(sys.modules, "magazyn", SimpleNamespace(TRYB="s3"))
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_ALLOWED_TENANT", "pilot01")


def test_scoped_policy_endpoint_is_read_only_and_cannot_submit(monkeypatch):
    setup_tenant(monkeypatch)
    response = automatic_policy(RequestFake())
    doc = json.loads(response.body)
    assert doc["mode"] == "auto" and doc["can_submit"] is False
    assert doc["thinking_enabled"] is False
    assert response.headers["cache-control"] == "no-store"
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_ALLOWED_TENANT", "other")
    with pytest.raises(HTTPException) as error:
        automatic_policy(RequestFake())
    assert error.value.status_code == 403


@pytest.mark.parametrize(("query", "body"), [
    ("mode=supervised", b""), ("submit=true", b""),
    ("", b'{"submit": true}'), ("mode=auto", b'{"thinking": true}'),
])
def test_preview_blocks_mutative_input_before_any_s3_or_sqs(
    monkeypatch, query, body
):
    setup_tenant(monkeypatch)
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_JOB_TENANT", "pilot01")
    with pytest.raises(HTTPException) as error:
        run(queue_preview(RequestFake(query, body), "case01", "scan01"))
    assert error.value.status_code == 400


def test_valid_default_auto_preview_queues_metadata_only(monkeypatch):
    setup_tenant(monkeypatch)
    class S3:
        def head_object(self, **kwargs):
            if kwargs["Key"] == "kancelarie/pilot01/confidential/case01/scan01.origin.json":
                # Separate signed-origin sidecar exists before SQS admission.
                return {"ContentLength": 160}
            assert kwargs["Key"] == "kancelarie/pilot01/confidential/case01/scan01.json"
            return {"VersionId": "v000001", "ContentLength": 120, "Metadata": {
                "document-version": "a" * 32,
                "content-sha256": "b" * 64,
            }}
    class SQS:
        calls = []
        def send_message(self, **kwargs):
            self.calls.append(kwargs)
    sqs = SQS()
    ddb = FakeDdb()
    import confidential.router as router
    class FakeRegistry:
        called = []
        def claim_preview(self, **kwargs):
            self.called.append(kwargs)
    registry = FakeRegistry()
    monkeypatch.setattr(router, "_registry", lambda tenant: registry)
    import boto3
    module = sys.modules["magazyn"]
    module._klient_s3 = lambda: S3()
    monkeypatch.setattr(
        boto3, "client",
        lambda name, **k: ddb if name == "dynamodb" else sqs,
    )
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_JOB_TENANT", "pilot01")
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_BUCKET", "notarai-ciphertext-pilot01")
    monkeypatch.setenv(
        "PIECZAPP_CONFIDENTIAL_KMS_KEY_ARN",
        "arn:aws:kms:eu-central-1:111122223333:key/pilot",
    )
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_PUBLIC_KEY_SHA256", "A" * 43 + "=")
    monkeypatch.setenv(
        "PIECZAPP_CONFIDENTIAL_JOB_QUEUE_URL",
        "https://sqs.eu-central-1.amazonaws.com/111122223333/"
        "notarai-confidential-pilot01.fifo",
    )
    response = run(queue_preview(
        RequestFake(), "case01", "scan01",
    ))
    body = json.loads(response.body)
    assert response.status_code == 202
    assert body["mode"] == "auto"
    assert body["operation"] == "preview-only"
    assert body["thinking_enabled"] is False
    assert body["can_submit"] is False
    assert len(registry.called) == 1
    assert registry.called[0]["document_version"] == "a" * 32
    assert registry.called[0]["s3_version"] == "v000001"
    assert len(sqs.calls) == 1
    msg = json.loads(sqs.calls[0]["MessageBody"])
    assert set(msg) == {"tenant_id", "case_id", "object_id", "job_id", "s3_version"}
    assert msg["s3_version"] == "v000001"
    assert "mode" not in msg and "submit" not in msg
    assert sqs.calls[0]["MessageGroupId"] == "pilot01"
    assert len(ddb.rows) == 1
    assert next(iter(ddb.rows.values()))["state"]["S"] == "queued"
    assert next(iter(ddb.rows.values()))["s3_version"]["S"] == "v000001"
    job_status = json.loads(preview_status(RequestFake(), body["job_id"]).body)
    assert job_status["status"] == "queued"
    assert job_status["submitted"] is False


def test_unknown_job_returns_404_from_tenant_scoped_ledger(monkeypatch):
    setup_tenant(monkeypatch)
    import boto3
    ddb = FakeDdb()
    monkeypatch.setattr(boto3, "client", lambda name, **k: ddb)
    with pytest.raises(HTTPException) as exc:
        preview_status(RequestFake(), "missingjob")
    assert exc.value.status_code == 404
