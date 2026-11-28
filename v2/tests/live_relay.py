"""Opt-in live check of a deployed relay with synthetic data.

Run from v2/:  python tests/live_relay.py wss://<api>.execute-api.eu-central-1.amazonaws.com/v1
A temporary worker connects outbound; a reference device pairs, writes and reads one synthetic
document through the relay, reconnects with its key only, and is then revoked.
"""
import asyncio
import base64
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import websockets  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402

from worker.api import create_app  # noqa: E402
from worker.devices import DeviceRegistry  # noqa: E402
from worker.init_vault import initialize  # noqa: E402
from worker.tunnel import Client, RelayClient, TunnelError, TunnelKeys  # noqa: E402


async def device(url, keys):
    socket = await websockets.connect(f"{url}?role=client&office={keys.office}", open_timeout=20)

    async def send(frame):
        await socket.send(frame)
        return [await asyncio.wait_for(socket.recv(), 30)]
    client = Client(keys.public, send)
    await client.connect()
    return socket, client


async def main(url: str) -> int:
    with tempfile.TemporaryDirectory() as directory:
        home = Path(directory) / "home"
        initialize(home)
        app, keys, devices = create_app(home), TunnelKeys(home), DeviceRegistry(home)
        worker = RelayClient(url, keys, devices, app.state.dispatch)
        task = asyncio.create_task(worker.run())
        try:
            await asyncio.wait_for(worker.connected.wait(), 30)
            print("worker connected outbound; office", keys.office[:8] + "…")
            key = ec.generate_private_key(ec.SECP256R1())
            socket, client = await device(url, keys)
            paired = await client.pair(devices.invite("telefon", "write")["code"], key)
            body = base64.b64encode("Fikcyjny akt, test przekaźnika.".encode()).decode()
            status, saved = await client.request("POST", "/v2/documents", {
                "name": "test.txt", "expected_version": 0, "content_b64": body})
            assert status == 200, status
            big = base64.b64encode(bytes(range(256)) * 1200).decode()          # ~300 kB, many frames
            status, large = await client.request("POST", "/v2/documents", {
                "name": "duzy.bin", "expected_version": 0, "content_b64": big})
            assert status == 200, status
            assert (await client.request("GET", "/v2/documents/" + large["id"]))[1]["content_b64"] == big
            await socket.close()
            print("paired; wrote and read documents through the relay (including a chunked one)")

            socket, client = await device(url, keys)
            await client.authenticate(paired["device"], key)
            assert (await client.request("GET", "/v2/documents/" + saved["id"]))[1]["content_b64"] == body
            devices.revoke(paired["device"])
            assert (await client.request("GET", "/v2/documents"))[0] == 401
            await socket.close()
            print("reconnected with the device key only; revocation took effect at once")

            try:
                stranger = await websockets.connect(f"{url}?role=client&office={'0' * 32}", open_timeout=20)
                await stranger.recv()
                raise AssertionError("unknown office accepted")
            except (websockets.exceptions.InvalidStatus, websockets.exceptions.ConnectionClosed):
                print("unknown office refused")
            try:
                forged = await websockets.connect(
                    f"{url}?role=worker&office={keys.office}&key=AAAA&ts=1&sig=AAAA", open_timeout=20)
                await forged.recv()
                raise AssertionError("forged worker accepted")
            except (websockets.exceptions.InvalidStatus, websockets.exceptions.ConnectionClosed):
                print("forged worker refused")
        finally:
            task.cancel()
    print("LIVE RELAY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1])))
