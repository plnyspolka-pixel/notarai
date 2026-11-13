"""NotarAI Sealed v2 API: private ciphertext-only storage.

Never accepts key passphrases or plaintext fields, never decrypts contents.
No server-provided JavaScript is trusted to create a 'Sealed' assurance.
"""
from __future__ import annotations
import base64
import hashlib
import json
import re
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import magazyn

router=APIRouter(prefix="/api/sealed/v2",tags=["Sealed Vault v2"])
STORE="sealed_vault_v2"
VERSION="notarai.sealed.v2"
B64=re.compile(r"^[A-Za-z0-9_-]+$")
KID=re.compile(r"^[0-9a-f]{40}$")
MAX_CIPHER_CHARS=5_600_000
MAX_DOCS=50

def b64check(value:str, length:int|None=None) -> bytes:
    if not isinstance(value,str) or not B64.fullmatch(value):
        raise ValueError("Invalid base64url")
    try: result=base64.urlsafe_b64decode(value+"="*(-len(value)%4))
    except Exception as error: raise ValueError("Invalid base64url") from error
    if base64.urlsafe_b64encode(result).decode("ascii").rstrip("=")!=value:
        raise ValueError("Noncanonical base64url")
    if length is not None and len(result)!=length: raise ValueError("Wrong binary length")
    return result

class Recipient(BaseModel):
    model_config=ConfigDict(extra="forbid")
    keyId:str=Field(min_length=40,max_length=40)
    ephemeralPublic:str=Field(min_length=43,max_length=43)
    salt:str=Field(min_length=43,max_length=43)
    nonce:str=Field(min_length=16,max_length=16)
    wrappedKey:str=Field(min_length=64,max_length=64)

class SealedDocument(BaseModel):
    model_config=ConfigDict(extra="forbid")
    schema_name:str=Field(alias="schema")
    documentId:uuid.UUID
    tenantRef:str=Field(min_length=1,max_length=120)
    algorithm:str
    keyWrap:str
    nonce:str=Field(min_length=16,max_length=16)
    ciphertext:str=Field(min_length=23,max_length=MAX_CIPHER_CHARS)
    recipients:list[Recipient]=Field(min_length=1,max_length=16)

def check(document:SealedDocument):
    if document.schema_name!=VERSION or document.algorithm!="AES-256-GCM" or \
        document.keyWrap!="X25519-HKDF-SHA256-AES256GCM":
        raise HTTPException(422,"Unsupported Sealed v2 envelope")
    if document.tenantRef!=magazyn.kancelaria():
        raise HTTPException(403,"Wrong office")
    if document.documentId.version!=4 or str(document.documentId)!=str(document.documentId).lower():
        raise HTTPException(422,"Invalid UUIDv4")
    if any(ord(c)<32 or ord(c)==127 for c in document.tenantRef):
        raise HTTPException(422,"Invalid office reference")
    try:
        b64check(document.nonce,12)
        ciphertext=b64check(document.ciphertext)
        if not 17<=len(ciphertext)<=4*1024*1024+16:
            raise ValueError("Invalid ciphertext size")
        identifiers=set()
        for recipient in document.recipients:
            if not KID.fullmatch(recipient.keyId) or recipient.keyId in identifiers:
                raise ValueError("Invalid or duplicated recipient")
            identifiers.add(recipient.keyId)
            b64check(recipient.ephemeralPublic,32)
            b64check(recipient.salt,32)
            b64check(recipient.nonce,12)
            b64check(recipient.wrappedKey,48)
    except ValueError as error:
        raise HTTPException(422,"Invalid Sealed envelope metadata") from error

def read_state():
    return magazyn.wczytaj_plik_kancelarii(STORE,{"documents":{}})

@router.get("/context")
def context():
    if magazyn.u_klienta():
        raise HTTPException(409,"Cloud vault disabled for local-storage office")
    return {"schema":VERSION,"tenantRef":magazyn.kancelaria(),
            "mode":"OFFLINE_ENCRYPTED_POC","keys":"OFFICE_HELD_ONLY"}

@router.post("/documents",status_code=201)
def register(document:SealedDocument):
    if magazyn.u_klienta():raise HTTPException(409,"Local-only office")
    check(document)
    payload=document.model_dump(by_alias=True,mode="json")
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    digest=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    def insert(state):
        objects=state.setdefault("documents",{})
        ident=str(document.documentId)
        existing=objects.get(ident)
        if existing:
            if existing["envelope_sha256"]==digest:
                return {"documentId":ident,"envelope_sha256":digest,"created":False}
            raise HTTPException(409,"Document ID is already used for another envelope")
        if len(objects)>=MAX_DOCS:
            raise HTTPException(413,"Sealed v2 POC office quota exceeded")
        objects[ident]={"envelope":payload,"envelope_sha256":digest}
        return {"documentId":ident,"envelope_sha256":digest,"created":True}
    return magazyn.zmien_plik_kancelarii(STORE,insert,{"documents":{}})

@router.get("/documents/{document_id}")
def get_document(document_id:uuid.UUID):
    if magazyn.u_klienta():raise HTTPException(409,"Local-only office")
    record=read_state().get("documents",{}).get(str(document_id))
    if not record:raise HTTPException(404,"Unknown sealed document")
    return record["envelope"]
