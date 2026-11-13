"""Offline cryptographic integrity tests: no AWS, RPC or document contents."""
import copy

import pytest

import proof_engine as pe


def test_canonicalization_and_salted_commitment():
    payload = {"a": 1, "x": "wartość"}
    salt1, salt2 = pe.new_salt(), pe.new_salt()
    assert len(salt1) == 64 and salt1 != salt2
    assert pe.commitment(payload, salt1) == pe.commitment({"x": "wartość", "a": 1}, salt1)
    assert pe.commitment(payload, salt1) != pe.commitment(payload, salt2)


def test_merkle_five_entries_and_tamper_detection():
    payloads = [{"doc": str(i), "version": i} for i in range(5)]
    salts = [pe.new_salt() for _ in payloads]
    commits = [pe.commitment(payload, salt) for payload, salt in zip(payloads, salts)]
    batch = pe.merkle_batch(commits)
    for i, witness in enumerate(batch["witnesses"]):
        receipt = {**witness, "salt": salts[i], "payload": payloads[i]}
        assert pe.verify_receipt(receipt)
        changed = copy.deepcopy(receipt)
        changed["payload"]["version"] = 999
        assert not pe.verify_receipt(changed)
    assert pe.anchor_calldata(batch["root"]).startswith("0x46595031")


def test_reject_invalid_witness():
    with pytest.raises(ValueError):
        pe.merkle_batch([])
    with pytest.raises(ValueError):
        pe.merkle_batch(["a" * 64, "a" * 64])
    assert not pe.verify_receipt({"root": "z" * 64})
    assert len(pe.anchor_calldata("a" * 64)) == 2 + 8 + 64


def test_cross_language_fixture():
    # Shared Finance You / NotarAI commitment construction.
    payload = {"event": "issued", "version": 1}
    salt = "00" * 32
    expected = pe.commitment(payload, salt)
    assert pe.commitment({"version": 1, "event": "issued"}, salt) == expected


def test_shared_finance_you_unicode_vector():
    payload = {"event": "exclusive_grant", "investor_ref": "I-TEST-001",
               "project_ref": "FY-TEST-001", "version": 1, "active": True,
               "notes": "zażółć gęślą jaźń"}
    digest = pe.commitment(payload, "00" * 32)
    assert digest == "6e4c84cb4f0df196c2848047068b1ed4677d44b843617e3a0bc0fbe7110873b5"
    assert pe.merkle_batch([digest])["root"] == (
        "b2a7abc7603e99ec0ddeb425140f62c7fbef92f6f88a05ceaf528b3700808bb7"
    )

def test_nonportable_floats_large_ints_unicode_keys_and_surrogates_are_rejected():
    for payload in (
        {"amount": 1.5}, {"value": 2**53},
        {"🪙": "test"}, {"event": chr(0xD800)},
    ):
        with pytest.raises(ValueError):
            pe.commitment(payload, "00" * 32)
