"""SEC-08 synthetic S3/DynamoDB endpoint policy perimeter.

Gateway prefix-list routes without endpoint policies allow presigned URL
access to third-party AWS buckets. These tests are static; real traffic
and effective IAM need independent validation.
"""
import copy

import pytest

from test_confidential_infra import template


def _sub(s):
    return {"Sub": s}


def _expected_s3():
    worker = _sub("arn:aws:iam::${AWS::AccountId}:role/notarai-confidential-${TenantId}")
    return [
        {
            "Sid": "WorkerCiphertextReadOnly", "Effect": "Allow",
            "Principal": {"AWS": worker},
            "Action": "s3:GetObject",
            "Resource": _sub(
                "arn:aws:s3:::${EncryptedBucketName}/kancelarie/${TenantId}/confidential/*"
            ),
        },
        {
            "Sid": "WorkerMetadataResultOnly", "Effect": "Allow",
            "Principal": {"AWS": worker},
            "Action": "s3:PutObject",
            "Resource": _sub(
                "arn:aws:s3:::${EncryptedBucketName}/kancelarie/${TenantId}/confidential-results/*"
            ),
        },
        {
            "Sid": "EcrLayerDownloadOnly", "Effect": "Allow",
            "Principal": {"AWS": _sub(
                "arn:aws:iam::${AWS::AccountId}:role/notarai-confidential-execution-${TenantId}"
            )},
            "Action": "s3:GetObject",
            "Resource": _sub("arn:aws:s3:::prod-${AWS::Region}-starport-layer-bucket/*"),
        },
    ]


def _expected_ddb():
    return [{
        "Sid": "WorkerLedgerOnly", "Effect": "Allow",
        "Principal": {"AWS": _sub(
            "arn:aws:iam::${AWS::AccountId}:role/notarai-confidential-${TenantId}"
        )},
        "Action": ["dynamodb:GetItem", "dynamodb:UpdateItem"],
        "Resource": _sub(
            "arn:aws:dynamodb:eu-central-1:${AWS::AccountId}:table/notarai-confidential-jobs-${TenantId}"
        ),
    }]


def check_policy(document):
    params = document["Parameters"]
    assert "EncryptedBucketName" in params
    assert "Default" not in params["EncryptedBucketName"]
    resources = document["Resources"]
    for name, actions in (("S3GatewayEndpoint", _expected_s3()),
                          ("DynamoDbGatewayEndpoint", _expected_ddb())):
        endpoint = resources[name]
        assert endpoint["Type"] == "AWS::EC2::VPCEndpoint"
        p = endpoint["Properties"]
        assert p["VpcEndpointType"] == "Gateway"
        assert p["RouteTableIds"] == [{"Ref": "PilotRouteTableId"}]
        policy = p["PolicyDocument"]
        assert set(policy) == {"Version", "Statement"}
        assert policy["Version"] == "2012-10-17"
        assert policy["Statement"] == actions


def test_gateway_endpoint_policy_exact_roles_resources_and_actions():
    check_policy(template("notarai-confidential-private-egress.yaml"))


@pytest.mark.parametrize("mutation", [
    lambda p: p["Resources"]["S3GatewayEndpoint"]["Properties"].pop("PolicyDocument"),
    lambda p: p["Resources"]["S3GatewayEndpoint"]["Properties"]["PolicyDocument"]["Statement"][0].update(
        Principal="*"),
    lambda p: p["Resources"]["S3GatewayEndpoint"]["Properties"]["PolicyDocument"]["Statement"][0].update(
        Resource="*"),
    lambda p: p["Resources"]["S3GatewayEndpoint"]["Properties"]["PolicyDocument"]["Statement"][1].update(
        Action="s3:*"),
    lambda p: p["Resources"]["S3GatewayEndpoint"]["Properties"]["PolicyDocument"]["Statement"][2].update(
        Action="s3:PutObject"),
    lambda p: p["Resources"]["S3GatewayEndpoint"]["Properties"]["PolicyDocument"]["Statement"][2].update(
        Resource=_sub("arn:aws:s3:::*")),
    lambda p: p["Resources"]["DynamoDbGatewayEndpoint"]["Properties"]["PolicyDocument"]["Statement"][0].update(
        Principal="*"),
    lambda p: p["Resources"]["DynamoDbGatewayEndpoint"]["Properties"]["PolicyDocument"]["Statement"][0].update(
        Resource="*"),
    lambda p: p["Resources"]["DynamoDbGatewayEndpoint"]["Properties"]["PolicyDocument"]["Statement"][0].update(
        Action=["dynamodb:*"]),
    lambda p: p["Resources"]["DynamoDbGatewayEndpoint"]["Properties"].pop("PolicyDocument"),
])
def test_gateway_policy_broadening_is_detected(mutation):
    document = copy.deepcopy(template("notarai-confidential-private-egress.yaml"))
    mutation(document)
    with pytest.raises((AssertionError, KeyError)):
        check_policy(document)
