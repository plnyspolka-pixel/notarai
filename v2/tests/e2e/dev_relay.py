"""Development relay with the same rules as relay/relay.mjs, for local end-to-end tests only."""
import asyncio
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

import websockets
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from worker.tunnel import b64d, load_public


class DevRelay:
    def __init__(self):
        self.workers, self.clients, self.frames = {}, {}, []

    @staticmethod
    def proof_ok(query) -> bool:
        try:
            office, raw, ts = query["office"], b64d(query["key"]), int(query["ts"])
            if abs(time.time() - ts) > 120 or hashlib.sha256(raw).hexdigest()[:32] != office:
                return False
            load_public(raw).verify(b64d(query["sig"]), f"notarai-relay-v1|{office}|{ts}".encode(), ec.ECDSA(hashes.SHA256()))
            return True
        except (KeyError, ValueError, InvalidSignature, Exception):
            return False

    async def handle(self, socket):
        query = {k: v[0] for k, v in parse_qs(urlsplit(socket.request.path).query).items()}
        ident = str(id(socket))
        if query.get("role") == "worker" and self.proof_ok(query):
            self.workers[query["office"]] = socket
            try:
                async for raw in socket:
                    envelope = json.loads(raw)
                    target = self.clients.get(envelope.get("to"))
                    if target and target[1] == query["office"]:
                        self.frames.append(envelope["data"])
                        await target[0].send(envelope["data"])
            finally:
                if self.workers.get(query["office"]) is socket:
                    del self.workers[query["office"]]
        elif query.get("role") == "client" and query.get("office") in self.workers:
            office = query["office"]
            self.clients[ident] = (socket, office)
            try:
                async for raw in socket:
                    self.frames.append(raw)
                    worker = self.workers.get(office)
                    if worker is None:
                        await socket.send(json.dumps({"t": "bye"}))
                        break
                    await worker.send(json.dumps({"from": ident, "data": raw}))
            finally:
                self.clients.pop(ident, None)
                worker = self.workers.get(office)
                if worker is not None:
                    try:
                        await worker.send(json.dumps({"from": ident, "gone": True}))
                    except Exception:
                        pass
        else:
            await socket.close(4403, "refused")

    async def serve(self, port=0):
        server = await websockets.serve(self.handle, "127.0.0.1", port, max_size=128 * 1024)
        return server, server.sockets[0].getsockname()[1]
