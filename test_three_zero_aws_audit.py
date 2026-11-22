"""No AWS calls: verify reporting cannot accidentally approve 3xZERO."""
import base64

import pytest

from scripts.audit_three_zero_aws import audit_offline, audit_live_readonly, main
from scripts.render_confidential_taskdef import make_task


def _task():
    t = make_task(
        "111122223333", "pilot01",
        "111122223333.dkr.ecr.eu-central-1.amazonaws.com/notarai-confidential-pilot01@sha256:" + "b"*64,
        "synthetic-bucket",
        "https://sqs.eu-central-1.amazonaws.com/111122223333/notarai-confidential-pilot01.fifo",
    )
    t["trustedExecutionConfiguration"] = {
        "isolationMode": "CONFIDENTIAL_SANDBOX",
        "attestationPolicy": base64.b64encode(b"test-attestation-policy").decode(),
    }
    return t


def test_missing_aws_evidence_defaults_to_no_go(capsys):
    report = audit_offline()
    assert report["decision"] == "NO_GO"
    assert all(x["status"] == "NOT_CHECKED" for x in report["checks"].values())
    assert main([]) == 1
    assert '"decision":"NO_GO"' in capsys.readouterr().out


def test_even_static_valid_configs_remain_no_go():
    report = audit_offline(
        {"taskDefinition": _task()},
        {"loggingConfig": {"textDataDeliveryEnabled": False}},
        {"tasks": [{"enableExecuteCommand": False,
                    "trustedExecutionSummary": {"isolationMode": "CONFIDENTIAL_SANDBOX",
                                                "attestationPolicyStatus": "CONFIGURED"}}]},
    )
    assert report["decision"] == "NO_GO"
    assert all(x["status"] == "PASS_STATIC" for x in report["checks"].values())
    assert "aws_nitro_hardware_attestation_and_negative_release" in report["requires_live_evidence"]


def test_unsafe_task_remains_no_go_and_fails_individual_check():
    t = _task()
    t["trustedExecutionConfiguration"]["isolationMode"] = "ISOLATED_SANDBOX"
    report = audit_offline(t, {"loggingConfig": {}}, None)
    assert report["checks"]["ecs_task_definition"] == {"status": "FAIL"}
    assert report["decision"] == "NO_GO"


@pytest.mark.parametrize("args", [
    {"profile": "demo", "account": "not-an-account", "task_definition": "task"},
    {"profile": "demo", "account": "111122223333", "task_definition": "../task"},
    {"profile": "demo", "account": "111122223333", "task_definition": "task", "cluster": "cluster"},
])
def test_live_scope_is_rejected_before_importing_boto3(args):
    with pytest.raises(ValueError):
        audit_live_readonly(**args)
