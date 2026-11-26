import os
import secrets
from pathlib import Path

def home_path():
    return Path(os.environ["NOTARAI_V2_HOME"]).expanduser().resolve()

def main():
    home = home_path()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Development only: production uses OS-backed key protection and restrictive ACLs.
    key_path = home / "vault.key"
    token_path = home / "api.token"
    if key_path.exists() or token_path.exists():
        raise SystemExit("Already initialized or partial setup; refusing to overwrite.")
    token = secrets.token_urlsafe(48)
    for path, data in ((key_path, secrets.token_bytes(32)), (token_path, token.encode())):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(data)
    print("Development API token:", token)

if __name__ == "__main__":
    main()
