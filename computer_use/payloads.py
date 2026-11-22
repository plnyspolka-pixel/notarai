"""Tenant-scoped encrypted S3 payload storage for NotarAI Virtual Employee.

No PII in DynamoDB/SQS/CloudWatch. The AWS identity running this must have
access ONLY to this tenant's prefix and tenant KMS key; application checks
are an additional layer, not a substitute for IAM/key policy.
"""
import hashlib
import json
import re

from .jobs import _require_identifier


class EncryptedPayloadStore:
    def __init__(self, *, s3, bucket: str, tenant_id: str, kms_key_id: str):
        _require_identifier(tenant_id)
        if not bucket or not kms_key_id:
            raise ValueError("missing_encrypted_payload_config")
        self.s3 = s3
        self.bucket = bucket
        self.tenant_id = tenant_id
        self.kms_key_id = kms_key_id

    def _key(self, tenant: str, job_id: str, part: str) -> str:
        if tenant != self.tenant_id:
            raise PermissionError("tenant_mismatch")
        _require_identifier(job_id)
        if part not in {"input", "result"}:
            raise ValueError("unknown_payload_part")
        return f"virtual-employee/tenants/{tenant}/jobs/{job_id}/{part}.json"

    def write(self, tenant: str, job_id: str, part: str, data) -> str:
        key = self._key(tenant, job_id, part)
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > 32 * 1024:
            raise ValueError("payload_too_large")
        digest = hashlib.sha256(raw).hexdigest()
        self.s3.put_object(
            Bucket=self.bucket, Key=key, Body=raw,
            ContentType="application/json", IfNoneMatch="*",
            ServerSideEncryption="aws:kms", SSEKMSKeyId=self.kms_key_id,
            SSEKMSEncryptionContext=json.dumps({
                "tenant": tenant, "job": job_id, "part": part,
            }, sort_keys=True),
            Metadata={"sha256": digest},
        )
        return digest  # never expose an arbitrary S3 key to the caller

    def read(self, tenant: str, job_id: str, part: str, expected_digest: str):
        if not isinstance(expected_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_digest):
            raise ValueError("invalid_payload_digest")
        key = self._key(tenant, job_id, part)
        result = self.s3.get_object(Bucket=self.bucket, Key=key)
        if result.get("ServerSideEncryption") != "aws:kms":
            raise PermissionError("unencrypted_object")
        if result.get("SSEKMSKeyId") != self.kms_key_id:
            raise PermissionError("unexpected_kms_key")
        raw = result["Body"].read(32769)
        if len(raw) > 32768 or hashlib.sha256(raw).hexdigest() != expected_digest:
            raise PermissionError("payload_integrity_check_failed")
        return json.loads(raw.decode("utf-8"))
