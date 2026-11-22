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
    assert bucket["VersioningConfiguration"]["Status"] == "Enabled"
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
    assert any("kms:Decrypt" == s.get("Action") and "kms:RecipientAttestation:PCR17" in
               s["Condition"]["StringEqualsIgnoreCase"] for s in statements)


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
    # Model API ECS: vCpuCount i memoryMiB sa wymagane, bez nich AWS CLI
    # odrzuca zadanie jeszcze przed wyslaniem (walidacja parametrow).
    assert launch["instanceRequirements"]["vCpuCount"] == {"min": 4, "max": 4}
    assert launch["instanceRequirements"]["memoryMiB"] == {"min": 16384, "max": 16384}
    bigger = render_capacity_provider(
        account="111122223333", tenant="pilot01",
        subnets=["subnet-0123456789abcdef0"], instance_sg="sg-0123456789abcdef0",
        instance_type="c6i.2xlarge",
    )["managedInstancesProvider"]["instanceLaunchTemplate"]["instanceRequirements"]
    assert bigger["vCpuCount"] == {"min": 8, "max": 8}
    assert bigger["memoryMiB"] == {"min": 16384, "max": 16384}
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
        kms_key_arn="arn:aws:kms:eu-central-1:111122223333:key/12345678-abcd",
        bucket="ntr-cf-pilot01-111122223333-eu-central-1",
        queue="https://sqs.eu-central-1.amazonaws.com/111122223333/notarai-confidential-pilot01.fifo",
    )
    t = template("notarai-confidential-task.yaml")
    c = t["Resources"]["ConfidentialTaskDefinition"]["Properties"]
    assert task["family"] == "notarai-confidential-pilot01"
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


def test_persistent_preview_ledger_and_guest_dynamodb_permissions_are_scoped():
    t = template("notarai-confidential-job-ledger.yaml")
    resource = t["Resources"]["PreviewJobs"]
    assert resource["Type"] == "AWS::DynamoDB::Table"
    assert resource["DeletionPolicy"] == "Retain"
    assert resource["Properties"]["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"]
    assert resource["Properties"]["SSESpecification"]["SSEEnabled"]
    assert "AWS::IAM::Role" not in {v["Type"] for v in t["Resources"].values()}
    task = template("notarai-confidential-task.yaml")
    role = task["Resources"]["ConfidentialTaskRole"]["Properties"]
    statements = role["Policies"][0]["PolicyDocument"]["Statement"]
    ledger_rule = [
        item for item in statements
        if "dynamodb:UpdateItem" in item.get("Action", [])
    ]
    assert len(ledger_rule) == 1
    assert set(ledger_rule[0]["Action"]) == {
        "dynamodb:GetItem", "dynamodb:UpdateItem"
    }
    assert ledger_rule[0]["Resource"]["Sub"].endswith(
        "/notarai-confidential-jobs-${TenantId}"
    )
    assert not any("dynamodb:PutItem" in x.get("Action", [])
                   for x in statements)


def test_broad_egress_bootstrap_apply_is_disabled(monkeypatch):
    import scripts.confidential_pilot_bootstrap as pilot
    import pytest

    calls = []
    def fake_cli(args, profile, *, capture=True):
        calls.append(args)
        if args[:2] == ["sts", "get-caller-identity"]:
            return "111122223333"
        if args[:2] == ["cloudformation", "validate-template"]:
            return "{}"
        raise AssertionError("AWS write unexpectedly attempted")
    monkeypatch.setattr(pilot, "cli", fake_cli)
    with pytest.raises(RuntimeError, match="insecure broad-egress bootstrap"):
        pilot.bootstrap(
            profile="pilot", account="111122223333", tenant="pilot01",
            vpc="vpc-0123456789abcdef0",
            subnets=["subnet-0123456789abcdef0"], apply=True,
        )
    assert len(calls) == 5
    assert not any(a[1] in ("deploy", "create-capacity-provider")
                   for a in calls)


