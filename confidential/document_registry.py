"""One-time encrypted document admission, independent of S3 current object state.

S3 IfNoneMatch='*' is insufficient after a delete marker. This DynamoDB
ledger makes a logical document identity and ciphertext digest immutable.
The application never stores plaintext, DEK, or public document identifiers
outside opaque IDs. AWS operator administrators may still alter this table;
the module alone is NOT a Zero Operator Access proof.
"""
from __future__ import annotations

import re

from confidential.job_ledger import validate_version_id, JobRejected

_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_V = re.compile(r"^[a-f0-9]{32}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class DocumentRegistryDenied(ValueError):
    """Never disclose records, raw identifiers or cloud exception messages."""


def _valid(pattern, value):
    return isinstance(value, str) and bool(pattern.fullmatch(value))


class DocumentVersionRegistry:
    """Fail-closed per-tenant table sharing the existing job-ledger PK schema.

    States: reserved -> stored -> queued. No operation resets a state or deletes
    an item. S3 failure after reservation intentionally requires manual review.
    """

    def __init__(self, dynamodb, *, tenant: str):
        if not _valid(_TENANT, tenant):
            raise DocumentRegistryDenied("invalid tenant scope")
        self.ddb = dynamodb
        self.tenant = tenant
        self.table = "notarai-confidential-jobs-" + tenant

    def _pk(self, case_id, object_id):
        if not _valid(_ID, case_id) or not _valid(_ID, object_id):
            raise DocumentRegistryDenied("invalid document identity")
        return {"pk": {"S": f"DOC#{self.tenant}#{case_id}#{object_id}"}}

    def reserve(self, *, case_id: str, object_id: str,
                document_version: str, ciphertext_sha256: str,
                key_pin: str) -> None:
        if not _valid(_V, document_version) or not _valid(_DIGEST, ciphertext_sha256):
            raise DocumentRegistryDenied("invalid document binding")
        if not isinstance(key_pin, str) or len(key_pin) != 44:
            raise DocumentRegistryDenied("invalid key fingerprint")
        item = {
            **self._pk(case_id, object_id),
            "tenant_id": {"S": self.tenant},
            "case_id": {"S": case_id},
            "object_id": {"S": object_id},
            "document_version": {"S": document_version},
            "sha256": {"S": ciphertext_sha256},
            "key_pin": {"S": key_pin},
            "state": {"S": "reserved"},
            "submitted": {"BOOL": False},
        }
        try:
            self.ddb.put_item(
                TableName=self.table, Item=item,
                ConditionExpression="attribute_not_exists(pk)",
            )
        except Exception:
            raise DocumentRegistryDenied("document identity already used or unavailable") from None

    def finalize(self, *, case_id: str, object_id: str,
                 document_version: str, ciphertext_sha256: str,
                 s3_version: str) -> None:
        try:
            validate_version_id(s3_version)
            self.ddb.update_item(
                TableName=self.table, Key=self._pk(case_id, object_id),
                UpdateExpression="SET #state = :stored, s3_version = :version",
                ConditionExpression=(
                    "#state = :reserved AND document_version = :logical "
                    "AND sha256 = :digest AND attribute_not_exists(s3_version)"
                ),
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":stored": {"S": "stored"},
                    ":reserved": {"S": "reserved"},
                    ":logical": {"S": document_version},
                    ":digest": {"S": ciphertext_sha256},
                    ":version": {"S": s3_version},
                },
            )
        except Exception:
            raise DocumentRegistryDenied("cannot finalize immutable document") from None

    def _record(self, case_id: str, object_id: str) -> dict:
        try:
            response = self.ddb.get_item(
                TableName=self.table,
                Key=self._pk(case_id, object_id),
                ConsistentRead=True,
            )
        except Exception:
            raise DocumentRegistryDenied("document ledger unavailable") from None
        item = response.get("Item") or {}
        if (item.get("tenant_id", {}).get("S") != self.tenant
            or item.get("case_id", {}).get("S") != case_id
            or item.get("object_id", {}).get("S") != object_id
            or item.get("submitted", {}).get("BOOL") is not False):
            raise DocumentRegistryDenied("document not authorized")
        return item

    def _check(self, item: dict, *, s3_version: str, ciphertext_sha256: str,
               document_version: str, key_pin: str) -> None:
        try:
            validate_version_id(s3_version)
        except JobRejected:
            raise DocumentRegistryDenied("invalid S3 version") from None
        if (item.get("s3_version", {}).get("S") != s3_version
            or item.get("sha256", {}).get("S") != ciphertext_sha256
            or item.get("document_version", {}).get("S") != document_version
            or item.get("key_pin", {}).get("S") != key_pin):
            raise DocumentRegistryDenied("version or ciphertext binding mismatch")

    def claim_preview(self, *, case_id: str, object_id: str,
                      document_version: str, ciphertext_sha256: str,
                      key_pin: str, s3_version: str) -> None:
        item = self._record(case_id, object_id)
        self._check(item, s3_version=s3_version,
                    ciphertext_sha256=ciphertext_sha256,
                    document_version=document_version, key_pin=key_pin)
        if item.get("state", {}).get("S") != "stored":
            raise DocumentRegistryDenied("already queued or not stored")
        try:
            self.ddb.update_item(
                TableName=self.table, Key=self._pk(case_id, object_id),
                UpdateExpression="SET #state = :queued",
                ConditionExpression=(
                    "#state = :stored AND s3_version = :version "
                    "AND document_version = :logical AND sha256 = :digest "
                    "AND key_pin = :pin AND submitted = :false"
                ),
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":queued": {"S": "queued"},
                    ":stored": {"S": "stored"},
                    ":version": {"S": s3_version},
                    ":logical": {"S": document_version},
                    ":digest": {"S": ciphertext_sha256},
                    ":pin": {"S": key_pin},
                    ":false": {"BOOL": False},
                },
            )
        except Exception:
            raise DocumentRegistryDenied("document replay or queue race") from None

    def require_stored(self, *, case_id: str, object_id: str,
                       s3_version: str, ciphertext_sha256: str,
                       document_version: str, key_pin: str) -> None:
        item = self._record(case_id, object_id)
        self._check(item, s3_version=s3_version,
                    ciphertext_sha256=ciphertext_sha256,
                    document_version=document_version, key_pin=key_pin)
        if item.get("state", {}).get("S") not in ("stored", "queued"):
            raise DocumentRegistryDenied("document is not committed")

    def require_guest(self, *, case_id: str, object_id: str,
                      s3_version: str, ciphertext_sha256: str,
                      document_version: str, key_pin: str) -> None:
        item = self._record(case_id, object_id)
        self._check(item, s3_version=s3_version,
                    ciphertext_sha256=ciphertext_sha256,
                    document_version=document_version, key_pin=key_pin)
        if item.get("state", {}).get("S") != "queued":
            raise DocumentRegistryDenied("guest document not queued")
