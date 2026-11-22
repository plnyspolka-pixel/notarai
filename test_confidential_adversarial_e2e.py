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
