import base64
import binascii
import secrets
from pathlib import Path
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from .devices import DeviceRegistry
from .sync import plan
from pydantic import BaseModel, Field
from .vault import Vault, Conflict, MAX_BYTES
from .init_vault import home_path
from .local_secrets import read_secret
from .bedrock import smoke_test

class Revision(BaseModel):
    id: str | None = None
    expected_version: int = Field(ge=0, strict=True)
    name: str = Field(min_length=1,max_length=255)
    content_b64: str = Field(max_length=((MAX_BYTES+2)//3)*4)

class Invitation(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    scope: str = "read"

class Redemption(BaseModel):
    code: str = Field(min_length=20,max_length=128)

class ManifestItem(BaseModel):
    id: str
    version: int = Field(ge=1,strict=True)

class Manifest(BaseModel):
    items: list[ManifestItem] = Field(max_length=10000)

def create_app(home: Path, *, allow_bedrock: bool = True):
    vault = Vault(home, read_secret(home, "vault.key"))
    devices = DeviceRegistry(home)
    token = read_secret(home, "api.token").decode().strip()
    if len(token) < 40:
        raise ValueError("invalid local token")
    app = FastAPI(title="NotarAI 2.0 development worker", docs_url=None, redoc_url=None, openapi_url=None)
    def auth(authorization: str = Header(default="")):
        if secrets.compare_digest(authorization.encode(), ("Bearer "+token).encode()):
            return ("local-admin","admin")
        if authorization.startswith("Bearer "):
            device = devices.authenticate(authorization[7:])
            if device:
                return device
        raise HTTPException(401,"unauthorized")

    def admin(identity=Depends(auth)):
        if identity[1] != "admin":
            raise HTTPException(403,"admin required")

    def writable(identity=Depends(auth)):
        if identity[1] not in {"admin","write"}:
            raise HTTPException(403,"read only")

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({"detail":"invalid request"},status_code=422)

    @app.middleware("http")
    async def no_cache(request, call_next):
        if request.url.hostname not in {"127.0.0.1","localhost","testserver"}:
            return JSONResponse({"detail":"invalid host"},status_code=403,headers={"Cache-Control":"no-store"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.post("/v2/devices/invite",dependencies=[Depends(admin)])
    def invite(req: Invitation):
        try:
            return devices.invite(req.name,req.scope)
        except ValueError:
            raise HTTPException(400,"invalid invitation")

    @app.post("/v2/devices/redeem")
    def redeem(req: Redemption):
        try:
            return devices.redeem(req.code)
        except PermissionError:
            raise HTTPException(403,"invalid invitation")

    @app.get("/v2/devices",dependencies=[Depends(admin)])
    def list_devices():
        return devices.list()

    @app.delete("/v2/devices/{device_id}",dependencies=[Depends(admin)])
    def revoke(device_id: str):
        if not devices.revoke(device_id):
            raise HTTPException(404,"device not found")
        return {"revoked":True}

    @app.post("/v2/sync/plan",dependencies=[Depends(auth)])
    def sync_plan(req: Manifest):
        try:
            return plan(vault.list(),[x.model_dump() for x in req.items])
        except ValueError:
            raise HTTPException(400,"invalid manifest")

    @app.get("/v2/pocket")
    def pocket():
        return FileResponse(Path(__file__).with_name("pocket.html"),media_type="text/html")

    @app.get("/v2/pocket.js")
    def pocket_script():
        return FileResponse(Path(__file__).with_name("pocket.js"),media_type="application/javascript")

    @app.get("/v2/health",dependencies=[Depends(auth)])
    def health():
        ai = "aws-bedrock" if allow_bedrock else "disabled"
        return {"version":"2.0-dev","storage":"local","ai":ai,"mode":"synthetic-only"}

    @app.get("/v2/documents",dependencies=[Depends(auth)])
    def documents(include_names: bool = False):
        return vault.summaries() if include_names else vault.list()

    @app.post("/v2/documents",dependencies=[Depends(writable)])
    def save(revision: Revision):
        try:
            data = base64.b64decode(revision.content_b64,validate=True)
            doc_id, version = vault.put(revision.id,revision.expected_version,revision.name,data)
            return {"id":doc_id,"version":version}
        except Conflict:
            raise HTTPException(409,"revision conflict")
        except (ValueError,binascii.Error):
            raise HTTPException(400,"invalid document")

    @app.get("/v2/documents/{doc_id}/versions", dependencies=[Depends(auth)])
    def versions(doc_id: str):
        try:
            return vault.versions(doc_id)
        except (KeyError, ValueError):
            raise HTTPException(404, "not found")

    @app.get("/v2/documents/{doc_id}",dependencies=[Depends(auth)])
    def read(doc_id: str, version: int | None = None):
        try:
            rev,name,data = vault.get(doc_id,version)
            return {"id":doc_id,"version":rev,"name":name,"content_b64":base64.b64encode(data).decode()}
        except (KeyError,ValueError):
            raise HTTPException(404,"not found")

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
