#!/usr/bin/env python3
"""Offline and read-only research catalog validation/search. No downloads or model calls."""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

LAB = Path(__file__).resolve().parents[1]
TRACKS = ("security", "sales", "research")
EVIDENCE = ("official_reference", "upstream_reference")


class CatalogError(ValueError):
    pass


def load_catalogs(root: Path = LAB) -> list[dict]:
    records = []
    seen = set()
    for track in TRACKS:
        file = root / "catalog" / f"{track}.json"
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CatalogError(f"cannot read {file}: {exc}") from exc
        if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("track") != track:
            raise CatalogError(f"bad catalog header: {file}")
        items = data.get("items")
        if not isinstance(items, list) or not items:
            raise CatalogError(f"catalog must contain entries: {track}")
        for row in items:
            if not isinstance(row, dict):
                raise CatalogError("entry is not an object")
            required = ("id", "name", "url", "purpose", "evidence", "license_review", "locally_tested", "review_status", "deployment")
            if any(field not in row for field in required):
                raise CatalogError(f"missing fields in {track}")
            if not all(isinstance(row[key], str) and row[key].strip() for key in ("id", "name", "url", "purpose", "evidence", "license_review", "review_status", "deployment")):
                raise CatalogError(f"invalid text fields in {track}")
            ident = row["id"]
            if not re.fullmatch(re.escape(track) + r"\.[0-9]{3}", ident) or ident in seen:
                raise CatalogError(f"invalid or duplicate id: {ident}")
            seen.add(ident)
            parsed = urlsplit(row["url"])
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise CatalogError(f"invalid URL: {ident}")
            if row["evidence"] not in EVIDENCE:
                raise CatalogError(f"unsupported evidence classification: {ident}")
            if row["license_review"] != "required" or row["locally_tested"] is not False:
                raise CatalogError(f"unjustified release/readiness claim: {ident}")
            if row["review_status"] != "candidate" or row["deployment"] != "not_integrated":
                raise CatalogError(f"invalid integration status: {ident}")
            records.append({**row, "track": track})
    return records


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    finder = sub.add_parser("list")
    finder.add_argument("--track", choices=TRACKS, default=None)
    finder.add_argument("--query", default=None)
    args = parser.parse_args(argv)
    try:
        rows = load_catalogs()
    except CatalogError as exc:
        print(f"CATALOG ERROR: {exc}", file=sys.stderr)
        return 2
    if args.cmd == "check":
        counts = {track: sum(x["track"] == track for x in rows) for track in TRACKS}
        print(json.dumps({"status": "valid", "count": len(rows), "by_track": counts}, ensure_ascii=False))
        return 0
    filtered = [x for x in rows if (args.track is None or x["track"] == args.track) and (not args.query or args.query.casefold() in (x["name"] + " " + x["purpose"]).casefold())]
    for item in filtered:
        print(f'{item["id"]}\t{item["name"]}\t{item["url"]}\t{item["purpose"]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
