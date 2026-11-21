"""Render an ECS task definition to generate Nitro policy/PCR measurements.

Use with ecs-nitro-sandbox-genpolicy on the final immutable image digest.
This command NEVER calls AWS and never prints secrets or plaintext documents.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

ACCOUNT = re.compile(r"^[0-9]{12}$")
TENANT = re.compile(r"^[a-z0-9]{1,12}$")
IMAGE = re.compile(r"^[0-9]{12}\.dkr\.ecr\.eu-central-1\.amazonaws\.com/notarai-confidential-[a-z0-9]+@sha256:[0-9a-f]{64}$")
KMS = re.compile(r"^arn:aws:kms:eu-central-1:[0-9]{12}:key/[0-9a-zA-Z-]+$")
QUEUE = re.compile(r"^https://sqs\.eu-central-1\.amazonaws\.com/[0-9]{12}/notarai-confidential-[a-z0-9]+\.fifo$")
BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{2,62}$")


def make_task(account: str, tenant: str, image: str, kms_key_arn: str,
              bucket: str, queue: str, shared_image: bool = False) -> dict:
    for pattern, value in (
        (ACCOUNT, account), (TENANT, tenant), (IMAGE, image),
        (KMS, kms_key_arn), (BUCKET, bucket), (QUEUE, queue),
    ):
        if not pattern.fullmatch(value):
            raise ValueError("invalid staging identifier")
    if type(shared_image) is not bool:
        raise ValueError("invalid shared image mode")
    expected_repo = (
        "notarai-confidential-shared" if shared_image
        else f"notarai-confidential-{tenant}"
    )
    if not image.startswith(
        f"{account}.dkr.ecr.eu-central-1.amazonaws.com/{expected_repo}@"
    ):
        raise ValueError("image does not belong to approved tenant or shared repository")
    if not kms_key_arn.startswith(f"arn:aws:kms:eu-central-1:{account}:"):
        raise ValueError("unexpected KMS key account")
    if not queue.startswith(f"https://sqs.eu-central-1.amazonaws.com/{account}/notarai-confidential-{tenant}.fifo"):
        raise ValueError("unexpected queue account or tenant")

    environment = [
        {"name": "NOTARAI_CONFIDENTIAL_REQUIRED", "value": "1"},
        {"name": "NOTARAI_CONFIDENTIAL_TENANT", "value": tenant},
        {"name": "NOTARAI_CONFIDENTIAL_BUCKET", "value": bucket},
        {"name": "NOTARAI_CONFIDENTIAL_QUEUE_URL", "value": queue},
        {"name": "NOTARAI_CONFIDENTIAL_KMS_KEY_ARN", "value": kms_key_arn},
        {"name": "AWS_REGION", "value": "eu-central-1"},
        {"name": "HOME", "value": "/tmp"},
        {"name": "XDG_CACHE_HOME", "value": "/tmp"},
        {"name": "TMPDIR", "value": "/tmp"},
    ]
    return {
        "family": f"notarai-confidential-{tenant}",
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["MANAGED_INSTANCES"],
        "cpu": "2048",
        "memory": "4096",
        "executionRoleArn": f"arn:aws:iam::{account}:role/notarai-confidential-execution-{tenant}",
        "taskRoleArn": f"arn:aws:iam::{account}:role/notarai-confidential-{tenant}",
        "containerDefinitions": [{
            "name": "confidential-browser",
            "image": image,
            "essential": True,
            "cpu": 2048,
            "memory": 4096,
            "user": "10001:10001",
            "readonlyRootFilesystem": True,
            "environment": environment,
            "linuxParameters": {
                "initProcessEnabled": True,
                "sharedMemorySize": 256,
                "tmpfs": [{
                    "containerPath": "/tmp",
                    "size": 512,
                    "mountOptions": ["rw", "nosuid", "nodev"]
                }],
            },
        }],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--kms-key-arn", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--shared-image", action="store_true",
                        help="Use the one regional immutable ECR repository")
    parser.add_argument("--output", type=Path, default=Path("confidential-taskdef.json"))
    args = parser.parse_args()
    task = make_task(
        args.account, args.tenant, args.image, args.kms_key_arn,
        args.bucket, args.queue, shared_image=args.shared_image,
    )
    args.output.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    print("Rendered task definition (contains no document or secret data).")


if __name__ == "__main__":
    main()
