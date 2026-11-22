#!/usr/bin/env python3
"""Offline tool for the public transparency log of custodian-signed releases.

No AWS calls, no network, no secrets. Anyone can run `verify`:

    python scripts/confidential_transparency_log.py verify \
      --log transparency-log.json \
      --trusted-custodian-public-key custody-public.pem \
      --trusted-custodian-public-key-sha256 <FINGERPRINT_PINNED_OUT_OF_BAND> \
      [--previous-checkpoint my-earlier-checkpoint.json] \
      [--write-checkpoint my-new-checkpoint.json]

The public key and its fingerprint must reach the verifier by a channel the
NotarAI operator does not control. A fingerprint copied from NotarAI alone is
not independent evidence.

`append` adds one already signed release to a log file. It never signs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from confidential.transparency_log import (  # noqa: E402
    LogRejected, append_release, checkpoint, empty_log, load_json, verify_log,
)


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write_new(path: str, value: object) -> None:
    """Create the file; never overwrite existing evidence."""
    data = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(data)


def _keys(args) -> dict:
    return {args.trusted_custodian_public_key_sha256:
            Path(args.trusted_custodian_public_key).read_bytes()}


def run(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "append"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--log", required=True)
        cmd.add_argument("--trusted-custodian-public-key", required=True)
        cmd.add_argument("--trusted-custodian-public-key-sha256", required=True)
    sub.choices["verify"].add_argument("--previous-checkpoint")
    sub.choices["verify"].add_argument("--write-checkpoint")
    sub.choices["append"].add_argument("--release-file", required=True)
    sub.choices["append"].add_argument("--source-commit", required=True)
    sub.choices["append"].add_argument("--output", required=True)
    args = parser.parse_args(argv)

    keys = _keys(args)
    log = load_json(_read(args.log)) if Path(args.log).exists() else None
    if args.command == "verify":
        if log is None:
            raise LogRejected("log file not found")
        previous = (load_json(_read(args.previous_checkpoint))
                    if args.previous_checkpoint else None)
        report = verify_log(log, trusted_keys=keys, previous_checkpoint=previous)
        if args.write_checkpoint:
            _write_new(args.write_checkpoint, checkpoint(report))
        return report

    extended = append_release(
        log if log is not None else empty_log(),
        release=load_json(_read(args.release_file)),
        source_commit=args.source_commit,
        custody_public_key_sha256=args.trusted_custodian_public_key_sha256,
        recorded_at=datetime.now(timezone.utc),
        trusted_keys=keys,
    )
    _write_new(args.output, extended)
    return verify_log(extended, trusted_keys=keys)


def main() -> int:
    try:
        report = run()
    except (LogRejected, OSError) as problem:
        print(json.dumps({"verified": False, "reason": str(problem)}))
        return 1
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
