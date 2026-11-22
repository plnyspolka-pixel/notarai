"""SEC-11 fixture-only tests for operator overwrite/delete denial probe."""
import pytest

from confidential.custody_denial_probe import (
    ProbeDenied, probe_operator_denials,
)

OPERATOR = "111122223333"
CUSTODY = "444455556666"
BUCKET = "notarai-sec11-custody-synthetic"
KEY = "sec11-fixture/offline-test-001"
VERSION = "vFICTIONAL001"


class FakeAccessDenied(Exception):
    response = {"Error": {"Code": "AccessDenied"}}


class FakeNotFound(Exception):
    response = {"Error": {"Code": "NoSuchVersion"}}


class FakeS3:
    def __init__(self, overwrite_exc=FakeAccessDenied,
                 delete_exc=FakeAccessDenied):
        self.calls = []
        self.overwrite_exc = overwrite_exc
        self.delete_exc = delete_exc

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))
        if self.overwrite_exc is not None:
            raise self.overwrite_exc()
        return {"VersionId": "synthetic-stub-new"}

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))
        if self.delete_exc is not None:
            raise self.delete_exc()
        return {"DeleteMarker": True}


class FakeSts:
    def __init__(self, account):
        self.account = account

    def get_caller_identity(self):
        return {"Account": self.account}


class FakeSession:
    def __init__(self, operator=OPERATOR, overwrite_exc=FakeAccessDenied,
                 delete_exc=FakeAccessDenied):
        self.s3 = FakeS3(overwrite_exc, delete_exc)
        self.sts = FakeSts(operator)

    def client(self, service, **kwargs):
        assert service in {"s3", "sts"}
        if service == "s3":
            assert kwargs == {"region_name": "eu-central-1"}
        return self.s3 if service == "s3" else self.sts


def run_probe(s, **overrides):
    args = {
        "session": s, "operator_account": OPERATOR,
        "custody_account": CUSTODY, "bucket": BUCKET,
        "fixture_key": KEY, "fixture_version": VERSION, "authorized": True,
    }
    args.update(overrides)
    return probe_operator_denials(**args)


def test_two_access_denied_are_reported_without_zoa_claim():
    s = FakeSession()
    result = run_probe(s)
    assert result == {
        "results": {
            "operator_overwrite_deny": "PASS",
            "operator_delete_deny": "PASS",
        },
        "both_access_denied_observed": True,
        "independent_bucket_owner_verified": False,
        "zero_operator_access_proven": False,
    }
    assert [name for name, _ in s.s3.calls] == ["put_object", "delete_object"]
    assert s.s3.calls[0][1]["Body"] == b"NOTARAI_SEC11_SYNTHETIC_ONLY"
    assert s.s3.calls[1][1]["VersionId"] == VERSION
    assert all(kwargs["ExpectedBucketOwner"] == CUSTODY
               for _, kwargs in s.s3.calls)


@pytest.mark.parametrize("overwrite_exc,delete_exc,expected", [
    (None, FakeAccessDenied, ("FAIL", "PASS")),
    (FakeAccessDenied, None, ("PASS", "FAIL")),
    (FakeNotFound, FakeAccessDenied, ("BLOCKED", "PASS")),
    (FakeAccessDenied, FakeNotFound, ("PASS", "BLOCKED")),
])
def test_write_success_and_unrelated_errors_never_count_as_denied(
    overwrite_exc, delete_exc, expected
):
    s = FakeSession(overwrite_exc=overwrite_exc, delete_exc=delete_exc)
    result = run_probe(s)
    assert tuple(result["results"].values()) == expected
    assert result["both_access_denied_observed"] is False
    assert result["independent_bucket_owner_verified"] is False
    assert result["zero_operator_access_proven"] is False


@pytest.mark.parametrize("overrides", [
    {"authorized": False},
    {"operator_account": CUSTODY},
    {"custody_account": OPERATOR},
    {"fixture_key": "client-data/real-object"},
    {"fixture_key": "sec11-fixture/../../x"},
    {"fixture_version": "null"},
    {"fixture_version": "v*invalid"},
    {"bucket": ""},
])
def test_unsafe_parameters_are_rejected_before_any_write(overrides):
    s = FakeSession()
    with pytest.raises(ProbeDenied):
        run_probe(s, **overrides)
    assert s.s3.calls == []


def test_wrong_sts_account_refuses_before_any_write():
    s = FakeSession(operator=CUSTODY)
    with pytest.raises(ProbeDenied, match="identity"):
        run_probe(s)
    assert s.s3.calls == []


def test_probe_absent_authorization_refuses_before_aws_client_access():
    class PoisonSession:
        def client(self, *args, **kwargs):
            raise AssertionError("AWS must not be called")
    with pytest.raises(ProbeDenied, match="not authorized"):
        run_probe(PoisonSession(), authorized=False)
