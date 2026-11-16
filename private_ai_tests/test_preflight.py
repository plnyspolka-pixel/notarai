"""Threat-driven EU residency and AWS route checks without credentials."""
import unittest
from private_ai.preflight import PreflightDenied, verify_bedrock_profile, verify_subnets, verify_route_tables

MODEL = "eu.anthropic.claude-opus-4-6-v1"


class PreflightTests(unittest.TestCase):
    def profile(self, regions):
        return {"status": "ACTIVE", "inferenceProfileId": MODEL,
                "models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/claude"} for r in regions]}

    def test_eu_only_is_valid(self):
        self.assertEqual(verify_bedrock_profile(self.profile(["eu-central-1", "eu-west-1"]), MODEL)["eu_destinations"],
                         ["eu-central-1", "eu-west-1"])

    def test_uk_is_not_eu(self):
        with self.assertRaises(PreflightDenied):
            verify_bedrock_profile(self.profile(["eu-central-1", "eu-west-2"]), MODEL)

    def test_switzerland_is_not_eu(self):
        with self.assertRaises(PreflightDenied):
            verify_bedrock_profile(self.profile(["eu-central-2"]), MODEL)

    def test_empty_profile_denied(self):
        with self.assertRaises(PreflightDenied):
            verify_bedrock_profile(self.profile([]), MODEL)

    def test_global_profile_denied(self):
        with self.assertRaises(PreflightDenied):
            verify_bedrock_profile(self.profile(["eu-central-1"]), "global.some-model")

    def test_two_private_subnets(self):
        subnets = [
            {"VpcId": "vpc-1", "AvailabilityZone": az, "MapPublicIpOnLaunch": False, "State": "available"}
            for az in ("eu-central-1a", "eu-central-1b")
        ]
        self.assertEqual(verify_subnets(subnets, "vpc-1")["subnets"], 2)
        subnets[0]["MapPublicIpOnLaunch"] = True
        with self.assertRaises(PreflightDenied):
            verify_subnets(subnets, "vpc-1")

    def test_route_must_be_private_and_explicitly_associated(self):
        table = {"Associations": [
            {"SubnetId": "subnet-1", "AssociationState": {"State": "associated"}},
            {"SubnetId": "subnet-2", "AssociationState": {"State": "associated"}}],
            "Routes": [{"GatewayId": "local"}]}
        self.assertEqual(verify_route_tables([table], ["subnet-1", "subnet-2"])["associated_subnets"], 2)
        table["Routes"].append({"GatewayId": "nat-123", "DestinationCidrBlock": "0.0.0.0/0"})
        with self.assertRaises(PreflightDenied):
            verify_route_tables([table], ["subnet-1", "subnet-2"])
