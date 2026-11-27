"""Several workstations of one office working as one NotarAI (owner's decision 27.11.2026).

Every computer runs the full program with its own encrypted vault. Workstations are joined once with
a code shown on one of them; from then on they share an office key (kept with Windows DPAPI) and every
few seconds each one asks the others, over the office network, for what changed since last time:
document revisions, the calendar, lessons, messenger messages and deletions. Everything on the wire is
encrypted and authenticated with the office key (AES-GCM, with a time window against replay), so the
local network sees nothing readable. Two edits of the same document never overwrite each other: the
second one is kept as a separate „(konflikt)” document.

The same channel carries requests between workstations: printing on the other computer's printer and,
only where that computer allows it, a picture of its screen.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .local_secrets import read_secret, secret_path, store_secret

PORT = 47321
WINDOW_S = 300
CODE_TTL_S = 600


class OfficeError(Exception):
    """Fixed Polish message, safe to show."""


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _unb64(text: str) -> bytes:
    return base64.b64decode(text, validate=True)


def local_address() -> str:
    """This computer's address in the office network (no packet is sent)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def _derive(secret: str) -> bytes:
    return HKDF(algorithm=SHA256(), length=32, salt=b"notarai-office-pair", info=b"v1").derive(secret.encode())


def http_transport(address: str, path: str, body: bytes) -> bytes:
    import httpx

    response = httpx.post(f"http://{address}/office/{path}", content=body, timeout=30,
                          headers={"Content-Type": "application/octet-stream"})
    if response.status_code != 200:
        raise OfficeError("Drugie stanowisko odrzuciło połączenie.")
    return response.content


