"""Read-only loopback Chat Completions adapter for Agent Forge synthetic experiments.

No model tools, generated code execution, browser, cloud provisioning or secrets.
An operator-provisioned endpoint may incur external GPU costs: pricing is UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from tools.agent_factory.forge_core import (
    ForgeError, RUN_ID, RunStore, digest, independent_evaluate,
    read_fixture, validate_rubric, validate_task,
)

MODEL_ID = re.compile(r"^[A-Za-z0-9._:/-]{1,120}$")
OPT_IN_ENV = "AGENT_FORGE_ALLOW_LOCAL_MODEL"
OPT_IN_VALUE = "I_APPROVE_SYNTHETIC_LOOPBACK_ONLY"


@dataclass(frozen=True)
class LocalModelConfig:
    model: str
    endpoint: str = "http://127.0.0.1:8000/v1"
    max_output_tokens: int = 48
    timeout_s: int = 15

    def validate(self) -> int:
        if not isinstance(self.model, str) or not MODEL_ID.fullmatch(self.model):
            raise ForgeError("Invalid model identifier")
        url = urlsplit(self.endpoint)
        try:
            port = url.port
        except ValueError as exc:
            raise ForgeError("Invalid endpoint port") from exc
        if (url.scheme != "http" or url.hostname != "127.0.0.1"
                or url.netloc != f"127.0.0.1:{port}"
                or url.path not in {"/v1", "/v1/"}
                or url.query or url.fragment or url.username or url.password
                or port is None or not 1024 <= port <= 65535):
            raise ForgeError("Only 127.0.0.1:PORT/v1 is allowed")
        if type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= 128:
            raise ForgeError("Output token limit must be 1-128")
        if type(self.timeout_s) is not int or not 1 <= self.timeout_s <= 60:
            raise ForgeError("Timeout must be 1-60 seconds")
        return port


def require_opt_in(flag: bool) -> None:
    if flag is not True or os.environ.get(OPT_IN_ENV) != OPT_IN_VALUE:
        raise ForgeError("Local model access disabled; requires explicit CLI and environment opt-in")


def model_messages(task: dict) -> list[dict[str, str]]:
    validate_task(task)
    return [
        {"role": "system", "content":
         'Output only a JSON object with one integer field: {"answer":integer}. '
         "Do not call tools, run code, browse or add explanation."},
        {"role": "user", "content":
         "Calculate " + task["operation"] + " over integers " +
         json.dumps(task["values"], separators=(",", ":"))},
    ]


def request_chat(config: LocalModelConfig, messages: list[dict]) -> dict:
    """Direct HTTPConnection avoids proxies, DNS lookups and 30x redirects."""
    port = config.validate()
    body = json.dumps({"model": config.model, "messages": messages,
                       "temperature": 0, "max_tokens": config.max_output_tokens,
                       "stream": False}, separators=(",", ":")).encode("utf-8")
    if len(body) > 4096:
        raise ForgeError("Request is too large")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=config.timeout_s)
    try:
        conn.request("POST", "/v1/chat/completions", body=body, headers={
            "Content-Type": "application/json", "Accept": "application/json",
            "Connection": "close",
        })
        response = conn.getresponse()
        if response.status != 200:
            raise ForgeError("Local model returned non-200 response")
        length = response.getheader("Content-Length")
        if length is not None:
            try:
                parsed = int(length)
            except ValueError as exc:
                raise ForgeError("Invalid Content-Length") from exc
            if parsed < 0 or parsed > 8192:
                raise ForgeError("Response exceeds 8192 bytes")
        raw = response.read(8193)
        if len(raw) > 8192:
            raise ForgeError("Response exceeds 8192 bytes")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise ForgeError("Malformed response JSON") from exc
        if not isinstance(data, dict):
            raise ForgeError("Malformed response JSON")
        return data
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        raise ForgeError("Local model transport failed") from exc
    finally:
        conn.close()


def parse_chat(data: dict) -> tuple[dict[str, int], dict]:
    try:
        choices = data["choices"]
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError
        message = choices[0]["message"]
        if not isinstance(message, dict) or message.get("tool_calls"):
            raise ValueError
        content = message["content"]
        if not isinstance(content, str) or len(content.encode("utf-8")) > 512:
            raise ValueError
        answer = json.loads(content)
        if not isinstance(answer, dict) or set(answer) != {"answer"}:
            raise ValueError
        if type(answer["answer"]) is not int or abs(answer["answer"]) > 128000000:
            raise ValueError
        usage = data.get("usage") or {}
        if not isinstance(usage, dict):
            raise ValueError
        tokens = {}
        for key in ("prompt_tokens", "completion_tokens"):
            value = usage.get(key)
            if value is not None and (type(value) is not int or value < 0 or value > 1000000):
                raise ValueError
            tokens[key] = value
        return answer, tokens
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ForgeError("Response did not satisfy strict output schema") from exc


def prepare_metrics(store: RunStore) -> None:
    store.conn.execute("""
        CREATE TABLE IF NOT EXISTS local_model_metrics(
        run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
        model TEXT NOT NULL, prompt_tokens INTEGER, completion_tokens INTEGER,
        elapsed_ms INTEGER NOT NULL, pricing TEXT NOT NULL)
    """)
    store.conn.commit()


def get_metrics(store: RunStore, run_id: str) -> dict | None:
    prepare_metrics(store)
    record = store.conn.execute(
        "SELECT model,prompt_tokens,completion_tokens,elapsed_ms,pricing "
        "FROM local_model_metrics WHERE run_id=?", (run_id,)
    ).fetchone()
    return dict(record) if record else None


def run_local_model(store: RunStore, root: Path, run_id: str, task_file: str,
                    rubric_file: str, config: LocalModelConfig,
                    *, operator_opt_in: bool = False) -> dict:
    """Single synthetic request; no retries and no automatic provider billing."""
    require_opt_in(operator_opt_in)
    config.validate()
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ForgeError("Invalid run ID")
    task = read_fixture(root, task_file)
    validate_task(task)
    rubric = read_fixture(root, rubric_file)
    validate_rubric(rubric, task)
    manifest = {
        "schema": "forge-local-model-v1", "run_id": run_id,
        "experiment_id": "EXP-01", "task_id": task["task_id"],
        "task_hash": digest(task), "rubric_hash": digest(rubric),
        "adapter": "local-chat-completions", "model": config.model,
        "endpoint": config.endpoint, "max_tokens": str(config.max_output_tokens),
        "timeout": str(config.timeout_s), "classification": "synthetic",
    }
    prepare_metrics(store)
    if not store.register(manifest):
        record = store.get(run_id)
        return {
            "run_id": run_id, "state": record["state"],
            "passed": None if record["passed"] is None else bool(record["passed"]),
            "replayed": True, "audit_valid": store.verify_events(run_id),
            "metrics": get_metrics(store, run_id), "actual_cost_pln": None,
        }
    store.transition(run_id, "running")
    began = time.monotonic()
    try:
        payload = request_chat(config, model_messages(task))
        answer, tokens = parse_chat(payload)
        result = independent_evaluate(answer, rubric)
        elapsed_ms = max(0, int((time.monotonic() - began) * 1000))
        with store.conn:
            store.conn.execute(
                "INSERT INTO local_model_metrics"
                "(run_id,model,prompt_tokens,completion_tokens,elapsed_ms,pricing)"
                " VALUES(?,?,?,?,?,?)",
                (run_id, config.model, tokens["prompt_tokens"],
                 tokens["completion_tokens"], elapsed_ms, "unpriced"),
            )
        state = "completed" if result["passed"] else "failed"
        store.transition(run_id, state, result_hash=digest(answer),
                         passed=result["passed"])
        return {
            "run_id": run_id, "state": state, "passed": result["passed"],
            "checks_passed": result["passed_checks"],
            "checks_total": result["total_checks"], "replayed": False,
            "audit_valid": store.verify_events(run_id),
            "result_hash": digest(answer),
            "metrics": get_metrics(store, run_id), "actual_cost_pln": None,
        }
    except ForgeError:
        store.transition(run_id, "failed", passed=False)
        raise
