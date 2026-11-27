"""Copy the Pocket page into a directory for static HTTPS hosting (e.g. notarai.pl/pocket/).

Run from v2/:  python tools/export_pocket.py <destination>
The page holds no data and no secrets: it only talks to the office through the encrypted tunnel.
"""
import re
import shutil
import sys
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "worker"
FILES = {"pocket.html": "index.html", "pocket.css": "pocket.css", "pocket.js": "pocket.js", "tunnel.js": "tunnel.js",
         "pocket-sw.js": "pocket-sw.js", "pocket.webmanifest": "pocket.webmanifest", "pocket-icon.svg": "pocket-icon.svg",
         "montserrat-latin.woff2": "montserrat-latin.woff2", "montserrat-latin-ext.woff2": "montserrat-latin-ext.woff2"}


def policy() -> str:
    """The same rules the workstation sends as a header, written into the page for hosts that set none.
    The relay is the only place the page may connect to."""
    import json

    preset = json.loads((WORKER.parent / "installer" / "preset.json").read_text(encoding="utf-8"))
    relay = re.match(r"wss://[^/]+", preset["tunnel"]["relay_url"]).group(0)
    return ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; manifest-src 'self'; "
            f"worker-src 'self'; connect-src 'self' {relay}; media-src 'self' blob:; base-uri 'none'; form-action 'none'")


def export(destination: Path) -> list[str]:
    destination.mkdir(parents=True, exist_ok=True)
    for source, target in FILES.items():
        shutil.copyfile(WORKER / source, destination / target)
    page = destination / "index.html"
    head = ('  <meta http-equiv="Content-Security-Policy" content="' + policy() + '">\n'
            '  <meta name="robots" content="noindex">\n  <meta name="referrer" content="no-referrer">\n')
    page.write_text(page.read_text(encoding="utf-8").replace('  <meta name="viewport"', head + '  <meta name="viewport"', 1),
                    encoding="utf-8")
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
