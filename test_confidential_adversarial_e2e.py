"""SEC-12: synthetic adversarial matrix, never actual AWS proof."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from confidential.adversarial_gate import (
    ATTACKS, FAULTS, TENANTS, SCENARIO_NAMES,
    _attack, evaluate_gate, make_attempt, offline_matrix,
    synthetic_admission,
)


NOW = datetime(2026, 11, 22, 8, tzinfo=timezone.utc)


def test_two_positive_tenants_use_isolated_kms_keys_roles_no_submit():
    one, two = (make_attempt(t, NOW) for t in TENANTS)
    assert one.kms_key != two.kms_key
    assert one.task_role != two.task_role
    assert one.image_digest == two.image_digest
    assert synthetic_admission(one, now=NOW) == "preview_completed"
    assert synthetic_admission(two, now=NOW) == "preview_completed"
    assert one.submit is False and two.submit is False


@pytest.mark.parametrize("attack", ATTACKS)
def test_thirteen_operator_attacks_rejected(attack):
    baseline = make_attempt("pilot01", NOW)
    modified = _attack(baseline, attack, NOW)
    assert modified != baseline
    assert synthetic_admission(modified, now=NOW) == "DENIED"


@pytest.mark.parametrize("fault", FAULTS)
def test_four_fault_injections_never_submit_or_lose_scope(fault):
    attempt = replace(make_attempt("pilot01", NOW), fault=fault)
    assert synthetic_admission(attempt, now=NOW) == "needs_review"
    assert attempt.submit is False
    assert synthetic_admission(replace(attempt, submit=True), now=NOW) == "DENIED"


def test_matrix_complete_and_mock_is_explicit():
    rows = offline_matrix(now=NOW)
    assert len(rows) == 2 + len(ATTACKS) + len(FAULTS) == 19
    assert len(set(x["case"] for x in rows)) == len(SCENARIO_NAMES)
    assert all(x["source"] == "MOCK" and not x["submitted"] for x in rows)
    assert evaluate_gate(rows)["offline_matrix"] == "PASS"


def test_untrusted_live_flags_never_authorize_commercial_deployment():
    rows = offline_matrix(now=NOW)
    result = evaluate_gate(rows, custody_independent=True,
        hardware_evidence_verified=True, signed_evidence_verified=True,
        canary_hits=0)
    assert result["decision"] == "NO_GO" and result["commercial_go"] is False
    assert result["live_hardware"] == "BLOCKED"
    assert result["signed_evidence"] == "BLOCKED"


@pytest.mark.parametrize("case", SCENARIO_NAMES)
def test_missing_each_required_case_prevents_even_offline_pass(case):
    rows = tuple(x for x in offline_matrix(now=NOW) if x["case"] != case)
    assert evaluate_gate(rows)["offline_matrix"] == "FAIL"
    assert evaluate_gate(rows)["commercial_go"] is False


@pytest.mark.parametrize("attack", ATTACKS)
def test_forged_negative_pass_or_submission_rejected(attack):
    rows = list(offline_matrix(now=NOW))
    pos = next(i for i, row in enumerate(rows) if row["case"] == attack)
    rows[pos] = {**rows[pos], "outcome": "preview_completed", "submitted": True}
    assert evaluate_gate(tuple(rows))["offline_matrix"] == "FAIL"


def test_duplicate_or_changed_source_is_not_admitted():
    rows = list(offline_matrix(now=NOW))
    rows.append(dict(rows[0]))
    assert evaluate_gate(tuple(rows))["offline_matrix"] == "FAIL"
    assert evaluate_gate(tuple(rows))["commercial_go"] is False
    rows = list(offline_matrix(now=NOW))
    rows[0] = {**rows[0], "source": "AWS"}
    assert evaluate_gate(tuple(rows))["offline_matrix"] == "FAIL"

def test_real_worker_parser_rejects_cross_tenant_and_invalid_versions():
    import json
    from confidential.worker import _parse_message
    message = {"tenant_id": "pilot02", "case_id": "case01",
               "object_id": "object01", "job_id": "job01", "s3_version": "v001"}
    with pytest.raises(ValueError):
        _parse_message(json.dumps(message), "pilot01")
    with pytest.raises(ValueError):
        _parse_message(json.dumps({**message, "s3_version": "null"}), "pilot02")


def test_real_auto_api_rejects_submission_and_untrusted_flags():
    from confidential.auto_mode import UnsafeAutoRequest, validate_preview_options
    class Params:
        def __init__(self, items):
            self.items = items
        def multi_items(self):
            return self.items
    for params in ([("submit", "true")], [("mode", "supervised")],
                   [("approved", "true")], [("mode", "auto"), ("submit", "false")]):
        with pytest.raises(UnsafeAutoRequest):
            validate_preview_options(Params(params), has_body=False)


def test_real_form_adapter_refuses_auto_submit_before_browser_interaction():
    import asyncio
    from confidential.form_engine import BlockedAction, fill_form, TrustedForm
    form = TrustedForm("test", "https://forms.example.test/",
        ("https://forms.example.test",), {"name": "#name"}, "#send")
    async def rejected():
        with pytest.raises(BlockedAction):
            await fill_form(object(), form, {"name": "FICTIONAL"},
                            job_id="fictional", submit=True)
    asyncio.run(rejected())


def test_real_custodian_release_rejects_modified_signed_digest():
    from confidential.release_approval import verify_release
    from confidential.operator_boundary import BoundaryDenied
    from test_confidential_release_approval import signed_case
    data = signed_case()
    assert verify_release(**data)["zero_operator_access_proven"] is False
    data["envelope"]["payload"]["image_sha256"] = "0" * 64
    with pytest.raises(BoundaryDenied):
        verify_release(**data)


@pytest.mark.parametrize("tenant,key_byte", [("pilot01", 1), ("pilot02", 2)])
def test_synthetic_envelope_to_real_form_preview_for_two_tenants(tenant, key_byte):
    """Real AES-GCM + real form validator; only a FAKE key-unwrapper and browser."""
    import asyncio
    import base64
    import json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from confidential.envelope import Envelope
    from confidential.form_engine import TrustedForm, fill_form
    from test_confidential import Page

    key = bytes([key_byte]) * 32
    nonce = bytes(range(12))
    case_id, object_id = "fictional_case", "fictional_scan"
    data = {"form_id": "local-demo",
            "fields": {"name": "FICTIONAL-ONLY", "reference": tenant}}
    authenticated_scope = f"notarai-v1|{tenant}|{case_id}|{object_id}".encode()
    ciphertext = AESGCM(key).encrypt(nonce, json.dumps(data).encode(),
                                      authenticated_scope)
    key_arn = f"arn:aws:kms:eu-central-1:444455556666:key/synthetic-{tenant}"
    payload = {
        "version": 1, "algorithm": "AES-256-GCM+RSA-OAEP-SHA256",
        "tenant_id": tenant, "case_id": case_id, "object_id": object_id,
        "kms_key_arn": key_arn,
        "nonce": base64.b64encode(nonce).decode(),
        "wrapped_dek": base64.b64encode(b"x" * 384).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
    }
    envelope = Envelope.parse(payload)
    class FakeAttestedKms:
        def unwrap(self, wrapped, arn):
            assert wrapped == b"x" * 384 and arn == key_arn
            return key  # synthetic mock: NO hardware / real custody evidence
    opened = json.loads(envelope.open_inside_attested_task(FakeAttestedKms()))
    assert opened == data
    if tenant == "pilot01":
        wrong = {**payload, "tenant_id": "pilot02"}
    else:
        wrong = {**payload, "tenant_id": "pilot01"}
    from confidential.envelope import InvalidEnvelope
    with pytest.raises(InvalidEnvelope):
        Envelope.parse(wrong).open_inside_attested_task(FakeAttestedKms())

    async def preview():
        form = TrustedForm("local-demo", "https://forms.example.test/app",
            ("https://forms.example.test",),
            {"name": "#name", "reference": "#reference"}, "#submit")
        page = Page()
        result = await fill_form(page, form, opened["fields"],
                                 job_id="synthetic_job", submit=False)
        assert result.filled_fields == 2
        assert result.submitted is False and page.clicks == []
        assert page.fills == [("#name", "FICTIONAL-ONLY"),
                              ("#reference", tenant)]
    asyncio.run(preview())


@pytest.mark.parametrize("switch", ["true", "TRUE", "1", "on", "yes"])
def test_actual_confidential_api_blocks_unverified_commercial_flag(
    monkeypatch, switch
):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from confidential.router import _scope
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_COMMERCIAL_ENABLED", switch)
    # This denial happens before any user lookup, AWS read or document work.
    with pytest.raises(HTTPException) as error:
        _scope(SimpleNamespace())
    assert error.value.status_code == 503


@pytest.mark.parametrize("tenant", ("office01", "client01", "notary01"))
def test_api_refuses_nonpilot_scope_even_if_configured(monkeypatch, tenant):
    import sys
    from types import SimpleNamespace
    from fastapi import HTTPException
    from confidential.router import _scope

    monkeypatch.setitem(sys.modules, "autoryzacja", SimpleNamespace(MULTI=True))
    monkeypatch.setitem(sys.modules, "magazyn", SimpleNamespace(TRYB="s3"))
    monkeypatch.delenv("PIECZAPP_CONFIDENTIAL_COMMERCIAL_ENABLED", raising=False)
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_ALLOWED_TENANT", tenant)
    request = SimpleNamespace(state=SimpleNamespace(
        email="synthetic@example.test", serwis=False, kancelaria=tenant,
    ))
    with pytest.raises(HTTPException) as error:
        _scope(request)
    assert error.value.status_code == 503


@pytest.mark.parametrize("tenant", ("pilot01", "pilot02"))
def test_api_admits_only_configured_synthetic_pilot(monkeypatch, tenant):
    import sys
    from types import SimpleNamespace
    from confidential.router import _scope

    monkeypatch.setitem(sys.modules, "autoryzacja", SimpleNamespace(MULTI=True))
    monkeypatch.setitem(sys.modules, "magazyn", SimpleNamespace(TRYB="s3"))
    monkeypatch.delenv("PIECZAPP_CONFIDENTIAL_COMMERCIAL_ENABLED", raising=False)
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_ALLOWED_TENANT", tenant)
    request = SimpleNamespace(state=SimpleNamespace(
        email="synthetic@example.test", serwis=False, kancelaria=tenant,
    ))
    assert _scope(request) == tenant


@pytest.mark.parametrize(("flag", "code"), [
    ("--offline", 0), ("--check", 2),
])
def test_cli_emits_redacted_case_level_report_and_never_goes_live(
    monkeypatch, capsys, flag, code
):
    import json
    import sys
    from scripts.run_confidential_adversarial_e2e import main

    monkeypatch.setattr(sys, "argv", ["sec12", flag])
    assert main() == code
    output = json.loads(capsys.readouterr().out)
    assert output["run_type"] == "SYNTHETIC_ONLY"
    assert output["real_aws_calls"] == 0
    assert output["scenario_count"] == len(SCENARIO_NAMES)
    assert {row["case"] for row in output["cases"]} == set(SCENARIO_NAMES)
    assert all(row["source"] == "MOCK" for row in output["cases"])
    assert all(row["submitted"] is False for row in output["cases"])
    assert output["commercial_go"] is False
    assert output["decision"] == "NO_GO"


@pytest.mark.parametrize("failure", ("timeout", "browser_crash", "network_put"))
def test_actual_worker_fault_injection_keeps_canary_out_of_logs(
    monkeypatch, capsys, failure
):
    import json
    import confidential.worker as worker
    from test_confidential_job_ledger import (
        FakeQueue, FakeS3, FakeSession, make,
    )
    marker = "FAKE-SEC12-CANARY-NOT-CLIENT-DATA"
    ddb, ledger = make()
    sqs = FakeQueue({"Body": json.dumps({
        "tenant_id": "pilot01", "case_id": "case01",
        "object_id": "object01", "job_id": "abc012",
        "s3_version": "v000001",
    }), "ReceiptHandle": "fictional"})
    s3 = FakeS3()
    session = FakeSession(ddb, sqs, s3)
    monkeypatch.setattr(worker, "_load_decrypted_form",
        lambda *args: {"name": marker, "reference": "SYNTHETIC"})
    async def preview(*args):
        if failure == "timeout":
            raise TimeoutError("synthetic timeout " + marker)
        if failure == "browser_crash":
            raise RuntimeError("synthetic chromium crash " + marker)
    monkeypatch.setattr(worker, "_prepare_fictional_form", preview)
    if failure == "network_put":
        def fail_store(**kwargs):
            raise ConnectionError("synthetic network error " + marker)
        monkeypatch.setattr(s3, "put_object", fail_store)
    import sys
    from types import SimpleNamespace
    monkeypatch.setattr(worker, "_config", lambda: (
        "pilot01", "fixture-bucket", "fixture-queue", "fixture-kms",
    ))
    monkeypatch.setitem(
        sys.modules, "boto3",
        SimpleNamespace(Session=lambda **kwargs: session),
    )
    assert worker.main() == 1
    stdout = capsys.readouterr()
    assert marker not in stdout.out and marker not in stdout.err
    assert "confidential-worker: failed (" in stdout.err
    assert sqs.deleted is False
    assert s3.markers == []
    assert ledger.status("abc012")["status"] == "retryable"
    assert ledger.status("abc012")["submitted"] is False


@pytest.mark.parametrize("tenant", ("office01", "client01", "notary01"))
def test_guest_entrypoint_denies_nonpilot_before_aws(monkeypatch, tenant):
    import confidential.worker as worker

    monkeypatch.setattr(worker.os.path, "exists", lambda path: path == "/dev/nsm")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_REQUIRED", "1")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_TENANT", tenant)
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_BUCKET", "synthetic-bucket")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_QUEUE_URL",
                       "https://sqs.eu-central-1.amazonaws.com/111122223333/synthetic")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_KMS_KEY_ARN",
                       "arn:aws:kms:eu-central-1:111122223333:key/synthetic")
    with pytest.raises(RuntimeError, match="only synthetic pilot"):
        worker._config()


@pytest.mark.parametrize("tenant", ("pilot01", "pilot02"))
def test_guest_entrypoint_keeps_synthetic_pilot_config(monkeypatch, tenant):
    import confidential.worker as worker

    monkeypatch.setattr(worker.os.path, "exists", lambda path: path == "/dev/nsm")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_REQUIRED", "1")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_TENANT", tenant)
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_BUCKET", "synthetic-bucket")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_QUEUE_URL",
                       "https://sqs.eu-central-1.amazonaws.com/111122223333/synthetic")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_KMS_KEY_ARN",
                       "arn:aws:kms:eu-central-1:111122223333:key/synthetic")
    assert worker._config()[0] == tenant


@pytest.mark.parametrize("tenant", ("office01", "client01", "notary01"))
def test_dispatch_entrypoint_denies_nonpilot_without_aws(tenant):
    from confidential.dispatch import (
        DispatcherConfig, UnsafeDispatch, dispatch_once,
    )

    class ForbiddenClient:
        def __getattr__(self, name):
            raise AssertionError("AWS must not be accessed")

    config = DispatcherConfig(
        account="111122223333", tenant=tenant,
        cluster="notarai-confidential-" + tenant,
        capacity_provider="notarai-confidential-" + tenant,
        task_definition_arn=(
            "arn:aws:ecs:eu-central-1:111122223333:task-definition/"
            "notarai-confidential-" + tenant + ":1"
        ),
        queue_url=(
            "https://sqs.eu-central-1.amazonaws.com/111122223333/"
            "notarai-confidential-" + tenant + ".fifo"
        ),
        subnet="subnet-0123456789abcdef0",
        security_group="sg-0123456789abcdef0",
        lease_table="notarai-confidential-dispatch-" + tenant,
    )
    blocked = ForbiddenClient()
    with pytest.raises(UnsafeDispatch, match="only synthetic pilot"):
        dispatch_once(config, sqs=blocked, ecs=blocked, dynamodb=blocked)
