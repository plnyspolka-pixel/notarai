#!/usr/bin/env python3
"""Build deterministic Chrome and Edge ZIPs from one NotarAI extension source."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "rozszerzenie"
SUFFIXES = {".js", ".json", ".html", ".css", ".png", ".svg", ".woff2"}
SKIP_DIRS = {"testy", "node_modules", "__pycache__", ".git", ".venv"}
SKIP_NAMES = {"package.json", "package-lock.json"}
REQUIRED = {
    "manifest.json", "panel.html", "panel.js", "panel.css",
    "tlo.js", "silnik.js", "strona.js", "notarai.js",
    "krz.js", "formularz.js", "ikony/16.png", "ikony/48.png",
    "ikony/128.png", "ikony/notarai.svg",
    "fonts/montserrat-latin-wght-normal.woff2",
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "extensions")
    output = parser.parse_args().out
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != 3:
        raise ValueError("Manifest V3 required")
    if manifest.get("update_url"):
        raise ValueError("Remove Chrome store update_url before Edge submission")
    if "<all_urls>" in manifest.get("host_permissions", []):
        raise ValueError("Unexpected permanent all-URLs permission")
    version = str(manifest["version"])
    if not version or any(c not in "0123456789." for c in version):
        raise ValueError("Invalid extension version")
    files = []
    for path in SOURCE.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(SOURCE)
        if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts):
            continue
        if rel.name in SKIP_NAMES or rel.suffix not in SUFFIXES:
            continue
        files.append(rel)
    files.sort(key=lambda p: p.as_posix())
    missing = REQUIRED - {p.as_posix() for p in files}
    if missing:
        raise ValueError("Missing runtime files: " + ", ".join(sorted(missing)))
    output.mkdir(parents=True, exist_ok=True)
    for browser in ("chrome", "edge"):
        archive = output / f"NotarAI-{browser}-{version}.zip"
        with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=9) as z:
            for rel in files:
                info = ZipInfo(rel.as_posix(), (1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, (SOURCE / rel).read_bytes())
        with ZipFile(archive) as z:
            assert "manifest.json" in z.namelist()
            assert z.testzip() is None
        print(f"Built {archive} ({len(files)} runtime files)")
if __name__ == "__main__":
    main()
