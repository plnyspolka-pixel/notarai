import asyncio
import base64
import binascii
import re
import secrets
import os
import threading
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

from fastapi import FastAPI, Depends, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from . import recovery
from .aws_credentials import Account, ChallengeRequired, LoginError
from .bedrock import smoke_test
from .chat import Chat
from .connect_sdk import ConnectSession, LocalReceipts
from .devices import DeviceRegistry
from .docx_adapter import DOCX_APP, OpenXmlDocx
from .domain import fee_catalog, fee_estimate
from .drafting import DraftError, Drafts
from .inference import Inference, InferenceError
from .layout import Layouts
from .init_vault import home_path
from .local_secrets import read_secret
from .policy import Policy, PolicyError
from .rules import RuleViolation, Rules
from .procedures import ProcedureError, Procedures
from .replica import Replica, ReplicaError
from .settings import load as load_settings, save as save_settings, validate as validate_settings
from .sync import plan
from .usage import UsageLedger
from .vault import Vault, Conflict, MAX_BYTES, valid_case
from .workcopy import WorkCopies, WorkCopyError

CASE = r"^[\w.-]{1,64}$"
# The program's own folders in the vault (procedures, the office's style, its rules): not cases of clients,
# so they are not offered in the case list. Their documents stay where they are.
HIDDEN_CASES = frozenset({"procedury", "styl-kancelarii", "zasady-kancelarii"})
STATIC = {"pocket.js": "application/javascript", "pocket.css": "text/css",
          "pocket.webmanifest": "application/manifest+json", "pocket-sw.js": "application/javascript",
          "pocket-icon.svg": "image/svg+xml", "montserrat-latin.woff2": "font/woff2", "montserrat-latin-ext.woff2": "font/woff2",           "tunnel.js": "application/javascript", "qrcode.js": "application/javascript",
          "attention.js": "application/javascript", "attention.css": "text/css"}


class Identity(NamedTuple):
    id: str
    scope: str
    cases: frozenset | None = None   # None = whole vault


