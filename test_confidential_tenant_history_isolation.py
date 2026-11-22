"""SEC-06: lifetime two-tenant isolation from independently signed histories."""
import copy

import pytest

from confidential.operator_boundary import BoundaryDenied
from scripts.verify_confidential_tenant_history_isolation import (
    verify_lifetime_isolation,
)
from test_confidential_custody_history import make_history
from test_confidential_independent_custody_ops import signer, state


def comparison(p1=None, p2=None):
    a = p1 if p1 is not None else make_history()
    b = p2 if p2 is not None else make_history("pilot02", 3)
    return {
        "pilot01": {k: a[k] for k in (
            "event_items", "state_item", "trust_roots",
            "pinned_final_state_sha256")},
        "pilot02": {k: b[k] for k in (
            "event_items", "state_item", "trust_roots",
            "pinned_final_state_sha256")},
        "clock": a["clock"],
    }


def test_k3_historical_isolation_all_generations_without_aws():
    evidence = verify_lifetime_isolation(**comparison())
    assert evidence["tenant_count"] == 2
    assert evidence["offline_signed_histories_checked"]
    assert evidence["generation_counts"] == {"pilot01": 2, "pilot02": 2}
    assert evidence["history_event_counts"] == {"pilot01": 3, "pilot02": 3}
    assert not evidence["lifetime_cross_tenant_key_overlap"]
    assert not evidence["lifetime_cross_tenant_signing_root_overlap"]
    assert not evidence["lifetime_cross_tenant_pcr_release_overlap"]
    assert evidence["aws_calls"] == 0
    assert evidence["status"] == "BLOCKED_PENDING_INDEPENDENT_AWS_EVIDENCE"
    assert not evidence["all_live_kms_grants_audited"]
    assert not evidence["live_cross_tenant_decrypt_denial_verified"]
    assert not evidence["can_authorize_decrypt"]


@pytest.mark.parametrize("old_field,colliding_field", [
    ("decrypt_key_arn", "decrypt_key_arn"),
    ("signing_key_arn", "signing_key_arn"),
    ("signing_key_arn", "decrypt_key_arn"),
    ("decrypt_key_arn", "signing_key_arn"),
    ("pcr17", "pcr17"),
    ("release_sha256", "release_sha256"),
    ("key_policy_sha256", "key_policy_sha256"),
])
def test_k3_reusing_pilot01_retired_binding_by_pilot02_denied(
    old_field, colliding_field,
):
    first = make_history("pilot01", 1)
    # Old generation was retired; current snapshots are distinct.
    original = state("pilot01", 1)
    second = make_history(
        "pilot02", 3, overrides={
            colliding_field: original[old_field],
        })
    with pytest.raises(BoundaryDenied):
        verify_lifetime_isolation(**comparison(first, second))


def test_k3_independent_kms_arns_cannot_share_signing_public_root():
    pair = signer()
    a = make_history("pilot01", 1, first_signer=pair)
    b = make_history("pilot02", 3, first_signer=pair)
    with pytest.raises(BoundaryDenied, match="trust root"):
        verify_lifetime_isolation(**comparison(a, b))


@pytest.mark.parametrize("mutation", [
    lambda c: c["pilot01"]["event_items"].pop(0),
    lambda c: c["pilot02"]["event_items"].pop(1),
    lambda c: c["pilot01"]["trust_roots"].pop(2),
    lambda c: c["pilot02"].update(pinned_final_state_sha256="a" * 64),
    lambda c: c["pilot01"]["state_item"]["state_sha256"].update(S="f" * 64),
])
def test_k3_tampered_cross_tenant_evidence_rejected_before_comparison(mutation):
    payloads = comparison()
    mutation(payloads)
    with pytest.raises(BoundaryDenied):
        verify_lifetime_isolation(**payloads)


def test_k3_lifetime_isolation_requires_both_external_anchors():
    payload = comparison()
    del payload["pilot01"]["pinned_final_state_sha256"]
    with pytest.raises(BoundaryDenied):
        verify_lifetime_isolation(**payload)


def test_k6_lifetime_isolation_cli_never_returns_release_success(monkeypatch, tmp_path):
    import json
    import scripts.verify_confidential_tenant_history_isolation as cli
    a = make_history()
    b = make_history("pilot02", 3)
    args = []
    for name, fixture in (("pilot01", a), ("pilot02", b)):
        export = tmp_path / f"{name}-export.json"
        export.write_text(json.dumps({
            "event_items": fixture["event_items"],
            "state_item": fixture["state_item"],
        }))
        roots = tmp_path / f"{name}-roots.json"
        manifest = {}
        for generation, (pem, pin) in fixture["trust_roots"].items():
            root = tmp_path / f"{name}-gen{generation}.pem"
            root.write_bytes(pem)
            manifest[str(generation)] = {
                "pem_file": str(root), "sha256": pin}
        roots.write_text(json.dumps(manifest))
        args.extend([
            f"--{name}-history", str(export),
            f"--{name}-trust-roots", str(roots),
            f"--{name}-final-sha256",
            fixture["pinned_final_state_sha256"],
        ])
    output = tmp_path / "isolation-report.json"
    args.extend(["--output", str(output)])
    assert cli.main(args) == 3
    report = json.loads(output.read_text())
    assert report["offline_signed_histories_checked"]
    assert not report["independent_custody_verified"]
    assert not report["can_authorize_decrypt"]
