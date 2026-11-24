"""Build store submission ZIPs; unsigned Firefox ZIP is not an installer."""
import json
import pathlib
import zipfile
import hashlib

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT.parent / "dist" / "browser"
OUT.mkdir(parents=True, exist_ok=True)
manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
files = [p for p in ROOT.rglob("*") if p.is_file() and (
    (p.parent == ROOT and p.suffix in {".js", ".html", ".css"}) or
    (p.relative_to(ROOT).parts[0] in {"ikony", "fonts"} and p.suffix in {".png", ".svg", ".woff2", ".woff", ".txt"})
)]
assert (ROOT / "panel.html") in files
for browser in ("chrome", "edge", "firefox"):
    m = json.loads(json.dumps(manifest))
    if browser == "firefox":
        m.pop("minimum_chrome_version", None)
        m.pop("side_panel", None)
        m["permissions"].remove("sidePanel")
        m["background"] = {"scripts": ["tlo.js"]}
        m["sidebar_action"] = {"default_title": "NotarAI", "default_panel": "panel.html", "open_at_install": False}
        m["browser_specific_settings"] = {"gecko": {"id": "notarai@notarai.pl", "strict_min_version": "142.0", "data_collection_permissions": {"required": ["authenticationInfo", "personallyIdentifyingInfo", "websiteContent", "browsingActivity"]}}}
    dest = OUT / f"notarai-{browser}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(m, ensure_ascii=False, indent=2))
        for p in sorted(files):
            z.write(p, p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        names = set(z.namelist())
        assert "manifest.json" in names and "panel.html" in names
        assert all(v in names for v in m["icons"].values())
        assert all(js in names for cs in m["content_scripts"] for js in cs["js"])
    print(dest.name, hashlib.sha256(dest.read_bytes()).hexdigest())
