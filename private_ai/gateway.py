"""Isolated synchronous Bedrock document adapter, no HTTP endpoint and no fallback."""
from dataclasses import dataclass
from typing import Any, Protocol
from .policy import Principal, Deployment, Classification, PolicyDenied, enforce

MAX_BYTES = 8 * 1024 * 1024
MAGIC = {
    "application/pdf": b"%PDF-",
    "image/png": bytes.fromhex("89504e470d0a1a0a"),
    "image/jpeg": bytes.fromhex("ffd8ff"),
}


class AuditSink(Protocol):
    def record(self, event: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class DocumentRequest:
    tenant_id: str
    request_id: str
    purpose: str
    classification: Classification
    prompt: str
    media_type: str
    content: bytes


@dataclass(frozen=True)
class GatewayResult:
    request_id: str
    text: str
    input_tokens: int
    output_tokens: int


def to_block(content: bytes, media_type: str) -> dict:
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_BYTES:
        raise PolicyDenied("Invalid file length")
    if media_type not in MAGIC or not content.startswith(MAGIC[media_type]):
        raise PolicyDenied("Unsupported file type/signature")
    if media_type == "application/pdf":
        return {"document": {"format": "pdf", "name": "document", "source": {"bytes": content}}}
    return {"image": {"format": "png" if media_type == "image/png" else "jpeg",
                      "source": {"bytes": content}}}


class DocumentGateway:
    def __init__(self, *, deployment: Deployment, client: Any, audit: AuditSink):
        if client is None or audit is None or not callable(getattr(audit, "record", None)):
            raise ValueError("EU runtime client and durable audit required")
        self.dep, self.client, self.audit = deployment, client, audit

    def process(self, principal: Principal, req: DocumentRequest) -> GatewayResult:
        enforce(principal, req.tenant_id, req.request_id,
                req.purpose, req.classification, self.dep)
        if not isinstance(req.prompt, str) or not (1 <= len(req.prompt) <= 4000):
            raise PolicyDenied("Invalid prompt")
        block = to_block(req.content, req.media_type)
        meta = {"tenant_id": req.tenant_id, "request_id": req.request_id,
                "purpose": req.purpose, "classification": req.classification.value,
                "region": self.dep.region, "model": self.dep.model_id}
        # Fail BEFORE inferencing if the audit sink is unavailable.
        self.audit.record({**meta, "event": "authorized"})
        try:
            response = self.client.converse(
                modelId=self.dep.model_id,
                messages=[{"role": "user", "content": [{"text": req.prompt}, block]}],
                inferenceConfig={"maxTokens": 2048},
            )
        except Exception:
            self.audit.record({**meta, "event": "failed"})
            raise
        usage = response.get("usage", {})
        output = response.get("output", {}).get("message", {}).get("content", [])
        text = "".join(item.get("text", "") for item in output if isinstance(item, dict))
        self.audit.record({**meta, "event": "completed",
                           "input_tokens": int(usage.get("inputTokens", 0)),
                           "output_tokens": int(usage.get("outputTokens", 0))})
        return GatewayResult(req.request_id, text,
                             int(usage.get("inputTokens", 0)),
                             int(usage.get("outputTokens", 0)))
