"""Build the only synthetic artifact authorized for AWS staging. No external I/O."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from private_ai.synthetic import fixture_sha256, png_fixture  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    contents = png_fixture()
    digest = fixture_sha256()
    if not args.verify_only:
        path = ROOT / ".private-ai-build" / "synthetic-only.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        print("Fixture:", path)
    print("SHA-256 FixtureSha256:", digest)
    print("Synthetic-only fixture: geometric pattern, 512 x 384; no PII")


if __name__ == "__main__":
    main()
