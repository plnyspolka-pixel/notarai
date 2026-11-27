"""NotarAI on the office computer: a background worker and an app window.

The worker runs without a console (started with Windows and by the window when needed). The
window is Edge in app mode with a profile of its own: no tabs, no address bar, and on this
computer no pairing code, because the launcher hands the window a one-time workstation code.
Phones still pair through the chat ("dodaj telefon") and use Pocket in their browser.
"""
import argparse
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import subprocess
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


def find_edge() -> Path | None:
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            candidate = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if candidate.is_file():
                return candidate
    return None


def open_window(link: str, local: Path) -> None:
    """The NotarAI window: Edge in app mode, its own profile (microphone permission is remembered there)."""
    edge = find_edge()
    if edge is None:
        open_pocket(link)
        return
    subprocess.Popen([str(edge), f"--app={link}", f"--user-data-dir={local / 'okno'}", "--no-first-run",
                      "--no-default-browser-check", "--window-size=1100,900"], close_fds=True)


def start_background() -> None:
    """The worker without a console window, detached from this short-lived launcher."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    flags = 0x00000008 | 0x00000200 | 0x08000000      # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen([str(pythonw if pythonw.is_file() else sys.executable), "-X", "utf8",
                      str(Path(__file__).resolve()), "--serve"], cwd=str(Path(__file__).resolve().parent),
                     creationflags=flags, close_fds=True)


def tell(message: str) -> None:
    """Without a console there is nowhere to print: show a message box instead."""
    print(message, file=sys.stderr)
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "NotarAI", 0x10)
    except Exception:
        pass


def serve(home: Path, state: Path, *, no_browser: bool, quiet: bool = False):
    home.mkdir(parents=True, exist_ok=True)
    if not any(secret_path(home, name).exists() for name in ("vault.key", "api.token")):
        if any(home.iterdir()):
            raise RuntimeError("Brak kluczy istniejącego sejfu testowego.")
        initialize(home)
    preset = Path(__file__).with_name("preset.json")
    if preset.is_file() and not (home / "settings.json").exists():
        # Addresses of the NotarAI services for this installation. Everything optional stays off
        # until the notary switches it on in the panel.
        (home / "settings.json").write_text(preset.read_text(encoding="utf-8"), encoding="utf-8")
    # AI stays off until the notary switches it on and signs in (settings ai.enabled, Cognito login).
    app = create_app(home)
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
            if not quiet:
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
    parser = argparse.ArgumentParser(description="NotarAI, tylko dane testowe")
    parser.add_argument("--no-browser", action="store_true", help="tryb konsoli: nie otwieraj okna")
    parser.add_argument("--new-code", action="store_true", help="pokaż nowy kod parowania")
    parser.add_argument("--admin", action="store_true", help="otwórz okno NotarAI (domyślne)")
    parser.add_argument("--serve", action="store_true", help="tylko część robocza w tle")
    args = parser.parse_args()
    try:
        local = Path(os.environ["LOCALAPPDATA"]) / "NotarAI"
        home = local / "V2-preview"
        runtime = local / "V2-preview-runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        state = runtime / "instance.json"
        if args.serve:
            with (runtime / "worker.lock").open("a+b") as lock:
                if not try_lock(lock):
                    return 0                 # already running
                state.unlink(missing_ok=True)
                serve(home, state, no_browser=True, quiet=True)
            return 0
        if args.no_browser or args.new_code:
            return console(args, home, runtime, state)
        url = discover(state)
        if url is None:
            start_background()
            deadline = monotonic() + 60
            while url is None and monotonic() < deadline:
                sleep(0.25)
                url = discover(state)
            if url is None:
                tell("NotarAI nie uruchomił się. Uruchom ponownie komputer albo zainstaluj program jeszcze raz.")
                return 1
        open_window(admin_url(home, url), local)
    except (OSError, RuntimeError, ValueError, sqlite3.Error, pywintypes.error) as error:
        tell(f"Nie udało się uruchomić NotarAI. {error}")
        return 1
    return 0


def console(args, home: Path, runtime: Path, state: Path) -> int:
    """The console mode used by tests and support: prints addresses and pairing codes."""
    with (runtime / "worker.lock").open("a+b") as lock:
        deadline = monotonic() + 8
        while not try_lock(lock):
            url = discover(state)
            if url is not None:
                print(f"Pocket: {url}", flush=True)
                if args.admin:
                    print(f"Panel: {admin_url(home, url)}", flush=True)
                elif args.new_code:
                    pairing_code(home)
                    if not args.no_browser and sys.stdin.isatty():
                        input("Skopiuj kod i naciśnij Enter, aby zamknąć to okno.")
                return 0
            if monotonic() >= deadline:
                raise RuntimeError("Pocket jeszcze nie odpowiada. Spróbuj otworzyć go ponownie.")
            sleep(0.1)
        state.unlink(missing_ok=True)
        serve(home, state, no_browser=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
