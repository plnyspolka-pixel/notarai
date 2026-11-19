"""AWS Lambda integration entrypoint: synthetic-only sandbox, NOT deployed.

The account/VPC/API configuration is an independently reviewed release gate.
No sensitive data may be used until end-to-end infrastructure is verified.
"""
import json
import os
import uuid

from .evidence import _metadata
from .gateway import DocumentGateway
from .ingress import process_event
from .policy import Deployment, PolicyDenied


class S3AuditSink:
    """WORM sink only if the real bucket has verified Object Lock COMPLIANCE."""
    def __init__(self, s3, bucket):
        if not bucket:
            raise ValueError("Audit bucket missing")
        self.s3, self.bucket = s3, bucket

    def record(self, event):
        sanitized = _metadata(event)
        key = "events/{}/{}/{}.json".format(
            sanitized["tenant_id"], sanitized["request_id"], uuid.uuid4().hex)
        # On failed authorized-event write, inference is never invoked.
        self.s3.put_object(
            Bucket=self.bucket, Key=key,
            ContentType="application/json",
            Body=json.dumps(sanitized, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _response(status, payload):
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
        },
        "body": json.dumps(payload, separators=(",", ":")),
    }


def lambda_handler(event, context):
    try:
        # Server environment, not request body, determines tenant/model/region.
        import boto3
        region = os.environ["AWS_REGION"]
        gateway = DocumentGateway(
            deployment=Deployment(
                region=region,
                model_id=os.environ["PRIVATE_AI_MODEL_ID"],
            ),
            client=boto3.client("bedrock-runtime", region_name=region),
            audit=S3AuditSink(
                boto3.client("s3", region_name=region),
                os.environ["PRIVATE_AI_AUDIT_BUCKET"],
            ),
        )
        result = process_event(
            event,
            allowed_role=os.environ["PRIVATE_AI_ALLOWED_ROLE_ARN"],
            api_id=os.environ["PRIVATE_AI_GATEWAY_API_ID"],
            tenant_id=os.environ["PRIVATE_AI_TENANT"],
            expected_fixture_sha256=os.environ["PRIVATE_AI_FIXTURE_SHA256"],
            gateway=gateway,
        )
        return _response(200, result)
    except (PolicyDenied, KeyError, ValueError, TypeError):
        return _response(403, {"error": "request_denied"})
    except Exception:
        # No prompt/body/response/provider error is ever returned or logged.
        return _response(503, {"error": "processor_unavailable"})
