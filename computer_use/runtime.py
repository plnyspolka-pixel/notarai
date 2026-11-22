"""Standalone tenant-bound polling entrypoint for an authorized worker session.

Usage (from an interactive user Windows session or isolated browser worker):
  python -m computer_use.runtime

The environment and signed profile are PROVISIONING inputs, never downloaded
from the current job, page, model or browser. Long-lived credentials and keys
are provided by a secure launcher at runtime (never in repository or logs).
"""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

from .daemon import QueueConsumer
from .jobs import JobControl, _require_identifier
from .payloads import EncryptedPayloadStore
from .profile_loader import load_verified_profile
from .worker import TenantWorker
from .vision import BedrockVisionModel, WindowsDesktop

LOG = logging.getLogger("notarai.virtual_worker")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError("worker_configuration_incomplete")
    return value


def _profile_from_environment(tenant: str):
    file_path = Path(required("NOTARAI_VE_PROFILE_FILE"))
    if not file_path.is_file() or file_path.stat().st_size > 32768:
        raise RuntimeError("signed_worker_profile_missing")
    signature = required("NOTARAI_VE_PROFILE_SIGNATURE")
    signing_key = base64.b64decode(required("NOTARAI_VE_PROFILE_SIGNING_KEY_B64"), validate=True)
    signed = load_verified_profile(
        file_path.read_bytes(), signature, signing_key, tenant_id=tenant,
    )
    return signed.app


def prepare_worker(*, config=None, boto3_module=None):
    cfg = dict(os.environ if config is None else config)

    def require(name):
        val = cfg.get(name)
        if not isinstance(val, str) or not val:
            raise RuntimeError("worker_configuration_incomplete")
        return val

    tenant = _require_identifier(require("NOTARAI_VE_TENANT"))
    worker_id = _require_identifier(require("NOTARAI_VE_WORKER_ID"))
    queue_url = require("NOTARAI_VE_TENANT_QUEUE_URL")
    table_name = require("NOTARAI_VE_JOBS_TABLE")
    settings_name = require("NOTARAI_VE_SETTINGS_TABLE")
    bucket = require("NOTARAI_VE_PAYLOAD_BUCKET")
    kms_key = require("NOTARAI_VE_TENANT_KMS_KEY")
    # Hardcode the AWS region to avoid accidentally switching out of the EU.
    region = cfg.get("AWS_REGION", "eu-central-1")
    if region != "eu-central-1":
        raise RuntimeError("invalid_worker_region")

    profile_path = Path(require("NOTARAI_VE_PROFILE_FILE"))
    if not profile_path.is_file() or profile_path.stat().st_size > 32768:
        raise RuntimeError("signed_worker_profile_missing")
    signing_key = base64.b64decode(require("NOTARAI_VE_PROFILE_SIGNING_KEY_B64"), validate=True)
    profile = load_verified_profile(
        profile_path.read_bytes(),
        require("NOTARAI_VE_PROFILE_SIGNATURE"),
        signing_key, tenant_id=tenant,
    ).app

    if boto3_module is None:
        import boto3 as boto3_module
    table = boto3_module.resource("dynamodb", region_name=region).Table(table_name)
    settings = boto3_module.resource("dynamodb", region_name=region).Table(settings_name)
    sqs = boto3_module.client("sqs", region_name=region)
    payloads = EncryptedPayloadStore(
        s3=boto3_module.client("s3", region_name=region),
        bucket=bucket, tenant_id=tenant, kms_key_id=kms_key,
    )
    control = JobControl(
        table=table, settings_table=settings, sqs=sqs, payloads=payloads,
        queue_resolver=lambda t: queue_url if t == tenant else None,
    )

    vision = None
    desktop = None
    enabled = cfg.get("NOTARAI_VE_VISUAL_ENABLED", "false").lower() == "true"
    if enabled:
        if os.name != "nt":
            raise RuntimeError("visual_worker_requires_windows")
        vision = BedrockVisionModel(
            client=boto3_module.client("bedrock-runtime", region_name=region),
            model_id=require("NOTARAI_VE_EU_VISION_MODEL"),
            region=region, expressly_enabled=True,
        )
        desktop = WindowsDesktop()

    worker = TenantWorker(
        tenant_id=tenant, profiles={profile.app_id: profile},
        vision_model=vision, visual_desktop=desktop,
        visual_processing_enabled=enabled,
    )
    consumer = QueueConsumer(
        bound_tenant=tenant, worker_id=worker_id,
        queue_url=queue_url, sqs=sqs, control=control, worker=worker,
    )
    return consumer


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # No raw job bodies, profiles, screenshots, exception messages or PII.
    worker = prepare_worker()
    LOG.info("worker_started")
    while True:
        try:
            code = worker.poll_once()
            if code not in {"idle", "disabled"}:
                LOG.info("worker_tick status=%s", code)
            if code == "disabled":
                # The stop command must not hammer SQS while disabled.
                import time
                time.sleep(10)
        except KeyboardInterrupt:
            LOG.info("worker_stopped")
            return 0
        except Exception:
            # Some failures may contain data/ARNs: log only a constant code.
            LOG.error("worker_control_error")
            import time
            time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
