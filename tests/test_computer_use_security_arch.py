"""Static security gates for CloudFormation before live AWS validation."""
from pathlib import Path
import yaml


def load(path):
    return yaml.safe_load((Path(__file__).resolve().parents[1]/"infra"/path).read_text("utf-8"))


def test_shared_metadata_and_settings_are_independent():
    c=load("notarai-ve-control-plane.yaml")["Resources"]
    assert c["JobsTable"]["Type"]=="AWS::DynamoDB::Table"
    assert c["SettingsTable"]["Type"]=="AWS::DynamoDB::Table"
    for name in ("JobsTable","SettingsTable","TenantsTable"):
        assert c[name]["Properties"]["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"]
        assert c[name]["Properties"]["SSESpecification"]["SSEEnabled"]


def test_cross_tenant_access_blocked_by_aws_iam():
    c=load("notarai-ve-tenant.yaml")["Resources"]
    for role in ("TenantRobotRole","TenantControllerRole"):
        policy=c[role]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        for s in policy:
            if s["Sid"]=="TenantJobPartitionOnly":
                cond=s["Condition"]["ForAllValues:StringEquals"]["dynamodb:LeadingKeys"]
                assert cond==[{"Fn::Sub":"TENANT#${TenantTechnicalId}"}]
    worker=c["TenantRobotRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    settings=next(s for s in worker if s["Sid"]=="ReadTenantSettingsOnly")
    assert settings["Action"]==["dynamodb:GetItem"]
    assert "dynamodb:UpdateItem" not in settings["Action"]


def test_one_tenant_one_queue_one_key_one_vm_and_no_public_rdp():
    c=load("notarai-ve-tenant.yaml")["Resources"]
    queue=c["TenantJobQueue"]["Properties"]
    assert queue["FifoQueue"] and queue["SqsManagedSseEnabled"]
    assert queue["RedrivePolicy"]["maxReceiveCount"]==3
    assert c["TenantPayloadKey"]["Properties"]["EnableKeyRotation"]
    vm=c["TenantWindowsVM"]["Properties"]
    assert vm["NetworkInterfaces"][0]["AssociatePublicIpAddress"] is False
    assert vm["BlockDeviceMappings"][0]["Ebs"]["Encrypted"] is True
    assert vm["MetadataOptions"]["HttpTokens"]=="required"
    sg=c["TenantRobotSG"]["Properties"]
    assert "SecurityGroupIngress" not in sg
    assert all(r["ToPort"]==443 and r["FromPort"]==443 for r in sg["SecurityGroupEgress"])


def test_payloads_are_denied_without_sse_kms():
    c=load("notarai-ve-control-plane.yaml")["Resources"]
    policy=c["PayloadBucketPolicy"]["Properties"]["PolicyDocument"]["Statement"]
    must=next(s for s in policy if s["Sid"]=="DenyUnencryptedObjectWrite")
    assert must["Condition"]["StringNotEquals"]["s3:x-amz-server-side-encryption"]=="aws:kms"
    assert c["PayloadBucket"]["Properties"]["PublicAccessBlockConfiguration"]["BlockPublicPolicy"]