def test_github_image_role_can_only_push_to_pilot_ecr_from_one_branch():
    doc = template("notarai-confidential-github.yaml")
    assert set(doc["Resources"]) == {"GuestImagePushRole"}
    role = doc["Resources"]["GuestImagePushRole"]["Properties"]
    assert "ManagedPolicyArns" not in role
    trust = role["AssumeRolePolicyDocument"]["Statement"]
    assert len(trust) == 1 and trust[0]["Action"] == "sts:AssumeRoleWithWebIdentity"
    condition = trust[0]["Condition"]
    assert set(condition) == {"StringEquals"}  # no StringLike wildcards
    assert condition["StringEquals"]["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    sub = condition["StringEquals"]["token.actions.githubusercontent.com:sub"]["Sub"]
    assert sub == "repo:${Repository}:ref:refs/heads/${Branch}"
    assert "*" not in doc["Parameters"]["Branch"]["AllowedPattern"].replace("]{1,200}", "")
    statements = role["Policies"][0]["PolicyDocument"]["Statement"]
    for statement in statements:
        actions = statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
        assert all(action.startswith("ecr:") for action in actions)
        assert not any("Delete" in action or "Policy" in action for action in actions)
        if statement["Resource"] == "*":
            assert actions == ["ecr:GetAuthorizationToken"]
        else:
            # Exactly one repository per deployment: shared OR the tenant one.
            flag, shared, tenant = statement["Resource"]["If"]
            assert flag == "PushToShared"
            assert shared["Sub"].endswith(":repository/notarai-confidential-shared")
            assert tenant["Sub"].endswith(":repository/notarai-confidential-${TenantId}")
            assert "*" not in shared["Sub"] and "*" not in tenant["Sub"]
    assert doc["Parameters"]["ImageRepository"]["AllowedValues"] == ["tenant", "shared"]
    assert doc["Conditions"] == {
        "PushToShared": {"Equals": [{"Ref": "ImageRepository"}, "shared"]}}


def test_guest_image_workflow_pushes_only_from_pilot_branch_after_smoke():
    text = (ROOT.parent / ".github" / "workflows" / "confidential-image.yml").read_text("utf-8")
    workflow = yaml.safe_load(text)
    triggers = workflow[True] if True in workflow else workflow["on"]
    assert set(triggers) == {"push"}
    assert triggers["push"]["branches"] == ["claude/shared-fabric-aws-pilot-20261122"]
    assert "ECR_REPOSITORY: notarai-confidential-shared" in text
    assert "notarai-confidential-pilot01\n" not in text.replace("image-pilot01", "")
    assert "notarai-confidential-github-image-pilot01" in text
    assert "notarai-github-wdrozenie" not in text
    assert "get-secret-value" not in text
    assert text.index("confidential.demo_browser") < text.index("docker push")
    assert text.index("confidential.worker") < text.index("docker push")


def test_guest_image_workflow_verifies_aws_generator_signature_before_running_it():
    text = (ROOT.parent / ".github" / "workflows" / "confidential-image.yml").read_text("utf-8")
    assert "d1uvmbvklg8rt.cloudfront.net/${GENPOLICY_VERSION}/x86_64" in text
    assert "/latest/" not in text  # pinned release, not a moving target
    verify = text.index("openssl dgst -sha384 -verify")
    checksum = text.index("sha256sum -c")
    first_run = text.index("bin/ecs-nitro-sandbox-genpolicy --version")
    assert verify < checksum < first_run
    assert "--skip-image-fetch" not in text and "--allow-unpinned-identity" not in text
    assert "--allow-additional-env" not in text and "--allow-exec-command" not in text
    key = (ROOT / "nitro-sandboxes-runtime-v1.pub").read_text("utf-8")
    assert key.startswith("-----BEGIN PUBLIC KEY-----")
