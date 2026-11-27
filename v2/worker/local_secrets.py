"""User-scoped Windows DPAPI for new V2 development vaults."""
import os
from pathlib import Path

DPAPI_UI_FORBIDDEN = 0x1


def secret_path(home: Path, name: str) -> Path:
    legacy = home / name
    protected = home / f"{name}.dpapi"
    if protected.exists():
        if legacy.exists():
            raise ValueError("ambiguous local secret")
        return protected
    return legacy


def read_secret(home: Path, name: str) -> bytes:
    path = secret_path(home, name)
    data = path.read_bytes()
    if path.suffix != ".dpapi":
        return data
    if os.name != "nt":
        raise ValueError("DPAPI secrets require their Windows user profile")
    import win32crypt

    return win32crypt.CryptUnprotectData(
        data, _entropy(name), None, None, DPAPI_UI_FORBIDDEN
    )[1]


def write_new_secret(home: Path, name: str, data: bytes) -> None:
    if os.name == "nt":
        import win32crypt

        data = win32crypt.CryptProtectData(
            data, None, _entropy(name), None, None, DPAPI_UI_FORBIDDEN
        )
        name += ".dpapi"
    fd = os.open(home / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(data)


def _entropy(name: str) -> bytes:
    return f"NotarAI V2 development:{name}".encode("ascii")
