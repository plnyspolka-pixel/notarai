"""Encrypted tunnel: handshake, device-bound key, replay, revocation, relay routing."""
import asyncio
import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from worker import tunnel
from worker.api import create_app
from worker.devices import DeviceRegistry
from worker.init_vault import initialize
from worker.tunnel import Client, RelayClient, Session, TunnelError, TunnelKeys


@pytest.fixture
def office(tmp_path):
    home = tmp_path / "home"
    initialize(home)
    app = create_app(home)
    return home, app, TunnelKeys(home), DeviceRegistry(home)


def run(coroutine):
    return asyncio.run(coroutine)


def wire(session, tap=None):
    async def send(frame):
        if tap is not None:
            tap.append(frame)
        replies = await session.handle(frame)
        if tap is not None:
            tap.extend(replies)
        return replies
    return send


def test_keys_are_stable_and_self_certifying(office):
    home, _, keys, _ = office
    again = TunnelKeys(home)
    assert again.public == keys.public and again.office == keys.office and len(keys.office) == 32
    assert not any(p.name in {"tunnel.key", "relay.key"} and b"PRIVATE" in p.read_bytes() for p in home.iterdir())


def test_pair_then_reconnect_with_the_device_key_only(office):
    home, app, keys, devices = office
    wire_log = []

    async def scenario():
        device_key = ec.generate_private_key(ec.SECP256R1())
        code = devices.invite("telefon", "write", cases=["sprawa-1"])["code"]
        first = Client(keys.public, wire(Session(keys, devices, app.state.dispatch), wire_log))
        await first.connect()
        paired = await first.pair(code, device_key)
        assert paired["scope"] == "write" and paired["cases"] == ["sprawa-1"] and "token" not in paired
        secret = base64.b64encode("TAJNA TREŚĆ AKTU".encode()).decode()
        status, body = await first.request("POST", "/v2/documents", {
            "name": "akt.txt", "expected_version": 0, "case": "sprawa-1", "content_b64": secret})
        assert status == 200
        # Same permission checks as a local call.
        assert (await first.request("POST", "/v2/documents", {
            "name": "x.txt", "expected_version": 0, "case": "sprawa-2", "content_b64": secret}))[0] == 404
        assert (await first.request("GET", "/v2/audit"))[0] == 403
        assert (await first.request("GET", "/v2/settings"))[0] == 403

        # A later session needs no code and no token: only the key that never left the device.
        second = Client(keys.public, wire(Session(keys, devices, app.state.dispatch), wire_log))
        await second.connect()
        assert (await second.authenticate(paired["device"], device_key))["scope"] == "write"
        status, document = await second.request("GET", "/v2/documents/" + body["id"])
        assert status == 200 and document["content_b64"] == secret

        # A different key is refused, even with the right device id.
        thief = Client(keys.public, wire(Session(keys, devices, app.state.dispatch)))
        await thief.connect()
        with pytest.raises(TunnelError):
            await thief.authenticate(paired["device"], ec.generate_private_key(ec.SECP256R1()))

        # Revocation cuts an open session at the next request.
        devices.revoke(paired["device"])
        assert (await second.request("GET", "/v2/documents"))[0] == 401
        return secret, code

    secret, code = run(scenario())
    on_the_wire = "\n".join(wire_log)
    assert secret not in on_the_wire and "akt.txt" not in on_the_wire and code not in on_the_wire
    assert "sprawa-1" not in on_the_wire and "/v2/documents" not in on_the_wire


def test_large_document_is_chunked(office):
    _, app, keys, devices = office
    frames = []

    async def scenario():
        client = Client(keys.public, wire(Session(keys, devices, app.state.dispatch), frames))
        await client.connect()
        await client.pair(devices.invite("telefon", "write")["code"], ec.generate_private_key(ec.SECP256R1()))
        data = base64.b64encode(bytes(range(256)) * 2000).decode()      # about 0.5 MB
        status, saved = await client.request("POST", "/v2/documents", {
            "name": "skan.bin", "expected_version": 0, "content_b64": data})
        assert status == 200
        status, back = await client.request("GET", "/v2/documents/" + saved["id"])
        assert back["content_b64"] == data
    run(scenario())
    assert len(frames) > 60 and max(map(len, frames)) < tunnel.MAX_FRAME


def test_wrong_worker_key_replay_and_garbage_end_the_session(office, tmp_path):
    _, app, keys, devices = office

    async def scenario():
        # A device that pinned another office's key cannot talk to this worker.
        other = tmp_path / "other"
        other.mkdir()
        stranger = Client(TunnelKeys(other).public, wire(Session(keys, devices, app.state.dispatch)))
        await stranger.connect()
        with pytest.raises(TunnelError):
            await stranger.pair(devices.invite("x", "read")["code"], ec.generate_private_key(ec.SECP256R1()))

        # Replay of a captured record.
        session, captured = Session(keys, devices, app.state.dispatch), []
        client = Client(keys.public, wire(session, captured))
        await client.connect()
        await client.pair(devices.invite("telefon", "read")["code"], ec.generate_private_key(ec.SECP256R1()))
        await client.request("GET", "/v2/documents")
        request_frame = [f for f in captured if '"t":"d"' in f.replace(" ", "")][-2]
        assert json.loads((await session.handle(request_frame))[0]) == {"t": "bye"}
        assert session.closed and await session.handle(request_frame) == []

        # Requests before authentication, bad paths, panel codes, junk.
        for message in ({"op": "req", "id": 1, "method": "GET", "path": "/v2/documents"},
                        {"op": "nonsense"}):
            fresh = Client(keys.public, wire(Session(keys, devices, app.state.dispatch)))
            await fresh.connect()
            with pytest.raises(TunnelError):
                await fresh.exchange(message)
        admin_code = devices.invite("panel", "admin", allow_admin=True)["code"]
        fresh = Client(keys.public, wire(Session(keys, devices, app.state.dispatch)))
        await fresh.connect()
        with pytest.raises(TunnelError):
            await fresh.pair(admin_code, ec.generate_private_key(ec.SECP256R1()))
        paired = Client(keys.public, wire(Session(keys, devices, app.state.dispatch)))
        await paired.connect()
        await paired.pair(devices.invite("telefon", "read")["code"], ec.generate_private_key(ec.SECP256R1()))
        for path in ("http://evil/v2/x", "/etc/passwd", "/v2/x\r\nHost: evil"):
            with pytest.raises(TunnelError):
                await paired.request("GET", path)
        for junk in ("", "{", "[]", '{"t":"hello","v":2}', '{"t":"hello","v":1,"e":"AAAA"}', "x" * 40000):
            assert json.loads((await Session(keys, devices, app.state.dispatch).handle(junk))[0]) == {"t": "bye"}
    run(scenario())


