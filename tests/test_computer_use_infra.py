"""Static baseline test only: does NOT deploy AWS resources."""
from pathlib import Path

import yaml


def template():
    path = Path(__file__).resolve().parents[1] / 'infra' / 'notarai-universal-worker-vm.yaml'
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def test_private_network_no_rdp():
    t = template()
    sg = t['Resources']['RobotSecurityGroup']['Properties']
    assert 'SecurityGroupIngress' not in sg
    assert all(r['ToPort'] == 443 and r['FromPort'] == 443 for r in sg['SecurityGroupEgress'])
    vm = t['Resources']['RobotVm']['Properties']
    assert vm['NetworkInterfaces'][0]['AssociatePublicIpAddress'] is False
    assert vm['MetadataOptions']['HttpTokens'] == 'required'


def test_disk_encrypted_and_technical_tenant_name_only():
    t = template()
    vm = t['Resources']['RobotVm']['Properties']
    assert all(x['Ebs']['Encrypted'] for x in vm['BlockDeviceMappings'])
    assert all(x['Ebs']['KmsKeyId']['Ref'] == 'EbsKmsKeyArn' for x in vm['BlockDeviceMappings'])
    assert t['Parameters']['TenantTechnicalId']['AllowedPattern'] == '[a-zA-Z0-9_-]+'


def test_only_ssm_instance_role():
    t = template()
    role = t['Resources']['RobotRole']['Properties']
    assert role['ManagedPolicyArns'] == ['arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore']
    assert 'Policies' not in role
