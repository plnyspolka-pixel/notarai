"""Static regression on AWS staging control boundaries; no account/credentials."""
from pathlib import Path
import re
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / "infra" / "private-ai-pilot.yaml"


class CloudBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TEMPLATE.read_text(encoding="utf-8")

    def test_no_empty_egress_that_triggers_aws_allow_all(self):
        self.assertNotIn("SecurityGroupEgress: []", self.source)
        self.assertNotRegex(self.source, r"CidrIp:\s*(0\.0\.0\.0/0|::/0)")
        self.assertIn("DestinationSecurityGroupId: !GetAtt BedrockSG.GroupId", self.source)
        self.assertIn("DestinationPrefixListId: !Ref S3PrefixListId", self.source)

    def test_iam_only_and_source_endpoint(self):
        self.assertIn("AuthorizationType: AWS_IAM", self.source)
        self.assertIn('"aws:SourceVpce": !Ref BedrockEndpoint', self.source)
        self.assertIn('"aws:SourceVpce": !Ref AuditS3Endpoint', self.source)
        self.assertIn("VpcConfig:", self.source)
        self.assertIn("PrivateSubnetIds", self.source)

    def test_synthetic_fixture_and_immutable_audit(self):
        self.assertIn("PRIVATE_AI_FIXTURE_SHA256: !Ref FixtureSha256", self.source)
        self.assertIn("ObjectLockEnabled: true", self.source)
        self.assertIn("Mode: COMPLIANCE", self.source)
        self.assertIn("DeletionPolicy: Retain", self.source)
        self.assertIn("PublicAccessBlockConfiguration:", self.source)

    def test_template_has_no_auto_deploy_workflow(self):
        # AutoDeploy on API Gateway stage is not a GitHub auto-deploy.
        self.assertIn("SYNTHETIC STAGING ONLY", self.source)
        self.assertNotIn("AWS::ECS::Service", self.source)
        self.assertNotIn("AWS::EC2::Instance", self.source)
