"""Start the packaged, local-only NotarAI V2 Pocket preview."""
import argparse
import os
from pathlib import Path
import socket

import uvicorn

from worker.api import create_app
from worker.devices import DeviceRegistry
from worker.init_vault import initialize
from worker.local_secrets import secret_path


def main():
    parser = argparse.ArgumentParser(description="NotarAI V2 Preview, tylko dane testowe")
    parser.add_argument("--no-browser", action="store_true", help="nie otwieraj przeglądarki")
    args = parser.parse_args()

    home = Path(os.environ["LOCALAPPDATA"]) / "NotarAI" / "V2-preview"
    home.mkdir(parents=True, exist_ok=True)
    if not any(secret_path(home, name).exists() for name in ("vault.key", "api.token")):
        if any(home.iterdir()):
            raise SystemExit("Brak kluczy istniejącego sejfu testowego.")
        initialize(home)
    app = create_app(home, allow_bedrock=False)

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, access_log=False, proxy_headers=False,
        ))
        invitation = DeviceRegistry(home).invite("Pocket Preview", "write")
        url = f"http://127.0.0.1:{port}/v2/pocket"
        print("NotarAI V2 Preview — wyłącznie dane testowe", flush=True)
        print(f"Pocket: {url}", flush=True)
        print(f"Kod parowania: {invitation['code']}", flush=True)
        print("Kod jest ważny przez 5 minut. Aby zakończyć, naciśnij Ctrl+C.", flush=True)
        if not args.no_browser:
            try:
                os.startfile(url)
            except OSError:
                print("Otwórz powyższy adres w przeglądarce.", flush=True)
        server.run(sockets=[listener])


if __name__ == "__main__":
    main()
