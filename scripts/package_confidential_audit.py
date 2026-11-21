"""Package only the read-only synthetic DynamoDB Stream audit Lambda.

Deterministic ZIP bytes and SHA-256 filename, no credentials or customer files.
Usage:
  python scripts/package_confidential_audit.py --output /tmp/audit.zip
"""
from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    Path("confidential/__init__.py"),
    Path("confidential/event_journal.py"),
)


def package(output: Path) -> str:
    source = ROOT.resolve()
    output = output.resolve()
    if output.is_relative_to(source):
        raise ValueError("audit package must be emitted outside the repository")
    if not output.parent.is_dir():
        raise ValueError("output directory unavailable")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for relative in FILES:
            path = (source / relative).resolve(strict=True)
            if not path.is_relative_to(source) or not path.is_file():
                raise ValueError("invalid audit source file")
            info = zipfile.ZipInfo(str(relative).replace("\\", "/"))
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print("Audit package digest sha256:" + digest)
    print("Suggested immutable artifact key: confidential-audit/" + digest + ".zip")
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package(args.output)


if __name__ == "__main__":
    main()
