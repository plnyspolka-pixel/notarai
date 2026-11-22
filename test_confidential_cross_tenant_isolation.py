"""SEC-09 synthetic cross-tenant regression tests; never calls AWS."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json

import pytest

from confidential.tenant_isolation import (
    TenantBoundary, TenantIsolationRejected, validate_pair,
    validate_worker_binding,
)
from confidential.job_ledger import JobRejected, PreviewJobLedger
from confidential.worker import _config, _parse_message, _process_one
from test_confidential_infra import template
from test_confidential_job_ledger import FakeDdb, FakeQueue, FakeS3, FakeSession

ACCOUNT = "111122223333"
REGION = "eu-central-1"
DIGEST = "a" * 64


def pilot(tenant: str) -> TenantBoundary:
    family = f"notarai-confidential-{tenant}"
    return TenantBoundary(
        tenant=tenant, account=ACCOUNT, session_tenant=tenant,
        cluster="notarai-confidential-shared",
        capacity_provider="notarai-confidential-shared",
        task_definition_arn=f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/{family}:3",
        task_role_arn=f"arn:aws:iam::{ACCOUNT}:role/{family}",
        execution_role_arn=f"arn:aws:iam::{ACCOUNT}:role/notarai-confidential-execution-{tenant}",
        image_digest=DIGEST,
        kms_key_arn=f"arn:aws:kms:{REGION}:999988887777:key/{tenant}",
        bucket="synthetic-confidential-ciphertext",
        queue_url=f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/{family}.fifo",
        jobs_table=f"notarai-confidential-jobs-{tenant}",
        dispatch_table=f"notarai-confidential-dispatch-{tenant}",
        s3_namespace=f"kancelarie/{tenant}/confidential/",
    )


def test_K1_distinct_pilot_identities_on_same_pinned_shared_compute():
    one, two = pilot("pilot01"), pilot("pilot02")
    validate_pair(one, two)
    assert one.bucket == two.bucket  # optional shared ciphertext bucket
    assert one.s3_namespace != two.s3_namespace
    assert one.task_role_arn != two.task_role_arn
    assert one.kms_key_arn != two.kms_key_arn


@pytest.mark.parametrize("change", [
    {"session_tenant": "pilot02"},  # impersonated API session
    {"queue_url": pilot("pilot02").queue_url},  # tampered queue
    {"task_definition_arn": pilot("pilot02").task_definition_arn},
    {"task_role_arn": pilot("pilot02").task_role_arn},
    {"execution_role_arn": pilot("pilot02").execution_role_arn},
    {"jobs_table": pilot("pilot02").jobs_table},
    {"dispatch_table": pilot("pilot02").dispatch_table},
    {"s3_namespace": pilot("pilot02").s3_namespace},
    {"cluster": "notarai-confidential-pilot02"},
    {"image_digest": "b" * 64},
])
def test_K3_reject_cross_tenant_control_plane_tampering(change):
    left = replace(pilot("pilot01"), **change)
    if "image_digest" in change:
        left.validate()
        with pytest.raises(TenantIsolationRejected):
            validate_pair(left, pilot("pilot02"))
    else:
        with pytest.raises(TenantIsolationRejected):
            validate_pair(left, pilot("pilot02"))


@pytest.mark.parametrize("value", [
    "https://sqs.eu-central-1.amazonaws.com/111122223333/notarai-confidential-pilot02.fifo",
    "https://sqs.us-east-1.amazonaws.com/111122223333/notarai-confidential-pilot01.fifo",
    "https://sqs.eu-central-1.amazonaws.com/999988887777/notarai-confidential-pilot01.fifo",
    "https://sqs.eu-central-1.amazonaws.com/111122223333/notarai-confidential-pilot01-dead.fifo",
])
def test_K3_worker_rejects_foreign_queue(value):
    with pytest.raises(TenantIsolationRejected):
        validate_worker_binding(
            tenant="pilot01", bucket="fictional-bucket",
            queue_url=value, kms_key_arn=pilot("pilot01").kms_key_arn,
            expected_account=ACCOUNT,
        )


def test_K3_worker_boot_check_happens_before_network(monkeypatch):
    import confidential.worker as worker
    monkeypatch.setattr(worker.os.path, "exists", lambda path: path == "/dev/nsm")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_REQUIRED", "1")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_TENANT", "pilot01")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_BUCKET", "fictional-bucket")
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_QUEUE_URL", pilot("pilot02").queue_url)
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_KMS_KEY_ARN", pilot("pilot01").kms_key_arn)
    with pytest.raises(RuntimeError, match="invalid confidential task configuration"):
        _config()


@pytest.mark.parametrize("change", [
    {"tenant_id": "pilot02"},
    {"case_id": "../pilot02"},
    {"object_id": "pilot02/secret"},
    {"job_id": "invalid/other"},
    {"s3_version": "null"},
    {"submit": True},
])
def test_K3_sqs_metadata_tampering_fails_closed(change):
    raw = {"tenant_id": "pilot01", "case_id": "case01", "object_id": "scan01",
           "job_id": "job01", "s3_version": "version01"}
    raw.update(change)
    with pytest.raises(ValueError):
        _parse_message(json.dumps(raw), "pilot01")


def _queued(ddb, tenant: str, job_id: str = "samejob") -> PreviewJobLedger:
    ledger = PreviewJobLedger(ddb, tenant=tenant)
    ledger.create(job_id=job_id, case_id="case01", object_id="scan01",
                  s3_version="v001", now=100)
    return ledger


def test_K4_same_job_id_never_crosses_two_tenant_ledgers():
    ddb = FakeDdb()
    one, two = _queued(ddb, "pilot01"), _queued(ddb, "pilot02")
    assert one.status("samejob")["status"] == "queued"
    assert two.status("samejob")["status"] == "queued"
    claim = one.claim(job_id="samejob", case_id="case01", object_id="scan01",
                      s3_version="v001", now=101, token="a" * 32)
    with pytest.raises(JobRejected):
        two.complete(job_id="samejob", token=claim.token)
    assert two.status("samejob")["status"] == "queued"
    one.complete(job_id="samejob", token=claim.token)
    assert one.status("samejob")["status"] == "preview_completed"


def test_K4_concurrent_duplicate_delivery_is_one_lease_only():
    ddb = FakeDdb()
    ledger = _queued(ddb, "pilot01")
    tokens = ("a" * 32, "b" * 32)
    def attempt(token):
        return ledger.claim(job_id="samejob", case_id="case01", object_id="scan01",
                            s3_version="v001", now=101, token=token).state
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, tokens))
    assert sorted(results) == ["busy", "claimed"]
    assert ledger.status("samejob")["attempts"] == 1


def test_K5_two_synthetic_preview_workers_never_submit(monkeypatch):
    import confidential.worker as worker
    async def preview(job_id, fields):
        assert fields == {"name": "FICTIONAL", "reference": "FAKE"}
    monkeypatch.setattr(worker, "_prepare_fictional_form", preview)
    seen = []
    def decrypt(s3, kms, bucket, tenant, case, obj, key, version):
        seen.append((tenant, case, obj, version))
        return {"name": "FICTIONAL", "reference": "FAKE"}
    monkeypatch.setattr(worker, "_load_decrypted_form", decrypt)
    for tenant in ("pilot01", "pilot02"):
        ddb = FakeDdb()
        _queued(ddb, tenant)
        queue = FakeQueue({"Body": json.dumps({
            "tenant_id": tenant, "case_id": "case01", "object_id": "scan01",
            "job_id": "samejob", "s3_version": "v001",
        }), "ReceiptHandle": "fictional"})
        storage = FakeS3()
        session = FakeSession(ddb, queue, storage)
        assert _process_one(session, tenant, "fictional-bucket",
                            pilot(tenant).queue_url, pilot(tenant).kms_key_arn) == 0
        assert queue.deleted is True
        assert storage.markers[0]["Key"] == (
            f"kancelarie/{tenant}/confidential-results/samejob.json"
        )
        assert json.loads(storage.markers[0]["Body"])["submitted"] is False
    assert len(seen) == 2 and {x[0] for x in seen} == {"pilot01", "pilot02"}


def test_K2_static_worker_policy_scopes_versioned_reads_and_other_services():
    task = template("notarai-confidential-task.yaml")
    role = task["Resources"]["ConfidentialTaskRole"]["Properties"]
    rules = role["Policies"][0]["PolicyDocument"]["Statement"]
    by_sid = {r["Sid"]: r for r in rules}
    s3 = by_sid["ReadOnlyOwnCiphertexts"]
    assert set(s3["Action"]) == {"s3:GetObject", "s3:GetObjectVersion"}
    assert "${TenantId}/confidential/*" in str(s3["Resource"])
    assert by_sid["ConsumeOwnQueue"]["Resource"] == {"Ref": "JobQueueArn"}
    assert "notarai-confidential-jobs-${TenantId}" in str(
        by_sid["ClaimAndFinalizeOwnPreviewJobs"]["Resource"]
    )
    assert by_sid["AttestedKmsDecrypt"]["Resource"] == {"Ref": "ConfidentialKmsKeyArn"}


def test_K2_static_dispatch_role_pins_run_task_and_passrole():
    config = template("notarai-confidential-dispatch.yaml")
    rules = config["Resources"]["DispatcherRole"]["Properties"]["Policies"][0][
        "PolicyDocument"]["Statement"
    ]
    by_sid = {r["Sid"]: r for r in rules}
    assert by_sid["StartOnlyPinnedTask"]["Resource"] == {"Ref": "TaskDefinitionArn"}
    assert by_sid["PassOnlyGuestTaskRoles"]["Resource"] == [
        {"Ref": "TaskRoleArn"}, {"Ref": "TaskExecutionRoleArn"},
    ]
    assert by_sid["PassOnlyGuestTaskRoles"]["Condition"]["StringEquals"][
        "iam:PassedToService"
    ] == "ecs-tasks.amazonaws.com"


def test_K6_read_only_simulator_is_never_misreported_as_real_denial():
    from scripts.verify_confidential_tenant_isolation import inspect, _probe_spec

    assert len(_probe_spec(pilot("pilot01"), pilot("pilot02"))) == 7
    calls = []

    class Sts:
        def get_caller_identity(self):
            calls.append("sts:get")
            return {"Account": ACCOUNT}

    class Ecs:
        def describe_task_definition(self, *, taskDefinition):
            calls.append("ecs:describe_task_definition")
            tenant = taskDefinition.rsplit("-", 1)[-1]
            p = pilot(tenant)
            environment = {
                "NOTARAI_CONFIDENTIAL_REQUIRED": "1",
                "NOTARAI_CONFIDENTIAL_TENANT": tenant,
                "NOTARAI_CONFIDENTIAL_BUCKET": p.bucket,
                "NOTARAI_CONFIDENTIAL_QUEUE_URL": p.queue_url,
                "NOTARAI_CONFIDENTIAL_KMS_KEY_ARN": p.kms_key_arn,
                "AWS_REGION": REGION,
                "HOME": "/tmp", "XDG_CACHE_HOME": "/tmp", "TMPDIR": "/tmp",
            }
            return {"taskDefinition": {
                "taskDefinitionArn": p.task_definition_arn,
                "taskRoleArn": p.task_role_arn,
                "executionRoleArn": p.execution_role_arn,
                "status": "ACTIVE", "networkMode": "awsvpc",
                "trustedExecutionConfiguration": {"isolationMode": "CONFIDENTIAL_SANDBOX"},
                "containerDefinitions": [{"image": (
                    f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/"
                    f"notarai-confidential-shared@sha256:{DIGEST}"
                ), "environment": [
                    {"name": k, "value": v} for k, v in environment.items()
                ]}],
            }}

        def describe_capacity_providers(self, *, capacityProviders):
            calls.append("ecs:describe_capacity_providers")
            assert capacityProviders == ["notarai-confidential-shared"]
            return {"capacityProviders": [{
                "status": "ACTIVE",
                "managedInstancesProvider": {
                    "instanceLaunchTemplate": {"nitroEnclavesEnabled": True}
                },
            }]}

    class Iam:
        def simulate_principal_policy(self, **kwargs):
            calls.append("iam:simulate_principal_policy")
            assert len(kwargs["ActionNames"]) == 1
            assert len(kwargs["ResourceArns"]) == 1
            return {"EvaluationResults": [{"EvalDecision": "implicitDeny"}]}

    class Session:
        clients = {"sts": Sts(), "ecs": Ecs(), "iam": Iam()}

        def client(self, name):
            assert name in self.clients
            return self.clients[name]

    def factory(**kwargs):
        assert kwargs == {"profile_name": "auditor", "region_name": REGION}
        return Session()

    evidence = inspect(profile="auditor", account=ACCOUNT, session_factory=factory)
    assert evidence["completed"] is False
    assert evidence["actual_negative_probes"] == 0
    assert evidence["simulated_probes"] == 14
    assert len(evidence["configuration_sha256"]) == 64
    assert set(evidence["criteria"].values()) == {"BLOCKED"}
    assert calls.count("iam:simulate_principal_policy") == 14
    assert all(call.startswith(("iam:simulate_", "sts:get", "ecs:describe_"))
               for call in calls)


def test_K6_wrong_account_never_simulates_or_inspects_resources():
    from scripts.verify_confidential_tenant_isolation import inspect

    class Sts:
        def get_caller_identity(self):
            return {"Account": ACCOUNT}

    class Session:
        def client(self, name):
            assert name == "sts"  # no ECS or IAM after mismatch
            return Sts()

    with pytest.raises(ValueError, match="does not match"):
        inspect(profile="auditor", account="999988887777",
                session_factory=lambda **kwargs: Session())
