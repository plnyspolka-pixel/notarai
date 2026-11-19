"""Build a minimal, auditable Lambda ZIP locally. Never deploy automatically."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / ".private-ai-build" / "pilot-lambda.zip"
SOURCES = (
    "private_ai/__init__.py", "private_ai/policy.py",
    "private_ai/gateway.py", "private_ai/evidence.py",
    "private_ai/ingress.py", "private_ai/lambda_entry.py",
)


def main():
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(DEST, "w", compression=ZIP_DEFLATED) as z:
        for name in SOURCES:
            z.write(ROOT / name, arcname=name)
    print("Generated locally:", DEST)


if __name__ == "__main__":
    main()
