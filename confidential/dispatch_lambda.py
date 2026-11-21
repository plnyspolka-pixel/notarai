"""Scheduled AWS Lambda entry point for a SINGLE preview-only Nitro worker.

Deployment is deliberately disabled by default. Only synthetic pilot data.
No SQS receipt is consumed here and no client data is ever logged.
"""
from __future__ import annotations

import os

from confidential.dispatch import DispatcherConfig, dispatch_once


def handler(event, context):
    if os.getenv("NOTARAI_DISPATCH_ENABLED") != "true":
        return {"state": "disabled"}
    if not isinstance(event, dict) or event.get("source") != "notarai.confidential.tick":
        return {"state": "ignored"}
    import boto3

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
    )
    session = boto3.session.Session(region_name="eu-central-1")
    try:
        state = dispatch_once(
            config,
            sqs=session.client("sqs"),
            ecs=session.client("ecs"),
            dynamodb=session.client("dynamodb"),
        )
    except Exception:
        # Avoid logging exception text (request/queue identifiers).
        print("notarai-confidential-dispatch: configuration or AWS check failed")
        raise RuntimeError("confidential scheduler denied launch") from None
    print("notarai-confidential-dispatch: " + state)
    return {"state": state}
