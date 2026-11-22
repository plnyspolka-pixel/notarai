"""Ciphertext-only AWS S3/SQS admission for customer-owned Nitro v3.

Reuses existing DocumentVersionRegistry and PreviewJobLedger rather than adding
a second job engine. The web/transport operator never receives a DEK.
This module does NOT implement the customer/guest handshake or certify ZOA.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping

from confidential.customer_origin import verify_customer_origin
from confidential.customer_release import _json, parse_envelope, ReleaseDenied
from confidential.document_registry import DocumentRegistryDenied, DocumentVersionRegistry
from confidential.job_ledger import JobRejected, PreviewJobLedger, validate_version_id

_TENANT = re.compile(r"[a-z0-9]{1,12}\Z")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{2,62}\Z")
_ACCOUNT = re.compile(r"[0-9]{12}\Z")
_JOB = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_MAX_WIRE = 35 * 1024 * 1024


class CustomerTransportDenied(ValueError):
    """Never include source data, AWS error messages, or identifiers."""


def _deny() -> None:
    raise CustomerTransportDenied("confidential transport denied")


class CustomerCiphertextTransport:
    """Use existing tenant-specific DDB table and encrypted S3 bucket.

    Not a REST handler: authentication/tenant role must already have been
    checked by the existing application before instantiating this object.
    """

    def __init__(self, *, s3, sqs, ddb, tenant: str, bucket: str,
                 queue_url: str, account: str) -> None:
        if (not isinstance(tenant, str) or not _TENANT.fullmatch(tenant)
                or not isinstance(bucket, str) or not _BUCKET.fullmatch(bucket)
                or not isinstance(account, str) or not _ACCOUNT.fullmatch(account)
                or queue_url !=
                f"https://sqs.eu-central-1.amazonaws.com/{account}/notarai-confidential-{tenant}.fifo"):
            _deny()
        self.s3 = s3
        self.sqs = sqs
        self.tenant = tenant
        self.bucket = bucket
        self.queue_url = queue_url
        self.registry = DocumentVersionRegistry(ddb, tenant=tenant)
        self.jobs = PreviewJobLedger(ddb, tenant=tenant)

    def _scope(self, envelope: Mapping) -> dict:
        try:
            env = parse_envelope(envelope)
            if env["tenant_id"] != self.tenant:
                _deny()
            return env
        except (ReleaseDenied, KeyError, TypeError):
            _deny()

    def _key(self, env: Mapping) -> str:
        return (f"kancelarie/{self.tenant}/confidential/"
                f"{env['case_id']}/{env['object_id']}.json")

    def admit_ciphertext(self, envelope: Mapping) -> dict:
        """Reserve logical identity in DDB BEFORE PUT, then require S3 VersionId."""
        env = self._scope(envelope)
        wire = _json(env)
        if len(wire) > _MAX_WIRE:
            _deny()
        digest = hashlib.sha256(wire).hexdigest()
        try:
            self.registry.reserve(
                case_id=env["case_id"], object_id=env["object_id"],
                document_version=env["document_version"],
                ciphertext_sha256=digest, key_pin=env["owner_spki_sha256"],
            )
            result = self.s3.put_object(
                Bucket=self.bucket, Key=self._key(env), Body=wire,
                ContentType="application/json", IfNoneMatch="*",
                ServerSideEncryption="AES256",
                Metadata={"content-sha256": digest,
                          "document-version": env["document_version"]},
            )
            version = validate_version_id(result.get("VersionId"))
            self.registry.finalize(
                case_id=env["case_id"], object_id=env["object_id"],
                document_version=env["document_version"],
                ciphertext_sha256=digest, s3_version=version,
            )
        except (DocumentRegistryDenied, JobRejected, KeyError, ValueError, TypeError):
            # A PUT may have committed. Never retry blindly with the same ID.
            _deny()
        except Exception:
            _deny()
        return {"stored": True, "s3_version": version,
                "ciphertext_sha256": digest,
                "document_version": env["document_version"]}

    def enqueue_signed_preview(self, envelope: Mapping, *,
                               s3_version: str, ciphertext_sha256: str,
                               job_id: str, origin_receipt: Mapping,
                               origin_signature: bytes,
                               pinned_notary_signing_public_raw: bytes,
                               expected_issuer_id: str, now: int) -> dict:
        """Metadata-only SQS enqueue AFTER verifying exact version and origin.

        Backend signature verification is an early gate only. Guest MUST verify
        again against its image-pinned issuer key before decrypting.
        """
        env = self._scope(envelope)
        if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
            _deny()
        try:
            version = validate_version_id(s3_version)
            raw = _json(env)
            if (len(raw) > _MAX_WIRE
                    or not isinstance(ciphertext_sha256, str)
                    or hashlib.sha256(raw).hexdigest() != ciphertext_sha256):
                _deny()
            self.registry.require_stored(
                case_id=env["case_id"], object_id=env["object_id"],
                document_version=env["document_version"],
                ciphertext_sha256=ciphertext_sha256,
                key_pin=env["owner_spki_sha256"], s3_version=version,
            )
            verify_customer_origin(
                env, origin_receipt, origin_signature,
                pinned_notary_signing_public_raw=pinned_notary_signing_public_raw,
                expected_issuer_id=expected_issuer_id,
                expected_s3_version=version, now=now,
            )
            observed = self.s3.get_object(
                Bucket=self.bucket, Key=self._key(env), VersionId=version,
            )
            with observed["Body"] as stream:
                actual = stream.read(_MAX_WIRE + 1)
            if len(actual) > _MAX_WIRE or actual != raw:
                _deny()
            bundle = _json({
                "schema": "notarai.customer-origin-bundle.v1",
                "receipt": dict(origin_receipt),
                "signature_b64": base64.b64encode(origin_signature).decode("ascii"),
            })
            self.s3.put_object(
                Bucket=self.bucket,
                Key=self._key(env) + ".origin.v3.json", Body=bundle,
                ContentType="application/json", IfNoneMatch="*",
                ServerSideEncryption="AES256",
            )
            self.jobs.create(job_id=job_id, case_id=env["case_id"],
                             object_id=env["object_id"], s3_version=version,
                             now=now)
            self.registry.claim_preview(
                case_id=env["case_id"], object_id=env["object_id"],
                document_version=env["document_version"],
                ciphertext_sha256=ciphertext_sha256,
                key_pin=env["owner_spki_sha256"], s3_version=version,
            )
            msg = _json({
                "schema": "notarai.customer-job.v1",
                "tenant_id": self.tenant,
                "case_id": env["case_id"],
                "object_id": env["object_id"],
                "job_id": job_id,
                "s3_version": version,
            })
            self.sqs.send_message(
                QueueUrl=self.queue_url, MessageBody=msg.decode("ascii"),
                MessageGroupId=self.tenant, MessageDeduplicationId=job_id,
            )
        except (ReleaseDenied, DocumentRegistryDenied, JobRejected,
                KeyError, ValueError, TypeError):
            _deny()
        except Exception:
            # The SQS write may have succeeded: fail closed, never auto-resend.
            try:
                self.jobs.mark_queue_uncertain(job_id)
            except Exception:
                pass
            _deny()
        return {"queued": True, "job_id": job_id,
                "operation": "preview-only", "submitted": False}
