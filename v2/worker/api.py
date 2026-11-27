import asyncio
import base64
import binascii
import re
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

from fastapi import FastAPI, Depends, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
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
STATIC = {"pocket.js": "application/javascript", "pocket.css": "text/css",
          "pocket.webmanifest": "application/manifest+json", "pocket-sw.js": "application/javascript",
          "pocket-icon.svg": "image/svg+xml",           "tunnel.js": "application/javascript", "qrcode.js": "application/javascript"}


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
    narration: str = Field(max_length=20000)
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


def create_app(home: Path, *, allow_bedrock: bool = True, inference: Inference | None = None,
               account: Account | None = None, opener=None, mail_detect=None, transcriber=None,
               fill_targets: dict | None = None):
    recovery.finish_interrupted_rotation(home)
    vault = Vault(home, read_secret(home, "vault.key"))
    devices = DeviceRegistry(home)
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
    drafts = Drafts(vault, lambda: state["inference"], connect, rules=rules, style=style)
    redeem_throttle = _Throttle()
    workcopies = WorkCopies(home, vault, opener, rules=rules) if opener else WorkCopies(home, vault, rules=rules)
    mode = "local" if settings.ai.real_data_approved else "synthetic-only"
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
        return Replica(home, state["account"], current.replica.bucket, current.replica.region)

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

    def maintain() -> dict:
        """Daily copies without anyone remembering: local disk when present, off-site when enabled."""
        done = {}
        if not recovery.enrolled(home):
            return done
        if state["settings"].backup_dir is not None and due("backup"):
            try:
                done["local"] = local_backup()["file"]
            except (recovery.RecoveryError, OSError):
                pass        # disk unplugged or full: the panel shows the overdue notice
        target = replica()
        if target is not None and state["account"].signed_in and due("offsite-backup"):
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
            await asyncio.sleep(1800)

    @asynccontextmanager
    async def lifespan(_app):
        from .local_lock import acquire

        _app.state.lock = acquire(home)       # one serving process per vault; key rotation checks this
        await restart_relay()
        upkeep = asyncio.create_task(maintenance_loop())
        ears = asyncio.create_task(listening_loop())
        yield
        upkeep.cancel()
        ears.cancel()
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
        if path.split("?")[0] in {"/v2/devices/redeem", "/v2/devices/invite"}:
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
        response.headers["Content-Security-Policy"] = f"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; manifest-src 'self'; worker-src 'self'; connect-src {connect_src}; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
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
        return {"version":"2.0-dev","storage":"local","ai":ai,"mode":mode}

    @app.get("/v2/status")
    def status(identity: Identity = Depends(auth)):
        last_backup = vault.last_action("backup")
        settings, account, inference = state["settings"], state["account"], state["inference"]
        overdue = last_backup is None or time.time_ns() - last_backup > settings.backup_reminder_days * 86400 * 10**9
        return {
            "version": "2.0-dev", "mode": mode, "scope": identity.scope,
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
        return [c for c in vault.cases() if identity.cases is None or c in identity.cases]

    @app.get("/v2/documents")
    def documents(include_names: bool = False, case: str | None = None, identity: Identity = Depends(auth)):
        allowed = identity.cases
        if case is not None:
            see_case(identity, case)
            allowed = frozenset({case})
        return vault.summaries(allowed) if include_names else vault.list(allowed)

    @app.post("/v2/documents")
    def save(revision: Revision, identity: Identity = Depends(writable)):
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
        return drafts.approve(
            draft_id, identity.id, req.name, paragraphs=req.paragraphs,
            base=req.base.model_dump() if req.base else None,
            template=req.template.model_dump() if req.template else None,
        )

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

            browser_box["web"] = Browser(home / "przegladarka")
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
    app.state.close_browser = lambda: browser_box.get("web") and browser_box["web"].close()

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

    listening = Listening(vault, lambda audio, suffix: speech_to_text(audio, suffix), lambda: state["inference"],
                          lambda: state["settings"].listen, extract=extract_docx)
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
        layouts=layouts, procedures=procedures, autofill=autofill, transcribe_document=transcribe_document,
        rules=rules, style=style, listening=lambda: app.state.listening,
        general=lambda question, names: drafts.general(question, names),
        status_listen=lambda: state["settings"].listen.model_dump(),
        can_transcribe=lambda: speech_available(),
        transcribes=lambda: speech_available(),
        mail_detect=mail_detect or mail_module.detect,
        mail_source=lambda: mail_module.open_source(state["settings"].mail.source, state["settings"].mail.path),
        vault=vault, drafts=drafts, devices=devices, workcopies=workcopies,
        cases=lambda identity: [c for c in vault.cases() if identity.cases is None or c in identity.cases],
        may_see_case=lambda identity, case: (identity.cases is None or case in identity.cases),
        documents=lambda identity, case: [
            {"id": d["id"], "name": d["name"], "version": d["version"], "case": d["case"]}
            for d in vault.summaries(frozenset({case}) if case is not None else identity.cases)],
        pseudonymizes=lambda: state["inference"].pseudonymizes,
        fee_catalog=fee_catalog, fee_estimate=fee_estimate, status=chat_status,
        enroll=enroll_code, backup_dir=lambda: state["settings"].backup_dir, local_backup=local_backup,
        offsite_enabled=lambda: state["settings"].replica.enabled, offsite_backup=offsite_backup,
        update_settings=update_settings, usage=ledger.summary, pairing_link=pairing_link,
        account_configured=lambda: state["account"] is not None,
        signed_in=lambda: bool(state["account"] and state["account"].signed_in),
        logout=lambda: state["account"] and state["account"].logout(),
    ))
    SAID = (PolicyError, InferenceError, DraftError, LoginError, recovery.RecoveryError, ReplicaError, WorkCopyError,
            mail_module.MailError, ProcedureError, FillError, RuleViolation)

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
            raise HTTPException(403, "Bedrock is disabled in the Windows preview")
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
