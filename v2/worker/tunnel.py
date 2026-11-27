"""End-to-end encrypted channel between a paired device and this worker.

The relay in the middle forwards opaque frames and stores nothing. Trust comes from
two keys: the worker's static key, which the device learns from the pairing link, and
the device's signing key, generated on the device and never exported.

Handshake (P-256):
  device -> worker   hello   {e}                      e = ephemeral ECDH public key
  worker -> device   welcome {f}                      f = ephemeral ECDH public key
  secret  = ECDH(e, S) || ECDH(e, f)                  S = worker static key
  keys    = HKDF(secret, salt = SHA-256(label || S || e || f))  one key per direction
Only the holder of S can derive the keys, so the first valid record proves the worker.
The device then proves itself inside the channel: either a one-time pairing code, or a
signature over the handshake hash with the key registered at pairing.

Records are AES-256-GCM with a strict counter nonce: a replayed, dropped or reordered
frame ends the session.
"""
import asyncio
import base64
import hashlib
import json
from typing import Awaitable, Callable

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .local_secrets import read_secret, secret_path, write_new_secret

LABEL = b"notarai-tunnel-v1"
CHUNK = 16 * 1024               # plaintext per record; fits one WebSocket frame after base64
MAX_MESSAGE = 30 * 1024 * 1024
MAX_FRAME = 32 * 1024
CURVE = ec.SECP256R1()


class TunnelError(Exception):
    pass


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def b64d(text: str) -> bytes:
    if not isinstance(text, str) or len(text) > MAX_FRAME:
        raise TunnelError("bad encoding")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except ValueError:
        raise TunnelError("bad encoding") from None


def raw_public(key) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def load_public(raw: bytes):
    try:
        if len(raw) != 65:
            raise ValueError
        return ec.EllipticCurvePublicKey.from_encoded_point(CURVE, raw)
    except ValueError:
        raise TunnelError("bad public key") from None


