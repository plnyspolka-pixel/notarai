import base64
import binascii
import secrets
from pathlib import Path
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from .vault import Vault, Conflict, MAX_BYTES
from .init_vault import home_path
from .bedrock import smoke_test

class Revision(BaseModel):
    id: str | None = None
    expected_version: int = Field(ge=0, strict=True)
    name: str = Field(min_length=1,max_length=255)
    content_b64: str = Field(max_length=((MAX_BYTES+2)//3)*4)

def create_app(home: Path):
    vault = Vault(home, (home/"vault.key").read_bytes())
    token = (home/"api.token").read_text().strip()
    if len(token) < 40:
        raise ValueError("invalid local token")
    app = FastAPI(title="NotarAI 2.0 development worker", docs_url=None, redoc_url=None, openapi_url=None)
    def auth(request: Request, authorization: str = Header(default="")):
        if request.url.hostname not in {"127.0.0.1","localhost","testserver"}:
            raise HTTPException(403,"invalid host")
        if not secrets.compare_digest(authorization.encode(), ("Bearer "+token).encode()):
            raise HTTPException(401,"unauthorized")

    @app.middleware("http")
    async def no_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/v2/health",dependencies=[Depends(auth)])
    def health():
        return {"version":"2.0-dev","storage":"local","ai":"aws-bedrock","mode":"synthetic-only"}

    @app.get("/v2/documents",dependencies=[Depends(auth)])
    def documents():
        return vault.list()

    @app.post("/v2/documents",dependencies=[Depends(auth)])
    def save(revision: Revision):
        try:
            data = base64.b64decode(revision.content_b64,validate=True)
            doc_id, version = vault.put(revision.id,revision.expected_version,revision.name,data)
            return {"id":doc_id,"version":version}
        except Conflict:
            raise HTTPException(409,"revision conflict")
        except (ValueError,binascii.Error):
            raise HTTPException(400,"invalid document")

    @app.get("/v2/documents/{doc_id}",dependencies=[Depends(auth)])
    def read(doc_id: str, version: int | None = None):
        try:
            rev,name,data = vault.get(doc_id,version)
            return {"id":doc_id,"version":rev,"name":name,"content_b64":base64.b64encode(data).decode()}
        except (KeyError,ValueError):
            raise HTTPException(404,"not found")

    @app.post("/v2/bedrock/smoke",dependencies=[Depends(auth)])
    def bedrock():
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
