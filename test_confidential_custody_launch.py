"""No AWS calls or customer data: external custody admission preflight tests."""
import copy
import json

import pytest

from confidential.pilot_preflight import PilotPreflightRejected, validate_preflight
from confidential.operator_boundary import BoundaryDenied
from test_confidential_operator_boundary import (
    fixture, OPERATOR, CUSTODY, TENANT, PCR, DIGEST, TASK, KEY,
)
from scripts import confidential_pilot_run as runner

SHARED = "notarai-confidential-shared"


def setup():
    data = fixture()
    task = data["task_definition"]
    env = {x["name"]: x["value"] for x in task["containerDefinitions"][0]["environment"]}
    capacity = {"capacityProviders": [{
        "name": SHARED, "status": "ACTIVE",
        "managedInstancesProvider": {
            "instanceLaunchTemplate": {"nitroEnclavesEnabled": True},
        },
    }]}
    approval = {
        "operator_account": OPERATOR,
        "custody_account": CUSTODY,
        "tenant": TENANT,
        "kms_key_arn": KEY,
        "task_definition_arn": TASK,
        "expected_pcr17": PCR,
        "image_sha256": DIGEST,
        "release_id": "a" * 32,
        "static_configuration_verified": True,
        "independent_release_signature_verified": True,
        "zero_operator_access_proven": False,
    }
    return {"task": {"taskDefinition": task}, "capacity": capacity,
            "env": env, "approval": approval}


def check(*, change=None, approval=True, key_policy=None, shared=True):
    values = setup()
    if change:
        change(values)
    return validate_preflight(
        values["task"], values["capacity"], key_policy,
        account=OPERATOR, tenant=TENANT, task_arn=TASK,
        kms_key_arn=KEY, bucket=values["env"]["NOTARAI_CONFIDENTIAL_BUCKET"],
        queue_url=values["env"]["NOTARAI_CONFIDENTIAL_QUEUE_URL"],
        expected_pcr17=PCR, shared_pool=shared,
        custody_approval=values["approval"] if approval else None,
    )


def test_external_kms_is_supported_only_with_separately_verified_release():
    assert check() is None
    with pytest.raises(PilotPreflightRejected, match="wrong KMS key ARN"):
        check(approval=False)
    with pytest.raises(PilotPreflightRejected, match="shared Nitro"):
        check(shared=False)


@pytest.mark.parametrize("tamper", [
    lambda d: d["approval"].update(custody_account=OPERATOR),
    lambda d: d["approval"].update(tenant="pilot02"),
    lambda d: d["approval"].update(kms_key_arn="arn:aws:kms:eu-central-1:111122223333:key/evil"),
    lambda d: d["approval"].update(task_definition_arn=TASK[:-2] + "99"),
    lambda d: d["approval"].update(expected_pcr17="b" * 96),
    lambda d: d["approval"].update(image_sha256="a" * 64),
    lambda d: d["approval"].update(release_id="not-a-uuid"),
    lambda d: d["approval"].update(static_configuration_verified=False),
    lambda d: d["approval"].update(independent_release_signature_verified=False),
    lambda d: d["approval"].update(zero_operator_access_proven=True),
    lambda d: d["task"]["taskDefinition"]["containerDefinitions"][0].update(
        image="rogue:latest"
    ),
    lambda d: d["task"]["taskDefinition"]["trustedExecutionConfiguration"].update(
        isolationMode="OTHER"
    ),
    lambda d: d["task"]["taskDefinition"]["containerDefinitions"][0][
        "environment"][4].update(value="unapproved-key"),
])
def test_operator_cannot_switch_identity_key_pcr_code_or_approval(tamper):
    values = setup()
    tamper(values)
    with pytest.raises(PilotPreflightRejected):
        validate_preflight(
            values["task"], values["capacity"], None,
            account=OPERATOR, tenant=TENANT, task_arn=TASK,
            kms_key_arn=KEY, bucket=values["env"]["NOTARAI_CONFIDENTIAL_BUCKET"],
            queue_url=values["env"]["NOTARAI_CONFIDENTIAL_QUEUE_URL"],
            expected_pcr17=PCR, shared_pool=True,
            custody_approval=values["approval"],
        )


def test_operator_supplied_policy_cannot_replace_independent_live_audit():
    with pytest.raises(PilotPreflightRejected):
        check(key_policy={"Statement": []})


