"""Synthetic bridge tests: live v3 crypto with an untrusted S3 handshake.

These tests do not assert genuine NSM, real AWS, external forms, or GO status.
"""
import asyncio
import base64
import json

import pytest
pytest.importorskip("cbor2")

from confidential.customer_attested_release import challenge_user_data
from confidential.customer_release import _json, envelope_sha256
from confidential.customer_v3_worker import (
    DispatchDenied, _challenge, _message, _trust_from_image,
    process_queued_v3,
)
from test_customer_v3_execution import create_case


def _put_control(s3, job, name, value):
    key = f"kancelarie/pilot01/confidential-control/{job}/{name}"
    s3.items[key] = {"version": "synthetic-control-v1", "bytes": value}


def _setup(monkeypatch):
    args, ddb, s3, sqs = create_case(monkeypatch)
    key = "kancelarie/pilot01/confidential/case01/object01.json"
    envelope = json.loads(s3.items[key]["bytes"])
    nonce = b"N" * 32
    context = {
        "schema": "notarai.customer-nitro-challenge.v1",
        "job_id": "job01", "envelope_sha256": envelope_sha256(envelope),
        "created_at": 1000, "expires_at": 1180,
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "user_data_b64": base64.b64encode(
            challenge_user_data(envelope, job_id="job01", nonce=nonce)
        ).decode("ascii"),
    }
    _put_control(s3, "job01", "challenge.json", _json(context))
    _put_control(s3, "job01", "grant.json", _json(args["grant"]))

    # create_case has already attested its *synthetic* guest; use that exact
    # ephemeral recipient to verify the real asymmetric unwrap in this test.
    guest = args["guest"]
    monkeypatch.setattr(guest, "attest", lambda *_, **__: b"FAKE-NSM")
    monkeypatch.setattr("confidential.customer_v3_worker.CustomerGuestSession", lambda: guest)
    monkeypatch.setattr("confidential.customer_v3_worker._trust_from_image",
                        lambda: ("notary01", args["pinned_notary_signing_public_raw"]))
    monkeypatch.setattr("confidential.customer_v3_worker.time.time", lambda: 1001)
    seen = []
    async def fake_preview(job_id, fields):
        seen.append((job_id, dict(fields)))
    monkeypatch.setattr("confidential.worker._prepare_fictional_form", fake_preview)
    return args, ddb, s3, sqs, context, seen


def test_v3_fifo_to_customer_attested_handshake_to_preview(monkeypatch):
    args, ddb, s3, sqs, _, seen = _setup(monkeypatch)
    result = asyncio.run(process_queued_v3(
        s3=s3, ddb=ddb, tenant="pilot01", bucket="synthetic-three-zero",
        body=sqs.messages[0]["MessageBody"], now=1001, poll_seconds=0,
    ))
    assert result["status"] == "preview_completed"
    assert result["submitted"] is False
    assert seen == [("job01", {"name": "FAKE-SECRET-CANARY", "reference": "abc01"})]
    assert "release_consumed_sha256" in ddb.rows["JOB#pilot01#job01"]
    assert s3.items["kancelarie/pilot01/confidential-control/job01/attestation.cbor"]["bytes"] == b"FAKE-NSM"
    for key, item in s3.items.items():
        assert b"FAKE-SECRET-CANARY" not in item["bytes"]
    with pytest.raises(DispatchDenied):
        asyncio.run(process_queued_v3(
            s3=s3, ddb=ddb, tenant="pilot01", bucket="synthetic-three-zero",
            body=sqs.messages[0]["MessageBody"], now=1001, poll_seconds=0,
        ))
    assert len(seen) == 1


def test_wrong_challenge_digest_denied_before_new_attestation(monkeypatch):
    args, ddb, s3, sqs, context, seen = _setup(monkeypatch)
    context["envelope_sha256"] = "0" * 64
    _put_control(s3, "job01", "challenge.json", _json(context))
    with pytest.raises(DispatchDenied):
        asyncio.run(process_queued_v3(
            s3=s3, ddb=ddb, tenant="pilot01", bucket="synthetic-three-zero",
            body=sqs.messages[0]["MessageBody"], now=1001, poll_seconds=0,
        ))
    assert not seen
    assert "release_consumed_sha256" not in ddb.rows["JOB#pilot01#job01"]
    assert "kancelarie/pilot01/confidential-control/job01/attestation.cbor" not in s3.items


def test_wrong_tenant_message_and_replay_denied():
    good = {"schema": "notarai.customer-job.v1", "tenant_id": "pilot01",
            "case_id": "case01", "object_id": "object01", "job_id": "job01",
            "s3_version": "version-01"}
    assert _message(json.dumps(good), "pilot01") == (
        "case01", "object01", "job01", "version-01")
    with pytest.raises(DispatchDenied):
        _message(json.dumps(dict(good, tenant_id="pilot02")), "pilot01")
    with pytest.raises(ValueError):
        _message(json.dumps(good)[:-1] + ',"job_id":"duplicate"}', "pilot01")


def test_customer_challenge_wrong_user_data_and_expiry(monkeypatch):
    _, _, s3, _, context, _ = _setup(monkeypatch)
    env = json.loads(s3.items[
        "kancelarie/pilot01/confidential/case01/object01.json"]["bytes"])
    assert _challenge(_json(context), envelope=env, job_id="job01", now=1001) == b"N" * 32
    with pytest.raises(DispatchDenied):
        _challenge(_json(context), envelope=env, job_id="job01", now=1180)
    context["user_data_b64"] = base64.b64encode(b"0" * 32).decode("ascii")
    with pytest.raises(DispatchDenied):
        _challenge(_json(context), envelope=env, job_id="job01", now=1001)


def test_trust_file_strictly_image_pinned_format(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    public = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    file = tmp_path / "trust.json"
    file.write_bytes(_json({"schema": "notarai.customer-origin-trust.v1",
                            "issuer_id": "notary01",
                            "public_ed25519_b64": base64.b64encode(public).decode("ascii")}))
    assert _trust_from_image(file) == ("notary01", public)
    file.write_text('{"schema":"notarai.customer-origin-trust.v1","issuer_id":"bad",'
                    '"issuer_id":"evil","public_ed25519_b64":"abc"}')
    with pytest.raises(ValueError):
        _trust_from_image(file)


def test_origin_trust_bake_requires_explicit_key(tmp_path):
    from confidential.bake_trust import bake
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    public = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    encoded = base64.b64encode(public).decode("ascii")
    destination = tmp_path / "trust" / "customer-origin-v1.json"
    with pytest.raises(ValueError):
        bake(issuer_id="", signing_public_b64=encoded, target=destination)
    with pytest.raises(ValueError):
        bake(issuer_id="notary01", signing_public_b64="bad", target=destination)
    assert not destination.exists()
    bake(issuer_id="notary01", signing_public_b64=encoded, target=destination)
    assert _trust_from_image(destination) == ("notary01", public)
    with pytest.raises(FileExistsError):
        bake(issuer_id="notary01", signing_public_b64=encoded, target=destination)
