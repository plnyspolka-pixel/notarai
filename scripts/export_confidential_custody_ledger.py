"""SEC-06: safe, paginated READ-ONLY export of synthetic custody ledger.

Default is dry-run (zero AWS calls). With explicit --check, use ONLY an
independently controlled read-only custodian identity. No DynamoDB writes,
KMS calls, Decrypt, GitHub Actions credentials or automatic production access.

This is a CONSISTENT table read, not an atomic whole-history snapshot:
we read STATE, query EVENT records, and read STATE again; any observed
change is a hard denial. Out-of-band trust-root and anchor validation is
performed separately by confidential/custody_history.py.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidential.custody_cas import _TABLE
from confidential.operator_boundary import BoundaryDenied, canonical_digest

_REGION = "eu-central-1"
_TENANT = re.compile(r"pilot0[12]\Z")
_MAX_PAGES = 200
_MAX_EVENTS = 10000


def _require(value: bool, message: str) -> None:
    if not value:
        raise BoundaryDenied(message)


def _get_state(ddb, table: str, partition: str) -> dict:
    try:
        result = ddb.get_item(
            TableName=table, Key={
                "tenant": {"S": partition},
                "record": {"S": "STATE"},
            },
            ConsistentRead=True)
    except Exception:
        raise BoundaryDenied("custody ledger state inaccessible") from None
    item = result.get("Item") if isinstance(result, dict) else None
    _require(isinstance(item, dict) and item,
             "custody state missing or ledger read incomplete")
    return item


def fetch_ledger(*, tenant: str, ledger_table_arn: str,
                 custody_profile: str, check: bool = False,
                 session_factory=None) -> dict:
    """Read-only, strongly consistent base-table export, never live proof."""
    _require(isinstance(tenant, str) and _TENANT.fullmatch(tenant) is not None,
             "synthetic tenant required")
    match = (_TABLE.fullmatch(ledger_table_arn)
             if isinstance(ledger_table_arn, str) else None)
    _require(match is not None, "custody ledger must be EU pilot table ARN")
    _require(isinstance(custody_profile, str) and bool(custody_profile),
             "independent custodian AWS profile required")
    if not check:
        return {
            "status": "BLOCKED", "mode": "dry-run", "aws_calls": 0,
            "event_items": [], "state_item": None,
            "independent_custody_verified": False,
            "history_integrity_verified": False,
        }
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    try:
        session = session_factory(
            profile_name=custody_profile, region_name=_REGION)
        caller = session.client("sts").get_caller_identity()
        _require(isinstance(caller, dict) and
                 caller.get("Account") == match.group(1),
                 "custody ledger must be read from custody account")
        ddb = session.client("dynamodb")
    except BoundaryDenied:
        raise
    except Exception:
        raise BoundaryDenied("independent custodian identity unavailable") from None

    partition = "TENANT#" + tenant
    before = _get_state(ddb, ledger_table_arn, partition)
    event_items = []
    markers = set()
    marker = None
    page_count = 0

    for _ in range(_MAX_PAGES):
        args = {
            "TableName": ledger_table_arn,
            "KeyConditionExpression": "#tenant = :tenant AND begins_with(#record, :prefix)",
            "ExpressionAttributeNames": {
                "#tenant": "tenant", "#record": "record",
            },
            "ExpressionAttributeValues": {
                ":tenant": {"S": partition}, ":prefix": {"S": "EVENT#"},
            },
            "ConsistentRead": True,
            "ScanIndexForward": True,
            "Limit": 100,
        }
        if marker is not None:
            args["ExclusiveStartKey"] = marker
        try:
            page = ddb.query(**args)
        except Exception:
            raise BoundaryDenied("custody ledger event pagination inaccessible") from None
        _require(isinstance(page, dict) and isinstance(page.get("Items"), list),
                 "custody ledger query response incomplete")
        items = page["Items"]
        _require(type(page.get("Count")) is int and
                 page["Count"] == len(items),
                 "custody ledger query page count mismatch")
        event_items.extend(items)
        _require(len(event_items) <= _MAX_EVENTS,
                 "custody ledger event count exceeds audit budget")
        page_count += 1
        next_marker = page.get("LastEvaluatedKey")
        if next_marker in (None, {}):
            break
        _require(isinstance(next_marker, dict) and
                 set(next_marker) == {"tenant", "record"} and
                 next_marker["tenant"] == {"S": partition} and
                 isinstance(next_marker["record"], dict) and
                 isinstance(next_marker["record"].get("S"), str) and
                 next_marker["record"]["S"].startswith("EVENT#"),
                 "custody event pagination marker invalid")
        signature = canonical_digest(next_marker)
        _require(signature not in markers,
                 "custody event pagination marker repeated")
        markers.add(signature)
        marker = next_marker
    else:
        raise BoundaryDenied("custody event pagination cap exceeded")

    after = _get_state(ddb, ledger_table_arn, partition)
    _require(before == after,
             "custody state changed during historical read")
    _require(bool(event_items),
             "custody event history empty: cannot establish provenance")
    return {
        "schema": "notarai.confidential.custody-ledger-export.v1",
        "status": "BLOCKED",
        "tenant": tenant,
        "state_item": after,
        "event_items": event_items,
        "event_pages_read": page_count,
        "aws_calls": 3 + page_count,
        "history_integrity_verified": False,
        "snapshot_atomic": False,
        "ledger_export_exhaustiveness_proven": False,
        "independent_custody_verified": False,
        "read_only": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True, choices=("pilot01", "pilot02"))
    parser.add_argument("--ledger-table-arn", required=True)
    parser.add_argument("--custody-profile", required=True)
    parser.add_argument("--check", action="store_true",
                        help="Explicitly call read-only STS, DynamoDB GetItem/Query")
    parser.add_argument("--output", required=True,
                        help="Create-only local export, mode 0600; never stdout contents")
    args = parser.parse_args(argv)
    try:
        snapshot = fetch_ledger(
            tenant=args.tenant, ledger_table_arn=args.ledger_table_arn,
            custody_profile=args.custody_profile, check=args.check)
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                     0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # Accept only strict offline replay-compatible shape.
            json.dump({
                "state_item": snapshot["state_item"],
                "event_items": snapshot["event_items"],
            }, f, sort_keys=True, indent=2)
            f.write("\n")
    except (OSError, BoundaryDenied) as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": str(exc) if isinstance(
                exc, BoundaryDenied) else "custody ledger export unavailable",
            "aws_calls": "0 or read-only",
        }))
        return 2
    print(json.dumps({
        "status": "BLOCKED", "read_only": True,
        "event_count": len(snapshot["event_items"]),
        "independent_custody_verified": False,
        "history_integrity_verified": False,
    }))
    return 3 if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
