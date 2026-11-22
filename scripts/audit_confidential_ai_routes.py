"""SEC-04 static AI-route inventory. Best-effort, NOT runtime dataflow proof.

Scans Python AST and JS transport primitives; best-effort only. CI fails on
new direct model calls in confidential/ and risky browser transports in
static/confidential*.js. JS regex checks do not replace real browser egress proof.
Only outputs file paths, line numbers and mechanism names (never source lines).
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SKIP = frozenset({".git", ".venv", "venv", "node_modules", "dane", "__pycache__"})
_MODEL_IMPORTS = frozenset({
    "anthropic", "openai", "google.generativeai", "google.genai", "langchain",
    "langchain_openai", "langchain_anthropic",
})
_NETWORK_CALLS = frozenset({
    "requests.post", "requests.get", "requests.request",
    "httpx.post", "httpx.get", "httpx.request",
    "urllib.request.urlopen", "urllib.request.Request",
    "http.client.HTTPConnection", "http.client.HTTPSConnection",
    "socket.create_connection", "socket.socket",
})
_MODEL_CALLS = frozenset({
    "converse", "converse_stream", "invoke_model", "invoke_model_with_response_stream",
    "create_embedding", "embed", "transcribe", "generate_content",
})


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted(node.value)
        return prefix + "." + node.attr if prefix else node.attr
    return ""


def scan_source(source: str, filename: str) -> list[dict[str, object]]:
    tree = ast.parse(source, filename=filename)
    findings: list[dict[str, object]] = []
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name in _MODEL_IMPORTS or any(
                    item.name.startswith(prefix + ".") for prefix in _MODEL_IMPORTS
                ):
                    findings.append({"file": filename, "line": node.lineno,
                                     "mechanism": "model-sdk-import"})
        elif isinstance(node, ast.ImportFrom):
            if node.module in _MODEL_IMPORTS:
                findings.append({"file": filename, "line": node.lineno,
                                 "mechanism": "model-sdk-import"})
        elif isinstance(node, ast.Call):
            name = _dotted(node.func)
            tail = name.rsplit(".", 1)[-1]
            kind = None
            if tail == "client" and node.args and isinstance(node.args[0], ast.Constant):
                if node.args[0].value == "bedrock-runtime":
                    kind = "bedrock-runtime-client"
            elif tail in _MODEL_CALLS:
                kind = "model-method-" + tail
            elif name in _NETWORK_CALLS:
                kind = "network-" + name
            if kind:
                findings.append({"file": filename, "line": node.lineno,
                                 "mechanism": kind})
    return sorted(findings, key=lambda item: (item["line"], item["mechanism"]))



# This conservative scan intentionally reports only the location and primitive.
# Dynamic routes, imported code and content security policy need runtime review.
_JS_NETWORK = re.compile(
    r"\b(?:fetch|WebSocket|XMLHttpRequest|EventSource|WebTransport|sendBeacon)\s*\("
)
_JS_RISKS = (
    # Any variable/unknown fetch destination, or a literal outside the
    # confidential same-origin API prefix, is denied by the CI source gate.
    # This is a conservative static policy; runtime network verification
    # is still required for K1/K2.
    ("js-risk-untrusted-fetch", re.compile(
        r"\b(?:window\.)?fetch\s*\(\s*(?!['\"\x60]/api/confidential/)")),
    ("js-risk-absolute-fetch", re.compile(
        r"\b(?:window\.)?fetch\s*\(\s*['\"\x60](?:https?:)?//")),
    ("js-risk-websocket", re.compile(r"\b(?:new\s+)?WebSocket\s*\(")),
    ("js-risk-beacon", re.compile(r"\b(?:navigator\.)?sendBeacon\s*\(")),
    ("js-risk-xhr", re.compile(r"\b(?:new\s+)?XMLHttpRequest\s*\(")),
    ("js-risk-eventsource", re.compile(r"\b(?:new\s+)?EventSource\s*\(")),
    ("js-risk-webtransport", re.compile(r"\b(?:new\s+)?WebTransport\s*\(")),
    ("js-risk-webrtc", re.compile(r"\b(?:new\s+)?RTCPeerConnection\s*\(")),
    ("js-risk-eval", re.compile(r"\beval\s*\(")),
    ("js-risk-function", re.compile(r"\bnew\s+Function\s*\(")),
    ("js-risk-service-worker", re.compile(
        r"\b(?:navigator\.)?serviceWorker\.register\s*\(")),
    ("js-risk-remote-import", re.compile(
        r"\bimport\s*\(\s*['\"\x60](?:https?:)?//")),
)


def scan_js_source(source: str, filename: str) -> list[dict[str, object]]:
    """Conservative transport inventory, NOT a complete JavaScript parser."""
    findings: list[dict[str, object]] = []
    for match in _JS_NETWORK.finditer(source):
        findings.append({"file": filename,
                         "line": source.count("\n", 0, match.start()) + 1,
                         "mechanism": "js-network-primitive"})
    for mechanism, pattern in _JS_RISKS:
        for match in pattern.finditer(source):
            findings.append({"file": filename,
                             "line": source.count("\n", 0, match.start()) + 1,
                             "mechanism": mechanism})
    return sorted(findings, key=lambda hit: (hit["line"], hit["mechanism"]))


def scan_repo(root: Path = _ROOT) -> dict:
    py_files = 0
    js_files = 0
    findings = []
    errors = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in _SKIP for part in rel.parts) or path.name.startswith("test_"):
            continue
        py_files += 1
        try:
            findings.extend(scan_source(path.read_text(encoding="utf-8"), rel.as_posix()))
        except (SyntaxError, UnicodeError, OSError):
            errors.append(rel.as_posix())
    for path in sorted(root.rglob("*.js")):
        rel = path.relative_to(root)
        if any(part in _SKIP for part in rel.parts) or path.name.startswith("test_"):
            continue
        js_files += 1
        try:
            findings.extend(scan_js_source(path.read_text(encoding="utf-8"), rel.as_posix()))
        except (UnicodeError, OSError):
            errors.append(rel.as_posix())
    confidential_violations = [
        entry for entry in findings if (
            (entry["file"].startswith("confidential/")
             and (entry["mechanism"].startswith("bedrock")
                  or entry["mechanism"].startswith("model-")
                  or entry["mechanism"] == "model-sdk-import"
                  or entry["mechanism"].startswith("network-")))
            or (entry["file"].startswith("static/confidential")
                and entry["mechanism"].startswith("js-risk-"))
        )
    ]
    return {
        "schema": "sec04-route-static-v2",
        "scope": "python-and-js-static-no-runtime-claim",
        "files_scanned": py_files + js_files,
        "python_files_scanned": py_files,
        "js_files_scanned": js_files,
        "routes": findings,
        "errors": errors,
        "confidential_violations": confidential_violations,
        "zk_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = scan_repo()
    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        print("SEC-04 routes=%d scanned=%d errors=%d confidential_violations=%d" %
              (len(report["routes"]), report["files_scanned"],
               len(report["errors"]), len(report["confidential_violations"])))
    return 1 if report["errors"] or report["confidential_violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
