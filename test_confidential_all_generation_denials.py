"""SEC-06: verify synthetic negative decrypt against every old/current KMS key."""
import pytest

from botocore.exceptions import ClientError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from confidential.operator_boundary import BoundaryDenied
from scripts.probe_confidential_all_generation_denials import (
    probe_all_generations,
)
from test_confidential_custody_history import make_history
from test_confidential_independent_custody_ops import CUSTODY, WORKLOAD, state


OLD = state("pilot01", 1)["decrypt_key_arn"]
NEW = state("pilot01", 2)["decrypt_key_arn"]


class MultiKeyProbe:
    def __init__(self, *, allow_key=None, error_key=None, account=WORKLOAD):
        self.allow_key = allow_key
        self.error_key = error_key
        self.account = account
        self.calls = []
        private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        self.public_der = private.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo)

    def __call__(self, *, profile_name, region_name):
        assert profile_name == "isolated-negative-test"
        assert region_name == "eu-central-1"
        mock = self

        class Session:
            def client(self, name):
                assert name in ("sts", "kms")
                return self

            def get_caller_identity(self):
                mock.calls.append(("sts", None))
                return {"Account": mock.account}

            def get_public_key(self, *, KeyId):
                assert KeyId in (OLD, NEW)
                mock.calls.append(("get_public_key", KeyId))
                return {
                    "KeyId": KeyId,
                    "PublicKey": mock.public_der,
                    "KeySpec": "RSA_3072",
                    "KeyUsage": "ENCRYPT_DECRYPT",
                    "EncryptionAlgorithms": ["RSAES_OAEP_SHA_256"],
                }

            def decrypt(self, **kwargs):
                arn = kwargs["KeyId"]
                assert arn in (OLD, NEW)
                assert "Recipient" not in kwargs
                assert kwargs["EncryptionAlgorithm"] == "RSAES_OAEP_SHA_256"
                mock.calls.append(("decrypt", arn))
                if arn == mock.allow_key:
                    return {"Plaintext": b"SYNTHETIC-ONLY-DISCARD"}
                code = ("InvalidCiphertextException" if arn == mock.error_key
                        else "AccessDeniedException")
                raise ClientError(
                    {"Error": {"Code": code, "Message": "synthetic test"}},
                    "Decrypt")

        return Session()


def check(fixture, mock, *, execute=False, ack=False):
    return probe_all_generations(
        tenant=fixture["tenant"],
        event_items=fixture["event_items"],
        state_item=fixture["state_item"],
        trust_roots=fixture["trust_roots"],
        pinned_final_state_sha256=fixture["pinned_final_state_sha256"],
        operator_profile="isolated-negative-test",
        execute=execute,
        synthetic_only_ack=ack,
        clock=fixture["clock"],
        session_factory=mock,
    )


def test_k4_multi_generation_probe_default_zero_aws():
    fixture = make_history()
    mock = MultiKeyProbe()
    result = check(fixture, mock)
    assert result["status"] == "BLOCKED_DRY_RUN"
    assert result["expected_key_count"] == 2
    assert result["verified_denial_count"] == 0
    assert result["aws_calls"] == 0
    assert result["customer_data_used"] is False
    assert mock.calls == []


def test_k4_all_old_and_current_keys_denied_for_one_operator_identity():
    fixture = make_history()
    mock = MultiKeyProbe()
    result = check(fixture, mock, execute=True, ack=True)
    assert result["status"] == "BLOCKED_ONE_IDENTITY_NEGATIVE_TESTS_ONLY"
    assert result["verified_denial_count"] == 2
    assert result["expected_key_count"] == 2
    assert result["single_operator_identity_denied_all_generations"]
    assert result["aws_calls"] == 6
    assert not result["other_operator_identities_tested"]
    assert not result["all_historical_grants_checked"]
    assert not result["effective_revocation_verified"]
    assert not result["independent_custody_verified"]
    assert not result["customer_data_used"]
    assert not result["plaintext_logged_or_returned"]
    assert mock.calls == [
        ("sts", None), ("get_public_key", OLD), ("decrypt", OLD),
        ("sts", None), ("get_public_key", NEW), ("decrypt", NEW),
    ]


