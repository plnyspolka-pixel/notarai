"""Static safety checks for optional CloudFormation templates; no AWS credentials."""
from pathlib import Path

import yaml

ROOT = Path(__file__).parent / "infra"


class CloudFormationLoader(yaml.SafeLoader):
    pass


def _tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    return {tag_suffix: loader.construct_mapping(node)}


CloudFormationLoader.add_multi_constructor("!", _tag)


def template(name):
    return yaml.load((ROOT / name).read_text("utf-8"), Loader=CloudFormationLoader)


def test_staging_bucket_and_queue_are_independent_of_live_application():
    t = template("notarai-confidential-staging.yaml")
    assert {"DemoBucket", "DemoQueue", "DemoDeadLetterQueue", "DemoBucketPolicy"} <= set(t["Resources"])
    assert all(x["Type"] not in ("AWS::ECS::Service", "AWS::IAM::Policy")
               for x in t["Resources"].values())
    bucket = t["Resources"]["DemoBucket"]["Properties"]
    assert all(bucket["PublicAccessBlockConfiguration"].values())
    assert bucket["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"
    assert t["Resources"]["DemoQueue"]["Properties"]["SqsManagedSseEnabled"]


def test_kms_decrypt_requires_attested_ecs_and_exact_role():
    t = template("notarai-confidential-demo-kms.yaml")
    key = t["Resources"]["DemoRsaKey"]["Properties"]
    assert key["KeySpec"] == "RSA_3072"
    assert key["KeyUsage"] == "ENCRYPT_DECRYPT"
    rules = key["KeyPolicy"]["Statement"]
    decrypt = [r for r in rules if "kms:Decrypt" in r.get("Action", [])]
    assert len(decrypt) == 1
    gate = decrypt[0]["Condition"]
    assert "aws:PrincipalArn" in gate["ArnEquals"]
    assert gate["StringEqualsIgnoreCase"]["kms:RecipientAttestation:PCR8:ServiceName"] == "ecs.amazonaws.com"
    assert "kms:RecipientAttestation:PCR17" in gate["StringEqualsIgnoreCase"]
    assert len(t["Parameters"]["ExpectedPCR17"]["Default"]) == 96


def test_confidential_task_is_separate_with_no_exec_and_minimum_iam():
    t = template("notarai-confidential-task.yaml")
    task = t["Resources"]["ConfidentialTaskDefinition"]["Properties"]
    assert task["RequiresCompatibilities"] == ["MANAGED_INSTANCES"]
    assert task["NetworkMode"] == "awsvpc"
    assert task["TrustedExecutionConfiguration"]["IsolationMode"] == "CONFIDENTIAL_SANDBOX"
    container = task["ContainerDefinitions"][0]
    assert container["ReadonlyRootFilesystem"]
    assert not container.get("LogConfiguration")
    assert "ExecuteCommand" not in task
    role = t["Resources"]["ConfidentialTaskRole"]["Properties"]
    statements = role["Policies"][0]["PolicyDocument"]["Statement"]
    assert any(s.get("Action") == "s3:GetObject" for s in statements)
    assert not any("kms:Decrypt" in str(s.get("Action")) for s in statements)
    assert any("dynamodb:UpdateItem" in s.get("Action", []) for s in statements)
    assert container["Command"] == ["python", "-m", "confidential.customer_v3_worker"]


def test_dedicated_nitro_capacity_roles_and_sg():
    t = template("notarai-confidential-capacity-base.yaml")
    resources = t["Resources"]
    assert "ConfidentialCluster" in resources
    assert "ManagedInfrastructureRole" in resources
    assert "ManagedInstanceProfile" in resources
    assert "ManagedInstanceRole" in resources
    role = resources["ManagedInstanceRole"]["Properties"]
    # AWS policy for Managed Instances only passes ecsInstanceRole*.
    assert role["RoleName"]["Sub"].startswith("ecsInstanceRole")
    assert "AmazonECSInstanceRolePolicyForManagedInstances" in role["ManagedPolicyArns"][0]
    infra = resources["ManagedInfrastructureRole"]["Properties"]
    assert "AmazonECSInfrastructureRolePolicyForManagedInstances" in infra["ManagedPolicyArns"][0]
    sg = resources["PilotSecurityGroup"]["Properties"]
    assert "SecurityGroupIngress" not in sg
    assert all(rule["FromPort"] == 443 and rule["ToPort"] == 443
               for rule in sg["SecurityGroupEgress"])
    assert all(x["Type"] != "AWS::ECS::Service" for x in resources.values())


def test_nitro_provider_uses_ecs_api_flag_and_only_approved_instance_types():
    import pytest
    from scripts.render_confidential_capacity import render_capacity_provider

    payload = render_capacity_provider(
        account="111122223333", tenant="pilot01",
        subnets=["subnet-0123456789abcdef0"], instance_sg="sg-0123456789abcdef0"
    )
    assert payload["cluster"] == "notarai-confidential-pilot01"
    provider = payload["managedInstancesProvider"]
    launch = provider["instanceLaunchTemplate"]
    assert launch["nitroEnclavesEnabled"] is True
    assert launch["capacityOptionType"] == "ON_DEMAND"
    assert launch["instanceRequirements"]["allowedInstanceTypes"] == ["m6i.xlarge"]
    assert launch["ec2InstanceProfileArn"].endswith("/ecsInstanceProfileNotaraiConfidentialpilot01")
    with pytest.raises(ValueError):
        render_capacity_provider(
            account="111122223333", tenant="pilot01",
            subnets=["subnet-0123456789abcdef0"], instance_sg="sg-0123456789abcdef0",
            instance_type="t3.large"
        )
    with pytest.raises(ValueError):
        render_capacity_provider(
            account="111122223333", tenant="demo/../root",
            subnets=["subnet-0123456789abcdef0"], instance_sg="sg-0123456789abcdef0"
        )


def test_pilot_bootstrap_is_dry_run_and_rejects_wrong_account(monkeypatch):
    import pytest
    import scripts.confidential_pilot_bootstrap as pilot

    seen = []

    def fake_cli(args, profile, *, capture=True):
        seen.append(args)
        if args[:2] == ["sts", "get-caller-identity"]:
            return "111122223333"
        if args[:2] == ["cloudformation", "validate-template"]:
            return "{}"
        raise AssertionError("unexpected mutation called during dry run")

    monkeypatch.setattr(pilot, "cli", fake_cli)
    pilot.bootstrap(
        profile="pilot", account="111122223333", tenant="pilot01",
        vpc="vpc-0123456789abcdef0",
        subnets=["subnet-0123456789abcdef0"], apply=False,
    )
    assert len(seen) == 5
    assert not any(x[1] in {"deploy", "create-capacity-provider"} for x in seen)

    seen.clear()
    with pytest.raises(RuntimeError, match="account mismatch"):
        pilot.bootstrap(
            profile="pilot", account="999988887777", tenant="pilot01",
            vpc="vpc-0123456789abcdef0",
            subnets=["subnet-0123456789abcdef0"], apply=True,
        )
    assert len(seen) == 1


def test_policy_generator_matches_cloudformation_guest_runtime():
    """Prevent drift between measured task spec and the actual ECS deployment."""
    from scripts.render_confidential_taskdef import make_task

    image = "111122223333.dkr.ecr.eu-central-1.amazonaws.com/notarai-confidential-pilot01@sha256:" + "f" * 64
    task = make_task(
        account="111122223333", tenant="pilot01", image=image,
        bucket="ntr-cf-pilot01-111122223333-eu-central-1",
        queue="https://sqs.eu-central-1.amazonaws.com/111122223333/notarai-confidential-pilot01.fifo",
    )
    t = template("notarai-confidential-task.yaml")
    c = t["Resources"]["ConfidentialTaskDefinition"]["Properties"]
    assert task["family"] == "notarai-confidential-pilot01"
    assert task["containerDefinitions"][0]["command"] == c["ContainerDefinitions"][0]["Command"]
    assert task["networkMode"] == c["NetworkMode"]
    assert task["requiresCompatibilities"] == c["RequiresCompatibilities"]
    assert task["cpu"] == c["Cpu"]
    assert task["memory"] == c["Memory"]

    observed = task["containerDefinitions"][0]
    expected = c["ContainerDefinitions"][0]
    for py, cfn in (
        ("name", "Name"), ("essential", "Essential"), ("cpu", "Cpu"),
        ("memory", "Memory"), ("user", "User"),
        ("readonlyRootFilesystem", "ReadonlyRootFilesystem"),
    ):
        assert observed[py] == expected[cfn]
    py_linux, aws_linux = observed["linuxParameters"], expected["LinuxParameters"]
    assert py_linux["initProcessEnabled"] == aws_linux["InitProcessEnabled"]
    assert py_linux["sharedMemorySize"] == aws_linux["SharedMemorySize"]
    assert py_linux["tmpfs"][0]["containerPath"] == aws_linux["Tmpfs"][0]["ContainerPath"]
    assert py_linux["tmpfs"][0]["size"] == aws_linux["Tmpfs"][0]["Size"]
    assert py_linux["tmpfs"][0]["mountOptions"] == aws_linux["Tmpfs"][0]["MountOptions"]
    assert [v["name"] for v in observed["environment"]] == [
        v["Name"] for v in expected["Environment"]
    ]
    assert c["TrustedExecutionConfiguration"]["IsolationMode"] == "CONFIDENTIAL_SANDBOX"
