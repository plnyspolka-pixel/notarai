"""Purely synthetic tests: public transparency log of custodian-signed releases."""
import base64
import copy
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.operator_boundary import inspect_operator_boundary
from confidential.release_approval import (
    canonical_bytes, make_release_payload, public_key_fingerprint,
)
from confidential.transparency_log import (
    GENESIS, LogRejected, append_release, checkpoint, empty_log, entry_hash,
    verify_log,
)
from scripts.confidential_transparency_log import run
from test_confidential_operator_boundary import fixture

NOW = datetime(2026, 11, 22, 1, 30, tzinfo=timezone.utc)
COMMIT = "a" * 40


class Custodian:
    def __init__(self):
        self.private = ec.generate_private_key(ec.SECP256R1())
        self.pem = self.private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        self.fingerprint = public_key_fingerprint(self.pem)
        self.keys = {self.fingerprint: self.pem}

    def release(self, number: int, **changes) -> dict:
        config = dict(inspect_operator_boundary(**fixture()))
        payload = make_release_payload(
            config, clock=NOW + timedelta(hours=number),
            release_id=f"{number:032x}", lifetime_hours=24)
        payload.update(changes)
        signature = self.private.sign(canonical_bytes(payload), ec.ECDSA(hashes.SHA256()))
        return {"payload": payload, "signature_b64": base64.b64encode(signature).decode()}

    def log(self, count: int) -> dict:
        log = empty_log()
        for number in range(1, count + 1):
            log = append_release(
                log, release=self.release(number), source_commit=COMMIT,
                custody_public_key_sha256=self.fingerprint,
                recorded_at=NOW + timedelta(hours=number, minutes=5),
                trusted_keys=self.keys)
        return log


@pytest.fixture()
def custodian():
    return Custodian()


def test_empty_log_verifies_with_genesis_head(custodian):
    report = verify_log(empty_log(), trusted_keys=custodian.keys)
    assert report["size"] == 0 and report["head_hash"] == GENESIS


def test_log_verifies_offline_and_never_claims_live_or_hardware_proof(custodian):
    log = custodian.log(3)
    report = verify_log(log, trusted_keys=custodian.keys)
    assert report["size"] == 3
    assert report["head_hash"] == entry_hash(log["entries"][2])
    assert report["signatures_verified"] is True
    assert report["hash_chain_verified"] is True
    assert report["extends_previous_checkpoint"] is None
    assert report["live_kms_policy_verified"] is False
    assert report["hardware_nitro_attestation_verified"] is False
    assert report["zero_operator_access_proven"] is False
    assert [e["index"] for e in report["entries"]] == [0, 1, 2]


def test_append_does_not_modify_the_input_log(custodian):
    log = custodian.log(1)
    before = copy.deepcopy(log)
    custodian_log = append_release(
        log, release=custodian.release(2), source_commit=COMMIT,
        custody_public_key_sha256=custodian.fingerprint,
        recorded_at=NOW + timedelta(hours=3), trusted_keys=custodian.keys)
    assert log == before and len(custodian_log["entries"]) == 2


@pytest.mark.parametrize("field,value", [
    ("image_sha256", "9" * 64),
    ("expected_pcr17", "c" * 96),
    ("key_policy_sha256", "d" * 64),
    ("task_definition_sha256", "e" * 64),
    ("tenant", "other01"),
])
def test_changing_any_signed_release_field_is_detected(custodian, field, value):
    log = custodian.log(2)
    log["entries"][0]["release"]["payload"][field] = value
    with pytest.raises(LogRejected, match="signature invalid"):
        verify_log(log, trusted_keys=custodian.keys)


def test_forged_signature_from_another_key_is_rejected(custodian):
    log = custodian.log(1)
    forger = Custodian()
    forged = forger.release(1)
    log["entries"][0]["release"] = forged
    with pytest.raises(LogRejected, match="signature invalid"):
        verify_log(log, trusted_keys=custodian.keys)


def test_entry_naming_an_unpinned_key_is_rejected(custodian):
    forger = Custodian()
    log = forger.log(1)
    with pytest.raises(LogRejected, match="not pinned"):
        verify_log(log, trusted_keys=custodian.keys)


def test_public_key_must_match_the_out_of_band_fingerprint(custodian):
    with pytest.raises(LogRejected, match="differs from the pinned"):
        verify_log(custodian.log(1), trusted_keys={"f" * 64: custodian.pem})
    with pytest.raises(LogRejected, match="at least one"):
        verify_log(custodian.log(1), trusted_keys={})


def test_rewriting_an_old_entry_breaks_the_chain_even_when_resigned(custodian):
    log = custodian.log(3)
    log["entries"][0]["release"] = custodian.release(1, image_sha256="9" * 64)
    with pytest.raises(LogRejected, match="hash chain broken"):
        verify_log(log, trusted_keys=custodian.keys)


def test_removed_reordered_or_renumbered_entries_are_rejected(custodian):
    removed = custodian.log(3)
    del removed["entries"][1]
    with pytest.raises(LogRejected, match="out of sequence"):
        verify_log(removed, trusted_keys=custodian.keys)

    swapped = custodian.log(3)
    swapped["entries"][1], swapped["entries"][2] = swapped["entries"][2], swapped["entries"][1]
    with pytest.raises(LogRejected, match="out of sequence"):
        verify_log(swapped, trusted_keys=custodian.keys)

    renumbered = custodian.log(3)
    del renumbered["entries"][1]
    renumbered["entries"][1]["index"] = 1
    with pytest.raises(LogRejected, match="hash chain broken"):
        verify_log(renumbered, trusted_keys=custodian.keys)


