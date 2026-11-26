"""Keep V2 collection in its own dependency environment."""
from pathlib import Path


def pytest_ignore_collect(collection_path, config):
    v2_root = Path(__file__).resolve().parents[1]
    if config.inipath != v2_root / "pytest.ini":
        return True
    return None
