"""Scheduled Lambda entry point for the shared endpoint switch.

Disabled by default. Logs only a fixed state word: no queue names, tenants,
identifiers or AWS error text.
"""
from __future__ import annotations

import os

from confidential.fabric_scaler import ScalerConfig, scale_once


def handler(event, context):
    if os.getenv("NOTARAI_FABRIC_SCALER_ENABLED") != "true":
        return {"state": "disabled"}
    if not isinstance(event, dict) or event.get("source") != "notarai.confidential.fabric":
        return {"state": "ignored"}
    import boto3

    tenants = tuple(
        t for t in os.environ.get("NOTARAI_TENANTS", "").split(",") if t
    )
    config = ScalerConfig(
        account=os.environ["NOTARAI_ACCOUNT"],
        tenants=tenants,
        min_on_seconds=int(os.environ.get("NOTARAI_MIN_ON_SECONDS", "3000")),
    )
    session = boto3.session.Session(region_name="eu-central-1")
    try:
        state = scale_once(
            config,
            sqs=session.client("sqs"),
            ecs=session.client("ecs"),
            cloudformation=session.client("cloudformation"),
        )
    except Exception:
        print("notarai-confidential-fabric: check failed, nothing changed")
        raise RuntimeError("confidential fabric switch made no change") from None
    print("notarai-confidential-fabric: " + state)
    return {"state": state}