def test_token_from_local_pairing_cannot_authenticate_a_tunnel(office):
    _, app, keys, devices = office

    async def scenario():
        local = devices.redeem(devices.invite("laptop", "write")["code"])      # paired locally, no device key
        client = Client(keys.public, wire(Session(keys, devices, app.state.dispatch)))
        await client.connect()
        with pytest.raises(TunnelError):
            await client.authenticate(local["id"], ec.generate_private_key(ec.SECP256R1()))
    run(scenario())


def test_internal_ticket_is_not_a_credential(office):
    from fastapi.testclient import TestClient

    _, app, _, _ = office
    assert TestClient(app).get("/v2/documents", headers={"Authorization": "Tunnel anything"}).status_code == 401


def test_relay_routing_and_connect_url(office):
    _, app, keys, devices = office
    with pytest.raises(ValueError):
        RelayClient("ws://relay.example", keys, devices, app.state.dispatch)
    relay = RelayClient("wss://relay.example/v1", keys, devices, app.state.dispatch, clock=lambda: 1_800_000_000)
    url = relay.connect_url()
    assert url.startswith("wss://relay.example/v1?role=worker&office=" + keys.office) and "&ts=1800000000&sig=" in url

    async def scenario():
        async def send(frame):
            replies = await relay.route(json.dumps({"from": "conn-A", "data": frame}))
            assert all(json.loads(r)["to"] == "conn-A" for r in replies)
            return [json.loads(r)["data"] for r in replies]
        client = Client(keys.public, send)
        await client.connect()
        await client.pair(devices.invite("telefon", "read")["code"], ec.generate_private_key(ec.SECP256R1()))
        assert (await client.request("GET", "/v2/cases")) == (200, [])
        assert len(relay._sessions) == 1
        assert await relay.route(json.dumps({"from": "conn-A", "gone": True})) == []
        assert relay._sessions == {}
        for junk in ("x", "{}", json.dumps({"from": 5, "data": "x"})):
            assert await relay.route(junk) == []
    run(scenario())


def test_relay_accepts_the_python_worker_proof(office):
    """The relay is JavaScript, the worker is Python: check they agree on the signature format."""
    import shutil
    import subprocess
    from pathlib import Path
    from urllib.parse import parse_qs, urlsplit

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    _, app, keys, devices = office
    url = RelayClient("wss://relay.example/v1", keys, devices, app.state.dispatch).connect_url()
    query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    relay = Path(__file__).resolve().parents[1] / "relay" / "relay.mjs"
    script = (f"import {{workerProofIsValid}} from {json.dumps(relay.as_uri())};"
              f"const q = {json.dumps(query)}; const now = Number(q.ts);"
              "console.log(workerProofIsValid(q, now), workerProofIsValid({...q, ts: String(now - 1)}, now));")
    out = subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.stdout.split() == ["true", "false"], out.stderr


def test_worker_reaches_devices_through_a_relay_with_no_listening_port(office):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "e2e"))
    import websockets
    from dev_relay import DevRelay

    _, app, keys, devices = office

    async def scenario():
        hub = DevRelay()
        server, port = await hub.serve()
        worker = RelayClient(f"ws://127.0.0.1:{port}", keys, devices, app.state.dispatch)
        task = asyncio.create_task(worker.run())
        await asyncio.wait_for(worker.connected.wait(), 5)
        try:
            async with websockets.connect(f"ws://127.0.0.1:{port}?role=client&office={keys.office}") as socket:
                async def send(frame):
                    await socket.send(frame)
                    return [await asyncio.wait_for(socket.recv(), 5)]
                client = Client(keys.public, send)
                await client.connect()
                await client.pair(devices.invite("telefon", "write")["code"], ec.generate_private_key(ec.SECP256R1()))
                status, _ = await client.request("POST", "/v2/documents", {
                    "name": "TAJNE.txt", "expected_version": 0, "content_b64": base64.b64encode(b"TAJNE").decode()})
                assert status == 200
            # An unknown office and a forged worker are refused.
            with pytest.raises(websockets.exceptions.ConnectionClosed):
                async with websockets.connect(f"ws://127.0.0.1:{port}?role=client&office={'0' * 32}") as socket:
                    await socket.recv()
            with pytest.raises(websockets.exceptions.ConnectionClosed):
                async with websockets.connect(
                        f"ws://127.0.0.1:{port}?role=worker&office={keys.office}&key=AAAA&ts=1&sig=AAAA") as socket:
                    await socket.recv()
        finally:
            task.cancel()
            server.close()
        assert hub.frames and not any("TAJNE" in frame or "documents" in frame for frame in hub.frames)
    run(scenario())
