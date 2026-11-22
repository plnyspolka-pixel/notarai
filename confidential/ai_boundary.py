"""SEC-04: fail-closed AI trust-boundary policy.

This code is NOT hardware-attestation evidence. The existing Bedrock workflow
runs outside Nitro and must never be described as strict Zero Knowledge.
No prompts, outputs, identifiers, source documents or secret values are logged.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping

_REGION = "eu-central-1"
_MODEL = re.compile(r"^eu\.[A-Za-z0-9][A-Za-z0-9._:-]{2,160}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_OPERATIONS = frozenset({"transcribe", "extract", "draft", "summarize", "classify", "embed", "ocr", "preview"})
_PUBLIC_ENDPOINT = re.compile(r"(?i)(?:https?://|wss?://|ftp://)")
_FORBIDDEN_KEYS = frozenset({
    "content", "prompt", "messages", "completion", "response", "document",
    "plaintext", "dek", "secret", "authorization", "headers", "url",
    "body", "payload", "query", "text", "output", "input", "trace",
})


class AIBoundaryDenied(PermissionError):
    """Purposefully generic; never interpolate data or upstream exceptions."""

    def __init__(self, code: str = "AI_BOUNDARY_DENIED") -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class InferencePolicy:
    """Explicit legacy processing policy; NOT evidence of confidential inference."""

    provider: str
    model_id: str
    region: str
    operations: frozenset[str]
    classification: str
    transport: str
    approved_external_processing: bool = False
    retention_evidence: bool = False
    processor_evidence: bool = False


@dataclass(frozen=True)
class BoundaryDecision:
    allowed: bool
    zk_status: str
    boundary: str
    reason: str


def evaluate_inference(
    policy: InferencePolicy | None,
    *,
    operation: str,
    model_id: str,
    region: str,
    provider: str,
    transport: str,
) -> BoundaryDecision:
    """Fail closed. Bedrock must be an explicit, non-ZK trust-boundary choice.

    No caller-provided boolean, environment variable, or mock can produce a
    strict-ZK PASS. Genuine Nitro evidence belongs to SEC-07/SEC-11.
    """
    if policy is None:
        raise AIBoundaryDenied("MISSING_AI_POLICY")
    if operation not in _OPERATIONS or operation not in policy.operations:
        raise AIBoundaryDenied("OPERATION_NOT_APPROVED")
    if not all(isinstance(v, str) for v in (model_id, region, provider, transport)):
        raise AIBoundaryDenied()
    if (policy.region != _REGION or region != _REGION
            or model_id != policy.model_id or provider != policy.provider
            or transport != policy.transport):
        raise AIBoundaryDenied("MODEL_OR_ROUTE_MISMATCH")
    if policy.classification not in {"synthetic", "public", "case_plaintext"}:
        raise AIBoundaryDenied("UNKNOWN_DATA_CLASS")

    if provider == "aws-bedrock":
        if not _MODEL.fullmatch(model_id) or transport != "aws-sdk":
            raise AIBoundaryDenied("UNAPPROVED_EXTERNAL_ENDPOINT")
        # This is explicitly a distinct external trust boundary, even in EU.
        if not policy.approved_external_processing:
            raise AIBoundaryDenied("EXTERNAL_PROCESSING_NOT_APPROVED")
        return BoundaryDecision(True, "UNVERIFIED", "aws-bedrock-outside-nitro",
                                "EXTERNAL_PLAINTEXT_BOUNDARY")

    # No generic HTTP or public-model fallback is ever permitted.
    if provider != "enclave-local" or transport != "in-process":
        raise AIBoundaryDenied("UNAPPROVED_AI_PROVIDER")
    if not _DIGEST.fullmatch(model_id):
        raise AIBoundaryDenied("UNPINNED_LOCAL_MODEL")

    # Local model execution is not wired yet; unit/mock attestations cannot
    # authorize handling confidential document contents.
    if policy.classification == "case_plaintext":
        raise AIBoundaryDenied("CONFIDENTIAL_INFERENCE_NOT_ATTESTED")
    return BoundaryDecision(True, "UNVERIFIED", "synthetic-offline-only",
                            "NO_HARDWARE_EVIDENCE")


def enforce_bedrock_dispatch(*, model_id: str, region: str, pinned_model: str) -> BoundaryDecision:
    """Mandatory guard called before *every* Bedrock converse_stream request.

    Confidential workers cannot send plaintext to a separate AWS Bedrock
    trust boundary. Existing legacy Bedrock processing remains functional,
    but is *never* represented as verified Zero Knowledge.
    """
    if os.environ.get("NOTARAI_CONFIDENTIAL_REQUIRED") == "1":
        raise AIBoundaryDenied("BEDROCK_OUTSIDE_NITRO_DENIED")
    if region != _REGION or not _MODEL.fullmatch(model_id):
        raise AIBoundaryDenied("BEDROCK_REGION_OR_MODEL_DENIED")
    # A legacy model override is possible for the non-confidential app.
    # Both default and explicit overrides remain UNVERIFIED, not strict ZK.
    if not isinstance(pinned_model, str) or not _MODEL.fullmatch(pinned_model):
        raise AIBoundaryDenied("INVALID_CONFIGURED_MODEL")
    return BoundaryDecision(True, "UNVERIFIED", "aws-bedrock-outside-nitro",
                            "LEGACY_EXTERNAL_PROCESSING")


def validate_model_action(action: Mapping[str, object]) -> None:
    """No arbitrary tools, navigation, URL retrieval or submission by AI.

    Treat all model output as untrusted instructions, irrespective of wording.
    A caller can only supply structured, non-executable preview metadata.
    """
    if not isinstance(action, Mapping) or set(action) != {"action", "fields_count"}:
        raise AIBoundaryDenied("MODEL_ACTION_SCHEMA_DENIED")
    if action["action"] != "preview-only":
        raise AIBoundaryDenied("MODEL_ACTION_DENIED")
    count = action["fields_count"]
    if type(count) is not int or not 0 <= count <= 100:
        raise AIBoundaryDenied("MODEL_ACTION_SCHEMA_DENIED")


def validate_operator_result(result: Mapping[str, object]) -> dict[str, object]:
    """Only bounded non-content metadata is allowed to cross to operator APIs.

    No free-form model response, document text, URLs or full filenames.
    Strict schema prevents arbitrary extra fields, even if named innocuously.
    """
    if not isinstance(result, Mapping) or set(result) != {
        "operation", "submitted", "fields_count", "status"
    }:
        raise AIBoundaryDenied("RESULT_SCHEMA_DENIED")
    if result["operation"] != "preview-only" or result["submitted"] is not False:
        raise AIBoundaryDenied("UNSAFE_RESULT")
    if type(result["fields_count"]) is not int or not 0 <= result["fields_count"] <= 100:
        raise AIBoundaryDenied("RESULT_SCHEMA_DENIED")
    if result["status"] not in ("previewed", "denied", "not-run"):
        raise AIBoundaryDenied("RESULT_SCHEMA_DENIED")
    return dict(result)


def safe_telemetry(event: Mapping[str, object]) -> dict[str, object]:
    """Reject any sensitive fields; telemetry is an allowlisted numeric event."""
    if not isinstance(event, Mapping) or set(event) != {
        "event", "count", "zk_status"
    }:
        raise AIBoundaryDenied("TELEMETRY_SCHEMA_DENIED")
    if event["event"] not in ("model-call-denied", "preview-finished", "model-call-failed"):
        raise AIBoundaryDenied("TELEMETRY_EVENT_DENIED")
    if type(event["count"]) is not int or not 0 <= event["count"] <= 1000000:
        raise AIBoundaryDenied("TELEMETRY_COUNT_DENIED")
    if event["zk_status"] not in ("UNVERIFIED", "BLOCKED"):
        raise AIBoundaryDenied("UNSUPPORTED_ZK_CLAIM")
    return dict(event)


def reject_untrusted_endpoint(endpoint: str | None) -> None:
    """No external tool/plugin endpoint is supported in confidential mode."""
    if endpoint is not None or (isinstance(endpoint, str) and _PUBLIC_ENDPOINT.search(endpoint)):
        raise AIBoundaryDenied("EXTERNAL_ENDPOINT_DENIED")
