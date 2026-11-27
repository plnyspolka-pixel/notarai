"""Small updates of the program code, without the big installer.

The full installer carries Python and the libraries (about 140 MB) and is needed only on a new computer
or when the libraries change. Every other release is a code package of a few hundred kilobytes:
`aktualizacja.json` (version, size, SHA-256, library fingerprint) and the zip it names, both on the
NotarAI download address. The worker checks it now and then, downloads a newer package, verifies
size and SHA-256, unpacks it next to the program and the launcher swaps it in at the next start.
No document leaves the computer; the request carries no data about the office.
"""
import hashlib
import io
import json
import re
import shutil
import threading
import time
import zipfile
from pathlib import Path

MANIFEST_URL = "https://daw6bv5zhb6ck.cloudfront.net/aktualizacja.json"
ALLOWED_TOP = {"worker", "launch.py", "preview_instance.py", "apply_update.py", "preset.json", "wersja.json"}
MAX_PACKAGE = 30 * 2**20


class UpdateError(Exception):
    """Fixed Polish message, safe to show."""


def version_tuple(text: str) -> tuple:
    if not re.fullmatch(r"\d{1,4}(\.\d{1,4}){1,3}", str(text)):
        raise ValueError("bad version")
    return tuple(int(part) for part in text.split("."))


def installed(app_dir: Path) -> dict | None:
    """{"version", "runtime"} of the installed program; None when not running from an installation."""
    try:
        data = json.loads((Path(app_dir) / "wersja.json").read_text(encoding="utf-8"))
        version_tuple(data["version"])
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _http_get(url: str, limit: int) -> bytes:
    import httpx

    with httpx.Client(timeout=30, follow_redirects=False) as client:
        with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise UpdateError("Serwer aktualizacji nie odpowiada. Spróbuję później.")
            body = bytearray()
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > limit:
                    raise UpdateError("Paczka aktualizacji jest za duża; nie instaluję jej.")
            return bytes(body)


class Updater:
    def __init__(self, app_dir: Path, manifest_url: str = MANIFEST_URL, *, fetch=_http_get, clock=time.time):
        self._app = Path(app_dir)
        self._url = manifest_url
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self.staging = self._app / "aktualizacja"
        self.state = {"checked": None, "available": None, "ready": self.ready_version(), "error": None,
                      "full_installer": False}

    @property
    def current(self) -> dict | None:
        return installed(self._app)

    def ready_version(self) -> str | None:
        try:
            return json.loads((self.staging / "gotowa.json").read_text(encoding="utf-8"))["version"]
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def check(self, *, download: bool = True) -> dict:
        """Look for a newer package; with `download`, fetch, verify and stage it. Returns the state."""
        current = self.current
        if current is None:
            return {**self.state, "error": "Ta kopia programu nie jest zainstalowana instalatorem; aktualizacje są wyłączone."}
        with self._lock:
            self.state["checked"] = self._clock()
            try:
                manifest = json.loads(self._fetch(self._url, 64 * 1024))
                offered = str(manifest["version"])
                if version_tuple(offered) <= version_tuple(current["version"]):
                    self.state.update(available=None, error=None, full_installer=False)
                    return dict(self.state)
                self.state["available"] = offered
                if manifest.get("runtime") != current.get("runtime"):
                    # New libraries: only the full installer can bring them.
                    self.state.update(full_installer=True, error=None)
                    return dict(self.state)
                self.state["full_installer"] = False
                if download and self.ready_version() != offered:
                    self._stage(manifest)
                self.state.update(ready=self.ready_version(), error=None)
            except UpdateError as error:
                self.state["error"] = str(error)
            except Exception:
                self.state["error"] = "Nie udało się sprawdzić aktualizacji. Spróbuję później."
            return dict(self.state)

    def _stage(self, manifest: dict) -> None:
        name, size, digest = str(manifest["file"]), int(manifest["size"]), str(manifest["sha256"]).lower()
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}\.zip", name) or not 0 < size <= MAX_PACKAGE \
                or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise UpdateError("Opis aktualizacji jest nieprawidłowy; nie instaluję jej.")
        package = self._fetch(self._url.rsplit("/", 1)[0] + "/" + name, MAX_PACKAGE)
        if len(package) != size or hashlib.sha256(package).hexdigest() != digest:
            raise UpdateError("Pobrana aktualizacja ma złą sumę kontrolną; nie instaluję jej.")
        unpacked = self.staging / "nowa"
        shutil.rmtree(self.staging, ignore_errors=True)
        unpacked.mkdir(parents=True)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            for entry in archive.infolist():
                parts = Path(entry.filename).parts
                if not parts or parts[0] not in ALLOWED_TOP or ".." in parts or entry.filename.startswith(("/", "\\")) \
                        or ":" in entry.filename:
                    raise UpdateError("Paczka aktualizacji zawiera nieoczekiwane pliki; nie instaluję jej.")
            archive.extractall(unpacked)
        packaged = installed(unpacked)
        if packaged is None or packaged["version"] != manifest["version"] or not (unpacked / "worker").is_dir():
            shutil.rmtree(self.staging, ignore_errors=True)
            raise UpdateError("Paczka aktualizacji jest niekompletna; nie instaluję jej.")
        (self.staging / "gotowa.json").write_text(json.dumps({"version": manifest["version"]}), encoding="utf-8")
