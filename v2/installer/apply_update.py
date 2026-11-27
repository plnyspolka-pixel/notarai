"""Swap in a staged code update before anything of the program is imported.

Runs at the very top of launch.py. Only when no worker is running (its lock is free), so files in
use are never replaced. On any problem the old program simply keeps working; the staged package
is removed so a broken one cannot block every start.
"""
import json
import shutil
from pathlib import Path


def apply(app_dir: Path, lock_path: Path, try_lock) -> str | None:
    """The version swapped in, or None."""
    staging = app_dir / "aktualizacja"
    ready = staging / "gotowa.json"
    if not ready.is_file():
        return None
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        if not try_lock(lock):
            return None                           # the worker is running: next start
        try:
            version = json.loads(ready.read_text(encoding="utf-8"))["version"]
            new = staging / "nowa"
            backup = staging / "poprzednia"
            shutil.rmtree(backup, ignore_errors=True)
            backup.mkdir(parents=True)
            moved = []
            try:
                for item in sorted(new.iterdir()):
                    target = app_dir / item.name
                    if target.exists():
                        target.rename(backup / item.name)
                    moved.append(item.name)
                    item.rename(target)
            except OSError:
                for name in reversed(moved):      # put the previous program back as it was
                    shutil.rmtree(app_dir / name, ignore_errors=True) if (app_dir / name).is_dir() \
                        else (app_dir / name).unlink(missing_ok=True)
                    if (backup / name).exists():
                        (backup / name).rename(app_dir / name)
                return None
            return version
        except (OSError, ValueError, KeyError):
            return None
        finally:
            ready.unlink(missing_ok=True)
            shutil.rmtree(staging / "nowa", ignore_errors=True)
