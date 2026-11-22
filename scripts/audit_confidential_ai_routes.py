"""SEC-04 static AI-route inventory. Best-effort, NOT runtime dataflow proof.

Scans Python AST for model SDK/HTTP execution. CI fails on new direct model
calls inside confidential/ instead of treating tests/docs as an allowlist.
Only outputs file paths, line numbers and mechanism names (never source lines).
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SKIP = frozenset({".git", ".venv", "venv", "node_modules", "dane", "__pycache__"})
_MODEL_IMPORTS = frozenset({
    "anthropic", "openai", "google.generativeai", "google.genai", "langchain",
    "langchain_openai", "langchain_anthropic",
})
_NETWORK_CALLS = frozenset({
    "requests.post", "httpx.post", "urllib.request.urlopen",
    "http.client.HTTPConnection", "http.client.HTTPSConnection",
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


def scan_repo(root: Path = _ROOT) -> dict:
    files = 0
    findings = []
    errors = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in _SKIP for part in rel.parts) or path.name.startswith("test_"):
            continue
        files += 1
        try:
            findings.extend(scan_source(path.read_text(encoding="utf-8"), rel.as_posix()))
        except (SyntaxError, UnicodeError, OSError):
            errors.append(rel.as_posix())
    confidential_violations = [
        entry for entry in findings if entry["file"].startswith("confidential/")
        and (entry["mechanism"].startswith("bedrock")
             or entry["mechanism"].startswith("model-")
             or entry["mechanism"] == "model-sdk-import"
             or entry["mechanism"].startswith("network-"))
    ]
    return {
        "schema": "sec04-route-static-v1",
        "scope": "python-only-static-no-runtime-claim",
        "files_scanned": files,
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
