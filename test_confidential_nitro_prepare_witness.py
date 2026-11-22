"""SEC-07 deterministic witness package: signed only outside NotarAI."""
import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

from confidential.nitro_denial_matrix import CASES, DenialEvidenceRejected
from confidential.nitro_witness import canonical_witness
from scripts import prepare_nitro_witness as cli
from test_confidential_nitro_denial_matrix import sample


def inputs():
    matrix, _, _ = sample()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
    return matrix, matrix["ended_at"], fmt(now + timedelta(minutes=20))


def test_reproducible_identical_witness_bytes():
    matrix, observed, expires = inputs()
    a, left = cli.generate_payload(matrix, observed, expires)
    b, right = cli.generate_payload(matrix, observed, expires)
    assert a == b
    assert left == right == canonical_witness(a)
    assert left.startswith(b"NotarAI:SEC-07:independent-witness:v1\x00")
    assert set(a["trial_receipt_sha256"]) == set(CASES)
    assert a["signed"] is False
    assert a["submitted"] is False


@pytest.mark.parametrize("change", [
    lambda m: m["trials"]["wrong_key"].update(receipt_sha256="0" * 64),
    lambda m: m.update(tenant="pilot02"),
    lambda m: m.update(job_id="f" * 32),
])
def test_tampered_matrix_changes_the_bytes(change):
    matrix, observed, expires = inputs()
    _, signed = cli.generate_payload(matrix, observed, expires)
    change(matrix)
    changed, signing_bytes = cli.generate_payload(matrix, observed, expires)
    assert signing_bytes != signed


@pytest.mark.parametrize("expires", [
    "2025-01-01T00:00:00Z",
    "2099-01-01T00:00:00Z",
    "not-a-date",
])
def test_invalid_expiry_fails_closed(expires):
    matrix, observed, _ = inputs()
    with pytest.raises(DenialEvidenceRejected):
        cli.generate_payload(matrix, observed, expires)


def test_cli_creates_two_distinct_non_overwriting_files(
    tmp_path, monkeypatch, capsys,
):
    matrix, observed, expires = inputs()
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    witness_path = tmp_path / "witness.json"
    bytes_path = tmp_path / "witness.signing.bin"
    monkeypatch.setattr(sys, "argv", [
        "prepare_nitro_witness.py",
        "--matrix", str(matrix_path),
        "--observed-at", observed, "--expires-at", expires,
        "--payload-out", str(witness_path),
        "--signing-bytes-out", str(bytes_path),
    ])
    assert cli.main() == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "PREPARED_NOT_SIGNED"
    assert status["witness_hardware_verified"] is False
    assert bytes_path.read_bytes() == canonical_witness(
        json.loads(witness_path.read_text(encoding="utf-8"))
    )
    # Existing evidence must not be silently overwritten.
    assert cli.main() == 2
    status = json.loads(capsys.readouterr().out)
    assert status["hardware_attestation_verified"] is False
    assert bytes_path.read_bytes() == canonical_witness(
        json.loads(witness_path.read_text(encoding="utf-8"))
    )


def test_cli_rejects_identical_outputs_and_does_not_create_file(
    tmp_path, monkeypatch, capsys,
):
    matrix, observed, expires = inputs()
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    output = tmp_path / "same"
    monkeypatch.setattr(sys, "argv", [
        "prepare_nitro_witness.py", "--matrix", str(matrix_path),
        "--observed-at", observed, "--expires-at", expires,
        "--payload-out", str(output), "--signing-bytes-out", str(output),
    ])
    assert cli.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"
    assert not output.exists()



def test_refuse_oversized_matrix_before_processing(tmp_path, monkeypatch, capsys):
    matrix_file = tmp_path / "too-large.json"
    matrix_file.write_bytes(b"x" * (32 * 1024 + 1024))
    payload = tmp_path / "witness.json"
    signing = tmp_path / "signing.bin"
    monkeypatch.setattr(sys, "argv", [
        "prepare_nitro_witness.py",
        "--matrix", str(matrix_file),
        "--observed-at", "2026-11-22T09:00:00Z",
        "--expires-at", "2026-11-22T10:00:00Z",
        "--payload-out", str(payload),
        "--signing-bytes-out", str(signing),
    ])
    assert cli.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"
    assert not payload.exists()
    assert not signing.exists()


def test_audit_rejects_oversized_witness_signature(tmp_path):
    from confidential.nitro_denial_matrix import DenialEvidenceRejected
    from scripts import audit_nitro_denials
    signature = tmp_path / "huge.b64"
    signature.write_bytes(b"A" * 4100)
    with pytest.raises(DenialEvidenceRejected):
        audit_nitro_denials._bounded_bytes(str(signature), 4096)
