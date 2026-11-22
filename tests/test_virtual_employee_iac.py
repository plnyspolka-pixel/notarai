"""Offline invariant tests for NotarAI Virtual Employee pilot (no AWS calls)."""
from pathlib import Path
import yaml

PATH = Path(__file__).resolve().parents[1] / "infra" / "virtual-employee" / "notarai-virtual-employee-pilot.yaml"

class Loader(yaml.SafeLoader):
    pass

def intrinsic(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    return {tag_suffix: loader.construct_mapping(node)}

Loader.add_multi_constructor("!", intrinsic)
TEMPLATE = yaml.load(PATH.read_text(encoding="utf-8"), Loader=Loader)
RESOURCES = TEMPLATE["Resources"]

def props(name):
    return RESOURCES[name]["Properties"]

def test_no_public_network_and_no_port_ingress():
    types = {r["Type"] for r in RESOURCES.values()}
    for forbidden in ("AWS::EC2::InternetGateway", "AWS::EC2::NatGateway", "AWS::EC2::EIP", "AWS::EC2::Route"):
        assert forbidden not in types
    assert props("PilotSubnet")["MapPublicIpOnLaunch"] is False
    assert "SecurityGroupIngress" not in props("WindowsSecurityGroup")
    assert props("WindowsSecurityGroup")["SecurityGroupEgress"] == [
        {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
         "DestinationSecurityGroupId": {"GetAtt": "EndpointSecurityGroup.GroupId"},
         "Description": "Only SSM PrivateLink endpoints"}]

def test_ssm_only_role_and_private_endpoints():
    role = props("WindowsRole")
    assert role["ManagedPolicyArns"] == ["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"]
    endpoints = [name for name, r in RESOURCES.items() if r["Type"] == "AWS::EC2::VPCEndpoint"]
    assert set(endpoints) == {"SsmEndpoint", "SsmMessagesEndpoint", "Ec2MessagesEndpoint"}
    assert RESOURCES["Ec2MessagesEndpoint"]["Condition"] == "EnableLegacyMessages"
    assert TEMPLATE["Parameters"]["LegacyEc2Messages"]["Default"] == "false"
    for name in endpoints:
        p = props(name)
        assert p["PrivateDnsEnabled"] is True
        assert p["VpcEndpointType"] == "Interface"
        assert p["SubnetIds"] == [{"Ref": "PilotSubnet"}]

def test_windows_encrypted_imdsv2_private():
    vm = props("WindowsInstance")
    assert vm["MetadataOptions"]["HttpTokens"] == "required"
    assert vm["MetadataOptions"]["HttpPutResponseHopLimit"] == 1
    assert vm["SubnetId"] == {"Ref": "PilotSubnet"}
    assert vm["IamInstanceProfile"] == {"Ref": "WindowsInstanceProfile"}
    ebs = vm["BlockDeviceMappings"][0]["Ebs"]
    assert ebs["Encrypted"] is True and ebs["DeleteOnTermination"] is True
    assert "NetworkInterfaces" not in vm

def test_bootstrap_no_secrets_or_antivirus_bypass():
    userdata = str(props("WindowsInstance")["UserData"]).lower()
    for forbidden in ("pesel", "privatekey", "password=", "secret=", "set-mppreference",
                      "disableantispyware", "rejnet.exe", "invoke-webrequest"):
        assert forbidden not in userdata
