#!/usr/bin/env python3
"""Read-only SEC-11 archive history inspection from independent custodian account.

Receipt JSON must be obtained out-of-band from independent custody:
[{"sequence":1, "version_id":"..."}, ...] with no gaps or extra fields.
Never use a receipt reconstructed by querying the present S3 latest view.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from confidential.archive_history import audit_archive_history


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--custody-account", required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--tenant", required=True)
    p.add_argument("--independent-receipt-json", required=True, type=Path)
    p.add_argument("--custody-auditor-profile", required=True)
    p.add_argument("--run-read-only", action="store_true")
    args = p.parse_args(argv)
    if not args.run_read_only:
        print(json.dumps({
            "inventory_integrity": "UNVERIFIED",
            "assurance_status": "BLOCKED",
            "zero_operator_access_proven": False,
        }, sort_keys=True))
        return 4
    try:
        path = args.independent_receipt_json
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("invalid independent receipt file")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("invalid independent receipt")
        entries = []
        for row in raw:
            if not isinstance(row, dict) or set(row) != {"sequence", "version_id"}:
                raise ValueError("invalid receipt entry")
            entries.append((row["sequence"], row["version_id"]))
        import boto3
        session = boto3.Session(
            profile_name=args.custody_auditor_profile, region_name="eu-central-1"
        )
        report = audit_archive_history(
            session=session, custody_account=args.custody_account,
            bucket=args.bucket, tenant=args.tenant,
            expected_versions=tuple(entries),
        )
    except Exception:
        report = {
            "inventory_integrity": "BLOCKED",
            "assurance_status": "BLOCKED",
            "zero_operator_access_proven": False,
        }
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 2 if report["inventory_integrity"] == "FAIL" else 4


if __name__ == "__main__":
    raise SystemExit(main())
