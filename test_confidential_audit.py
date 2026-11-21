"""Read-only confidential pilot audit tests without AWS connections."""
import copy

import pytest

from scripts.audit_confidential_pilot import audit, _count
from test_confidential_job_ledger import FakeDdb
from confidential.job_ledger import PreviewJobLedger

ACCOUNT = "111122223333"
TENANT = "pilot01"
JOB = "abc012"
BASE = "notarai-confidential-" + TENANT
QUEUE = f"https://sqs.eu-central-1.amazonaws.com/{ACCOUNT}/{BASE}.fifo"
BUCKET = f"ntr-cf-{TENANT}-{ACCOUNT}-eu-central-1"


class Stage:
    def describe_stacks(self, **kwargs):
        assert kwargs["StackName"] == "notarai-confidential-staging"
        return {"Stacks": [{
            "StackStatus": "CREATE_COMPLETE",
            "Outputs": [
                {"OutputKey": "BucketName", "OutputValue": BUCKET},
                {"OutputKey": "QueueUrl", "OutputValue": QUEUE},
            ],
        }]}


class Queue:
    def get_queue_url(self, **kwargs):
        assert kwargs["QueueName"] == BASE + "-dead.fifo"
        return {"QueueUrl": QUEUE[:-5] + "-dead.fifo"}

    def get_queue_attributes(self, **kwargs):
        if kwargs["QueueUrl"].endswith("-dead.fifo"):
            return {"Attributes": {"ApproximateNumberOfMessages": "1"}}
        assert kwargs["QueueUrl"] == QUEUE
        return {"Attributes": {
            "ApproximateNumberOfMessages": "2",
            "ApproximateNumberOfMessagesNotVisible": "1",
        }}


class ECS:
    def list_tasks(self, **kwargs):
        assert kwargs["cluster"] == BASE
        assert kwargs["desiredStatus"] == "RUNNING"
        return {"taskArns": ["arn:aws:ecs:eu-central-1:111122223333:task/pilot"]}


class S3:
    def head_object(self, **kwargs):
        assert kwargs["Bucket"] == BUCKET
        assert kwargs["Key"].endswith("/abc012.json")
        return {"ContentLength": 140}


class STS:
    def __init__(self, account=ACCOUNT):
        self.account = account

    def get_caller_identity(self):
        return {"Account": self.account}


class Session:
    def __init__(self, account=ACCOUNT, status="queued"):
        self.ddb = FakeDdb()
        ledger = PreviewJobLedger(self.ddb, tenant=TENANT)
        ledger.create(
            job_id=JOB, case_id="case01", object_id="obj01",
            s3_version="v000001", now=100,
        )
        if status == "preview_completed":
            ticket = ledger.claim(
                job_id=JOB, case_id="case01", object_id="obj01",
                s3_version="v000001", token="a" * 32, now=101,
            )
            ledger.complete(job_id=JOB, token=ticket.token)
        self.clients = {
            "sts": STS(account), "cloudformation": Stage(),
            "sqs": Queue(), "ecs": ECS(), "s3": S3(),
            "dynamodb": self.ddb,
        }
        self.requested = []

    def client(self, name):
        self.requested.append(name)
        return self.clients[name]


def test_dry_run_makes_zero_aws_calls():
    def never_session(**kwargs):
        raise AssertionError("No AWS session allowed in dry run")
    result = audit(
        profile="fictional", account=ACCOUNT, tenant=TENANT, job_id=JOB,
        check=False, session_factory=never_session,
    )
    assert result == {"mode": "dry_run", "aws_calls": 0}


def test_readonly_audit_reports_counts_and_expected_status():
    session = Session(status="preview_completed")
    result = audit(
        profile="fictional", account=ACCOUNT, tenant=TENANT, job_id=JOB,
        check=True, session_factory=lambda **kwargs: session,
    )
    assert result["submitted"] is False
    assert result["job_status"] == "preview_completed"
    assert result["result_marker_exists"] is True
    assert result["queue_visible_approx"] == 2
    assert result["dead_letter_visible_approx"] == 1
    assert result["queue_inflight_approx"] == 1
    assert result["ecs_active_count"] == 1
    assert all(name not in ("kms", "secretsmanager")
               for name in session.requested)


def test_sts_mismatch_denies_before_other_clients():
    session = Session(account="999988887777")
    with pytest.raises(RuntimeError, match="account"):
        audit(
            profile="fictional", account=ACCOUNT, tenant=TENANT, job_id=JOB,
            check=True, session_factory=lambda **kwargs: session,
        )
    assert session.requested == ["sts"]


def test_invalid_counts_are_rejected():
    with pytest.raises(ValueError):
        _count("not-a-number")
    with pytest.raises(ValueError):
        _count(1)