def test_same_release_cannot_be_recorded_twice(custodian):
    log = custodian.log(1)
    with pytest.raises(LogRejected, match="recorded twice"):
        append_release(
            log, release=custodian.release(1), source_commit=COMMIT,
            custody_public_key_sha256=custodian.fingerprint,
            recorded_at=NOW + timedelta(hours=5), trusted_keys=custodian.keys)


def test_entry_cannot_predate_its_release_or_earlier_entries(custodian):
    with pytest.raises(LogRejected, match="before its release"):
        append_release(
            empty_log(), release=custodian.release(2), source_commit=COMMIT,
            custody_public_key_sha256=custodian.fingerprint,
            recorded_at=NOW, trusted_keys=custodian.keys)
    log = custodian.log(2)
    log["entries"][1]["recorded_at"] = "2026-11-22T02:30:00Z"
    with pytest.raises(LogRejected):
        verify_log(log, trusted_keys=custodian.keys)


@pytest.mark.parametrize("mutate", [
    lambda e: e.update(note="Jan Kowalski, PESEL"),
    lambda e: e.pop("source_commit"),
    lambda e: e.update(source_commit="main"),
    lambda e: e.update(kind="attestation"),
    lambda e: e.update(index=True),
    lambda e: e["release"].update(comment="free text"),
    lambda e: e["release"]["payload"].update(tenant="Kancelaria Nowak"),
    lambda e: e["release"]["payload"].update(operator_account="12345"),
    lambda e: e["release"]["payload"].update(extra="x"),
])
def test_free_text_and_unknown_fields_cannot_enter_the_log(custodian, mutate):
    log = custodian.log(1)
    mutate(log["entries"][0])
    with pytest.raises(LogRejected):
        verify_log(log, trusted_keys=custodian.keys)


def test_checkpoint_detects_truncated_and_rewritten_history(custodian):
    log = custodian.log(2)
    witness = checkpoint(verify_log(log, trusted_keys=custodian.keys))

    longer = append_release(
        log, release=custodian.release(3), source_commit=COMMIT,
        custody_public_key_sha256=custodian.fingerprint,
        recorded_at=NOW + timedelta(hours=4), trusted_keys=custodian.keys)
    report = verify_log(longer, trusted_keys=custodian.keys, previous_checkpoint=witness)
    assert report["extends_previous_checkpoint"] is True

    shorter = {"schema": log["schema"], "entries": log["entries"][:1]}
    with pytest.raises(LogRejected, match="history removed"):
        verify_log(shorter, trusted_keys=custodian.keys, previous_checkpoint=witness)

    # A different, internally valid history shown to another client.
    fork = custodian.log(1)
    fork = append_release(
        fork, release=custodian.release(2, image_sha256="9" * 64), source_commit=COMMIT,
        custody_public_key_sha256=custodian.fingerprint,
        recorded_at=NOW + timedelta(hours=3), trusted_keys=custodian.keys)
    verify_log(fork, trusted_keys=custodian.keys)
    with pytest.raises(LogRejected, match="history rewritten"):
        verify_log(fork, trusted_keys=custodian.keys, previous_checkpoint=witness)


@pytest.mark.parametrize("bad", [
    {"schema": "x", "size": 0, "head_hash": GENESIS},
    {"schema": "notarai.confidential.transparency-checkpoint.v1", "size": 1, "head_hash": GENESIS},
    {"schema": "notarai.confidential.transparency-checkpoint.v1", "size": -1, "head_hash": "a" * 64},
    {"schema": "notarai.confidential.transparency-checkpoint.v1", "size": 0},
])
def test_malformed_checkpoint_is_rejected(custodian, bad):
    with pytest.raises(LogRejected):
        verify_log(custodian.log(1), trusted_keys=custodian.keys, previous_checkpoint=bad)


def test_cli_appends_verifies_and_refuses_to_overwrite(custodian, tmp_path):
    key = tmp_path / "custody-public.pem"
    key.write_bytes(custodian.pem)
    release = tmp_path / "release.json"
    release.write_text(json.dumps(custodian.release(1)), encoding="utf-8")
    base = ["--trusted-custodian-public-key", str(key),
            "--trusted-custodian-public-key-sha256", custodian.fingerprint]

    # recorded_at comes from the real clock, which is after the synthetic issue time.
    out = tmp_path / "log-1.json"
    report = run(["append", "--log", str(tmp_path / "missing.json"),
                  "--release-file", str(release), "--source-commit", COMMIT,
                  "--output", str(out), *base])
    assert report["size"] == 1

    saved = tmp_path / "witness.json"
    verified = run(["verify", "--log", str(out), "--write-checkpoint", str(saved), *base])
    assert verified["head_hash"] == report["head_hash"]
    again = run(["verify", "--log", str(out), "--previous-checkpoint", str(saved), *base])
    assert again["extends_previous_checkpoint"] is True

    with pytest.raises(FileExistsError):
        run(["append", "--log", str(tmp_path / "missing.json"),
             "--release-file", str(release), "--source-commit", COMMIT,
             "--output", str(out), *base])
    with pytest.raises(LogRejected, match="not found"):
        run(["verify", "--log", str(tmp_path / "missing.json"), *base])
