"""SEC-07 positive+negative evidence must refer to one actual trial."""
import copy
import json
import sys
from uuid import UUID

import pytest

from confidential.nitro_scope_binding import (
    ScopeBindingRejected, bind_positive_negative_scope,
)
from scripts import check_nitro_scope as cli
from test_confidential_nitro_denial_matrix import sample
from test_confidential_nitro_hardware_plan import fixtures


def matched():
    positive, _, _, _, _ = fixtures()
    negative, _, _ = sample()
    for field in (
        "region", "tenant", "workload_account", "custody_account",
        "job_id", "image_sha256", "expected_pcr17",
        "started_at", "ended_at",
    ):
        negative[field] = positive[field]
    negative["approved_kms_key_arn"] = positive["kms_key_arn"]
    # V1's positive EventId cannot be relabeled as a V2 denied EventId.
    negative["trials"]["ordinary_host"]["event_id"] = str(UUID(int=499))
    return positive, negative


def test_matching_evidence_is_structurally_bound_but_hardware_remains_blocked():
    positive, negative = matched()
    report = bind_positive_negative_scope(positive=positive, negative=negative)
    assert report["scope_consistent"] is True
    assert report["status"] == "BLOCKED"
    assert len(report["scope_sha256"]) == 64
    assert report["hardware_attestation_verified"] is False
    assert report["negative_cases_independently_verified"] is False
    assert report["zero_operator_access_proven"] is False
    assert report["production_enabled"] is False


@pytest.mark.parametrize("field", [
    "region", "tenant", "workload_account", "custody_account",
    "job_id", "image_sha256", "expected_pcr17",
    "started_at", "ended_at",
])
def test_mismatch_in_each_immutable_field_is_rejected(field):
    positive, negative = matched()
    other = {
        "region": "us-east-1",
        "tenant": "pilot02",
        "workload_account": "999999999999",
        "custody_account": "999988887777",
        "job_id": "e" * 32,
        "image_sha256": "f" * 64,
        "expected_pcr17": "c" * 96,
        "started_at": "2020-01-01T00:00:00Z",
        "ended_at": "2020-01-01T00:00:00Z",
    }[field]
    negative[field] = other
    with pytest.raises(ScopeBindingRejected):
        bind_positive_negative_scope(positive=positive, negative=negative)


def test_another_custody_key_refuses_scope_join():
    positive, negative = matched()
    negative["approved_kms_key_arn"] = (
        "arn:aws:kms:eu-central-1:444455556666:key/"
        "99999999-2222-3333-4444-555555555555"
    )
    with pytest.raises(ScopeBindingRejected):
        bind_positive_negative_scope(positive=positive, negative=negative)


def test_cannot_reuse_one_positive_kms_event_as_negative():
    positive, negative = matched()
    negative["trials"]["wrong_key"]["event_id"] = positive["positive_event_id"]
    with pytest.raises(ScopeBindingRejected):
        bind_positive_negative_scope(positive=positive, negative=negative)


def test_malformed_legacy_six_denial_ids_cannot_prove_v2():
    positive, negative = matched()
    positive["denied_event_ids"]["altered_image"] = None
    with pytest.raises(ScopeBindingRejected):
        bind_positive_negative_scope(positive=positive, negative=negative)


def test_cli_prints_only_blocked_even_for_matching_inputs(
    tmp_path, monkeypatch, capsys,
):
    positive, negative = matched()
    p = tmp_path / "positive.json"
    n = tmp_path / "negative.json"
    p.write_text(json.dumps(positive), encoding="utf-8")
    n.write_text(json.dumps(negative), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "check_nitro_scope.py", "--positive-manifest", str(p),
        "--negative-matrix", str(n),
    ])
    assert cli.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["scope_consistent"] is True
    assert report["status"] == "BLOCKED"
    assert report["hardware_attestation_verified"] is False
    assert report["production_enabled"] is False
    # Deliberately reject and redact mismatched evidence after same command.
    negative["job_id"] = "f" * 32
    n.write_text(json.dumps(negative), encoding="utf-8")
    assert cli.main() == 2
    failed = json.loads(capsys.readouterr().out)
    assert failed["scope_consistent"] is False
    assert failed["hardware_attestation_verified"] is False
