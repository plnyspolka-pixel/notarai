"""Copy the Pocket page into a directory for static HTTPS hosting (e.g. notarai.pl/pocket/).

Run from v2/:  python tools/export_pocket.py <destination>
The page holds no data and no secrets: it only talks to the office through the encrypted tunnel.
"""
import shutil
import sys
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "worker"
FILES = {"pocket.html": "index.html", "pocket.css": "pocket.css", "pocket.js": "pocket.js", "tunnel.js": "tunnel.js",
         "pocket-sw.js": "pocket-sw.js", "pocket.webmanifest": "pocket.webmanifest", "pocket-icon.svg": "pocket-icon.svg"}


def export(destination: Path) -> list[str]:
    destination.mkdir(parents=True, exist_ok=True)
    for source, target in FILES.items():
        shutil.copyfile(WORKER / source, destination / target)
    # Served as a directory index, so the app starts at "./" instead of "pocket".
    manifest = destination / "pocket.webmanifest"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('"start_url": "pocket"', '"start_url": "./"'),
                        encoding="utf-8")
    worker = destination / "pocket-sw.js"
    worker.write_text(worker.read_text(encoding="utf-8").replace('const FILES = ["pocket", ', 'const FILES = ["./", '),
                      encoding="utf-8")
    return sorted(FILES.values())


if __name__ == "__main__":
    print("\n".join(export(Path(sys.argv[1]))))
