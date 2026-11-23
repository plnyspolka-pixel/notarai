"""Deterministyczne pliki do strony notarai.pl/do-pobrania.

Budowanie podczas publikacji strony (nie umieszczamy ZIP/OXT w Git).
Nie pakuje testów, README, źródeł deweloperskich ani EXE.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "strona" / "do-pobrania" / "pliki"
BROWSER_FILES = (
    "manifest.json", "tlo.js", "panel.html", "panel.css", "panel.js",
    "silnik.js", "strona.js", "notarai.js", "krz.js", "formularz.js",
    "ikony/16.png", "ikony/48.png", "ikony/128.png", "ikony/notarai.svg",
    "fonts/montserrat-latin-wght-normal.woff2",
)
OPENOFFICE_FILES = (
    "description.xml", "Addons.xcu", "META-INF/manifest.xml",
    "package/notarai.py",
)


def archive(target: Path, base: Path, paths: tuple[str, ...]) -> None:
    with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for name in paths:
            source = base / name
            if not source.is_file():
                raise FileNotFoundError(source)
            entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            bundle.writestr(entry, source.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)


def build(output: Path = OUTPUT, root: Path = ROOT) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True)
    browser = root / "rozszerzenie"
    manifest = json.loads((browser / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != 3:
        raise ValueError("Wymagany Chromium Manifest V3")
    if "https://app.notarai.pl/*" not in manifest.get("host_permissions", []):
        raise ValueError("Nieznany adres główny rozszerzenia")
    for target in ("notarai-chrome.zip", "notarai-edge.zip"):
        archive(output / target, browser, BROWSER_FILES)
    archive(output / "notarai-openoffice.oxt", root / "dodatki" / "openoffice", OPENOFFICE_FILES)
    shutil.copyfile(root / "dodatki" / "word" / "manifest.xml", output / "notarai-word.xml")
    names = ("notarai-word.xml", "notarai-openoffice.oxt", "notarai-chrome.zip", "notarai-edge.zip")
    checksums = {n: hashlib.sha256((output / n).read_bytes()).hexdigest() for n in names}
    (output / "SHA256SUMS.txt").write_text(
        "".join(f"{checksums[name]}  {name}\n" for name in names),
        encoding="utf-8",
    )
    return checksums


if __name__ == "__main__":
    for name, digest in build().items():
        print(f"{digest}  {name}")