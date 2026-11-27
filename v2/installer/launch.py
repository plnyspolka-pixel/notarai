"""Start the packaged, local-only NotarAI V2 Pocket preview."""
import argparse
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import sys
from time import monotonic, sleep

from fastapi import Request, Response
import pywintypes
import uvicorn

from preview_instance import (
    INSTANCE_HEADER, INSTANCE_PATH, announce, discover, pocket_url, proof, try_lock,
)
from worker import recovery
from worker.api import create_app
from worker.devices import DeviceRegistry
from worker.init_vault import initialize
from worker.local_secrets import secret_path


def pairing_code(home):
    invitation = DeviceRegistry(home).invite("Pocket Preview", "write", replace_pending=True)
    print(f"Kod parowania: {invitation['code']}", flush=True)
    print("Kod jest ważny przez 5 minut.", flush=True)


def admin_url(home, url):
    code = DeviceRegistry(home).invite("panel stanowiska", "admin", replace_pending=True, allow_admin=True)["code"]
    return url.removesuffix("/pocket") + "/admin#" + code


def open_pocket(url):
    try:
        os.startfile(url)
    except OSError:
        print("Otwórz powyższy adres w przeglądarce.", flush=True)


def serve(home: Path, state: Path, *, no_browser: bool):
    home.mkdir(parents=True, exist_ok=True)
    if not any(secret_path(home, name).exists() for name in ("vault.key", "api.token")):
        if any(home.iterdir()):
            raise RuntimeError("Brak kluczy istniejącego sejfu testowego.")
        initialize(home)
    app = create_app(home, allow_bedrock=False)
    nonce = secrets.token_hex(32)

    @app.head(INSTANCE_PATH, include_in_schema=False)
    def identify_instance(request: Request):
        challenge = request.headers.get(INSTANCE_HEADER, "")
        if not re.fullmatch(r"[0-9a-f]{32}", challenge):
            return Response(status_code=404)
        return Response(status_code=204, headers={INSTANCE_HEADER: proof(nonce, challenge)})

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        url = pocket_url(port)
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, access_log=False, proxy_headers=False,
            timeout_graceful_shutdown=4,
        ))
        try:
            announce(state, port, nonce)
            print("NotarAI V2 Preview — wyłącznie dane testowe", flush=True)
            print(f"Pocket: {url}", flush=True)
            pairing_code(home)
            if not recovery.enrolled(home):
                print("UWAGA: sejf nie ma kodu odzyskiwania. Otwórz „NotarAI – panel stanowiska” i utwórz go.", flush=True)
            print("Aby zakończyć, naciśnij Ctrl+C.", flush=True)
            if not no_browser:
                open_pocket(url)
            server.run(sockets=[listener])
        finally:
            state.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="NotarAI V2 Preview, tylko dane testowe")
    parser.add_argument("--no-browser", action="store_true", help="nie otwieraj przeglądarki")
    parser.add_argument("--new-code", action="store_true", help="pokaż nowy kod parowania")
    parser.add_argument("--admin", action="store_true", help="otwórz panel stanowiska")
    args = parser.parse_args()
    try:
        local = Path(os.environ["LOCALAPPDATA"]) / "NotarAI"
        home = local / "V2-preview"
        runtime = local / "V2-preview-runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        state = runtime / "instance.json"
        with (runtime / "worker.lock").open("a+b") as lock:
            deadline = monotonic() + 8
            while not try_lock(lock):
                url = discover(state)
                if url is not None:
                    print(f"Pocket: {url}", flush=True)
                    if args.admin:
                        link = admin_url(home, url)
                        if args.no_browser:
                            print(f"Panel: {link}", flush=True)
                        else:
                            open_pocket(link)
                    elif args.new_code:
                        pairing_code(home)
                        if not args.no_browser and sys.stdin.isatty():
                            input("Skopiuj kod i naciśnij Enter, aby zamknąć to okno.")
                    elif not args.no_browser:
                        open_pocket(url)
                    return 0
                if monotonic() >= deadline:
                    raise RuntimeError("Pocket jeszcze nie odpowiada. Spróbuj otworzyć go ponownie.")
                sleep(0.1)
            state.unlink(missing_ok=True)
            serve(home, state, no_browser=args.no_browser)
    except (OSError, RuntimeError, ValueError, sqlite3.Error, pywintypes.error) as error:
        print(f"Nie udało się uruchomić Pocket. {error}", file=sys.stderr)
        if not args.no_browser and sys.stdin.isatty():
            input("Naciśnij Enter, aby zamknąć okno.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
