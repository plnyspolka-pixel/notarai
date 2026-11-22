"""SEC-06 read-only DynamoDB custody export and pagination denial tests."""
import copy

import pytest

from confidential.operator_boundary import BoundaryDenied
from scripts.export_confidential_custody_ledger import fetch_ledger
from test_confidential_custody_history import make_history
from test_confidential_custody_cas import TABLE
from test_confidential_independent_custody_ops import CUSTODY, WORKLOAD


class FakeLedgerSession:
    def __init__(self, *, account=CUSTODY, state_changed=False,
                 bad_count=False, repeat_marker=False, wrong_marker=False,
                 no_state=False, omit_records=False):
        self.account = account
        self.state_changed = state_changed
        self.bad_count = bad_count
        self.repeat_marker = repeat_marker
        self.wrong_marker = wrong_marker
        self.no_state = no_state
        self.omit_records = omit_records
        self.fixture = make_history()
        self.calls = []

    def __call__(self, *, profile_name, region_name):
        assert profile_name == "separate-custodian"
        assert region_name == "eu-central-1"
        outer = self

        class Session:
            def client(self, name):
                assert name in ("sts", "dynamodb")
                return self

            def get_caller_identity(self):
                outer.calls.append("sts:GetCallerIdentity")
                return {"Account": outer.account}

            def get_item(self, **kwargs):
                outer.calls.append("dynamodb:GetItem")
                assert kwargs["TableName"] == TABLE
                assert kwargs["ConsistentRead"] is True
                assert kwargs["Key"] == {
                    "tenant": {"S": "TENANT#pilot01"},
                    "record": {"S": "STATE"}}
                if outer.no_state:
                    return {}
                item = copy.deepcopy(outer.fixture["state_item"])
                if outer.state_changed and outer.calls.count("dynamodb:GetItem") == 2:
                    item["revision"]["N"] = "99"
                return {"Item": item}

            def query(self, **kwargs):
                outer.calls.append("dynamodb:Query")
                assert kwargs["TableName"] == TABLE
                assert kwargs["ConsistentRead"] is True
                assert kwargs["ScanIndexForward"] is True
                assert kwargs["Limit"] == 100
                assert kwargs["KeyConditionExpression"] == (
                    "#tenant = :tenant AND begins_with(#record, :prefix)")
                events = copy.deepcopy(outer.fixture["event_items"])
                if outer.omit_records:
                    events = events[1:]
                marker = {"tenant": {"S": "TENANT#pilot01"},
                          "record": {"S": "EVENT#00000000000000000001"}}
                if "ExclusiveStartKey" in kwargs:
                    assert kwargs["ExclusiveStartKey"] == marker
                    if outer.repeat_marker:
                        return {"Items": events[:1], "Count": 1,
                                "LastEvaluatedKey": marker}
                    return {"Items": events[1:], "Count": len(events[1:])}
                if outer.wrong_marker:
                    marker["tenant"] = {"S": "TENANT#pilot02"}
                return {
                    "Items": events[:1],
                    "Count": 99 if outer.bad_count else 1,
                    "LastEvaluatedKey": marker,
                }

        return Session()


def test_k6_custody_export_default_has_zero_aws_calls():
    fake = FakeLedgerSession()
    report = fetch_ledger(
        tenant="pilot01", ledger_table_arn=TABLE,
        custody_profile="separate-custodian", session_factory=fake)
    assert report["status"] == "BLOCKED"
    assert report["aws_calls"] == 0
    assert not report["history_integrity_verified"]
    assert fake.calls == []


def test_k6_custody_export_strong_reads_all_pages_without_writes():
    fake = FakeLedgerSession()
    report = fetch_ledger(
        tenant="pilot01", ledger_table_arn=TABLE,
        custody_profile="separate-custodian", check=True,
        session_factory=fake)
    assert report["status"] == "BLOCKED"
    assert report["event_pages_read"] == 2
    assert report["aws_calls"] == 5
    assert len(report["event_items"]) == 3
    assert report["state_item"] == fake.fixture["state_item"]
    assert not report["history_integrity_verified"]
    assert not report["snapshot_atomic"]
    assert not report["ledger_export_exhaustiveness_proven"]
    assert not report["independent_custody_verified"]
    assert fake.calls == [
        "sts:GetCallerIdentity", "dynamodb:GetItem", "dynamodb:Query",
        "dynamodb:Query", "dynamodb:GetItem",
    ]


@pytest.mark.parametrize("change", [
    {"account": WORKLOAD},
    {"state_changed": True},
    {"bad_count": True},
    {"repeat_marker": True},
    {"wrong_marker": True},
    {"no_state": True},
])
def test_k6_custody_export_denies_partial_or_concurrent_reads(change):
    fake = FakeLedgerSession(**change)
    with pytest.raises(BoundaryDenied):
        fetch_ledger(
            tenant="pilot01", ledger_table_arn=TABLE,
            custody_profile="separate-custodian", check=True,
            session_factory=fake)


@pytest.mark.parametrize("invalid", [
    ("pilot02", TABLE),
    ("pilot01", TABLE.replace("eu-central-1", "us-east-1")),
    ("pilot01", TABLE.replace(CUSTODY, WORKLOAD)),
    ("pilot01", "notarai-custody-ledger"),
])
def test_k1_custody_export_has_pinned_tenant_and_table(invalid):
    tenant, table = invalid
    fake = FakeLedgerSession()
    with pytest.raises(BoundaryDenied):
        fetch_ledger(
            tenant=tenant, ledger_table_arn=table,
            custody_profile="separate-custodian", check=True,
            session_factory=fake)
    if table != TABLE:
        assert not any(call.startswith("dynamodb:") for call in fake.calls)


def test_k6_ledger_read_can_succeed_with_truncated_history_but_replay_refuses():
    from confidential.custody_history import verify_history
    fake = FakeLedgerSession(omit_records=True)
    export = fetch_ledger(
        tenant="pilot01", ledger_table_arn=TABLE,
        custody_profile="separate-custodian", check=True,
        session_factory=fake)
    assert export["status"] == "BLOCKED"
    with pytest.raises(BoundaryDenied):
        verify_history(
            tenant="pilot01", event_items=export["event_items"],
            state_item=export["state_item"],
            trust_roots=fake.fixture["trust_roots"],
            pinned_final_state_sha256=fake.fixture["pinned_final_state_sha256"],
            clock=fake.fixture["clock"])


def test_k6_read_only_export_not_equal_to_signed_history_replay():
    from confidential.custody_history import verify_history
    fake = FakeLedgerSession()
    report = fetch_ledger(
        tenant="pilot01", ledger_table_arn=TABLE,
        custody_profile="separate-custodian", check=True,
        session_factory=fake)
    assert report["history_integrity_verified"] is False
    # A separate verifier using independent trust roots and final SHA is
    # explicitly required; retrieving a successful snapshot is not approval.
    validated = verify_history(
        tenant="pilot01", event_items=report["event_items"],
        state_item=report["state_item"],
        trust_roots=fake.fixture["trust_roots"],
        pinned_final_state_sha256=fake.fixture[
            "pinned_final_state_sha256"],
        clock=fake.fixture["clock"])
    assert validated["offline_chain_integrity_checked"]
    assert validated["independent_custody_verified"] is False