def test_k4_double_opt_in_required_before_first_aws_call():
    fixture = make_history()
    mock = MultiKeyProbe()
    with pytest.raises(BoundaryDenied, match="synthetic-only"):
        check(fixture, mock, execute=True)
    assert mock.calls == []


@pytest.mark.parametrize("allowed_key", [OLD, NEW])
def test_k4_any_old_or_current_key_allowing_decrypt_is_fail_open(allowed_key):
    fixture = make_history()
    mock = MultiKeyProbe(allow_key=allowed_key)
    with pytest.raises(BoundaryDenied, match="FAIL_OPEN") as error:
        check(fixture, mock, execute=True, ack=True)
    assert "SYNTHETIC-ONLY-DISCARD" not in str(error.value)
    assert ("decrypt", allowed_key) in mock.calls


@pytest.mark.parametrize("inconclusive_key", [OLD, NEW])
def test_k4_any_unexpected_kms_error_is_not_a_denial_proof(inconclusive_key):
    fixture = make_history()
    mock = MultiKeyProbe(error_key=inconclusive_key)
    with pytest.raises(BoundaryDenied, match="inconclusive"):
        check(fixture, mock, execute=True, ack=True)
    assert ("decrypt", inconclusive_key) in mock.calls


@pytest.mark.parametrize("mutation", [
    lambda f: f["event_items"].pop(0),
    lambda f: f["event_items"].pop(1),
    lambda f: f.update(pinned_final_state_sha256="f" * 64),
    lambda f: f["trust_roots"].pop(2),
])
def test_k5_corrupt_custody_ledger_denies_all_live_calls(mutation):
    fixture = make_history()
    mutation(fixture)
    mock = MultiKeyProbe()
    with pytest.raises(BoundaryDenied):
        check(fixture, mock, execute=True, ack=True)
    assert mock.calls == []


def test_k1_multi_key_negative_probe_checks_operator_aws_account():
    fixture = make_history()
    mock = MultiKeyProbe(account=CUSTODY)
    with pytest.raises(BoundaryDenied):
        check(fixture, mock, execute=True, ack=True)
    assert mock.calls == [("sts", None)]


def test_k6_multi_key_negative_probe_cli_never_returns_release_success(
    monkeypatch, tmp_path,
):
    import json
    import scripts.probe_confidential_all_generation_denials as cli

    fixture = make_history()
    history = tmp_path / "synthetic-history.json"
    history.write_text(json.dumps({
        "state_item": fixture["state_item"],
        "event_items": fixture["event_items"],
    }))
    manifest = {}
    for gen, (pem, pin) in fixture["trust_roots"].items():
        path = tmp_path / f"root-{gen}.pem"
        path.write_bytes(pem)
        manifest[str(gen)] = {
            "pem_file": str(path), "sha256": pin}
    manifest_file = tmp_path / "independent-roots.json"
    manifest_file.write_text(json.dumps(manifest))
    calls = []
    def fake_probe(**kwargs):
        calls.append(kwargs)
        return {
            "status": (
                "BLOCKED_ONE_IDENTITY_NEGATIVE_TESTS_ONLY"
                if kwargs["execute"] else "BLOCKED_DRY_RUN"),
            "verified_denial_count": 2 if kwargs["execute"] else 0,
            "independent_custody_verified": False,
            "customer_data_used": False,
        }
    monkeypatch.setattr(cli, "probe_all_generations", fake_probe)
    common = [
        "--tenant", "pilot01",
        "--history-file", str(history),
        "--trust-roots-file", str(manifest_file),
        "--pinned-final-sha256", fixture["pinned_final_state_sha256"],
        "--operator-profile", "isolated-negative-test",
    ]
    dry = tmp_path / "dry-report.json"
    assert cli.main(common + ["--output", str(dry)]) == 0
    live = tmp_path / "manual-report.json"
    assert cli.main(common + [
        "--execute-negative-probes", "--acknowledge-synthetic-only",
        "--output", str(live),
    ]) == 3
    assert json.loads(live.read_text())["independent_custody_verified"] is False
    assert [v["execute"] for v in calls] == [False, True]
