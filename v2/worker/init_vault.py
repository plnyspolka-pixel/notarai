import os
import secrets
from pathlib import Path
from .local_secrets import secret_path, write_new_secret

def home_path():
    return Path(os.environ["NOTARAI_V2_HOME"]).expanduser().resolve()

def initialize(home: Path) -> str:
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        initialized = any(secret_path(home, name).exists() for name in ("vault.key", "api.token"))
    except ValueError:
        initialized = True
    if initialized:
        raise SystemExit("Already initialized or partial setup; refusing to overwrite.")
    token = secrets.token_urlsafe(48)
    write_new_secret(home, "vault.key", secrets.token_bytes(32))
    write_new_secret(home, "api.token", token.encode())
    return token


def main():
    print("Development API token:", initialize(home_path()))

if __name__ == "__main__":
    main()
