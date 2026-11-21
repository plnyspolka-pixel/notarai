"""Create a reproducible deployable Python Lambda zip; NEVER deploy it.

python scripts/package_confidential_dispatch.py --output /tmp/notarai-dispatch.zip
Then a separate authorized operator uploads the ZIP to a versioned EU S3
artifact bucket and deploys the DISABLED CloudFormation stack.
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "confidential/__init__.py",
    "confidential/dispatch.py",
    "confidential/dispatch_lambda.py",
)


def package(output: Path) -> str:
    output = output.expanduser().resolve()
    if output.suffix.lower() != ".zip":
        raise ValueError("output must be a ZIP path")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCES:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (ROOT / name).read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = package(args.output)
    print("Dispatcher Lambda ZIP packaged, sha256=" + digest)
    print("No AWS resources created or changed.")


if __name__ == "__main__":
    main()
