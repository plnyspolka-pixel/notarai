"""Scheduled AWS Lambda entry point for a SINGLE preview-only Nitro worker.

Deployment is deliberately disabled by default. Only synthetic pilot data.
No SQS receipt is consumed here and no client data is ever logged.
"""
from __future__ import annotations

import os

from confidential.dispatch import DispatcherConfig, dispatch_once
from confidential.release_enforcement import LiveReleaseGate, assume_custody_readonly


def handler(event, context):
    if os.getenv("NOTARAI_DISPATCH_ENABLED") != "true":
        return {"state": "disabled"}
    if not isinstance(event, dict) or event.get("source") != "notarai.confidential.tick":
        return {"state": "ignored"}
    import boto3

    # Scheduled launches have no legacy/same-account demo KMS fallback.
    # No operator-controlled flag may turn off signed custody enforcement.
    if os.environ.get("NOTARAI_SHARED_POOL") != "true":
        raise RuntimeError("independent custody requires shared compute")
    config = DispatcherConfig(
        account=os.environ["NOTARAI_ACCOUNT"],
        tenant=os.environ["NOTARAI_TENANT"],
        cluster=os.environ["NOTARAI_CLUSTER"],
        capacity_provider=os.environ["NOTARAI_CAPACITY_PROVIDER"],
        task_definition_arn=os.environ["NOTARAI_TASK_DEFINITION_ARN"],
        queue_url=os.environ["NOTARAI_WORK_QUEUE_URL"],
        subnet=os.environ["NOTARAI_PRIVATE_SUBNET"],
        security_group=os.environ["NOTARAI_INSTANCE_SECURITY_GROUP"],
        lease_table=os.environ["NOTARAI_LEASE_TABLE"],
        shared_pool=True,
        external_custody_key_arn=os.environ["NOTARAI_CUSTODY_KMS_KEY_ARN"],
    )
    session = boto3.session.Session(region_name="eu-central-1")
    try:
        sts = session.client("sts")
        release_gate = LiveReleaseGate(
            config=config, workload_sts=sts, ecs=session.client("ecs"),
            assume_custody=lambda role: assume_custody_readonly(sts, role),
            custody_account=os.environ["NOTARAI_CUSTODY_ACCOUNT"],
            custody_audit_role_arn=os.environ["NOTARAI_CUSTODY_AUDIT_ROLE_ARN"],
            kms_key_arn=os.environ["NOTARAI_CUSTODY_KMS_KEY_ARN"],
            signing_key_arn=os.environ["NOTARAI_CUSTODY_SIGNING_KEY_ARN"],
            approved_pcr17=os.environ["NOTARAI_APPROVED_PCR17"],
            approved_image_sha256=os.environ["NOTARAI_APPROVED_IMAGE_SHA256"],
            pinned_signer_sha256=os.environ["NOTARAI_CUSTODY_SIGNER_FINGERPRINT"],
            release_bucket=os.environ["NOTARAI_CUSTODY_RELEASE_BUCKET"],
            release_key=os.environ["NOTARAI_CUSTODY_RELEASE_KEY"],
            release_version=os.environ["NOTARAI_CUSTODY_RELEASE_VERSION"],
        )
        state = dispatch_once(
            config,
            sqs=session.client("sqs"),
            ecs=session.client("ecs"),
            dynamodb=session.client("dynamodb"),
            release_gate=release_gate,
        )
    except Exception:
        # Avoid logging exception text (request/queue identifiers).
        print("notarai-confidential-dispatch: configuration or AWS check failed")
        raise RuntimeError("confidential scheduler denied launch") from None
    print("notarai-confidential-dispatch: " + state)
    return {"state": state}
