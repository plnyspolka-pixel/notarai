"""Offline generator: ONE shared Nitro capacity provider for all tenants.

Never creates AWS resources. Each kancelaria still has an independent
CONFIDENTIAL_SANDBOX task definition + IAM role + KMS policy + FIFO queue.
No tenant identifier is accepted for the shared provider.

Example:
  python scripts/render_confidential_shared_capacity.py --account 123456789012 \
    --subnet subnet-0123456789abcdef0 \
    --security-group sg-0123456789abcdef0 \
    --output /tmp/notarai-shared-capacity.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.render_confidential_capacity import _INSTANCE_SHAPES

ACCOUNT = re.compile(r"^[0-9]{12}$")
SUBNET = re.compile(r"^subnet-(?:[0-9a-f]{8}|[0-9a-f]{17})$")
SG = re.compile(r"^sg-(?:[0-9a-f]{8}|[0-9a-f]{17})$")
SHARED = "notarai-confidential-shared"


def shared_capacity(
    *, account: str, subnets: list[str], security_group: str,
    instance_type: str = "m6i.xlarge",
) -> dict:
    if not isinstance(account, str) or not ACCOUNT.fullmatch(account):
        raise ValueError("invalid AWS account")
    if (not isinstance(subnets, list) or not (1 <= len(subnets) <= 2)
            or len(set(subnets)) != len(subnets)
            or any(not isinstance(s, str) or not SUBNET.fullmatch(s) for s in subnets)):
        raise ValueError("one or two distinct private subnets required")
    if not isinstance(security_group, str) or not SG.fullmatch(security_group):
        raise ValueError("unverified shared runtime security group")
    if instance_type not in _INSTANCE_SHAPES:
        raise ValueError("unsupported Nitro instance")
    cpu, ram = _INSTANCE_SHAPES[instance_type]
    return {
        "name": SHARED,
        "cluster": SHARED,
        "managedInstancesProvider": {
            "infrastructureRoleArn":
                f"arn:aws:iam::{account}:role/notarai-confidential-shared-infra",
            "instanceLaunchTemplate": {
                "ec2InstanceProfileArn":
                    f"arn:aws:iam::{account}:instance-profile/"
                    "ecsInstanceProfileNotaraiConfidentialShared",
                "networkConfiguration": {
                    "subnets": subnets,
                    "securityGroups": [security_group],
                },
                "storageConfiguration": {"storageSizeGiB": 40},
                "instanceRequirements": {
                    "vCpuCount": {"min": cpu, "max": cpu},
                    "memoryMiB": {"min": ram, "max": ram},
                    "allowedInstanceTypes": [instance_type],
                    "bareMetal": "excluded",
                    "burstablePerformance": "excluded",
                },
                "capacityOptionType": "ON_DEMAND",
                "nitroEnclavesEnabled": True,
            },
            "propagateTags": "NONE",
        },
        "tags": [
            {"key": "project", "value": "notarai"},
            {"key": "network", "value": "regional-shared-endpoints"},
            {"key": "environment", "value": "synthetic-until-hardware-attested"},
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--subnet", action="append", required=True)
    parser.add_argument("--security-group", required=True)
    parser.add_argument("--instance-type", choices=sorted(_INSTANCE_SHAPES),
                        default="m6i.xlarge")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.output.parent.exists():
        raise ValueError("output directory unavailable")
    config = shared_capacity(
        account=args.account, subnets=args.subnet,
        security_group=args.security_group, instance_type=args.instance_type,
    )
    args.output.write_text(json.dumps(config, indent=2)+"\n", encoding="utf-8")
    print("Shared Nitro capacity JSON generated: NO AWS operation performed.")


if __name__ == "__main__":
    main()
