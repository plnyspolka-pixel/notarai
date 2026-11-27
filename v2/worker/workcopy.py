"""Edit a vault document in Word or LibreOffice on this computer.

Check-out writes one working copy into the user's private profile and opens it in the
default application. Check-in stores the edited file as the next revision, only if nobody
saved a newer revision in the meantime, and removes the working copy. While a working
copy exists the document is plaintext on this disk; the panel lists such copies so none
is forgotten.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .vault import MAX_BYTES, Conflict, Vault

EDITABLE = (".docx", ".doc", ".odt", ".rtf", ".txt", ".xlsx", ".pdf")
_LOCKS = ("~$", ".~lock.")      # Word and LibreOffice lock files: the document is still open


class WorkCopyError(Exception):
    """Fixed message, safe to show."""


def _safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "dokument"
    stem = name.rsplit(".", 1)[0]
    if name.startswith(_LOCKS):       # would look like an editor lock file and block check-in forever
        name = "_" + name
    if stem.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        name = "_" + name
    return name[:120]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def open_in_default_app(path: Path) -> None:
    if os.name == "nt":
        os.startfile(path)  # noqa: S606 - a file we created, opened by its registered application
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class WorkCopies:
    def __init__(self, home: Path, vault: Vault, opener=open_in_default_app):
        self._root, self._vault, self._open = Path(home) / "workcopies", vault, opener

    def _folder(self, doc_id: str) -> Path:
        try:
            return self._root / str(uuid.UUID(doc_id))      # one folder per document, whatever the spelling
        except (ValueError, AttributeError, TypeError):
            raise WorkCopyError("Nie ma takiego dokumentu.") from None

    def _state(self, doc_id: str) -> dict:
        try:
            return json.loads((self._folder(doc_id) / "state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise WorkCopyError("Ten dokument nie jest otwarty do edycji.") from None

    def checkout(self, doc_id: str, actor: str = "local-admin") -> dict:
        try:
            version, name, data = self._vault.get(doc_id, actor=actor)
        except (KeyError, ValueError):
            raise WorkCopyError("Nie ma takiego dokumentu.") from None
        if not name.lower().endswith(EDITABLE):
            raise WorkCopyError("Tego rodzaju pliku nie otwieramy do edycji. Pobierz go i wgraj nową wersję.")
        folder = self._folder(doc_id)
        if folder.exists():
            raise WorkCopyError("Ten dokument jest już otwarty do edycji. Zapisz go do sejfu albo porzuć zmiany.")
        folder.mkdir(mode=0o700, parents=True)
        path = folder / _safe_name(name)
        state = {"id": folder.name, "version": version, "name": name, "file": path.name,
                 "sha256": hashlib.sha256(data).hexdigest(), "opened": int(time.time())}
        try:
            # The record first, the plaintext second: a copy on disk is always listed and removable.
            (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as file:
                file.write(data)
        except OSError:
            self._remove(folder.name)
            raise WorkCopyError("Nie udało się zapisać kopii roboczej na dysku.") from None
        self._vault.log(actor, "checkout", doc_id, version)
        try:
            self._open(path)
        except OSError:
            pass        # the panel shows the path; the notary can open it by hand
        return self._describe(state)

    def _describe(self, state: dict) -> dict:
        folder = self._folder(state["id"])
        path = folder / state["file"]
        exists = path.is_file()
        return {
            "id": state["id"], "name": state["name"], "version": state["version"], "opened": state["opened"],
            "path": str(path), "missing": not exists,
            "changed": exists and _digest(path) != state["sha256"],
            "in_use": any(p.name.startswith(_LOCKS) and p.name != state["file"] for p in folder.iterdir()),
        }

    def list(self) -> list[dict]:
        if not self._root.is_dir():
            return []
        result = []
        for folder in sorted(self._root.iterdir()):
            try:
                result.append(self._describe(self._state(folder.name)))
            except WorkCopyError:
                continue
        return result

    def checkin(self, doc_id: str, actor: str = "local-admin") -> dict:
        state = self._state(doc_id)
        info = self._describe(state)
        path = Path(info["path"])
        if info["missing"]:
            raise WorkCopyError("Plik roboczy zniknął. Porzuć edycję i otwórz dokument ponownie.")
        if info["in_use"]:
            raise WorkCopyError("Zamknij dokument w edytorze, a potem zapisz go do sejfu.")
        if not info["changed"]:
            self._remove(doc_id)
            return {"id": state["id"], "version": state["version"], "saved": False}
        if path.stat().st_size > MAX_BYTES:
            raise WorkCopyError("Plik przekracza 20 MiB.")
        try:
            _, version = self._vault.put(state["id"], state["version"], state["name"], path.read_bytes(), actor=actor)
        except Conflict:
            # Keep the working copy: the notary decides what to do with both versions.
            raise WorkCopyError("W sejfie jest już nowsza wersja tego dokumentu. Twoja kopia robocza została "
                                "zachowana; zapisz ją w edytorze pod inną nazwą i wgraj jako nowy dokument.") from None
        try:
            self._remove(doc_id)
        except WorkCopyError:
            pass        # the revision is safely stored; the leftover copy stays listed in the panel
        return {"id": state["id"], "version": version, "saved": True}

    def discard(self, doc_id: str, actor: str = "local-admin") -> None:
        state = self._state(doc_id)
        if self._describe(state)["in_use"]:
            raise WorkCopyError("Zamknij dokument w edytorze, zanim porzucisz zmiany.")
        self._remove(doc_id)
        self._vault.log(actor, "discard-workcopy", state["id"], state["version"])

    def _remove(self, doc_id: str) -> None:
        folder = self._folder(doc_id)
        if not folder.is_dir():
            return
        files = sorted(folder.iterdir(), key=lambda p: p.name == "state.json")     # the record goes last
        try:
            for path in files:
                if path.is_file() and path.name != "state.json":
                    try:    # best effort: overwrite before unlinking; SSDs may still keep old blocks
                        with path.open("r+b") as file:
                            file.write(b"\x00" * path.stat().st_size)
                            file.flush()
                            os.fsync(file.fileno())
                    except OSError:
                        pass
                path.unlink(missing_ok=True)
            folder.rmdir()
        except OSError:
            # Typically a viewer still holding the file on Windows; it stays listed for another try.
            raise WorkCopyError("Nie udało się usunąć kopii roboczej. Zamknij program, który ją otworzył, "
                                "i spróbuj ponownie.") from None
