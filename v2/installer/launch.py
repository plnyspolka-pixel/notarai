"""Start the packaged, local-only NotarAI V2 Pocket preview."""
import argparse
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import sys
from threading import Thread
from time import monotonic, sleep

from fastapi import Request, Response
import pywintypes
import uvicorn

from preview_instance import (
    INSTANCE_HEADER, INSTANCE_PATH, announce, discover, pocket_url, proof, try_lock,
)
from preview_window import message, open_pocket, show
from worker.api import create_app
from worker.devices import DeviceRegistry
from worker.init_vault import initialize
from worker.local_secrets import secret_path


def serve(home: Path, state: Path, *, no_browser: bool):
    home.mkdir(parents=True, exist_ok=True)
    if not any(secret_path(home, name).exists() for name in ("vault.key", "api.token")):
        if any(home.iterdir()):
            raise RuntimeError("Brak kluczy istniejącego sejfu testowego.")
        initialize(home)
    app = create_app(home, allow_bedrock=False)
    devices = DeviceRegistry(home)
    nonce = secrets.token_hex(32)

    @app.head(INSTANCE_PATH, include_in_schema=False)
    def identify_instance(request: Request):
        challenge = request.headers.get(INSTANCE_HEADER, "")
        if not re.fullmatch(r"[0-9a-f]{32}", challenge):
            return Response(status_code=404)
        return Response(status_code=204, headers={INSTANCE_HEADER: proof(nonce, challenge)})

    def invite():
        return devices.invite("Pocket Preview", "write", replace_pending=True)["code"]

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, access_log=False, proxy_headers=False,
            log_config=None, timeout_graceful_shutdown=4,
        ))
        task = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        task.start()
        try:
            deadline = monotonic() + 5
            while not server.started:
                if not task.is_alive() or monotonic() >= deadline:
                    raise RuntimeError("Nie udało się uruchomić lokalnego Pocket.")
                sleep(0.025)
            announce(state, port, nonce)
            url = pocket_url(port)
            print(f"Pocket: {url}", flush=True)
            show(url, invite, open_on_start=not no_browser)
        finally:
            server.should_exit = True
            task.join(timeout=7)
            state.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="NotarAI V2 Preview, tylko dane testowe")
    parser.add_argument("--no-browser", action="store_true", help="nie otwieraj przeglądarki przy starcie")
    args = parser.parse_args()
    try:
        local = Path(os.environ["LOCALAPPDATA"]) / "NotarAI"
        runtime = local / "V2-preview-runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        state = runtime / "instance.json"
        with (runtime / "worker.lock").open("a+b") as lock:
            deadline = monotonic() + 8
            while not try_lock(lock):
                url = discover(state)
                if url is not None:
                    print(f"Pocket: {url}", flush=True)
                    if not args.no_browser:
                        open_pocket(url)
                    return 0
                if monotonic() >= deadline:
                    raise RuntimeError("Pocket jeszcze nie odpowiada. Spróbuj otworzyć go ponownie.")
                sleep(0.1)
            state.unlink(missing_ok=True)
            serve(local / "V2-preview", state, no_browser=args.no_browser)
    except (OSError, RuntimeError, ValueError, sqlite3.Error, pywintypes.error) as error:
        if sys.stderr is not None:
            print(f"NotarAI V2 Preview: {error}", file=sys.stderr)
        if not args.no_browser:
            message(f"Nie udało się uruchomić Pocket.\n{error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