def test_incomplete_external_custody_fails_before_any_aws_call(monkeypatch):
    monkeypatch.setattr(runner, "aws", lambda *args, **kw: (
        (_ for _ in ()).throw(AssertionError("AWS must not be called"))
    ))
    params = dict(
        profile="ops", account=OPERATOR, tenant=TENANT,
        subnet="subnet-0123456789abcdef0", job_id="a" * 32,
        apply=True, shared_compute=True,
    )
    with pytest.raises(RuntimeError, match="independent signed release"):
        runner.run_pilot(**params, external_custody_key_arn=KEY)
    with pytest.raises(RuntimeError, match="independent signed release"):
        runner.run_pilot(**params, external_custody_key_arn=KEY,
                         custody_profile="ops", custody_release_file="/tmp/none",
                         custodian_public_key_file="/tmp/none",
                         custodian_public_key_sha256="a" * 64)
    with pytest.raises(RuntimeError, match="independent signed release"):
        runner.run_pilot(**{**params, "shared_compute": False},
                         external_custody_key_arn=KEY,
                         custody_profile="custody",
                         custody_release_file="/tmp/none",
                         custodian_public_key_file="/tmp/none",
                         custodian_public_key_sha256="a" * 64)


def test_failed_independent_release_blocks_aws_run_task(monkeypatch, tmp_path):
    from scripts import verify_confidential_shared_fabric as fabric
    from scripts import verify_confidential_release as release
    data = setup()
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"not": "approved"}))
    pem = tmp_path / "custody.pem"
    pem.write_text("untrusted fixture")
    subnet = "subnet-0123456789abcdef0"
    vpc = "vpc-0123456789abcdef0"
    sg = "sg-0123456789abcdef0"
    endpoint_sg = "sg-11111111111111111"
    route = "rtb-0123456789abcdef0"

    monkeypatch.setattr(fabric, "verify", lambda **kwargs: {"network": "shared"})
    outputs = {
        "notarai-confidential-shared-fabric": {
            "SharedVpcId": vpc, "SharedPrivateSubnetId": subnet,
            "SharedRouteTableId": route, "SharedRuntimeSecurityGroupId": sg,
            "SharedEndpointSecurityGroupId": endpoint_sg,
        },
        "notarai-confidential-shared-capacity": {"SharedClusterName": SHARED},
        "notarai-confidential-task-pilot01": {"TaskDefinitionArn": TASK},
        "notarai-confidential-staging-pilot01": {
            "BucketName": data["env"]["NOTARAI_CONFIDENTIAL_BUCKET"],
            "QueueUrl": data["env"]["NOTARAI_CONFIDENTIAL_QUEUE_URL"],
        },
    }
    monkeypatch.setattr(runner, "outputs", lambda profile, stack: outputs[stack])
    monkeypatch.setattr(runner, "_verified_pcr17", lambda profile, task, attestation_dir=None: PCR)
    aws_calls = []

    def fake_aws(profile, args, **kw):
        aws_calls.append(args)
        if args[:2] == ["sts", "get-caller-identity"]:
            return {"Account": OPERATOR}
        if args[:2] == ["ecs", "describe-task-definition"]:
            return data["task"]
        if args[:2] == ["ecs", "describe-capacity-providers"]:
            return data["capacity"]
        raise AssertionError("RunTask or key policy read attempted before release")

    monkeypatch.setattr(runner, "aws", fake_aws)
    monkeypatch.setattr(release, "check_release", lambda **kwargs: (
        (_ for _ in ()).throw(BoundaryDenied("unapproved or expired"))
    ))
    with pytest.raises(RuntimeError, match="preflight rejected launch"):
        runner.run_pilot(
            profile="ops", account=OPERATOR, tenant=TENANT,
            subnet=subnet, job_id="a" * 32,
            vpc=vpc, route_table=route, guest_sg=sg, endpoint_sg=endpoint_sg,
            s3_prefix="pl-0123456789abcdef0",
            dynamodb_prefix="pl-11111111111111111",
            shared_compute=True, apply=True, external_custody_key_arn=KEY,
            custody_profile="independent", custody_release_file=str(receipt),
            custodian_public_key_file=str(pem),
            custodian_public_key_sha256="f" * 64,
        )
    assert not any(x[:2] in (
        ["ecs", "run-task"], ["kms", "get-key-policy"],
    ) for x in aws_calls)
