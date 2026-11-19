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
    assert any("kms:Decrypt" == s.get("Action") and "kms:RecipientAttestation:PCR17" in
               s["Condition"]["StringEqualsIgnoreCase"] for s in statements)
