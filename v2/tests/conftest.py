import os
"""Keep V2 collection in its own dependency environment."""
from pathlib import Path


def pytest_ignore_collect(collection_path, config):
    v2_root = Path(__file__).resolve().parents[1]
    if config.inipath != v2_root / "pytest.ini":
        return True
    return None


# Most tests walk through the "Tak / Nie" step; the owner's default (a command is the approval)
# has tests of its own that clear this variable.
os.environ.setdefault("NOTARAI_ALWAYS_CONFIRM", "1")
