"""Build a staging-only ECS Managed Instances capacity-provider CLI request.

The current CloudFormation InstanceLaunchTemplate resource (November 2026)
does not expose NitroEnclavesEnabled; the ECS CreateCapacityProvider API does.
This script does NOT call AWS. Review generated JSON before any cloud changes.

Usage:
 python scripts/render_confidential_capacity.py --tenant pilot01 \
   --account 123456789012 --subnet subnet-0aaaabbbb11112222 \
   --instance-sg sg-0aaaabbbb11112222 --output /tmp/pilot-capacity.json
 aws ecs create-capacity-provider --cli-input-json file:///tmp/pilot-capacity.json \
   --region eu-central-1 --profile notarai-admin
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_TENANT = re.compile(r"[a-z0-9]{1,12}")
_ACCOUNT = re.compile(r"\d{12}")
_SUBNET = re.compile(r"subnet-(?:[0-9a-f]{8}|[0-9a-f]{17})")
_SG = re.compile(r"sg-(?:[0-9a-f]{8}|[0-9a-f]{17})")
# ECS CreateCapacityProvider wymaga vCpuCount i memoryMiB w instanceRequirements
# (pola required w modelu API); allowedInstanceTypes tylko zaweza wybor.
# Wartosci = dokladny rozmiar typu, zeby zakres nie dopuscil niczego innego.
_INSTANCE_SHAPES = {
    "m6i.xlarge": (4, 16384),
    "m6i.2xlarge": (8, 32768),
    "c6i.2xlarge": (8, 16384),
}
_ALLOWED_INSTANCE_TYPES = set(_INSTANCE_SHAPES)


def render_capacity_provider(
    *, tenant: str, account: str, subnets: list[str], instance_sg: str,
    instance_type: str = "m6i.xlarge",
) -> dict:
    if not _TENANT.fullmatch(tenant) or not _ACCOUNT.fullmatch(account):
        raise ValueError("invalid pilot tenant or AWS account")
    if len(subnets) not in (1, 2, 3) or len(set(subnets)) != len(subnets) or any(
        not _SUBNET.fullmatch(x) for x in subnets
    ):
        raise ValueError("expected one to three distinct VPC subnet IDs")
    if not _SG.fullmatch(instance_sg):
        raise ValueError("invalid security group ID")
    if instance_type not in _ALLOWED_INSTANCE_TYPES:
        raise ValueError("instance type outside audited Nitro Sandbox allowlist")
    vcpus, memory_mib = _INSTANCE_SHAPES[instance_type]
    suffix = f"notarai-confidential-{tenant}"
    return {
        "name": suffix,
        "cluster": suffix,
        "managedInstancesProvider": {
            "infrastructureRoleArn": f"arn:aws:iam::{account}:role/notarai-confidential-infra-{tenant}",
            "instanceLaunchTemplate": {
                "ec2InstanceProfileArn": f"arn:aws:iam::{account}:instance-profile/ecsInstanceProfileNotaraiConfidential{tenant}",
                "networkConfiguration": {
                    "subnets": subnets,
                    "securityGroups": [instance_sg],
                },
                "storageConfiguration": {"storageSizeGiB": 40},
                "instanceRequirements": {
                    "vCpuCount": {"min": vcpus, "max": vcpus},
                    "memoryMiB": {"min": memory_mib, "max": memory_mib},
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
            {"key": "environment", "value": "synthetic-pilot"},
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--subnet", action="append", required=True,
                        help="Repeat once per subnet; must all belong to pilot VPC")
    parser.add_argument("--instance-sg", required=True)
    parser.add_argument("--instance-type", default="m6i.xlarge",
                        choices=sorted(_ALLOWED_INSTANCE_TYPES))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = render_capacity_provider(
        tenant=args.tenant, account=args.account, subnets=args.subnet,
        instance_sg=args.instance_sg, instance_type=args.instance_type,
    )
    args.output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("Generated ECS capacity-provider request. No AWS resources were changed.")


if __name__ == "__main__":
    main()
