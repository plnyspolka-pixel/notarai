"""Small stdio MCP bridge: Claude/Codex can delegate work to own GPU/CPU workers.

No third-party MCP package required. JSON-RPC message framing is line-delimited
stdio as supported by MCP stdio transport. All diagnostics go to stderr.
"""
from __future__ import annotations

import json
import sys

from tools.agent_factory.worker_pool import (
    WorkerPolicyError, capabilities, delegate, validate_batch
)

PROTOCOL_VERSION = "2025-06-18"
JOB_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "role", "instruction", "context", "paths", "data_class"],
    "properties": {
        "id": {"type": "string"},
        "role": {"type": "string", "enum": [
            "implementer", "test-designer", "reviewer",
            "bug-triage", "documentation", "research-assistant"
        ]},
        "instruction": {"type": "string"},
        "context": {"type": "string"},
        "paths": {"type": "array", "items": {"type": "string"}},
        "data_class": {"type": "string", "enum": ["synthetic", "public"]},
    }
}
TOOLS = [
    {
        "name": "worker_pool_status",
        "description": "Check which low-cost worker model is configured; no inference. "
                       "It does not start a CPU/GPU instance.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}
    },
    {
        "name": "delegate_workers",
        "description": "Delegate up to six independent, bounded PUBLIC/SYNTHETIC tasks "
                       "to cheap local CPU/GPU workers in parallel. Workers return "
                       "UNVERIFIED proposals only; Claude/Codex must test and integrate. "
                       "Never include secrets, customer data, private source or grader tests.",
        "inputSchema": {
            "type": "object",
            "required": ["jobs"],
            "additionalProperties": False,
            "properties": {
                "jobs": {"type": "array", "minItems": 1, "maxItems": 6,
                         "items": JOB_SCHEMA}
            },
        }
    },
    {
        "name": "validate_worker_batch",
        "description": "Validate worker packets and confidentiality safeguards offline; "
                       "does not invoke any model.",
        "inputSchema": {
            "type": "object", "required": ["jobs"], "additionalProperties": False,
            "properties": {"jobs": {"type": "array", "items": JOB_SCHEMA}}
        }
    },
]


def response(message: dict) -> dict | None:
    method = message.get("method")
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    req_id = message.get("id")
    if req_id is None:
        return None
    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "agent-forge-low-cost-workers", "version": "0.1.0"},
        }
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method != "tools/call":
        return {"jsonrpc": "2.0", "id": req_id, "error": {
            "code": -32601, "message": "Method not found"
        }}
    params = message.get("params") or {}
    try:
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            raise WorkerPolicyError("arguments must be an object")
        if name == "worker_pool_status":
            if args:
                raise WorkerPolicyError("no arguments accepted")
            data = capabilities()
        elif name == "delegate_workers":
            if set(args) != {"jobs"}:
                raise WorkerPolicyError("exact jobs field required")
            data = delegate(args["jobs"])
        elif name == "validate_worker_batch":
            if set(args) != {"jobs"}:
                raise WorkerPolicyError("exact jobs field required")
            accepted = validate_batch(args["jobs"])
            data = {"status": "validated_no_model_calls", "count": len(accepted),
                    "sha256s": [
                        __import__("hashlib").sha256(
                            json.dumps(j, sort_keys=True).encode()).hexdigest()
                        for j in accepted
                    ]}
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {
                "code": -32602, "message": "Unknown tool"
            }}
        body = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
    except (WorkerPolicyError, TypeError, ValueError) as exc:
        body = {"isError": True, "content": [{
            "type": "text", "text": type(exc).__name__ + ": " + str(exc)
        }]}
    return {"jsonrpc": "2.0", "id": req_id, "result": body}


def main() -> None:
    for line in sys.stdin:
        if not line.strip() or len(line) > 90_000:
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                continue
            reply = response(message)
            if reply is not None:
                sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except (ValueError, KeyError, TypeError) as exc:
            print(type(exc).__name__, file=sys.stderr)


if __name__ == "__main__":
    main()