class Revision(BaseModel):
    id: str | None = None
    expected_version: int = Field(ge=0, strict=True)
    name: str = Field(min_length=1,max_length=255)
    content_b64: str = Field(max_length=((MAX_BYTES+2)//3)*4)
    case: str | None = Field(default=None, pattern=CASE)

class Invitation(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    scope: str = "read"
    cases: list[str] | None = Field(default=None, max_length=200)

class Redemption(BaseModel):
    code: str = Field(min_length=20,max_length=128)

class ManifestItem(BaseModel):
    id: str
    version: int = Field(ge=1,strict=True)

class Manifest(BaseModel):
    items: list[ManifestItem] = Field(max_length=10000)

class Question(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    names: list[str] = Field(default_factory=list, max_length=50)

class Target(BaseModel):
    id: str
    version: int = Field(ge=1, strict=True)

class Approval(BaseModel):
    name: str = Field(min_length=6, max_length=255)
    paragraphs: list[str] | None = Field(default=None, max_length=5000)
    base: Target | None = None
    template: Target | None = None

class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    mfa_code: str | None = Field(default=None, max_length=12)
    new_password: str | None = Field(default=None, max_length=256)

class ChatTurn(BaseModel):
    text: str = Field(default="", max_length=8000)
    case: str | None = Field(default=None, pattern=CASE)
    names: list[str] = Field(default_factory=list, max_length=50)
    confirm: str | None = Field(default=None, max_length=64)
    hello: bool = False


class Lesson(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    narration: str = Field(max_length=80000)                       # three quarters of an hour of talking
    frames: list[str] = Field(min_length=1, max_length=20)          # JPEG screenshots, base64
    recording_b64: str | None = Field(default=None, max_length=((MAX_BYTES+2)//3)*4)


class VoiceNote(BaseModel):
    audio_b64: str = Field(max_length=((MAX_BYTES+2)//3)*4)
    name: str = Field(default="notatka-glosowa.webm", min_length=1, max_length=255)
    case: str | None = Field(default=None, pattern=CASE)


class Segment(BaseModel):
    audio_b64: str = Field(max_length=4 * 1024 * 1024)
    suffix: str = Field(default=".webm", pattern=r"^\.(webm|ogg|m4a|mp4|wav)$")
    started_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=0, le=10 * 60 * 1000)


class Recording(BaseModel):
    recording_b64: str = Field(max_length=((MAX_BYTES+2)//3)*4)


class FeeRequest(BaseModel):
    parameters: dict


class _Throttle:
    """Bounds guessing on the one unauthenticated write endpoint."""
    def __init__(self, limit=10, window=60):
        self._limit, self._window, self._failures, self._lock = limit, window, [], threading.Lock()
    def blocked(self):
        with self._lock:
            now = time.monotonic()
            self._failures = [t for t in self._failures if now - t < self._window]
            return len(self._failures) >= self._limit
    def failed(self):
        with self._lock:
            self._failures.append(time.monotonic())


def _windows_folder_picker():
    """The standard Windows "choose a folder" dialog, on top of other windows."""
    import ctypes

    from win32com.shell import shell, shellcon

    owner = ctypes.windll.user32.GetForegroundWindow()
    flags = shellcon.BIF_RETURNONLYFSDIRS | shellcon.BIF_NEWDIALOGSTYLE
    chosen = shell.SHBrowseForFolder(owner, None, "Wybierz folder", flags, None, None)
    if not chosen or chosen[0] is None:
        return None
    path = shell.SHGetPathFromIDList(chosen[0])
    return path.decode("mbcs", "replace") if isinstance(path, bytes) else path


windows_folder_picker = _windows_folder_picker if sys.platform == "win32" else None


def create_app(home: Path, *, allow_bedrock: bool = True, inference: Inference | None = None,
               account: Account | None = None, opener=None, mail_detect=None, transcriber=None,
               fill_targets: dict | None = None, attention_opener=None, team_invoke=None, computer_roots=None, computer_starter=None, computer_parts: dict | None = None, folder_picker=None, updater=None, restarter=None,
               dictation_stream=None, environment_scan=None, mail_composer=None, registers=None,
               office_transport=None, office_address=None, device_scan=None, ipp=None, escl=None, to_pdf=None,
               service_send=None, web_calendar_api=None):
    recovery.finish_interrupted_rotation(home)
    vault = Vault(home, read_secret(home, "vault.key"))
    devices = DeviceRegistry(home)
    from .team import PERMISSIONS, Team, TeamError
    team = Team(vault, lambda: state["account"], "eu-central-1", invoke=team_invoke)

    def need(key: str) -> None:
        """What the notary allowed the person signed in on this station (code, not the model)."""
        if not team.may(key):
            raise TeamError(f"Notariusz nie dał Ci uprawnienia: {PERMISSIONS[key][0]}. Poproś notariusza o zmianę.")

    def need_http(key: str) -> None:
        try:
            need(key)
        except TeamError as error:
            raise HTTPException(403, str(error)) from None

    class Guarded:
        """A service whose state-changing methods first ask `need(...)`."""
        def __init__(self, target, rules_: dict):
            self._target, self._rules = target, rules_

        def __getattr__(self, name):
            value = getattr(self._target, name)
            if name in self._rules and callable(value):
                def guarded(*args, **kwargs):
                    need(self._rules[name])
                    return value(*args, **kwargs)
                return guarded
            return value
    settings = load_settings(home)
    ledger = UsageLedger(home)
    token = read_secret(home, "api.token").decode().strip()
    if len(token) < 40:
        raise ValueError("invalid local token")
    connect = ConnectSession(
        [OpenXmlDocx(vault)], {DOCX_APP: frozenset({"inspect_docx", "write_docx"})}, LocalReceipts(home))
    injected = inference is not None or account is not None
    state = {"settings": settings, "account": account, "inference": inference}

    def configure(new_settings):
        """(Re)build the AI objects from settings. Injected test doubles are left alone."""
        state["settings"] = new_settings
        if injected:
            if inference is None:          # an injected account still powers the chat's assistant
                policy = Policy(new_settings.ai.region, new_settings.ai.model) if allow_bedrock and account is not None else None
                state["inference"] = Inference(
                    policy, account.client_factory(new_settings.ai.region) if policy else None, ledger,
                    pseudonymize=lambda: state["settings"].ai.pseudonymize)
            return
        current = None
        if allow_bedrock and new_settings.account is not None:
            current = Account(home, new_settings.account_config())
        policy = None
        # The assistant is the chat: it works whenever this workstation has a NotarAI account.
        if allow_bedrock and current is not None:
            policy = Policy(new_settings.ai.region, new_settings.ai.model)
        state["account"] = current
        state["inference"] = Inference(
            policy, current.client_factory(new_settings.ai.region) if policy else None, ledger,
            pseudonymize=lambda: state["settings"].ai.pseudonymize)

    configure(settings)
    rules = Rules(vault)
    from .style import Style

    style = Style(vault)
    from .learning import Learning

    learning = Learning(vault, lambda: state["settings"].learn, inference=lambda: state["inference"])
    drafts = Drafts(vault, lambda: state["inference"], connect, rules=rules, style=style, learning=learning)
    redeem_throttle = _Throttle()
    workcopies = WorkCopies(home, vault, opener, rules=rules) if opener else WorkCopies(home, vault, rules=rules)
    mode = "local" if settings.ai.real_data_approved else "synthetic-only"   # real cases unless an old gate says otherwise

    def installed_version() -> str:
        """NotarAI 2 production: the installed version (wersja.json), or "2" when run from the sources."""
        from .updater import installed
        return (installed(Path(__file__).resolve().parents[1]) or {}).get("version", "2")
    settings = None   # read state["settings"]; it can change while the worker runs

    relay: dict = {"task": None, "client": None, "keys": None}

    async def restart_relay():
        """One outbound connection to the relay when remote access is on; none otherwise."""
        if relay["task"] is not None:
            relay["task"].cancel()
            relay["task"] = relay["client"] = None
        tunnel_settings = state["settings"].tunnel
        if not tunnel_settings.enabled:
            return
        from .tunnel import RelayClient, TunnelKeys

        relay["keys"] = relay["keys"] or TunnelKeys(home)
        relay["client"] = RelayClient(tunnel_settings.relay_url, relay["keys"], devices, app.state.dispatch)
        relay["task"] = asyncio.create_task(relay["client"].run())

    def replica():
        current = state["settings"]
        if not current.replica.enabled or state["account"] is None:
            return None
        return Replica(home, state["account"], current.replica.bucket, current.replica.region,
                       keep_days=current.replica.keep_days)

    def local_backup():
        current = state["settings"]
        if current.backup_dir is None:
            raise recovery.RecoveryError("Wskaż w ustawieniach katalog kopii (inny dysk niż ten komputer).")
        directory = Path(current.backup_dir)
        if not directory.is_dir():
            raise recovery.RecoveryError("Katalog kopii jest niedostępny. Podłącz dysk i spróbuj ponownie.")
        name = time.strftime("notarai-%Y%m%d-%H%M%S.notarai-backup")
        manifest = recovery.backup(home, directory / name)
        return {"file": name, "documents": manifest["documents"], "revisions": manifest["revisions"]}

    def due(action: str, hours: int = 24) -> bool:
        last = vault.last_action(action)
        return last is None or time.time_ns() - last > hours * 3600 * 10**9

    from .updater import Updater

    program = updater or Updater(Path(__file__).resolve().parents[1])

    def check_updates() -> None:
        checked = program.state["checked"]
        if program.current is not None and (checked is None or time.time() - checked > 6 * 3600):
            program.check()

    def restart_for_update() -> None:
        """Start the launcher anew (it swaps the files in and reopens the window), then end this worker."""
        if restarter is not None:
            restarter()
            return
        import os
        import subprocess

        app_dir = Path(__file__).resolve().parents[1]
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        flags = 0x00000008 | 0x00000200 | 0x08000000      # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
        subprocess.Popen([str(pythonw if pythonw.is_file() else sys.executable), "-X", "utf8",
                          str(app_dir / "launch.py"), "--restart"], cwd=str(app_dir),
                         creationflags=flags if sys.platform == "win32" else 0, close_fds=True)
        threading.Timer(1.5, os._exit, [0]).start()

    def maintain() -> dict:
        """Daily copies without anyone remembering: local disk when present, off-site when enabled."""
        done = {}
        try:
            check_updates()
        except Exception:
            pass        # never let an update check stop the copies
        if not recovery.enrolled(home):
            return done
        if state["settings"].backup_dir is not None and due("backup"):
            try:
                done["local"] = local_backup()["file"]
            except (recovery.RecoveryError, OSError):
                pass        # disk unplugged or full: the panel shows the overdue notice
        target = replica()
        if target is not None and state["account"].signed_in and due("offsite-backup", state["settings"].replica.every_hours):
            try:
                done["offsite"] = target.upload()["file"]
            except (ReplicaError, recovery.RecoveryError, LoginError, OSError):
                pass
        return done

    app_maintain = maintain

    async def listening_loop():
        while True:
            await asyncio.sleep(3)
            try:
                await asyncio.to_thread(app.state.listening.tick)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass        # one bad segment must not stop the microphones

    async def maintenance_loop():
        while True:
            await asyncio.sleep(120)
            try:
                await asyncio.to_thread(maintain)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass        # full disk, locked file: try again next round; the panel shows the overdue copy
            await asyncio.sleep(600)       # hourly copies stay hourly

    @asynccontextmanager
    async def lifespan(_app):
        from .local_lock import acquire

        _app.state.lock = acquire(home)       # one serving process per vault; key rotation checks this
        _app.state.loop = asyncio.get_running_loop()
        await restart_relay()
        upkeep = asyncio.create_task(maintenance_loop())
        ears = asyncio.create_task(listening_loop())
        together = asyncio.create_task(office_loop())
        diary = asyncio.create_task(web_calendar_loop())
        yield
        upkeep.cancel()
        ears.cancel()
        together.cancel()
        diary.cancel()
        try:
            _app.state.close_browser()
        except Exception:
            pass
        if relay["task"] is not None:
            relay["task"].cancel()
        _app.state.lock.close()

    app = FastAPI(title="NotarAI 2.0 development worker", docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)

    LISTEN_PATHS = {"/v2/listen", "/v2/listen/state"}

    def identify(authorization: str) -> Identity:
        if secrets.compare_digest(authorization.encode(), ("Bearer "+token).encode()):
            return Identity("local-admin","admin")
        if authorization.startswith("Tunnel ") and authorization[7:] in internal:
            return internal[authorization[7:]]     # minted in-process for one tunnelled request
        if authorization.startswith("Bearer "):
            device = devices.authenticate(authorization[7:])
            if device:
                return Identity(*device)
        raise HTTPException(401,"unauthorized")

    def auth(request: Request, authorization: str = Header(default="")) -> Identity:
        identity = identify(authorization)
        if identity.scope == "listen" and request.url.path not in LISTEN_PATHS:
            # A microphone sends sound and nothing else: no documents, no chat, no settings.
            raise HTTPException(403, "microphone only")
        return identity

    def admin(identity: Identity = Depends(auth)) -> Identity:
        if identity.scope != "admin":
            raise HTTPException(403,"admin required")
        return identity

    def writable(identity: Identity = Depends(auth)) -> Identity:
        if identity.scope not in {"admin","write"}:
            raise HTTPException(403,"read only")
        return identity

    def see_case(identity: Identity, case):
        """A restricted device learns nothing about other cases, not even that they exist."""
        if identity.cases is not None and case not in identity.cases:
            raise HTTPException(404, "not found")

    def see_document(identity: Identity, doc_id: str):
        try:
            see_case(identity, vault.case_of(doc_id))
        except (KeyError, ValueError):
            raise HTTPException(404, "not found")

    internal: dict[str, Identity] = {}

    async def dispatch(device_id: str, method: str, path: str, body):
        """Run a tunnelled request through this same app, as that device, with every check intact."""
        import httpx

        known = devices.lookup(device_id)       # re-read on every request, so revocation is immediate
        if known is None or known["scope"] not in {"read", "write", "listen"}:
            return 401, {"detail": "unauthorized"}
        if path.split("?")[0] in {"/v2/devices/redeem", "/v2/devices/invite", "/v2/admin/reopen"} \
                or path.startswith("/v2/attention/"):
            return 403, {"detail": "local only"}      # pairing through the tunnel has its own message
        ticket = secrets.token_urlsafe(32)
        internal[ticket] = Identity(device_id, known["scope"], frozenset(known["cases"]) if known["cases"] else None)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://127.0.0.1") as client:
                response = await client.request(
                    method, path, json=body if method == "POST" else None,
                    headers={"Authorization": "Tunnel " + ticket})
        except Exception:
            # One bad request must never take the relay connection, and every other device, down.
            return 500, {"detail": "request failed"}
        finally:
            internal.pop(ticket, None)
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, None

    app.state.dispatch = dispatch
    app.state.maintain = app_maintain
    app.state.devices = devices

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({"detail":"invalid request"},status_code=422)

    @app.exception_handler(PolicyError)
    async def policy_blocked(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.exception_handler(InferenceError)
    async def inference_failed(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=502)

    @app.exception_handler(DraftError)
    async def draft_failed(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(LoginError)
    async def login_failed(request, exc):
        body = {"detail": str(exc)}
        if isinstance(exc, ChallengeRequired):
            body["challenge"] = exc.kind
        return JSONResponse(body, status_code=401)

    @app.exception_handler(WorkCopyError)
    async def workcopy_failed(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ReplicaError)
    async def replica_failed(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=502)

    @app.exception_handler(recovery.RecoveryError)
    async def recovery_failed(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.middleware("http")
    async def no_cache(request, call_next):
        if request.url.hostname not in {"127.0.0.1","localhost","testserver"}:
            return JSONResponse({"detail":"invalid host"},status_code=403,headers={"Cache-Control":"no-store"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        relay_origin = state["settings"].tunnel.relay_origin()
        connect_src = "'self'" + (" " + relay_origin if relay_origin else "")
        response.headers["Content-Security-Policy"] = f"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; manifest-src 'self'; worker-src 'self'; connect-src {connect_src}; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    # ------------------------------------------------------------ devices
    @app.post("/v2/devices/invite",dependencies=[Depends(admin)])
    def invite(req: Invitation):
        try:
            return devices.invite(req.name,req.scope,cases=req.cases)
        except ValueError:
            raise HTTPException(400,"invalid invitation")

    @app.post("/v2/devices/redeem")
    def redeem(req: Redemption):
        if redeem_throttle.blocked():
            raise HTTPException(429, "too many attempts")
        try:
            return devices.redeem(req.code)
        except PermissionError:
            redeem_throttle.failed()
            raise HTTPException(403,"invalid invitation")

    @app.get("/v2/devices",dependencies=[Depends(admin)])
    def list_devices():
        return devices.list()

    @app.delete("/v2/devices/{device_id}",dependencies=[Depends(admin)])
    def revoke(device_id: str):
        if not devices.revoke(device_id):
            raise HTTPException(404,"device not found")
        vault.log("local-admin", "revoke-device")
        return {"revoked":True}

    @app.post("/v2/sync/plan")
    def sync_plan(req: Manifest, identity: Identity = Depends(auth)):
        try:
            return plan(vault.list(identity.cases),[x.model_dump() for x in req.items])
        except ValueError:
            raise HTTPException(400,"invalid manifest")

    # ------------------------------------------------------------ Pocket
    @app.get("/v2/pocket")
    def pocket():
        return FileResponse(Path(__file__).with_name("pocket.html"),media_type="text/html")

    def static_route(asset: str, media_type: str):
        def serve():
            path = Path(__file__).with_name(asset)
            if not path.is_file():
                raise HTTPException(404, "not found")
            return FileResponse(path, media_type=media_type)
        app.get("/v2/" + asset)(serve)

    for asset, media_type in STATIC.items():
        static_route(asset, media_type)

    # ------------------------------------------------------------ status
    @app.get("/v2/health",dependencies=[Depends(auth)])
    def health():
        ai = "aws-bedrock" if allow_bedrock else "disabled"
        return {"version": installed_version(),"storage":"local","ai":ai,"mode":mode}

    @app.get("/v2/status")
    def status(identity: Identity = Depends(auth)):
        last_backup = vault.last_action("backup")
        settings, account, inference = state["settings"], state["account"], state["inference"]
        overdue = last_backup is None or time.time_ns() - last_backup > settings.backup_reminder_days * 86400 * 10**9
        return {
            "version": installed_version(), "mode": mode, "scope": identity.scope, "station": settings.station_name,
            "cases": sorted(identity.cases) if identity.cases is not None else None,
            "ai": {"enabled": inference.enabled, "signed_in": bool(account and account.signed_in),
                   "account_configured": account is not None, "pseudonymize": inference.pseudonymizes},
            "recovery": {"enrolled": recovery.enrolled(home), "last_backup": last_backup and last_backup // 10**9,
                         "backup_overdue": overdue, "backup_dir_configured": settings.backup_dir is not None,
                         "offsite_enabled": settings.replica.enabled,
                         "last_offsite": (vault.last_action("offsite-backup") or 0) // 10**9 or None},
        }

    @app.get("/v2/settings", dependencies=[Depends(admin)])
    def settings_read():
        return state["settings"].model_dump()

    @app.get("/v2/tunnel", dependencies=[Depends(admin)])
    def tunnel_status():
        tunnel_settings = state["settings"].tunnel
        if not tunnel_settings.enabled:
            return {"enabled": False}
        from .tunnel import b64e

        return {
            "enabled": True, "connected": bool(relay["client"] and relay["client"].connected.is_set()),
            "relay": tunnel_settings.relay_url, "pocket": tunnel_settings.pocket_url,
            "office": relay["keys"].office, "key": b64e(relay["keys"].public),
        }

    @app.put("/v2/settings", dependencies=[Depends(admin)])
    async def settings_write(body: dict):
        try:
            new = validate_settings(body)
        except ValueError:
            raise HTTPException(400, "invalid settings")
        try:
            rules.check_setting(new.ai.pseudonymize)
        except RuleViolation as violation:
            raise HTTPException(403, str(violation))
        if new.ai.real_data_approved != state["settings"].ai.real_data_approved:
            # A release gate, not a preference: it is changed outside the application.
            raise HTTPException(403, "release gate cannot be changed here")
        if new.backup_dir is not None and not Path(new.backup_dir).is_dir():
            raise recovery.RecoveryError("Katalog kopii nie istnieje albo dysk nie jest podłączony.")
        save_settings(home, new)
        tunnel_changed = new.tunnel != state["settings"].tunnel
        configure(new)
        if tunnel_changed:        # otherwise connected phones would lose their sessions for nothing
            await restart_relay()
        vault.log("local-admin", "settings")
        return new.model_dump()

    @app.get("/v2/admin")
    def admin_page():
        return FileResponse(Path(__file__).with_name("admin.html"), media_type="text/html")

    @app.get("/v2/audit", dependencies=[Depends(admin)])
    def audit(limit: int = 200, doc_id: str | None = None):
        try:
            return vault.audit(limit, doc_id)
        except ValueError:
            raise HTTPException(400, "invalid document")

    @app.get("/v2/usage", dependencies=[Depends(admin)])
    def usage(since: int = 0):
        return ledger.summary(since)

    # ------------------------------------------------------------ recovery
    @app.post("/v2/recovery/enroll", dependencies=[Depends(admin)])
    def enroll():
        code = recovery.enroll(home)
        vault.log("local-admin", "enroll-recovery")
        return {"code": code}

    @app.post("/v2/backup", dependencies=[Depends(admin)])
    def backup():
        return local_backup()

    @app.post("/v2/backup/offsite", dependencies=[Depends(admin)])
    def backup_offsite():
        target = replica()
        if target is None:
            raise recovery.RecoveryError("Kopia poza kancelarią nie jest włączona na tym stanowisku.")
        return target.upload()

    @app.get("/v2/backup/offsite", dependencies=[Depends(admin)])
    def backup_offsite_list():
        target = replica()
        return target.list() if target is not None else []

    # ------------------------------------------------------------ documents
    @app.get("/v2/cases")
    def cases(identity: Identity = Depends(auth)):
        return [c for c in vault.cases() if (identity.cases is None or c in identity.cases) and c not in HIDDEN_CASES]

    @app.get("/v2/documents")
    def documents(include_names: bool = False, case: str | None = None, identity: Identity = Depends(auth)):
        allowed = identity.cases
        if case is not None:
            see_case(identity, case)
            allowed = frozenset({case})
        return vault.summaries(allowed) if include_names else vault.list(allowed)

    @app.post("/v2/documents")
    def save(revision: Revision, identity: Identity = Depends(writable)):
        need_http("sprawy")
        try:
            data = base64.b64decode(revision.content_b64,validate=True)
            existing = None
            if revision.id is not None:
                try:
                    existing = vault.case_of(revision.id)
                    known = True
                except KeyError:
                    known = False
                if known:
                    see_case(identity, existing)      # also for expected_version 0: no hint that it exists
            if revision.id is None or not known:
                see_case(identity, revision.case)
            doc_id, version = vault.put(
                revision.id,revision.expected_version,revision.name,data,actor=identity.id,case=revision.case)
            return {"id":doc_id,"version":version}
        except Conflict:
            raise HTTPException(409,"revision conflict")
        except (ValueError,binascii.Error):
            raise HTTPException(400,"invalid document")

    @app.get("/v2/documents/{doc_id}/versions")
    def versions(doc_id: str, identity: Identity = Depends(auth)):
        see_document(identity, doc_id)
        try:
            return vault.versions(doc_id)
        except (KeyError, ValueError):
            raise HTTPException(404, "not found")

    @app.get("/v2/documents/{doc_id}")
    def read(doc_id: str, version: int | None = Query(default=None, ge=1, le=2**62),
             identity: Identity = Depends(auth)):
        see_document(identity, doc_id)
        try:
            rev,name,data = vault.get(doc_id,version,actor=identity.id)
            return {"id":doc_id,"version":rev,"name":name,"content_b64":base64.b64encode(data).decode()}
        except (KeyError,ValueError):
            raise HTTPException(404,"not found")

    # ------------------------------------------------------------ editing in Word (this computer only)
    @app.get("/v2/workcopies", dependencies=[Depends(admin)])
    def workcopies_list():
        return workcopies.list()

    @app.post("/v2/documents/{doc_id}/checkout")
    def checkout(doc_id: str, identity: Identity = Depends(admin)):
        return workcopies.checkout(doc_id, identity.id)

    @app.post("/v2/workcopies/{doc_id}/checkin")
    def checkin(doc_id: str, identity: Identity = Depends(admin)):
        return workcopies.checkin(doc_id, identity.id)

    @app.delete("/v2/workcopies/{doc_id}")
    def workcopy_discard(doc_id: str, identity: Identity = Depends(admin)):
        workcopies.discard(doc_id, identity.id)
        return {"discarded": True}

    # ------------------------------------------------------------ assistant
    @app.get("/v2/taksa/katalog", dependencies=[Depends(auth)])
    def taksa_katalog():
        return [{"id": r["id"], "grupa": r["grupa"], "nazwa": r["nazwa"]} for r in fee_catalog()["rodzaje"]]

    @app.post("/v2/taksa", dependencies=[Depends(auth)])
    def taksa(req: FeeRequest):
        try:
            return fee_estimate(req.parameters)
        except (ValueError, TypeError, ArithmeticError, KeyError):
            raise HTTPException(400, "invalid parameters")

    def known_case(identity: Identity, case: str):
        if not valid_case(case):
            raise HTTPException(404, "not found")
        see_case(identity, case)

    @app.post("/v2/cases/{case}/ask")
    def ask(case: str, req: Question, identity: Identity = Depends(auth)):
        known_case(identity, case)
        return drafts.ask(case, req.text, identity.id, req.names)

    @app.post("/v2/cases/{case}/draft")
    def draft(case: str, req: Question, identity: Identity = Depends(writable)):
        known_case(identity, case)
        return drafts.propose(case, req.text, identity.id, req.names).public()

    @app.get("/v2/drafts/{draft_id}")
    def draft_read(draft_id: str, identity: Identity = Depends(writable)):
        return drafts.get(draft_id, identity.id).public()

    @app.post("/v2/drafts/{draft_id}/approve")
    def draft_approve(draft_id: str, req: Approval, identity: Identity = Depends(writable)):
        need_http("zatwierdzanie")
        proposed = drafts.get(draft_id, identity.id)
        result = drafts.approve(
            draft_id, identity.id, req.name, paragraphs=req.paragraphs,
            base=req.base.model_dump() if req.base else None,
            template=req.template.model_dump() if req.template else None,
        )
        onboarding.mark("akt")        # the first whole act: a step of the first-run guide
        learned = []
        if req.paragraphs is not None:
            try:
                learned = learning.from_draft(proposed.paragraphs, req.paragraphs, vault.parties(proposed.case),
                                              kind=proposed.instruction[:60])
            except Exception:
                learned = []           # learning never stands in the way of saving
        return {**result, "learned": [{"id": l["id"], "text": l["text"]} for l in learned]} if isinstance(result, dict) else result

    @app.delete("/v2/drafts/{draft_id}")
    def draft_discard(draft_id: str, identity: Identity = Depends(writable)):
        drafts.discard(draft_id, identity.id)
        return {"discarded": True}

    # ------------------------------------------------------------ chat
    def chat_status():
        current, last = state["settings"], vault.last_action("backup")
        return {
            "mode": mode, "enrolled": recovery.enrolled(home), "last_backup": last,
            "backup_overdue": last is None or time.time_ns() - last > current.backup_reminder_days * 86400 * 10**9,
            "offsite": current.replica.enabled, "last_offsite": vault.last_action("offsite-backup"),
            "documents": len(vault.list()), "cases": len(vault.cases()),
            "devices": sum(1 for d in devices.list() if not d["revoked"]),
            "workcopies": len(workcopies.list()),
            "ai": state["inference"].enabled, "pseudonymize": state["inference"].pseudonymizes,
            "signed_in": bool(state["account"] and state["account"].signed_in),
            "tunnel": current.tunnel.enabled,
            "tunnel_connected": bool(relay["client"] and relay["client"].connected.is_set()),
        }

    def update_settings(mutate):
        data = state["settings"].model_dump()
        mutate(data)
        new = validate_settings(data)
        rules.check_setting(new.ai.pseudonymize)
        if new.backup_dir is not None and not Path(new.backup_dir).is_dir():
            raise recovery.RecoveryError("Ten katalog nie istnieje albo dysk nie jest podłączony.")
        state["relay_dirty"] = state.get("relay_dirty") or new.tunnel != state["settings"].tunnel
        save_settings(home, new)
        configure(new)
        vault.log("local-admin", "settings")

    def pairing_link(code: str):
        current = state["settings"].tunnel
        if not current.enabled or relay["keys"] is None:
            return None
        from urllib.parse import urlencode
        from .tunnel import b64e

        return current.pocket_url + "#" + urlencode(
            {"r": current.relay_url, "o": relay["keys"].office, "k": b64e(relay["keys"].public), "c": code})

    def offsite_backup():
        target = replica()
        if target is None:
            raise recovery.RecoveryError("Kopia poza kancelarią wymaga zalogowania kontem NotarAI.")
        return target.upload()

    def enroll_code(replace: bool):
        code = recovery.enroll(home, replace=replace)
        vault.log("local-admin", "enroll-recovery")
        return code

    layouts = Layouts(home)
    from .autofill import Autofill, FillError

    browser_box: dict = {}

    def web_target():
        if "web" not in browser_box:
            from .web_fill import Browser

            browser_box["web"] = Browser(home / "przegladarka", choice=lambda: state["settings"].agent.browser)
            browser_box["web"].background(lambda: state["settings"].agent.background)
        return browser_box["web"]

    def desktop_target():
        if "desktop" not in browser_box:
            from .win_fill import Desktop

            browser_box["desktop"] = Desktop()
        return browser_box["desktop"]

    def form_receipt(actor, action, procedure, kind, outcome):
        vault.log(actor, f"form-{action}-{outcome}")

    autofill = Autofill(fill_targets if fill_targets is not None else {"strona": web_target, "program": desktop_target},
                        receipts=form_receipt, rules=rules)
    app.state.close_browser = lambda: [b.close() for b in list(browser_box.values()) if hasattr(b, "close")]
    from .agent import Computer
    agent_computer = Computer(home, desktop=(fill_targets or {}).get("program", desktop_target),
                              browser=(fill_targets or {}).get("strona", web_target), rules=rules,
                              roots=(lambda: computer_roots) if computer_roots is not None else None,
                              starter=computer_starter, **(computer_parts or {}),
                              allowed=lambda: {"screen": state["settings"].agent.screen,
                                               "commands": state["settings"].agent.commands})

    @app.exception_handler(FillError)
    async def fill_failed(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)
    procedures = Procedures(vault, lambda: state["inference"], drafts)

    @app.exception_handler(ProcedureError)
    async def procedure_failed(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    from . import transcribe as local_speech

    from .cloud_speech import CloudSpeech, SpeechError

    def speech_available() -> bool:
        speech = state["settings"].speech
        if transcriber is not None:
            return True
        if speech.where == "chmura":
            return state["account"] is not None        # streaming needs no bucket; batch fallback does
        return local_speech.available()

    def speech_to_text(audio: bytes, suffix: str = ".webm") -> str | None:
        """None when speech recognition is not set up; raises on a failed attempt."""
        speech = state["settings"].speech
        if transcriber is not None:
            return transcriber(audio)
        if not speech_available():
            return None
        if speech.where == "chmura":
            return CloudSpeech(state["account"], speech.bucket, state["settings"].ai.region).transcribe(audio, suffix)
        return local_speech.transcribe(audio, speech.model, home / "modele-mowy", suffix)

    # ------------------------------------------------------------ live dictation into the message box
    from .cloud_speech import Dictation, transcribe_stream

    dictations: dict[str, tuple[str, Dictation]] = {}

    class DictationPiece(BaseModel):
        pcm_b64: str = Field(default="", max_length=400_000)      # a few seconds of 16 kHz PCM at most
        end: bool = False

    def local_dictation_stream(source, on_text):
        """Speech on this computer: collect the audio, then transcribe it once at the end."""
        import io
        import wave

        pcm = bytearray()
        while True:
            piece = source.get(timeout=60)
            if piece is None:
                break
            pcm += piece
            if len(pcm) > 16000 * 2 * 600:
                break
        on_text([], "…")
        wav = io.BytesIO()
        with wave.open(wav, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(bytes(pcm))
        heard = speech_to_text(wav.getvalue(), ".wav") or ""
        on_text([heard] if heard else [], "")

    def dictation_source():
        if dictation_stream is not None:
            return dictation_stream
        speech = state["settings"].speech
        if speech.where == "chmura" and transcriber is None:
            if state["account"] is None or not state["account"].signed_in:
                raise HTTPException(409, "Najpierw zaloguj stanowisko kontem NotarAI: napisz „zaloguj”. Bez tego "
                                         "Frankfurt nie przepisze mowy.")
            return transcribe_stream(state["account"].credentials, state["settings"].ai.region)
        if not speech_available():
            raise HTTPException(409, "Rozpoznawanie mowy nie jest jeszcze ustawione. Napisz „gdzie są dane”.")
        return local_dictation_stream

    def speech_check() -> list[tuple[bool, str]]:
        """Step by step, why dictation may give no text: setting, sign-in, credentials, stream, second way."""
        import time as _time

        speech, account = state["settings"].speech, state["account"]
        out = [(True, "Mowa: " + ("we Frankfurcie (Amazon Transcribe)." if speech.where == "chmura" else "na tym komputerze."))]
        if speech.where != "chmura":
            ok = local_speech.available()
            return out + [(ok, "Moduł mowy na tym komputerze: " + ("jest." if ok else "brak; napisz „mowa we frankfurcie”."))]
        if account is None:
            return out + [(False, "Konto NotarAI: brak ustawień konta na tym stanowisku. Zainstaluj NotarAI ponownie.")]
        if not account.signed_in:
            return out + [(False, "Logowanie: stanowisko NIE jest zalogowane. Napisz „zaloguj” i zaloguj się kontem NotarAI.")]
        out.append((True, "Logowanie: stanowisko zalogowane."))
        try:
            account.credentials()
            out.append((True, "Dostęp do usług we Frankfurcie: jest."))
        except Exception as error:
            return out + [(False, f"Dostęp do usług we Frankfurcie: odmowa ({error.__class__.__name__}). Wyloguj i zaloguj "
                                  "się ponownie; jeśli to nie pomoże, konto może nie mieć uprawnień do NotarAI 2.")]
        started = _time.monotonic()
        probe = Dictation(transcribe_stream(account.credentials, state["settings"].ai.region))
        probe.feed(b"\x00\x00" * 16000)
        probe.finish()
        probe.done.wait(30)
        took = _time.monotonic() - started
        if probe.cause is None and probe.done.is_set():
            out.append((True, f"Szybkie dyktowanie (strumień): działa, odpowiedź w {took:.1f} s."))
        else:
            out.append((False, "Szybkie dyktowanie (strumień): nie działa (" + (probe.cause or "brak odpowiedzi") + "). "
                               "Najczęściej sieć kancelarii albo zapora blokuje połączenie HTTP/2 do "
                               "transcribestreaming.eu-central-1.amazonaws.com (port 443)."))
        out.append((bool(speech.bucket), "Druga droga (wolniejsza, przez zaszyfrowany bucket we Frankfurcie): "
                                         + ("gotowa." if speech.bucket else "nieustawiona.")))
        return out

    @app.post("/v2/admin/reopen")
    def admin_reopen(request: Request):
        """The NotarAI window on this computer lost its session (restart, update, refresh): a fresh one-time
        panel code, only for a same-origin page on this very computer. Phones (tunnel), other stations
        (office network) and other websites cannot reach or read it; local programs of the same Windows user
        could already open the program from its icon."""
        client = request.client.host if request.client else ""
        host = request.headers.get("host", "")
        origin = request.headers.get("origin")
        site = request.headers.get("sec-fetch-site")
        local_host = re.fullmatch(r"(127\.0\.0\.1|localhost)(:\d+)?", host)
        if client not in {"127.0.0.1", "::1", "testclient"} or not local_host \
                or (origin is not None and origin != f"http://{host}") or (site is not None and site != "same-origin"):
            raise HTTPException(403, "only for the NotarAI window on this computer")
        return {"code": devices.invite("panel stanowiska", "admin", replace_pending=True, allow_admin=True)["code"]}

    @app.post("/v2/dictation")
    def dictation_start(identity: Identity = Depends(auth)):
        now = time.monotonic()
        for key in [k for k, (_, d) in dictations.items() if now - d.touched > 60 or d.done.is_set() and now - d.touched > 10]:
            dictations.pop(key)[1].finish()
        for key in [k for k, (owner, _) in dictations.items() if owner == identity.id]:
            dictations.pop(key)[1].finish()             # one dictation per device at a time
        ident = secrets.token_urlsafe(12)
        dictations[ident] = (identity.id, Dictation(dictation_source()))
        return {"id": ident}

    @app.post("/v2/dictation/{ident}")
    def dictation_piece(ident: str, piece: DictationPiece, identity: Identity = Depends(auth)):
        owner, dictation = dictations.get(ident, ("", None))
        if dictation is None or owner != identity.id:
            raise HTTPException(404, "not found")
        try:
            pcm = base64.b64decode(piece.pcm_b64, validate=True) if piece.pcm_b64 else b""
        except (ValueError, binascii.Error):
            raise HTTPException(400, "invalid audio")
        if pcm:
            dictation.feed(pcm)
        else:
            dictation.touched = time.monotonic()
        if piece.end:
            dictation.finish()
            dictation.done.wait(20)        # the last words arrive shortly after the end
            if (dictation.error and not dictation.login_needed or not dictation.text()) and len(dictation.audio) > 16000:
                # The stream failed or heard nothing: the whole recording the second (slower) way.
                from .cloud_speech import wav
                try:
                    heard = speech_to_text(wav(bytes(dictation.audio)), ".wav") or ""
                except Exception as error:
                    print(f"dyktowanie: druga droga nie dziala ({error.__class__.__name__})", file=sys.stderr, flush=True)
                    heard = ""
                if heard:
                    return {"text": learning.apply_dictation(heard), "done": True, "error": None, "second_way": True}
        return {"text": learning.apply_dictation(dictation.text()), "done": dictation.done.is_set(), "error": dictation.error,
                "login": dictation.login_needed}

    class Corrected(BaseModel):
        heard: str = Field(max_length=20_000)
        final: str = Field(max_length=20_000)

    @app.post("/v2/learning/dictation")
    def learning_dictation(req: Corrected, identity: Identity = Depends(writable)):
        return {"learned": [{"id": l["id"], "text": l["text"]} for l in learning.from_dictation(req.heard, req.final)]}

    class Decision(BaseModel):
        accept: bool

    @app.post("/v2/learning/{ident}")
    def learning_decide(ident: str, req: Decision, identity: Identity = Depends(writable)):
        decided = learning.decide(ident, req.accept, actor=identity.id)
        if decided is None:
            raise HTTPException(404, "not found")
        return {"status": decided["status"]}

    @app.get("/v2/learning")
    def learning_state(identity: Identity = Depends(auth)):
        return learning.summary()

    @app.delete("/v2/dictation/{ident}")
    def dictation_cancel(ident: str, identity: Identity = Depends(auth)):
        owner, dictation = dictations.get(ident, ("", None))
        if dictation is not None and owner == identity.id:
            dictations.pop(ident, None)
            dictation.finish()
        return {"ok": True}

    def heard_or_reason(audio: bytes, suffix: str):
        """(text, None) or (None, a sentence for the notary)."""
        try:
            heard = speech_to_text(audio, suffix)
        except LoginError as error:
            return None, str(error) + " Bez tego nie przepiszę nagrania."
        except SpeechError as error:
            return None, str(error)
        except Exception:
            return None, "Nie udało się rozpoznać mowy w tym nagraniu."
        if heard is None:
            return None, "Rozpoznawanie mowy nie jest skonfigurowane na tym stanowisku."
        if not heard:
            return None, "Nie rozpoznałem mowy w tym nagraniu."
        return heard, None

    @app.post("/v2/procedures/transcribe", dependencies=[Depends(admin)])
    def procedure_transcribe(req: Recording):
        """Narration to text on this computer; 409 means: type it instead."""
        try:
            audio = base64.b64decode(req.recording_b64, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(400, "invalid recording")
        heard, reason = heard_or_reason(audio, ".webm")
        if heard is None:
            raise ProcedureError(reason + " Wpisz komentarz ręcznie.")
        return {"text": heard}

    def store_voice_note(audio: bytes, name: str, case, actor: str) -> dict:
        """Keep the recording and, when speech recognition is available, its text beside it."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ".webm"
        if suffix not in local_speech.AUDIO:
            raise HTTPException(400, "not an audio file")
        original = re.sub(r"[^\w .-]", "", name.rsplit(".", 1)[0]).strip(" .")[:80]
        stem = f"notatka-glosowa-{stamp}" if not original or original.lower().startswith("notatka") else original
        audio_id, audio_version = vault.put(None, 0, stem + suffix, audio, actor=actor, case=case)
        stored = [{"id": audio_id, "name": stem + suffix, "version": audio_version}]
        heard, reason = heard_or_reason(audio, suffix)
        if heard is None:
            return {"documents": stored, "text": None if "nie jest skonfigurowane" in reason else "",
                    "detail": "Zapisałem nagranie. " + reason}
        body = f"Notatka głosowa z {time.strftime('%d.%m.%Y %H:%M')} (przepisana automatycznie, sprawdź):\n\n{heard}\n"
        text_name = stem + (" - tekst.txt" if stem != f"notatka-glosowa-{stamp}" else ".txt")
        text_id, text_version = vault.put(None, 0, text_name, body.encode(), actor=actor, case=case)
        stored.append({"id": text_id, "name": text_name, "version": text_version})
        return {"documents": stored, "text": heard, "detail": ""}

    from . import environment as environment_module

    found_here: dict = {}

    def environment(refresh: bool = False) -> dict:
        """What is on this computer (cached; the first scan starts with the worker)."""
        if refresh or not found_here:
            scanner = environment_scan or (lambda: environment_module.scan(mail_detect=mail_detect or mail_module.detect))
            found_here.clear()
            found_here.update(scanner())
            onboarding.mark("rozpoznanie")
        return dict(found_here)

    from .onboarding import Onboarding
    from .procedures import slug as procedure_slug

    def learned_activities() -> int:
        chosen = {procedure_slug(name) for name in onboarding.activities()}
        return len(chosen & {p["slug"] for p in procedures.list()})

    def has_device(scope: str) -> bool:
        return any(d["scope"] in ({scope} if scope == "listen" else {"read", "write"}) and not d["revoked"]
                   for d in devices.list())

    onboarding = Onboarding(home, {
        "kod": lambda: recovery.enrolled(home),
        "konto": lambda: bool(state["account"] and state["account"].signed_in),
        "kopia": lambda: state["settings"].backup_dir is not None or state["settings"].replica.enabled,
        "akty": lambda: state["settings"].acts_dir is not None,
        "styl": lambda: style.profile() is not None,
        "poczta": lambda: state["settings"].mail.source is not None,
        "learned": learned_activities,
        "telefon": lambda: has_device("write"),
        "mikrofony": lambda: has_device("listen"),
        "nazwa": lambda: bool(state["settings"].station_name),
        "kancelaria": lambda: app.state.office.joined if hasattr(app.state, "office") else False,
        "rola": lambda: app.state.office.joined if hasattr(app.state, "office") else False,
    })

    @app.post("/v2/pick-folder", dependencies=[Depends(admin)])
    def pick_folder():
        """A folder chosen in the Windows dialog on this computer (admin scope never comes through the tunnel)."""
        picker = folder_picker or windows_folder_picker
        if picker is None:
            raise HTTPException(501, "Wybieranie folderu działa tylko na komputerze z Windows. Napisz ścieżkę w czacie.")
        path = picker()
        return {"path": path if path and Path(path).is_dir() else None}

    # ------------------------------------------------------------ several workstations of one office
    from . import office as office_module

    def station_name() -> str:
        return state["settings"].station_name or "Stanowisko"

    office_link = office_module.OfficeLink(
        home, vault, station_name, transport=office_transport or office_module.http_transport,
        address=office_address, printers=office_module.windows_printers, printer=office_module.windows_print,
        screen=office_module.windows_screen if sys.platform == "win32" else None,
        screen_allowed=lambda: state["settings"].allow_screen, names=lambda: state["settings"].device_names)
    app.state.office = office_link

    from . import peripherals

    network_devices: dict = {"items": [], "when": 0.0}

    def find_devices(refresh: bool = False) -> list[dict]:
        """Printers and scanners in the office network (looked for at most every 10 minutes unless asked)."""
        if refresh or time.time() - network_devices["when"] > 600:
            network_devices["items"] = (device_scan or peripherals.discover)()
            network_devices["when"] = time.time()
        return list(network_devices["items"])

    def device_names() -> dict:
        names = {}
        for seen in office_link.stations.values():
            names.update(seen.get("names") or {})
        names.update(state["settings"].device_names)        # this station's own names win
        return names

    def office_lan_app():
        """The small server for the office network: only sealed envelopes from joined workstations."""
        from fastapi import FastAPI as _FastAPI
        from fastapi.responses import Response as _Response

        lan = _FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @lan.post("/office/{action}")
        async def office_action(action: str, request: Request):
            body = await request.body()
            if len(body) > 40 * 2**20 or action not in {"pair", "sync"}:
                return _Response(status_code=404)
            try:
                handler = office_link.handle_pair if action == "pair" else office_link.handle_sync
                return _Response(content=await asyncio.to_thread(handler, body), media_type="application/octet-stream")
            except Exception:
                return _Response(status_code=403)
        return lan

    app.state.office_lan_app = office_lan_app

    lan_server: dict = {"task": None}

    def start_office_server() -> None:
        """Listen in the office network (port 47321) once this station joins or invites; Windows asks once
        about the firewall. Only sealed envelopes are accepted there."""
        if lan_server["task"] is not None or office_transport is not None or sys.platform != "win32":
            return
        import uvicorn

        config = uvicorn.Config(office_lan_app(), host="0.0.0.0", port=office_module.PORT, access_log=False,
                                log_level="warning", lifespan="off")
        server = uvicorn.Server(config)
        if hasattr(server, "install_signal_handlers"):
            server.install_signal_handlers = lambda: None

        def begin():
            lan_server["task"] = asyncio.get_running_loop().create_task(server.serve())
        lan_server["task"] = "starting"
        try:
            asyncio.get_running_loop()
            begin()
        except RuntimeError:                        # called from a chat thread: hand it to the worker's loop
            loop = getattr(app.state, "loop", None)
            if loop is None:
                lan_server["task"] = None
                return
            loop.call_soon_threadsafe(begin)

    app.state.start_office_server = start_office_server

    async def office_loop():
        if office_link.joined:
            start_office_server()
        while True:
            busy = any(office_link._outbox.values())
            await asyncio.sleep(1 if busy else 5)
            if office_link.joined:
                try:
                    await asyncio.to_thread(office_link.sync_once)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass            # the other computer is off: try again later

    async def web_calendar_loop():
        """Every two minutes: the calendar the same here and in notarai.pl. Quiet on any trouble (no entry
        content is ever logged); the notary sees the result on „synchronizuj kalendarz”."""
        while True:
            await asyncio.sleep(120)
            if not state["settings"].calendar.web_sync:
                continue
            try:
                await asyncio.to_thread(web_calendar.sync)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

    # ------------------------------------------------------------ what the program is doing, in plain words
    activity: dict[str, list] = {}

    def narrate(identity: Identity, line: str) -> None:
        """One step of the current work, shown live under the notary's message (no document content)."""
        lines = activity.setdefault(identity.id, [])
        lines.append({"n": (lines[-1]["n"] + 1) if lines else 1, "text": line, "at": time.time()})
        del lines[:-600]          # the agent's exact log of a long task stays readable to its end

    @app.get("/v2/activity")
    def activity_since(after: int = 0, identity: Identity = Depends(auth)):
        return {"lines": [l for l in activity.get(identity.id, []) if l["n"] > after]}

    # ------------------------------------------------------------ long tasks (registers): run in the background
    jobs: dict[str, dict] = {}

    def start_job(identity: Identity, work) -> str:
        """`work()` returns chat blocks; the window asks for them by id until they are ready."""
        now = time.monotonic()
        for key in [k for k, v in jobs.items() if now - v["created"] > 3600]:
            jobs.pop(key, None)
        ident = secrets.token_urlsafe(12)
        job = {"owner": identity.id, "created": now, "seen": now, "done": threading.Event(), "blocks": None}
        jobs[ident] = job

        def run():
            try:
                job["blocks"] = work()
            except SAID as error:
                job["blocks"] = [{"type": "text", "text": str(error)}]
            except Exception:
                job["blocks"] = [{"type": "text", "text": "Zadanie nie powiodło się. Spróbuj ponownie."}]
            job["done"].set()
        threading.Thread(target=run, daemon=True, name="notarai-zadanie").start()
        return ident

    @app.get("/v2/jobs/{ident}")
    def job_result(ident: str, identity: Identity = Depends(auth)):
        job = jobs.get(ident)
        if job is None or job["owner"] != identity.id:
            raise HTTPException(404, "not found")
        job["seen"] = time.monotonic()          # the window is still open and waiting for this job
        if not job["done"].is_set():
            return {"done": False}
        jobs.pop(ident, None)
        return {"done": True, "blocks": job["blocks"]}

    from .service import ServiceDesk, ServiceError

    service_desk = ServiceDesk(home, vault, lambda: state["account"], state["settings"].ai.region,
                               lambda: state["settings"].station_name or "Stanowisko",
                               lambda: (program.current or {}).get("version"), send=service_send)

    from .registers import Registers

    def krz_target():
        """A browser of its own, without a window: KRZ is checked in the background."""
        if "krz" not in browser_box:
            from .web_fill import Browser

            browser_box["krz"] = Browser(home / "przegladarka-krz", headless=True,
                                         choice=lambda: state["settings"].agent.browser)
        return browser_box["krz"]

    register_service = registers or Registers(lambda: state["account"], state["settings"].ai.region,
                                              browser=krz_target, visible_browser=lambda: web_target())

    from .speech_model import ModelDownload

    model_download = ModelDownload(home / "modele-mowy")

    @app.get("/v2/speech/model", dependencies=[Depends(admin)])
    def speech_model_progress():
        return model_download.progress()

    voice_jobs: dict[str, dict] = {}

    @app.post("/v2/voice")
    def voice_note(req: VoiceNote, identity: Identity = Depends(writable)):
        """Stores the note and transcribes it in the background: the window never waits for the cloud.
        A quick result (under two seconds) comes back at once; otherwise the page asks again by job id."""
        import threading

        see_case(identity, req.case)
        try:
            audio = base64.b64decode(req.audio_b64, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(400, "invalid recording")
        if not audio or len(audio) > MAX_BYTES:
            raise HTTPException(400, "invalid recording")
        name = req.name or ""
        if "." in name and "." + name.rsplit(".", 1)[-1].lower() not in local_speech.AUDIO:
            raise HTTPException(400, "not an audio file")
        job = {"owner": identity.id, "done": threading.Event(), "result": None, "created": time.monotonic()}
        for key in [k for k, v in voice_jobs.items() if time.monotonic() - v["created"] > 3600]:
            voice_jobs.pop(key, None)

        def work():
            try:
                job["result"] = store_voice_note(audio, req.name, req.case, identity.id)
            except Exception:
                job["result"] = {"documents": [], "text": None, "detail": "Nie udało się zapisać notatki głosowej."}
            job["done"].set()
        threading.Thread(target=work, daemon=True, name="notarai-notatka").start()
        if job["done"].wait(2):
            return job["result"]
        ident = secrets.token_urlsafe(12)
        voice_jobs[ident] = job
        return {"job": ident, "documents": [], "text": None,
                "detail": "Przepisuję notatkę w chmurze. Tekst pojawi się tu sam, zwykle w ciągu minuty."}

    @app.get("/v2/voice/{ident}")
    def voice_note_result(ident: str, identity: Identity = Depends(writable)):
        job = voice_jobs.get(ident)
        if job is None or job["owner"] != identity.id:
            raise HTTPException(404, "not found")
        if not job["done"].is_set():
            return {"done": False}
        voice_jobs.pop(ident, None)
        return {"done": True, **job["result"]}

    from .listening import Listening
    from .docx_writer import extract as extract_docx

    from .terminarz import Calendar

    from . import web_calendar as web_calendar_module

    me = web_calendar_module.station_id(home)
    calendar = Calendar(vault, origin=lambda: me)

    def web_api():
        """The web calendar API with this station's login; None when it is not signed in."""
        if web_calendar_api is not None:
            return web_calendar_api()
        account = state["account"]
        if account is None or not account.signed_in:
            return None
        return web_calendar_module.http_api(state["settings"].calendar.web_url, account.id_token)

    web_calendar = web_calendar_module.WebCalendar(home, vault, me, web_api)
    listening = Listening(vault, lambda audio, suffix: speech_to_text(audio, suffix), lambda: state["inference"],
                          lambda: state["settings"].listen, extract=extract_docx, calendar=calendar)

    @app.get("/v2/calendar")
    def calendar_list(days: int = 14, start: str | None = None, identity: Identity = Depends(auth)):
        import datetime as dt

        first = None
        if start is not None:
            try:
                first = dt.date.fromisoformat(start)
            except ValueError:
                raise HTTPException(400, "invalid date")
        return {"items": calendar.upcoming(max(1, min(days, 92)), cases=identity.cases, start=first)}
    app.state.listening = listening

    def source_name(identity: Identity) -> str:
        if identity.scope == "admin":
            return "stanowisko"
        known = devices.lookup(identity.id)
        return known["name"] if known else "mikrofon"

    @app.post("/v2/listen")
    def listen_segment(req: Segment, identity: Identity = Depends(auth)):
        if identity.scope not in {"listen", "admin"}:
            raise HTTPException(403, "microphones only")
        try:
            audio = base64.b64decode(req.audio_b64, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(400, "invalid audio")
        accepted = listening.accept(source_name(identity), audio, req.suffix, req.started_ms / 1000, req.duration_ms / 1000)
        current = state["settings"].listen
        return {"accepted": accepted, "enabled": current.enabled, "paused": current.paused}

    @app.get("/v2/listen/state")
    def listen_state(identity: Identity = Depends(auth)):
        current = state["settings"].listen
        return {"enabled": current.enabled, "paused": current.paused, "source": source_name(identity)}

    def transcribe_document(doc_id: str, actor: str) -> dict:
        """Text for a recording already in the vault, stored next to it (the recording is not copied)."""
        version, name, data = vault.get(doc_id, actor=actor)
        if not local_speech.is_audio(name):
            raise ProcedureError("To nie jest nagranie.")
        heard, reason = heard_or_reason(data, "." + name.rsplit(".", 1)[-1].lower())
        if heard is None:
            return {"documents": [], "text": None, "detail": reason}
        text_name = name.rsplit(".", 1)[0] + " - tekst.txt"
        body = f"Tekst nagrania „{name}” (przepisany automatycznie, sprawdź):\n\n{heard}\n"
        text_id, text_version = vault.put(None, 0, text_name, body.encode(), actor=actor, case=vault.case_of(doc_id))
        return {"documents": [{"id": text_id, "name": text_name, "version": text_version}], "text": heard, "detail": ""}

    @app.post("/v2/procedures/learn")
    def procedure_learn(req: Lesson, identity: Identity = Depends(admin)):
        try:
            frames = [base64.b64decode(frame, validate=True) for frame in req.frames]
            recording = base64.b64decode(req.recording_b64, validate=True) if req.recording_b64 else None
        except (ValueError, binascii.Error):
            raise HTTPException(400, "invalid recording")
        return procedures.learn(req.name, req.narration, frames, identity.id, recording)

    @app.post("/v2/procedures/{token}/approve")
    def procedure_approve(token: str, body: dict, identity: Identity = Depends(admin)):
        return procedures.approve(token, body, identity.id)

    def layout_key(identity: Identity) -> str:
        return "admin" if identity.scope == "admin" else identity.id

    @app.get("/v2/rules")
    def rules_read(identity: Identity = Depends(auth)):
        """Everyone sees the office's rules; only the workstation changes them (through the chat)."""
        from .rules import describe

        return [{"number": n, "text": describe(rule)} for n, rule in enumerate(rules.all(), 1)]

    @app.get("/v2/layout")
    def layout_read(identity: Identity = Depends(auth)):
        return layouts.get(layout_key(identity))

    @app.post("/v2/layout")
    def layout_write(body: dict, identity: Identity = Depends(auth)):
        try:
            return layouts.put(layout_key(identity), body)
        except (ValueError, AttributeError, TypeError):
            raise HTTPException(400, "invalid layout")

    from . import mail as mail_module

    chat = Chat(SimpleNamespace(
        layouts=layouts, procedures=procedures, autofill=Guarded(autofill, {"send": "wnioski", "fill": "wnioski"}), transcribe_document=transcribe_document,
        rules=Guarded(rules, {"add": "ustawienia", "remove": "ustawienia"}), style=style, listening=lambda: app.state.listening,
        general=lambda question, names, mail=False: drafts.general(question, names, mail=mail),
        learning=learning,
        status_listen=lambda: state["settings"].listen.model_dump(),
        can_transcribe=lambda: speech_available(),
        transcribes=lambda: speech_available(),
        mail_detect=mail_detect or mail_module.detect,
        mail_source=lambda: mail_module.open_source(state["settings"].mail.source, state["settings"].mail.path),
        vault=Guarded(vault, {"put": "sprawy", "message_put": "kalendarz"}),
        drafts=Guarded(drafts, {"propose": "sprawy"}), devices=devices, workcopies=workcopies, team=team, need=need,
        cases=lambda identity: [c for c in vault.cases()
                                if (identity.cases is None or c in identity.cases) and c not in HIDDEN_CASES],
        may_see_case=lambda identity, case: (identity.cases is None or case in identity.cases),
        documents=lambda identity, case: [
            {"id": d["id"], "name": d["name"], "version": d["version"], "case": d["case"]}
            for d in vault.summaries(frozenset({case}) if case is not None else identity.cases)],
        pseudonymizes=lambda: state["inference"].pseudonymizes,
        fee_catalog=fee_catalog, fee_estimate=fee_estimate, status=chat_status,
        enroll=lambda *a, **k: (need("ustawienia"), enroll_code(*a, **k))[1], backup_dir=lambda: state["settings"].backup_dir, local_backup=local_backup,
        offsite_enabled=lambda: state["settings"].replica.enabled, offsite_backup=offsite_backup,
        update_settings=lambda *a, **k: (need("ustawienia"), update_settings(*a, **k))[1], usage=ledger.summary, pairing_link=pairing_link,
        send_mail=lambda identity, to, subject, body, original: need("poczta") or send_mail(
            identity, mail_module.open_source(state["settings"].mail.source, state["settings"].mail.path),
            to, subject, body, original, True),
        find_devices=find_devices, device_names=device_names,
        print_network=lambda device, name, data: (ipp or peripherals.ipp_print)(
            device, (to_pdf or peripherals.word_to_pdf)(name, data), name),
        scan=lambda device, **options: (escl or peripherals.escl_scan)(device, **options),
        speech_check=speech_check,
        service=service_desk, program_changes=lambda: (program.current or {}).get("zmiany", []),
        office=Guarded(office_link, {"invite": "ustawienia", "join": "ustawienia", "forget": "ustawienia"}), station_name=station_name, start_office_server=lambda: start_office_server(),
        office_printers=office_module.windows_printers, office_print=office_module.windows_print,
        computer=agent_computer,
        ask_notary=lambda identity, words, actions, free=None: ask_notary(identity, words, actions, free),
        withdraw_question=lambda identity: attention.withdraw(identity.id),
        web_browser=(fill_targets or {}).get("strona", web_target),
        ai_ready=lambda: bool(state["inference"] is not None and state["inference"].enabled),
        agent_ask=lambda system, question, images=(): state["inference"].ask(
            purpose="agent", system=system, text=question, names=vault.all_parties(), max_tokens=1500,
            images=tuple(images)).text,
        calendar=Guarded(calendar, {"add": "kalendarz", "delete": "kalendarz"}), web_calendar=web_calendar, onboarding=onboarding, environment=environment, registers=register_service,
        start_job=start_job, narrate=narrate,
        job_idle=lambda ident: (time.monotonic() - jobs[ident]["seen"]) if ident in jobs else 0.0, program=program, restart_for_update=restart_for_update, settings=lambda: state["settings"], local_speech_installed=lambda: local_speech.available(),
        download_speech_model=lambda: model_download.start(state["settings"].speech.model),
        speech_model_progress=model_download.progress,
        account_configured=lambda: state["account"] is not None,
        signed_in=lambda: bool(state["account"] and state["account"].signed_in),
        logout=lambda: state["account"] and state["account"].logout(),
    ))
    class Compose(BaseModel):
        n: int | None = Field(default=None, ge=1, le=50)
        to: str = Field(default="", max_length=500)
        subject: str = Field(default="", max_length=300)
        body: str = Field(default="", max_length=50_000)
        draft: str = Field(default="", max_length=50_000)       # what the assistant proposed, to learn from edits
        send: bool = False                                        # the notary's command said „wyślij”

    @app.post("/v2/mail/compose", dependencies=[Depends(admin)])
    def mail_compose(req: Compose, identity: Identity = Depends(admin)):
        """Opens the ready message in the office's mail program; the notary checks it and presses Send there."""
        need_http("poczta")
        source = mail_module.open_source(state["settings"].mail.source, state["settings"].mail.path)
        if source is None:
            raise HTTPException(409, "Poczta nie jest połączona. Napisz „połącz pocztę”.")
        original = chat.inbox_message(identity, req.n) if req.n else None
        try:
            return send_mail(identity, source, req.to, req.subject, req.body, original, req.send)
        except (mail_module.MailError, RuleViolation) as error:
            raise HTTPException(409, str(error))

    def send_mail(identity: Identity, source, to: str, subject: str, body: str, original, send: bool) -> dict:
        if send:
            rules.check_send("poczta", [])            # e.g. the office's sending hours
        if source is None:
            raise mail_module.MailError("Poczta nie jest połączona. Napisz „połącz pocztę”.")
        said = (mail_composer or mail_module.compose)(source, to, subject, body, original, send=send)
        vault.log(identity.id, "mail-send" if send and said.startswith("Wysłałem") else "mail-compose")
        learned = learning.from_reply(body, [original.sender] if original and original.sender else [])
        return {"detail": said, "sent": said.startswith("Wysłałem"), "learned": [{"id": l["id"], "text": l["text"]} for l in learned]}

    from .registers import RegisterError

    @app.get("/v2/suggestions")
    def suggestions(case: str | None = None, identity: Identity = Depends(auth)):
        if case is not None and (not valid_case(case) or (identity.cases is not None and case not in identity.cases)):
            raise HTTPException(404, "not found")
        try:
            return {"items": chat.suggestions(identity, case)}
        except Exception:
            return {"items": []}

    from .peripherals import DeviceError

    SAID = (ServiceError, DeviceError, PolicyError, InferenceError, DraftError, LoginError, recovery.RecoveryError, ReplicaError, WorkCopyError,
            RegisterError,
            mail_module.MailError, ProcedureError, FillError, RuleViolation, TeamError)

    def chat_turn(identity: Identity, turn: ChatTurn):
        if turn.case is not None and identity.cases is not None and turn.case not in identity.cases:
            return [{"type": "text", "text": "Nie ma takiej sprawy."}]
        try:
            if turn.confirm:
                return chat.confirm(identity, turn.confirm)
            if turn.hello or not turn.text.strip():
                blocks = chat.hello(identity, turn.case)
                recent = sorted(vault.summaries(identity.cases if turn.case is None else frozenset({turn.case})),
                                key=lambda d: -d["created"])[:6]
                if recent:
                    blocks.insert(1, {"type": "documents", "items": [
                        {"id": d["id"], "name": d["name"], "version": d["version"], "case": d["case"]} for d in recent]})
                return blocks
            return chat.say(identity, turn.text, turn.case, turn.names)
        except LoginError as error:
            # Sign-in happens right here in the conversation, on the workstation.
            blocks = [{"type": "text", "text": str(error)}]
            if identity.scope == "admin" and state["account"] is not None:
                blocks.append({"type": "login"})
            elif identity.scope != "admin":
                blocks[0]["text"] += " Zaloguj się na komputerze kancelarii, w panelu stanowiska."
            return blocks
        except SAID as error:        # these carry sentences written for the notary
            return [{"type": "text", "text": str(error)}]
        except (ValueError, KeyError):
            return [{"type": "text", "text": "Nie udało się tego wykonać. Sprawdź polecenie i spróbuj ponownie."}]

    # ------------------------------------------------------------ the small window on top (agent's questions)
    from .attention import PAGE as ATTENTION_PAGE, Attention, windows_popup

    attention = Attention(opener=attention_opener if attention_opener is not None else (
                              windows_popup(home / "okno-pytanie") if os.name == "nt" else None),
                          enabled=lambda: state["settings"].agent.popup)

    def this_computer(request: Request, *, writing: bool = False) -> None:
        """Only a page of this worker, opened on this very computer."""
        client = request.client.host if request.client else ""
        host = request.headers.get("host", "")
        origin = request.headers.get("origin")
        if client not in {"127.0.0.1", "::1", "testclient"} or not re.fullmatch(r"(127\.0\.0\.1|localhost|testserver)(:\d+)?", host) \
                or (writing and origin is not None and origin != f"http://{host}"):
            raise HTTPException(403, "only on this computer")
        state["local_base"] = f"http://{host}"

    def ask_notary(identity: Identity, words: str, actions: list, free: str | None = None):
        if identity.scope != "admin" or not state.get("local_base"):
            return None                   # a phone asked: its owner is looking at the phone, not at this screen
        return attention.ask(identity.id, words, actions, free=free,
                             url=lambda token: f"{state['local_base']}/v2/attention/{token}")

    @app.get("/v2/attention/{token}", response_class=HTMLResponse)
    def attention_page(token: str, request: Request):
        this_computer(request)
        return HTMLResponse(ATTENTION_PAGE.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store"})

    @app.get("/v2/attention/{token}/dane")
    def attention_data(token: str, request: Request):
        this_computer(request)
        shown = attention.shown(token)
        if shown is None:
            raise HTTPException(404, "not waiting")
        return shown

    class AttentionAnswer(BaseModel):
        choice: int | None = Field(default=None, ge=0, le=10)
        words: str | None = Field(default=None, max_length=1000)

    @app.post("/v2/attention/{token}")
    def attention_answer(token: str, answer: AttentionAnswer, request: Request):
        this_computer(request, writing=True)
        if not attention.answer(token, choice=answer.choice, words=answer.words):
            raise HTTPException(410, "not waiting")
        return {"ok": True}

    @app.get("/v2/agent/inbox")
    def agent_inbox(request: Request, identity: Identity = Depends(auth)):
        """Answers given in the small window, for the station's own window to put into the conversation."""
        try:
            this_computer(request)        # also how the worker learns its own address on this computer
        except HTTPException:
            pass
        return {"turns": attention.collect(identity.id) if identity.scope == "admin" else []}

    @app.post("/v2/agent/stop")
    def agent_stop(identity: Identity = Depends(auth)):
        """The station's window is closing (or the notary said stop): computer work stops before its next step."""
        return {"blocks": chat._stop_agent(identity)}

    @app.post("/v2/chat")
    async def chat_endpoint(turn: ChatTurn, identity: Identity = Depends(auth)):
        blocks = await asyncio.to_thread(chat_turn, identity, turn)
        if state.pop("relay_dirty", False):
            await restart_relay()
            if state["settings"].tunnel.enabled:
                try:
                    await asyncio.wait_for(relay["client"].connected.wait(), 3)
                except asyncio.TimeoutError:
                    pass
        return {"blocks": blocks}

    # ------------------------------------------------------------ account
    @app.post("/v2/account/login", dependencies=[Depends(admin)])
    def login(req: Login):
        account = state["account"]
        if account is None:
            raise HTTPException(409, "account not configured")
        account.login(req.email, req.password, mfa_code=req.mfa_code, new_password=req.new_password)
        return {"signed_in": True}

    @app.post("/v2/account/logout", dependencies=[Depends(admin)])
    def logout():
        account = state["account"]
        if account is not None:
            account.logout()
        return {"signed_in": False}

    @app.post("/v2/bedrock/smoke",dependencies=[Depends(admin)])
    def bedrock():
        if not allow_bedrock:
            raise HTTPException(403, "Bedrock is disabled on this workstation")
        try:
            return smoke_test()
        except (PermissionError,ValueError):
            raise HTTPException(403,"Bedrock unavailable under development policy")
        except Exception:
            raise HTTPException(502,"Bedrock smoke failed")

    return app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(home_path()),host="127.0.0.1",port=8765,access_log=False,proxy_headers=False)
