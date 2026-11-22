"""SEC-06 safety tests: no customer data in negative KMS decrypt probes."""
import pytest
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from confidential.operator_boundary import BoundaryDenied
from scripts.probe_confidential_operator_kms_denial import probe_operator_denial
from test_confidential_independent_custody_ops import CUSTODY, WORKLOAD, state


@pytest.fixture(scope="module")
def public_der():
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    return private.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo)


class FakeProbe:
    def __init__(self, der, account=WORKLOAD, outcome="deny",
                 key_spec="RSA_3072"):
        self.der = der
        self.account = account
        self.outcome = outcome
        self.key_spec = key_spec
        self.calls = []

    def __call__(self, profile_name, region_name):
        assert profile_name == "restricted-workload"
        assert region_name == "eu-central-1"
        outer = self

        class Session:
            def client(self, name):
                assert name in ("sts", "kms")
                return self

            def get_caller_identity(self):
                outer.calls.append("sts:GetCallerIdentity")
                return {"Account": outer.account}

            def get_public_key(self, **kwargs):
                outer.calls.append("kms:GetPublicKey")
                assert kwargs["KeyId"] == state()["decrypt_key_arn"]
                return {
                    "KeyId": kwargs["KeyId"],
                    "PublicKey": outer.der,
                    "KeySpec": outer.key_spec,
                    "KeyUsage": "ENCRYPT_DECRYPT",
                    "EncryptionAlgorithms": ["RSAES_OAEP_SHA_256"],
                }

            def decrypt(self, **kwargs):
                outer.calls.append("kms:Decrypt")
                assert kwargs["KeyId"] == state()["decrypt_key_arn"]
                assert kwargs["EncryptionAlgorithm"] == "RSAES_OAEP_SHA_256"
                assert "Recipient" not in kwargs
                assert "CiphertextBlob" in kwargs
                assert len(kwargs["CiphertextBlob"]) == 384
                if outer.outcome == "deny":
                    raise ClientError(
                        {"Error": {"Code": "AccessDeniedException",
                                   "Message": "synthetic mocked denial"}},
                        "Decrypt")
                if outer.outcome == "inconclusive":
                    raise ClientError(
                        {"Error": {"Code": "InvalidCiphertextException",
                                   "Message": "synthetic mock invalid"}},
                        "Decrypt")
                return {"Plaintext": b"NOTARAI_SYNTHETIC_MOCK_PLAINTEXT"}
        return Session()


def test_k4_negative_kms_probe_default_never_accesses_aws():
    output = probe_operator_denial(
        state=state(), operator_profile="restricted-workload",
        session_factory=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("AWS called in default dry run")))
    assert output["status"] == "BLOCKED_DRY_RUN"
    assert output["aws_calls"] == 0
    assert not output["single_operator_identity_denied"]
    assert not output["independent_custody_verified"]


def test_k4_negative_kms_probe_requires_explicit_double_opt_in(public_der):
    f = FakeProbe(public_der)
    with pytest.raises(BoundaryDenied, match="synthetic-only"):
        probe_operator_denial(
            state=state(), operator_profile="restricted-workload",
            execute=True, session_factory=f)
    assert f.calls == []


def test_k4_negative_kms_probe_fails_closed_on_wrong_operator_account(public_der):
    f = FakeProbe(public_der, account=CUSTODY)
    with pytest.raises(BoundaryDenied, match="workload account"):
        probe_operator_denial(
            state=state(), operator_profile="restricted-workload",
            execute=True, synthetic_only_ack=True, session_factory=f)
    assert f.calls == ["sts:GetCallerIdentity"]


def test_k4_expected_kms_access_denied_is_only_one_partial_evidence(public_der):
    f = FakeProbe(public_der, outcome="deny")
    result = probe_operator_denial(
        state=state(), operator_profile="restricted-workload",
        execute=True, synthetic_only_ack=True, session_factory=f)
    assert result["status"] == "OPERATOR_DECRYPT_DENIED_FOR_ONE_IDENTITY"
    assert result["single_operator_identity_denied"]
    assert result["aws_calls"] == 3
    assert not result["customer_data_used"]
    assert not result["synthetic_ciphertext_persisted"]
    assert not result["plaintext_logged_or_returned"]
    assert not result["nitro_attestation_presented"]
    assert not result["independent_custody_verified"]
    assert not result["effective_revocation_verified"]
    assert f.calls == [
        "sts:GetCallerIdentity", "kms:GetPublicKey", "kms:Decrypt"]


def test_k4_unexpected_kms_error_does_not_count_as_deny(public_der):
    f = FakeProbe(public_der, outcome="inconclusive")
    with pytest.raises(BoundaryDenied, match="inconclusive"):
        probe_operator_denial(
            state=state(), operator_profile="restricted-workload",
            execute=True, synthetic_only_ack=True, session_factory=f)
    assert f.calls[-1] == "kms:Decrypt"


def test_k4_accidental_operator_decrypt_success_is_fail_open(public_der):
    f = FakeProbe(public_der, outcome="allow")
    with pytest.raises(BoundaryDenied, match="FAIL_OPEN") as failure:
        probe_operator_denial(
            state=state(), operator_profile="restricted-workload",
            execute=True, synthetic_only_ack=True, session_factory=f)
    assert "NOTARAI_SYNTHETIC_MOCK_PLAINTEXT" not in str(failure.value)
    assert f.calls[-1] == "kms:Decrypt"


def test_k4_unapproved_rsa_key_type_blocks_before_decrypt(public_der):
    f = FakeProbe(public_der, key_spec="RSA_2048")
    with pytest.raises(BoundaryDenied):
        probe_operator_denial(
            state=state(), operator_profile="restricted-workload",
            execute=True, synthetic_only_ack=True, session_factory=f)
    assert "kms:Decrypt" not in f.calls


def test_k4_denial_probe_never_turns_into_release_green_gate(monkeypatch, tmp_path):
    import json
    import scripts.probe_confidential_operator_kms_denial as cli
    file = tmp_path / "synthetic-state.json"
    file.write_text(json.dumps(state()))
    monkeypatch.setattr(cli, "probe_operator_denial", lambda **kwargs: {
        "status": "OPERATOR_DECRYPT_DENIED_FOR_ONE_IDENTITY",
        "single_operator_identity_denied": True, "aws_calls": 3,
        "independent_custody_verified": False,
    })
    assert cli.main([
        "--state-file", str(file),
        "--operator-profile", "restricted-workload",
        "--execute-negative-probe", "--acknowledge-synthetic-only",
    ]) == 3
