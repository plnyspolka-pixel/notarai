"""One authorized customer-owned v3 preview *inside* AWS Nitro Sandbox.

This is the measured guest-side processing core, not an HTTP endpoint or a
complete async challenge/grant transport. A trusted client must verify AWS NSM
and issue a recipient grant to the *same* CustomerGuestSession beforehand.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
from collections.abc import Mapping

from confidential.customer_guest_v3 import CustomerGuestSession
from confidential.customer_release import (
    ReleaseDenied, _json, envelope_sha256, parse_envelope, parse_grant,
)
from confidential.document_registry import DocumentVersionRegistry
from confidential.job_ledger import PreviewJobLedger, validate_version_id

_MAX_WIRE = 35 * 1024 * 1024


class CustomerPreviewDenied(ValueError):
    pass


def _strict_json(data: bytes) -> dict:
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate JSON field")
            out[key] = value
        return out
    result = json.loads(data, object_pairs_hook=unique,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    if not isinstance(result, dict):
        raise ValueError("expected object")
    return result


def _read_object(s3, *, bucket: str, key: str, version: str | None = None) -> bytes:
    options = {"Bucket": bucket, "Key": key}
    if version is not None:
        options["VersionId"] = validate_version_id(version)
    result = s3.get_object(**options)
    with result["Body"] as stream:
        data = stream.read(_MAX_WIRE + 1)
    if len(data) > _MAX_WIRE:
        raise ValueError("oversized encrypted object")
    return data


def _origin_bundle(raw: bytes) -> tuple[dict, bytes]:
    if len(raw) > 8192:
        raise ValueError("oversized origin")
    bundle = _strict_json(raw)
    if (set(bundle) != {"schema", "receipt", "signature_b64"}
            or bundle["schema"] != "notarai.customer-origin-bundle.v1"
            or not isinstance(bundle["receipt"], dict)
            or not isinstance(bundle["signature_b64"], str)):
        raise ValueError("invalid signed origin")
    signature = base64.b64decode(bundle["signature_b64"], validate=True)
    if len(signature) != 64:
        raise ValueError("wrong origin signature size")
    return bundle["receipt"], signature


async def process_preview_once(*, s3, ddb, guest: CustomerGuestSession,
                               tenant: str, bucket: str, case_id: str,
                               object_id: str, job_id: str, s3_version: str,
                               grant: Mapping, expected_issuer_id: str,
                               pinned_notary_signing_public_raw: bytes,
                               now: int) -> dict:
    """Burn grant in durable ledger; re-check origin in Nitro; demo preview only.

    No KMS fallback. No LLM calls, arbitrary URLs or external submissions.
    S3 result contains only metadata. A failed, burned grant needs human review,
    not automatic replay.
    """
    if not isinstance(guest, CustomerGuestSession):
        raise CustomerPreviewDenied("customer preview denied")
    ledger = PreviewJobLedger(ddb, tenant=tenant)
    claim = ledger.claim(job_id=job_id, case_id=case_id, object_id=object_id,
                         s3_version=s3_version, now=now)
    if claim.state != "claimed":
        raise CustomerPreviewDenied("customer preview denied")
    try:
        key = f"kancelarie/{tenant}/confidential/{case_id}/{object_id}.json"
        raw = _read_object(s3, bucket=bucket, key=key, version=s3_version)
        envelope = parse_envelope(_strict_json(raw))
        if (envelope["tenant_id"] != tenant
                or envelope["case_id"] != case_id
                or envelope["object_id"] != object_id
                or raw != _json(envelope)):
            raise ValueError("ciphertext scope mismatch")
        digest = hashlib.sha256(raw).hexdigest()
        registry = DocumentVersionRegistry(ddb, tenant=tenant)
        registry.require_guest(
            case_id=case_id, object_id=object_id, s3_version=s3_version,
            ciphertext_sha256=digest,
            document_version=envelope["document_version"],
            key_pin=envelope["owner_spki_sha256"],
        )
        origin_raw = _read_object(s3, bucket=bucket,
                                  key=key + ".origin.v3.json")
        receipt, signature = _origin_bundle(origin_raw)
        approval = parse_grant(grant)
        # Burn *before* the first private-key operation, even if validation
        # inside the guest subsequently fails.
        ledger.consume_release_once(
            job_id=job_id, token=claim.token,
            grant_sha256=hashlib.sha256(_json(approval)).hexdigest(),
            now=now,
        )
        clear = guest.open_preview_once(
            envelope, approval,
            expected_tenant=tenant, expected_case=case_id,
            expected_object=object_id, expected_job=job_id,
            origin_receipt=receipt, origin_signature=signature,
            pinned_notary_signing_public_raw=pinned_notary_signing_public_raw,
            expected_issuer_id=expected_issuer_id,
            expected_s3_version=s3_version, now=now,
        )
        try:
            data = _strict_json(clear)
        finally:
            # Python does not provide guaranteed wiping. ECS task terminates
            # after one job; memory lifecycle is part of hardware E2E testing.
            del clear
        if (set(data) != {"form_id", "fields"}
                or data["form_id"] != "local-demo"
                or not isinstance(data["fields"], dict)
                or set(data["fields"]) != {"name", "reference"}):
            raise ValueError("unsupported demo adapter")
        # Existing controlled Playwright preview; submit=False is enforced by
        # _prepare_fictional_form itself.
        from confidential.worker import _prepare_fictional_form
        await _prepare_fictional_form(job_id, data["fields"])
        s3.put_object(
            Bucket=bucket,
            Key=f"kancelarie/{tenant}/confidential-results/{job_id}.json",
            Body=_json({"version": 1, "job_id": job_id,
                        "status": "preview_completed", "fields_filled": 2,
                        "submitted": False}),
            ContentType="application/json", ServerSideEncryption="AES256",
        )
        ledger.complete(job_id=job_id, token=claim.token)
        return {"job_id": job_id, "status": "preview_completed",
                "fields_filled": 2, "submitted": False}
    except Exception:
        try:
            ledger.fail(job_id=job_id, token=claim.token,
                        attempts=claim.attempts)
        except Exception:
            pass
        raise CustomerPreviewDenied("customer preview denied") from None
