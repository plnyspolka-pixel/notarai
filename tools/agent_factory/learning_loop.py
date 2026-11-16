"""Evidence-gated dataset preparation for QLoRA/LoRA worker specialization.

No model training, code execution, or network. Only synthetic examples approved
by an independent human reviewer and independently HMAC-signed verifier are
eligible. A model's self-reported success is NEVER training evidence.
"""
from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re

from tools.agent_factory.worker_pool import SECRET, WorkerPolicyError, ROLES, _safe_text

HEX40 = re.compile(r"[a-f0-9]{40}\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
TASK_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
SCHEMA = {
    "schema_version", "task_id", "task_family", "role",
    "instruction", "context", "accepted_answer", "base_commit",
    "verifier_name", "verifier_passed", "reviewer_approved",
    "candidate_sha256", "data_class", "signature"
}


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode()


def signature(record: dict, key: bytes) -> str:
    """For an INDEPENDENT grader to call; do not expose the key to workers."""
    if len(key) < 32:
        raise WorkerPolicyError("independent evidence signing key is too short")
    payload = {k: v for k, v in record.items() if k != "signature"}
    return hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()


def verify_record(row: object, key: bytes) -> dict:
    if not isinstance(row, dict) or set(row) != SCHEMA:
        raise WorkerPolicyError("unexpected evidence schema")
    if row["schema_version"] != 1:
        raise WorkerPolicyError("unsupported evidence schema version")
    for name in ("task_id", "task_family"):
        if not isinstance(row[name], str) or not TASK_NAME.fullmatch(row[name]):
            raise WorkerPolicyError("invalid task identity or family")
    if row["role"] not in ROLES:
        raise WorkerPolicyError("invalid worker role")
    if row["data_class"] != "synthetic":
        raise WorkerPolicyError("only synthetic material may be used for training")
    if row["verifier_passed"] is not True or row["reviewer_approved"] is not True:
        raise WorkerPolicyError("training requires independent success and approval")
    if row["verifier_name"] != "external-isolated-verifier":
        raise WorkerPolicyError("untrusted verifier")
    if (not isinstance(row["base_commit"], str) or not HEX40.fullmatch(row["base_commit"])
            or not isinstance(row["candidate_sha256"], str)
            or not HEX64.fullmatch(row["candidate_sha256"])):
        raise WorkerPolicyError("invalid content/version evidence")
    for name, size in (("instruction", 4000), ("context", 12000),
                       ("accepted_answer", 24000)):
        _safe_text(row[name], name, size)
    if hashlib.sha256(row["accepted_answer"].encode()).hexdigest() != row["candidate_sha256"]:
        raise WorkerPolicyError("accepted answer does not match verified candidate digest")
    if not isinstance(row["signature"], str) or not HEX64.fullmatch(row["signature"]):
        raise WorkerPolicyError("missing signature")
    expected = signature(row, key)
    if not hmac.compare_digest(expected, row["signature"]):
        raise WorkerPolicyError("evidence signature invalid")
    return row


def read_records(file: Path) -> list[dict]:
    file = Path(file)
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 6_000_000:
        raise WorkerPolicyError("missing or oversized evidence file")
    lines = file.read_text(encoding="utf-8").splitlines()
    if not 1 <= len(lines) <= 3000:
        raise WorkerPolicyError("evidence must contain 1..3000 rows")
    result = []
    for line in lines:
        if len(line) > 45000:
            raise WorkerPolicyError("oversized evidence row")
        result.append(json.loads(line))
    return result


def export_training_data(input_path: Path, out_dir: Path, key: bytes,
                         *, min_examples: int = 20,
                         min_families: int = 5) -> dict:
    """Create train/holdout splits grouped by task_family; refuse existing output."""
    raw = read_records(input_path)
    rows = [verify_record(item, key) for item in raw]
    if len(rows) < min_examples:
        raise WorkerPolicyError("insufficient verified examples")
    seen = set()
    for row in rows:
        dedupe = (row["task_id"], row["base_commit"], row["role"])
        if dedupe in seen:
            raise WorkerPolicyError("duplicate task+commit+role")
        seen.add(dedupe)
    families = sorted({r["task_family"] for r in rows},
                      key=lambda x: hashlib.sha256(x.encode()).hexdigest())
    if len(families) < min_families or len(families) < 2:
        raise WorkerPolicyError("insufficient independent families for holdout")
    holdout_families = set(families[:max(1, len(families) // 5)])
    train = [r for r in rows if r["task_family"] not in holdout_families]
    holdout = [r for r in rows if r["task_family"] in holdout_families]
    if not train or not holdout:
        raise WorkerPolicyError("empty train/holdout split")
    output = Path(out_dir).expanduser().resolve()
    if output.exists():
        raise WorkerPolicyError("refusing overwrite of an existing training dataset")
    if Path(out_dir).is_symlink():
        raise WorkerPolicyError("dataset destination symlink forbidden")
    output.mkdir(parents=True, mode=0o700)
    def save(name: str, examples: list[dict]) -> str:
        dest = output / name
        with dest.open("x", encoding="utf-8") as handle:
            for item in sorted(examples, key=lambda r: (r["task_family"], r["task_id"])):
                message = {
                    "messages": [
                        {"role": "system", "content": "You are a low-cost coding worker. "
                         "Follow the senior engineer's scoped task precisely. "
                         "Do not invent verification results."},
                        {"role": "user", "content": item["instruction"] + "\n\n" + item["context"]},
                        {"role": "assistant", "content": item["accepted_answer"]}
                    ],
                    "task_family": item["task_family"], "role": item["role"]
                }
                handle.write(json.dumps(message, ensure_ascii=False) + "\n")
        os.chmod(dest, 0o600)
        return hashlib.sha256(dest.read_bytes()).hexdigest()
    train_sha = save("train.jsonl", train)
    holdout_sha = save("holdout.jsonl", holdout)
    report = {
        "status": "VERIFIED_SYNTHETIC_EXPORT_NOT_TRAINED",
        "examples": len(rows), "train": len(train), "holdout": len(holdout),
        "families": len(families), "holdout_families": sorted(holdout_families),
        "train_sha256": train_sha, "holdout_sha256": holdout_sha,
        "role_distribution": dict(Counter(r["role"] for r in rows)),
        "restrictions": "No real customer data; model training not run"
    }
    (output / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(output / "manifest.json", 0o600)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HMAC-evidence gated training data export")
    parser.add_argument("evidence", type=Path)
    parser.add_argument("out", type=Path)
    opts = parser.parse_args(argv)
    key = os.environ.get("AGENT_FORGE_INDEPENDENT_EVIDENCE_KEY", "").encode()
    if len(key) < 32:
        print("BLOCKED: no independent verifier signing key configured")
        return 2
    try:
        result = export_training_data(opts.evidence, opts.out, key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (WorkerPolicyError, ValueError, OSError, KeyError, TypeError) as exc:
        print("BLOCKED:", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
