"""Paczka funkcji notarai-v2-rejestry: ekw.py i walidacja.py z V1 bez zmian + handler + httpx."""
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def build(output: Path) -> Path:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--target", str(root), "--no-compile",
                        "--only-binary=:all:", "--platform", "manylinux2014_x86_64", "--python-version", "3.13",
                        "httpx==0.28.1"], check=True)
        for name in ("ekw.py", "walidacja.py"):
            shutil.copy(REPO / name, root / name)
        for name in ("config.py", "rejestry.py"):
            shutil.copy(HERE / "shim" / name, root / name)
        shutil.copy(HERE / "handler.py", root / "handler.py")
        data = Path(scratch + ".zip")
        with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    info = zipfile.ZipInfo(str(path.relative_to(root)), date_time=(2026, 1, 1, 0, 0, 0))
                    info.external_attr = 0o644 << 16
                    archive.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED)
        digest = hashlib.sha256(data.read_bytes()).hexdigest()[:12]
        target = output / f"rejestry-{digest}.zip"
        shutil.move(data, target)
        return target


if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
