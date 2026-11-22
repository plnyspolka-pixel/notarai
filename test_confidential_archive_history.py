"""SEC-11 synthetic S3 evidence history pagination/rollback tests."""
import pytest

from confidential.archive_history import ArchiveHistoryDenied, audit_archive_history

ACCOUNT = "444455556666"
BUCKET = "notarai-sec11-custody-synthetic"
PREFIX = "sec11-evidence/pilot01/"
EXPECTED = ((1, "versionOne"), (2, "versionTwo"), (3, "versionThree"))


def version(number, vid=None, latest=True):
    return {
        "Key": f"{PREFIX}{number:08d}.json",
        "VersionId": vid or EXPECTED[number-1][1],
        "IsLatest": latest,
    }


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def paginate(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.pages)


class FakeSession:
    def __init__(self, pages, account=ACCOUNT):
        self.account = account
        self.paginator = FakePaginator(pages)
        self.services = []

    def client(self, service, **kwargs):
        self.services.append(service)
        if service == "sts":
            account = self.account
            class STS:
                def get_caller_identity(self):
                    return {"Account": account}
            return STS()
        assert service == "s3"
        assert kwargs == {"region_name": "eu-central-1"}
        paginator = self.paginator
        class S3:
            def get_paginator(self, name):
                assert name == "list_object_versions"
                return paginator
        return S3()


def run(session, **changes):
    opts = {
        "session": session, "custody_account": ACCOUNT,
        "bucket": BUCKET, "tenant": "pilot01",
        "expected_versions": EXPECTED,
    }
    opts.update(changes)
    return audit_archive_history(**opts)


def test_fully_paged_and_out_of_order_list_matches_independent_receipt():
    session = FakeSession([
        {"Versions": [version(2), version(1)]},
        {"Versions": [version(3)]},
    ])
    report = run(session)
    assert report["inventory_integrity"] == "PASS"
    assert report["assurance_status"] == "BLOCKED"
    assert report["checked_sequence_count"] == 3
    assert all(report["checks"].values())
    assert report["zero_operator_access_proven"] is False
    assert session.paginator.calls == [{
        "Bucket": BUCKET, "Prefix": PREFIX, "ExpectedBucketOwner": ACCOUNT,
    }]
    assert session.services == ["sts", "s3"]


@pytest.mark.parametrize("pages", [
    [{"Versions": [version(1), version(2)]}],  # missing last sequence
    [{"Versions": [version(1), version(2), version(3),
                   version(2, "shadowVersion", False)]}],  # extra S3 version
    [{"Versions": [version(1), version(2), version(3)],
      "DeleteMarkers": [{"Key": PREFIX + "00000002.json"}]}],
    [{"Versions": [version(1), version(2, "differentVersion"), version(3)]}],
    [{"Versions": [version(1), version(2), version(3, latest=False)]}],
    [{"Versions": [version(1), version(2), version(3),
                   {"Key": PREFIX + "00000004.json", "VersionId": "extra",
                    "IsLatest": True}]}],
    [{"Versions": [version(1), version(2), version(3),
                   {"Key": PREFIX + "unexpected.tmp", "VersionId": "extra",
                    "IsLatest": True}]}],
])
def test_shadowed_deleted_unexpected_and_missing_history_fails_closed(pages):
    result = run(FakeSession(pages))
    assert result["inventory_integrity"] == "FAIL"
    assert result["assurance_status"] == "BLOCKED"
    assert not result["zero_operator_access_proven"]


def test_wrong_sts_account_denied_before_listing():
    session = FakeSession([{"Versions": [version(1), version(2), version(3)]}],
                          account="111122223333")
    result = run(session)
    assert result["inventory_integrity"] == "FAIL"
    assert session.services == ["sts"]
    assert session.paginator.calls == []


@pytest.mark.parametrize("changes", [
    {"tenant": "client/unsafe"},
    {"custody_account": "bad"},
    {"expected_versions": ()},
    {"expected_versions": ((1, "versionOne"), (3, "versionThree"))},
    {"expected_versions": ((1, "null"),)},
    {"expected_versions": ((1, "ver*bad"),)},
    {"expected_versions": [(1, "versionOne")]},  # require immutable tuple receipt
])
def test_invalid_external_receipt_refused_before_any_aws_call(changes):
    class NoAws:
        def client(self, *args, **kwargs):
            raise AssertionError("no AWS should be touched")
    with pytest.raises(ArchiveHistoryDenied):
        run(NoAws(), **changes)
