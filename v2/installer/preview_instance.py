"""A profile-local process lock and verified discovery of the running Pocket URL."""
from errno import EACCES
from http.client import HTTPConnection, HTTPException
import hmac
import json
import msvcrt
from pathlib import Path
import re
import secrets

INSTANCE_PATH = "/v2/preview/instance"
INSTANCE_HEADER = "X-NotarAI-Preview"


def try_lock(handle) -> bool:
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as error:
        if error.errno != EACCES:
            raise
        return False
    return True


def pocket_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/v2/pocket"


def proof(nonce: str, challenge: str) -> str:
    return hmac.digest(bytes.fromhex(nonce), challenge.encode("ascii"), "sha256").hex()


def announce(state: Path, port: int, nonce: str) -> None:
    temporary = state.with_suffix(".tmp")
    temporary.write_text(json.dumps({"port": port, "nonce": nonce}), encoding="ascii")
    temporary.replace(state)


def discover(state: Path) -> str | None:
    try:
        value = json.loads(state.read_text(encoding="ascii"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    port, nonce = value.get("port"), value.get("nonce")
    if type(port) is not int or not 1 <= port <= 65535:
        return None
    if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{64}", nonce):
        return None

    connection = HTTPConnection("127.0.0.1", port, timeout=0.4)
    try:
        challenge = secrets.token_hex(16)
        connection.request("HEAD", INSTANCE_PATH, headers={INSTANCE_HEADER: challenge})
        response = connection.getresponse()
        if response.status == 204 and response.getheader(INSTANCE_HEADER) == proof(nonce, challenge):
            return pocket_url(port)
    except (OSError, HTTPException):
        pass
    finally:
        connection.close()
    return None
