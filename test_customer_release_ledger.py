"""Synthetic concurrency + crash regression for *durable* customer DEK grants."""
import copy
import pytest

from confidential.job_ledger import PreviewJobLedger, JobRejected


class ConditionalDenied(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class MemoryDdb:
    def __init__(self):
        self.rows = {}
        self.consumptions = 0

    def put_item(self, **kw):
        row = copy.deepcopy(kw["Item"])
        pk = row["pk"]["S"]
        if pk in self.rows or kw["ConditionExpression"] != "attribute_not_exists(pk)":
            raise ConditionalDenied()
        self.rows[pk] = row

    def get_item(self, **kw):
        assert kw["ConsistentRead"]
        pk = kw["Key"]["pk"]["S"]
        return {"Item": copy.deepcopy(self.rows[pk])} if pk in self.rows else {}

    def update_item(self, **kw):
        row = self.rows[kw["Key"]["pk"]["S"]]
        expr = kw["ConditionExpression"]
        v = kw["ExpressionAttributeValues"]
        if "ADD attempts" in kw["UpdateExpression"]:
            assert "attribute_not_exists(release_consumed_sha256)" in expr, repr(expr)
            assert row["tenant_id"] == v[":tenant"], ("tenant", row["tenant_id"], v[":tenant"])
            assert row["job_id"] == v[":job"], ("job", row["job_id"], v[":job"])
            assert row["case_id"] == v[":case"], ("case", row["case_id"], v[":case"])
            assert row["object_id"] == v[":object"], ("object", row["object_id"], v[":object"])
            assert row["s3_version"] == v[":version"], ("version", row["s3_version"], v[":version"])
            assert row["state"]["S"] in ("queued", "retryable"), ("state", row["state"])
            if ("release_consumed_sha256" in row or row["state"]["S"] not in ("queued", "retryable")
                    or row["tenant_id"] != v[":tenant"]
                    or row["job_id"] != v[":job"]
                    or row["case_id"] != v[":case"]
                    or row["object_id"] != v[":object"]
                    or row["s3_version"] != v[":version"]
                    or row["submitted"]["BOOL"] is not False
                    or int(row["attempts"]["N"]) >= int(v[":limit"])):
                raise ConditionalDenied()
            row["state"] = v[":running"]
            row["task_token"] = v[":token"]
            row["attempts"] = {"N": str(int(row["attempts"]["N"]) + 1)}
            row["lease_until"] = v[":lease"]
            return {"Attributes": copy.deepcopy(row)}
        if "release_consumed_sha256 = :digest" in kw["UpdateExpression"]:
            assert "attribute_not_exists(release_consumed_sha256)" in expr
            if ("release_consumed_sha256" in row
                    or row["state"]["S"] != "running"
                    or row["task_token"] != v[":token"]
                    or row["tenant_id"] != v[":tenant"]
                    or row["submitted"]["BOOL"] is not False):
                raise ConditionalDenied()
            self.consumptions += 1
            row["release_consumed_sha256"] = v[":digest"]
            row["release_consumed_at"] = v[":now"]
            return {}
        if ":next" in v:
            if row["state"]["S"] != "running" or row["task_token"] != v[":token"]:
                raise ConditionalDenied()
            row["state"] = v[":next"]
            del row["task_token"]
            return {}
        raise AssertionError("unexpected DynamoDB operation")


def new_job():
    ddb = MemoryDdb()
    ledger = PreviewJobLedger(ddb, tenant="pilot01")
    ledger.create(job_id="job01", case_id="case01", object_id="object01",
                  s3_version="s3-version-01", now=100)
    return ddb, ledger


def claim(ledger, token="a"*32, now=101):
    return ledger.claim(job_id="job01", case_id="case01",
                        object_id="object01", s3_version="s3-version-01",
                        token=token, now=now)


def test_customer_grant_consumed_once_and_not_retried_on_restart():
    ddb, ledger = new_job()
    first = claim(ledger)
    assert first.state == "claimed"
    ledger.consume_release_once(job_id="job01", token=first.token,
                                grant_sha256="f"*64, now=102)
    assert ddb.consumptions == 1
    with pytest.raises(JobRejected):
        ledger.consume_release_once(job_id="job01", token=first.token,
                                    grant_sha256="f"*64, now=103)
    assert claim(ledger, token="b"*32, now=2000).state == "needs_review"
    assert ddb.consumptions == 1


def test_customer_failed_after_grant_consumption_is_needs_review():
    ddb, ledger = new_job()
    first = claim(ledger)
    ledger.consume_release_once(job_id="job01", token=first.token,
                                grant_sha256="f"*64, now=102)
    ledger.fail(job_id="job01", token=first.token, attempts=1)
    assert ledger.status("job01")["status"] == "needs_review"
    assert claim(ledger, token="b"*32, now=2000).state == "needs_review"


def test_legacy_preview_without_grant_can_still_retry():
    _, ledger = new_job()
    first = claim(ledger)
    ledger.fail(job_id="job01", token=first.token, attempts=1)
    assert ledger.status("job01")["status"] == "retryable"
    again = claim(ledger, token="b"*32, now=200)
    assert again.state == "claimed"


def test_wrong_worker_token_cannot_consume():
    ddb, ledger = new_job()
    first = claim(ledger)
    with pytest.raises(JobRejected):
        ledger.consume_release_once(job_id="job01", token="b"*32,
                                    grant_sha256="f"*64, now=102)
    assert ddb.consumptions == 0
    ledger.consume_release_once(job_id="job01", token=first.token,
                                grant_sha256="f"*64, now=103)
    assert ddb.consumptions == 1


@pytest.mark.parametrize("digest", ["", "a", "0"*63, "x"*64, "0"*65])
def test_bogus_grant_digest_denied(digest):
    ddb, ledger = new_job()
    first = claim(ledger)
    with pytest.raises(JobRejected):
        ledger.consume_release_once(job_id="job01", token=first.token,
                                    grant_sha256=digest, now=102)
    assert ddb.consumptions == 0


def test_other_tenant_cannot_consume_grant():
    ddb, ledger = new_job()
    first = claim(ledger)
    other = PreviewJobLedger(ddb, tenant="pilot02")
    with pytest.raises(JobRejected):
        other.consume_release_once(job_id="job01", token=first.token,
                                   grant_sha256="f"*64, now=102)
    assert ddb.consumptions == 0


def test_completed_grant_stays_completed_but_cannot_be_redecrypted():
    ddb, ledger = new_job()
    first = claim(ledger)
    ledger.consume_release_once(job_id="job01", token=first.token,
                                grant_sha256="f"*64, now=102)
    ledger.complete(job_id="job01", token=first.token)
    assert claim(ledger, token="b"*32, now=2000).state == "completed"
    assert ddb.consumptions == 1