def verify_signature(public_raw: bytes, signature: bytes, message: bytes) -> bool:
    """`signature` is r || s (64 bytes), the WebCrypto ECDSA format."""
    if len(signature) != 64:
        return False
    der = encode_dss_signature(int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big"))
    try:
        load_public(public_raw).verify(der, message, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, TunnelError):
        return False


class TunnelKeys:
    """The worker's long-term keys, kept by the OS secret store."""

    def __init__(self, home):
        self.static = self._load(home, "tunnel.key")     # ECDH: devices pin its public half
        self.signing = self._load(home, "relay.key")     # ECDSA: proves this office to the relay
        self.public = raw_public(self.static)
        self.signing_public = raw_public(self.signing)
        # Self-certifying address: nobody else can register this office with the relay.
        self.office = hashlib.sha256(self.signing_public).hexdigest()[:32]

    @staticmethod
    def _load(home, name):
        if not secret_path(home, name).exists():
            key = ec.generate_private_key(CURVE)
            write_new_secret(home, name, key.private_bytes(
                serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            return key
        return serialization.load_der_private_key(read_secret(home, name), None)

    def relay_proof(self, timestamp: int) -> str:
        message = f"notarai-relay-v1|{self.office}|{timestamp}".encode()
        return b64e(self.signing.sign(message, ec.ECDSA(hashes.SHA256())))   # DER, verified by the relay


WINDOW = 512     # frames that may arrive ahead of their turn (the relay does not guarantee order)


class _Cipher:
    """AES-256-GCM where the nonce is the frame's sequence number, so each number is usable once."""

    def __init__(self, key: bytes):
        self._aead, self._counter = AESGCM(key), 0

    def next_number(self) -> int:
        number = self._counter
        self._counter += 1
        return number

    def seal(self, number: int, data: bytes, final: bool) -> str:
        return b64e(self._aead.encrypt(number.to_bytes(12, "big"), data, bytes([final])))

    def open(self, number: int, record: str, final: bool) -> bytes:
        try:
            return self._aead.decrypt(number.to_bytes(12, "big"), b64d(record), bytes([final]))
        except InvalidTag:
            raise TunnelError("record rejected") from None


def derive_keys(shared: bytes, static_public: bytes, e_raw: bytes, f_raw: bytes):
    transcript = hashlib.sha256(LABEL + static_public + e_raw + f_raw).digest()
    material = HKDF(hashes.SHA256(), 64, transcript, LABEL).derive(shared)
    return transcript, material[:32], material[32:]     # device->worker key, worker->device key


def encode_message(cipher: _Cipher, message: dict) -> list[str]:
    data = json.dumps(message, separators=(",", ":")).encode()
    if len(data) > MAX_MESSAGE:
        raise TunnelError("message too large")
    frames = []
    for offset in range(0, max(len(data), 1), CHUNK):
        final = offset + CHUNK >= len(data)
        number = cipher.next_number()
        frames.append(json.dumps(
            {"t": "d", "n": number, "f": int(final), "c": cipher.seal(number, data[offset:offset + CHUNK], final)}))
    return frames


class _Assembler:
    """Puts frames back in order and rebuilds messages. A number below the next expected one is a
    replay and ends the session; a tampered number fails authentication, because it is the nonce."""

    def __init__(self, cipher: _Cipher):
        self._cipher, self._parts, self._size = cipher, [], 0
        self._expected, self._early = 0, {}

    def feed(self, frame: dict) -> list[dict]:
        number = frame.get("n")
        if frame.get("f") not in (0, 1) or type(number) is not int or number < self._expected \
                or number >= self._expected + WINDOW or number in self._early:
            raise TunnelError("bad frame")
        self._early[number] = frame
        messages = []
        while self._expected in self._early:
            current = self._early.pop(self._expected)
            final = current["f"] == 1
            part = self._cipher.open(self._expected, current.get("c", ""), final)
            self._expected += 1
            self._size += len(part)
            if self._size > MAX_MESSAGE:
                raise TunnelError("message too large")
            self._parts.append(part)
            if not final:
                continue
            data, self._parts, self._size = b"".join(self._parts), [], 0
            try:
                message = json.loads(data)
            except ValueError:
                raise TunnelError("bad message") from None
            if not isinstance(message, dict):
                raise TunnelError("bad message")
            messages.append(message)
        return messages


Dispatch = Callable[[str, str, str, object], Awaitable[tuple[int, object]]]


class Session:
    """One device connection. `handle` takes a text frame and returns the frames to send back.

    `devices` is the DeviceRegistry; `dispatch(device_id, method, path, body)` runs the request
    through the same API and the same permission checks as a local call.
    """

    def __init__(self, keys: TunnelKeys, devices, dispatch: Dispatch):
        self._keys, self._devices, self._dispatch = keys, devices, dispatch
        self._inbound: _Assembler | None = None
        self._outbound: _Cipher | None = None
        self._transcript = b""
        self._device: str | None = None
        self.closed = False

    @property
    def authenticated(self) -> bool:
        return self._device is not None

    async def handle(self, text: str) -> list[str]:
        if self.closed:
            return []
        try:
            if not isinstance(text, str) or len(text) > MAX_FRAME:
                raise TunnelError("bad frame")
            try:
                frame = json.loads(text)
            except ValueError:
                raise TunnelError("bad frame") from None
            if not isinstance(frame, dict):
                raise TunnelError("bad frame")
            if self._inbound is None:
                return self._handshake(frame)
            if frame.get("t") != "d":
                raise TunnelError("bad frame")
            replies = []
            for message in self._inbound.feed(frame):
                replies += encode_message(self._outbound, await self._message(message))
            return replies
        except TunnelError:
            # One generic notice in clear, then silence: no detail for a probing peer.
            self.closed = True
            return [json.dumps({"t": "bye"})]

    def _handshake(self, frame: dict) -> list[str]:
        if frame.get("t") != "hello" or frame.get("v") != 1:
            raise TunnelError("bad hello")
        e_raw = b64d(frame.get("e", ""))
        peer = load_public(e_raw)
        ephemeral = ec.generate_private_key(CURVE)
        f_raw = raw_public(ephemeral)
        shared = self._keys.static.exchange(ec.ECDH(), peer) + ephemeral.exchange(ec.ECDH(), peer)
        self._transcript, inbound, outbound = derive_keys(shared, self._keys.public, e_raw, f_raw)
        self._inbound, self._outbound = _Assembler(_Cipher(inbound)), _Cipher(outbound)
        return [json.dumps({"t": "welcome", "f": b64e(f_raw)})]

    async def _message(self, message: dict) -> dict:
        op = message.get("op")
        if op == "pair" and self._device is None:
            public = b64d(message.get("key", ""))
            load_public(public)
            try:
                device = self._devices.redeem(str(message.get("code", "")), pubkey=b64e(public))
            except PermissionError:
                raise TunnelError("pairing refused") from None
            if device["scope"] == "admin":      # the workstation panel never travels through a relay
                self._devices.revoke(device["id"])
                raise TunnelError("pairing refused")
            self._device = device["id"]
            return {"ok": True, "device": device["id"], "scope": device["scope"], "cases": device["cases"]}
        if op == "auth" and self._device is None:
            device_id = str(message.get("device", ""))
            known = self._devices.lookup(device_id)
            if known is None or known["scope"] == "admin" or not known["pubkey"] or not verify_signature(
                b64d(known["pubkey"]), b64d(message.get("sig", "")), LABEL + b"|auth|" + self._transcript
            ):
                raise TunnelError("authentication refused")
            self._device = device_id
            return {"ok": True, "device": device_id, "scope": known["scope"], "cases": known["cases"]}
        if op == "req" and self._device is not None:
            method, path = message.get("method"), message.get("path")
            if method not in {"GET", "POST", "DELETE"} or not isinstance(path, str) or not path.startswith("/v2/") \
                    or len(path) > 2048 or not path.isascii() or any(c <= " " or c == "\x7f" for c in path):
                raise TunnelError("bad request")
            status, body = await self._dispatch(self._device, method, path, message.get("body"))
            return {"id": message.get("id"), "status": status, "body": body}
        raise TunnelError("unexpected message")


# ---------------------------------------------------------------- device side (tests, native clients)
class Client:
    """Reference implementation of the device side; the browser code in tunnel.js mirrors it."""

    def __init__(self, worker_public: bytes, send: Callable[[str], Awaitable[list[str]]]):
        self._worker_public, self._send = worker_public, send
        self._outbound: _Cipher | None = None
        self._inbound: _Assembler | None = None
        self.transcript = b""
        self._next = 0

    async def connect(self) -> None:
        ephemeral = ec.generate_private_key(CURVE)
        e_raw = raw_public(ephemeral)
        replies = await self._send(json.dumps({"t": "hello", "v": 1, "e": b64e(e_raw)}))
        welcome = json.loads(replies[0]) if replies else {}
        if welcome.get("t") != "welcome":
            raise TunnelError("no welcome")
        f_raw = b64d(welcome["f"])
        shared = ephemeral.exchange(ec.ECDH(), load_public(self._worker_public)) \
            + ephemeral.exchange(ec.ECDH(), load_public(f_raw))
        self.transcript, outbound, inbound = derive_keys(shared, self._worker_public, e_raw, f_raw)
        self._outbound, self._inbound = _Cipher(outbound), _Assembler(_Cipher(inbound))

    async def exchange(self, message: dict) -> dict:
        reply = None
        for frame in encode_message(self._outbound, message):
            for answer in await self._send(frame):
                parsed = json.loads(answer)
                if parsed.get("t") != "d":
                    raise TunnelError("session closed")
                for complete in self._inbound.feed(parsed):
                    reply = complete
        if reply is None:
            raise TunnelError("no reply")
        return reply

    async def pair(self, code: str, signing_key) -> dict:
        return await self.exchange({"op": "pair", "code": code, "key": b64e(raw_public(signing_key))})

    async def authenticate(self, device_id: str, signing_key) -> dict:
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

        r, s = decode_dss_signature(signing_key.sign(LABEL + b"|auth|" + self.transcript, ec.ECDSA(hashes.SHA256())))
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return await self.exchange({"op": "auth", "device": device_id, "sig": b64e(signature)})

    async def request(self, method: str, path: str, body=None) -> tuple[int, object]:
        self._next += 1
        reply = await self.exchange({"op": "req", "id": self._next, "method": method, "path": path, "body": body})
        if reply.get("id") != self._next:
            raise TunnelError("reply mismatch")
        return reply["status"], reply["body"]


# ---------------------------------------------------------------- relay connection
class RelayClient:
    """Keeps one outbound WebSocket to the relay. No inbound port is ever opened."""

    MAX_SESSIONS = 64

    def __init__(self, url: str, keys: TunnelKeys, devices, dispatch: Dispatch, *, clock=None):
        import time

        if not url.startswith("wss://") and not url.startswith("ws://127.0.0.1"):
            raise ValueError("relay must use TLS")
        self._url, self._keys, self._devices, self._dispatch = url, keys, devices, dispatch
        self._clock = clock or time.time
        self._sessions: dict[str, Session] = {}
        self.connected = asyncio.Event()

    def connect_url(self) -> str:
        # Strictly increasing: the relay refuses a timestamp it has already seen for this office.
        timestamp = self._last_stamp = max(int(self._clock()), getattr(self, "_last_stamp", 0) + 1)
        return (f"{self._url}?role=worker&office={self._keys.office}&key={b64e(self._keys.signing_public)}"
                f"&ts={timestamp}&sig={self._keys.relay_proof(timestamp)}")

    async def run(self) -> None:
        import websockets

        delay = 1
        while True:
            pumps: dict[str, tuple[asyncio.Queue, asyncio.Task]] = {}
            try:
                # Room for the relay's envelope around the largest frame a device may send.
                async with websockets.connect(self.connect_url(), max_size=8 * MAX_FRAME, open_timeout=15) as socket:
                    self.connected.set()
                    delay = 1
                    sending = asyncio.Lock()

                    async def pump(queue):
                        # One queue per device: a long draft for one phone never blocks another.
                        while True:
                            raw = await queue.get()
                            for index, reply in enumerate(await self.route(raw)):
                                async with sending:
                                    await socket.send(reply)
                                if index % 20 == 19:
                                    await asyncio.sleep(0.05)      # stay under the relay's rate limit

                    async for raw in socket:
                        source = self._source(raw)
                        if source is None:
                            continue
                        if source not in pumps:
                            if len(pumps) >= self.MAX_SESSIONS:
                                self._evict(pumps)
                            queue = asyncio.Queue(maxsize=2 * WINDOW)
                            pumps[source] = (queue, asyncio.create_task(pump(queue)))
                        try:
                            pumps[source][0].put_nowait(raw)
                        except asyncio.QueueFull:
                            pumps.pop(source)[1].cancel()
                            self._sessions.pop(source, None)
            except asyncio.CancelledError:
                for _, task in pumps.values():
                    task.cancel()
                raise
            except Exception:
                pass                       # network trouble: retry quietly, never log frames
            for _, task in pumps.values():
                task.cancel()
            self.connected.clear()
            self._sessions.clear()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    @staticmethod
    def _source(raw) -> str | None:
        try:
            source = json.loads(raw)["from"]
        except (ValueError, KeyError, TypeError):
            return None
        return source if isinstance(source, str) and len(source) <= 128 else None

    def _evict(self, pumps) -> None:
        """Make room by dropping a connection that never authenticated, if there is one."""
        victim = next((s for s in pumps if not getattr(self._sessions.get(s), "authenticated", False)),
                      next(iter(pumps)))
        pumps.pop(victim)[1].cancel()
        self._sessions.pop(victim, None)

    async def route(self, raw) -> list[str]:
        """Relay envelope: {"from": connection, "data": frame} in, {"to": connection, "data": frame} out."""
        try:
            envelope = json.loads(raw)
            source, data = envelope["from"], envelope.get("data")
            if not isinstance(source, str) or len(source) > 128:
                return []
        except (ValueError, KeyError, TypeError):
            return []
        if envelope.get("gone"):
            self._sessions.pop(source, None)
            return []
        session = self._sessions.get(source)
        if session is None:
            if len(self._sessions) >= self.MAX_SESSIONS:
                victim = next((s for s, v in self._sessions.items() if not v.authenticated),
                              next(iter(self._sessions)))
                self._sessions.pop(victim)
            session = self._sessions[source] = Session(self._keys, self._devices, self._dispatch)
        try:
            replies = await session.handle(data)
        except Exception:
            session.closed, replies = True, [json.dumps({"t": "bye"})]
        if session.closed:
            self._sessions.pop(source, None)
        return [json.dumps({"to": source, "data": reply}) for reply in replies]