class OfficeLink:
    def __init__(self, home: Path, vault, station_name, *, transport=http_transport, address=None,
                 printers=None, printer=None, screen=None, screen_allowed=lambda: False, clock=time.time):
        self._home, self._vault, self._name = Path(home), vault, station_name
        self._transport, self._clock = transport, clock
        self._address = address or (lambda: f"{local_address()}:{PORT}")
        self._printers = printers or (lambda: [])
        self._print = printer
        self._screen, self._screen_allowed = screen, screen_allowed
        self._lock = threading.Lock()
        self._invites: dict[str, float] = {}
        self._outbox: dict[str, list] = {}        # requests for a station, picked up when it asks us
        self._results: dict[str, list] = {}       # answers for a station, picked up the same way
        self.answers: dict[str, dict] = {}        # answers that came back to us, by request id
        self._seen: dict[bytes, float] = {}
        self.stations: dict[str, dict] = {}       # what the other stations last told about themselves

    # ------------------------------------------------------------ state
    @property
    def _state_path(self) -> Path:
        return self._home / "kancelaria.json"

    def peers(self) -> list[dict]:
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))["peers"]
        except (OSError, ValueError, KeyError):
            return []

    def _save_peers(self, peers: list[dict]) -> None:
        self._state_path.write_text(json.dumps({"peers": peers}, ensure_ascii=False, indent=1), encoding="utf-8")

    def _key(self) -> bytes | None:
        if not secret_path(self._home, "office.key").exists():
            return None
        return read_secret(self._home, "office.key")

    @property
    def joined(self) -> bool:
        return self._key() is not None and bool(self.peers())

    # ------------------------------------------------------------ joining
    def invite(self) -> str:
        """A one-time code for the other computer: this computer's address and a short secret."""
        if self._key() is None:
            store_secret(self._home, "office.key", secrets.token_bytes(32))
        secret = "-".join(secrets.token_hex(2).upper() for _ in range(3))
        with self._lock:
            now = self._clock()
            self._invites = {k: v for k, v in self._invites.items() if v > now}
            self._invites[secret] = now + CODE_TTL_S
        return f"{self._address()} {secret}"

    def join(self, code: str) -> str:
        """On the computer joining: ask the inviting one for the office key. Returns its station name."""
        parts = code.strip().split()
        if len(parts) != 2 or ":" not in parts[0]:
            raise OfficeError("Kod wygląda tak: „192.168.1.20:47321 AB12-CD34-EF56”. Przepisz go z drugiego komputera.")
        address, secret = parts[0], parts[1].upper()
        request = {"name": self._name(), "address": self._address(), "ts": self._clock(),
                   "proof": hmac.new(secret.encode(), b"notarai-office-join", hashlib.sha256).hexdigest()}
        try:
            reply = json.loads(self._transport(address, "pair", json.dumps(request).encode()))
            box = _unb64(reply["key"])
            key = AESGCM(_derive(secret)).decrypt(box[:12], box[12:], b"notarai-office-key")
        except OfficeError:
            raise
        except Exception:
            raise OfficeError("Nie udało się połączyć z drugim komputerem. Sprawdź, czy NotarAI jest tam włączony, "
                              "kod jest aktualny (10 minut), a oba komputery są w tej samej sieci.") from None
        store_secret(self._home, "office.key", key)
        self._add_peer(reply["name"], address)
        return reply["name"]

    def handle_pair(self, body: bytes) -> bytes:
        """On the inviting computer: check the proof, hand over the office key sealed with the code."""
        request = json.loads(body)
        with self._lock:
            now = self._clock()
            secret = next((s for s, until in self._invites.items() if until > now and hmac.compare_digest(
                hmac.new(s.encode(), b"notarai-office-join", hashlib.sha256).hexdigest(), str(request.get("proof", "")))), None)
            if secret is None:
                raise OfficeError("Kod jest nieprawidłowy albo wygasł.")
            self._invites.pop(secret)            # one use
        nonce = secrets.token_bytes(12)
        box = nonce + AESGCM(_derive(secret)).encrypt(nonce, self._key(), b"notarai-office-key")
        self._add_peer(str(request["name"])[:60], str(request["address"])[:60])
        return json.dumps({"key": _b64(box), "name": self._name()}).encode()

    def _add_peer(self, name: str, address: str) -> None:
        peers = [p for p in self.peers() if p["address"] != address and p["name"] != name]
        peers.append({"name": name, "address": address, "revisions": 0, "notes": 0})
        self._save_peers(peers)

    def forget(self, name: str) -> bool:
        peers = self.peers()
        kept = [p for p in peers if p["name"].lower() != name.lower()]
        self._save_peers(kept)
        return len(kept) != len(peers)

    # ------------------------------------------------------------ the sealed envelope
    def seal(self, payload: dict) -> bytes:
        key = self._key()
        if key is None:
            raise OfficeError("To stanowisko nie jest połączone z kancelarią.")
        nonce = secrets.token_bytes(12)
        plain = json.dumps({**payload, "ts": self._clock()}, ensure_ascii=False).encode()
        return nonce + AESGCM(key).encrypt(nonce, plain, b"notarai-office")

    def open(self, envelope: bytes) -> dict:
        key = self._key()
        if key is None or len(envelope) < 29:
            raise OfficeError("Nieznane stanowisko.")
        try:
            payload = json.loads(AESGCM(key).decrypt(envelope[:12], envelope[12:], b"notarai-office"))
        except Exception:
            raise OfficeError("Nieznane stanowisko.") from None
        now = self._clock()
        if abs(now - float(payload.get("ts", 0))) > WINDOW_S:
            raise OfficeError("Zegary stanowisk różnią się o więcej niż 5 minut.")
        with self._lock:
            self._seen = {n: t for n, t in self._seen.items() if t > now - WINDOW_S}
            if envelope[:12] in self._seen:
                raise OfficeError("Powtórzona wiadomość.")
            self._seen[envelope[:12]] = now
        return payload

    # ------------------------------------------------------------ requests between stations
    def request(self, station: str, kind: str, **data) -> str:
        """Queue a request for another station (print, screen); its answer arrives in `answers`."""
        if not any(p["name"].lower() == station.lower() for p in self.peers()):
            raise OfficeError(f"Nie ma stanowiska „{station}”. Napisz „stanowiska”, żeby zobaczyć połączone.")
        ident = secrets.token_hex(6)
        name = next(p["name"] for p in self.peers() if p["name"].lower() == station.lower())
        with self._lock:
            self._outbox.setdefault(name, []).append({"id": ident, "kind": kind, **data})
        return ident

    def _carry_out(self, ask: dict, origin: str) -> dict:
        try:
            if ask["kind"] == "print":
                if self._print is None:
                    raise OfficeError("Na tym stanowisku drukowanie nie działa.")
                self._print(ask["name"], _unb64(ask["data"]), ask.get("printer"))
                return {"id": ask["id"], "ok": True, "detail": f"Wydrukowano {ask['name']} na stanowisku {self._name()}."}
            if ask["kind"] == "screen":
                if not self._screen_allowed() or self._screen is None:
                    return {"id": ask["id"], "ok": False,
                            "detail": f"Stanowisko {self._name()} nie zezwala na podgląd ekranu."}
                self.watched_by = (origin, self._clock())
                return {"id": ask["id"], "ok": True, "image": _b64(self._screen())}
            return {"id": ask["id"], "ok": False, "detail": "Nieznane polecenie."}
        except OfficeError as error:
            return {"id": ask["id"], "ok": False, "detail": str(error)}
        except Exception:
            return {"id": ask["id"], "ok": False, "detail": f"Stanowisko {self._name()} nie wykonało polecenia."}

    # ------------------------------------------------------------ sync: answering and asking
    def handle_sync(self, envelope: bytes) -> bytes:
        ask = self.open(envelope)
        origin = str(ask.get("from", ""))[:60]
        if not any(p["name"] == origin for p in self.peers()):
            raise OfficeError("Nieznane stanowisko.")
        revisions = self._vault.revisions_since(int(ask.get("revisions", 0)))
        notes, tombs = self._vault.notes_since(int(ask.get("notes", 0)))
        for answer in ask.get("results", []):
            self.answers[answer["id"]] = answer
        with self._lock:
            requests, self._outbox[origin] = self._outbox.get(origin, []), []
            results, self._results[origin] = self._results.get(origin, []), []
        return self.seal({
            "from": self._name(), "printers": self._printers(), "screen": bool(self._screen_allowed()),
            "revisions": [{**r, "data": _b64(r["data"])} for r in revisions],
            "notes": notes, "tombs": tombs, "requests": requests, "results": results,
        })

    def sync_once(self) -> dict:
        """Ask every joined station for its changes; apply them here. Returns counts per station."""
        done = {}
        peers = self.peers()
        for peer in peers:
            with self._lock:
                results, self._results[peer["name"]] = self._results.get(peer["name"], []), []
            try:
                reply = self.open(self._transport(peer["address"], "sync", self.seal({
                    "from": self._name(), "revisions": peer["revisions"], "notes": peer["notes"], "results": results})))
            except Exception:
                with self._lock:              # keep the answers for the next attempt
                    self._results.setdefault(peer["name"], [])[:0] = results
                done[peer["name"]] = None
                continue
            applied = 0
            for revision in reply["revisions"]:
                self._vault.import_revision(revision["id"], revision["version"], revision["name"],
                                            _unb64(revision["data"]), revision["case"], "sync:" + peer["name"])
                peer["revisions"] = max(peer["revisions"], revision["created"])
                applied += 1
            stamps = [e.get("updated", 0) for e in reply["notes"].get("calendar", []) + reply["notes"].get("lessons", [])]
            stamps += [m.get("created", 0) for m in reply["notes"].get("messages", [])] + [t["ts"] for t in reply["tombs"]]
            applied += self._vault.apply_notes(reply["notes"], reply["tombs"])
            if stamps:
                peer["notes"] = max(peer["notes"], *stamps)
            for answer in reply.get("results", []):
                self.answers[answer["id"]] = answer
            for ask in reply.get("requests", []):
                outcome = self._carry_out(ask, peer["name"])
                with self._lock:
                    self._results.setdefault(peer["name"], []).append(outcome)
            self.stations[peer["name"]] = {"printers": reply.get("printers", []), "screen": reply.get("screen", False),
                                           "seen": self._clock()}
            done[peer["name"]] = applied
        if peers:
            current = {p["name"]: p for p in self.peers()}
            for peer in peers:                 # cursors move only for stations still joined
                if peer["name"] in current:
                    current[peer["name"]].update(revisions=peer["revisions"], notes=peer["notes"])
            self._save_peers(list(current.values()))
        return done


def windows_printers() -> list[str]:
    if os.name != "nt":
        return []
    try:
        import win32print

        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return [p[2] for p in win32print.EnumPrinters(flags)]
    except Exception:
        return []


def windows_print(name: str, data: bytes, printer: str | None = None) -> None:
    """Print a document with its program (Word for DOCX, the PDF reader...), on a chosen printer."""
    import tempfile

    if os.name != "nt":
        raise OfficeError("Drukowanie działa na komputerze z Windows.")
    import win32api

    folder = Path(tempfile.mkdtemp(prefix="notarai-druk-"))
    path = folder / Path(name).name
    path.write_bytes(data)
    if printer:
        win32api.ShellExecute(0, "printto", str(path), f'"{printer}"', str(folder), 0)
    else:
        win32api.ShellExecute(0, "print", str(path), None, str(folder), 0)


def windows_screen() -> bytes:
    """A picture of this computer's screen (JPEG), only when the station allows it."""
    import io

    from PIL import ImageGrab

    shot = ImageGrab.grab(all_screens=True)
    shot.thumbnail((1600, 1000))
    out = io.BytesIO()
    shot.convert("RGB").save(out, "JPEG", quality=60)
    return out.getvalue()
