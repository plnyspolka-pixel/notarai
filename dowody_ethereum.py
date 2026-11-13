"""Tenant-isolated evidence API for NotarAI document versions.

Read-only from actual office files, write evidence to the existing office
store. This branch does not broadcast anything to Ethereum or operate QTSP.
"""
from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import config
import magazyn
import proof_engine

router = APIRouter(prefix="/api/dowody", tags=["kryptograficzne dowody"])

def _anchoring_chain_id() -> int:
    """Use Sepolia by default; explicit configured chain for later confirmation."""
    value = int(os.getenv("NOTARAI_ETH_CHAIN_ID", "11155111"))
    if value not in (11155111, 31337, 1):
        raise HTTPException(503, "Unsupported Ethereum chain")
    return value

REJESTR = "ethereum_dowody"
MATTER = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
EXT = {".docx", ".pdf", ".txt", ".odt", ".rtf"}
DEFAULT = {"proofs": [], "batches": []}


class FileProofRequest(BaseModel):
    plik: str = Field(min_length=1, max_length=200)


class BatchRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)


class VerifyRequest(BaseModel):
    receipt: dict


def _file_for_matter(matter_id: str, relative: str) -> Path:
    if not MATTER.fullmatch(matter_id) or "\\" in relative:
        raise HTTPException(400, "Niepoprawny identyfikator sprawy lub pliku")
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts or rel.suffix.lower() not in EXT:
        raise HTTPException(400, "Niedozwolona sciezka pliku")
    directory = config.SPRAWY / matter_id  # resolved per tenant context from auth middleware
    magazyn.pobierz_sprawe(directory)
    root = directory.resolve()
    target = (directory / rel.as_posix()).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(404, "Nie znaleziono pliku w tej sprawie")
    return target


def _read_state() -> dict:
    return magazyn.wczytaj_plik_kancelarii(REJESTR, {"proofs": [], "batches": []})


@router.post("/sprawy/{matter_id}/dokument", status_code=201)
def document_proof(matter_id: str, data: FileProofRequest):
    if magazyn.u_klienta():
        raise HTTPException(409, "Dla plikow przechowywanych tylko u klienta potrzebny jest osobny mechanizm dowodowy")
    target = _file_for_matter(matter_id, data.plik)
    h = hashlib.sha256()
    with target.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    payload = {"schema": "notarai-document-v1",
               "kancelaria": magazyn.kancelaria(),
               "sprawa_id": matter_id,
               "plik": data.plik,
               "sha256": h.hexdigest()}
    salt = proof_engine.new_salt()
    row = {"id": str(uuid.uuid4()), "payload": payload, "salt": salt,
           "commitment": proof_engine.commitment(payload, salt),
           "created_at": proof_engine.utc_timestamp(), "batch_id": None}
    def insert(state):
        state.setdefault("proofs", []).append(row)
        return row
    return magazyn.zmien_plik_kancelarii(REJESTR, insert, {"proofs": [], "batches": []})


@router.post("/partie", status_code=201)
def make_batch(data: BatchRequest):
    if magazyn.u_klienta():
        raise HTTPException(409, "Chmurowy rejestr dowodow jest wylaczony dla kancelarii przechowujacej pliki u siebie")
    def seal(state):
        pending = [row for row in state.get("proofs", []) if not row.get("batch_id")][:data.limit]
        if not pending:
            raise HTTPException(409, "Brak nieprzypisanych dowodow")
        batch = proof_engine.merkle_batch([row["commitment"] for row in pending])
        batch_id = str(uuid.uuid4())
        for row, witness in zip(pending, batch["witnesses"]):
            row["batch_id"] = batch_id
            row["witness"] = witness
        record = {"id": batch_id, "root": batch["root"],
                  "created_at": proof_engine.utc_timestamp(),
                  "event_count": len(pending), "status": "prepared",
                  "ethereum_tx_hash": None, "chain_id": _anchoring_chain_id(),
                  "calldata": proof_engine.anchor_calldata(batch["root"])}
        state.setdefault("batches", []).append(record)
        return record
    return magazyn.zmien_plik_kancelarii(REJESTR, seal, {"proofs": [], "batches": []})


@router.get("/sprawy/{matter_id}")
def matter_proofs(matter_id: str):
    if not MATTER.fullmatch(matter_id):
        raise HTTPException(400, "Niepoprawny identyfikator sprawy")
    state = _read_state()
    return {"proofs": [
        {**row, **(row.get("witness") or {})}
        for row in state.get("proofs", []) if row.get("payload", {}).get("sprawa_id") == matter_id
    ]}


@router.get("/partie/{batch_id}")
def batch_by_id(batch_id: str):
    try:
        uuid.UUID(batch_id)
    except ValueError:
        raise HTTPException(400, "Niepoprawny identyfikator partii")
    for row in _read_state().get("batches", []):
        if row["id"] == batch_id:
            return row
    raise HTTPException(404, "Nie znaleziono partii")


@router.post("/weryfikuj")
def verify(data: VerifyRequest):
    valid = proof_engine.verify_receipt(data.receipt)
    return {"integrity_valid": valid,
            "ethereum_verified": False,
            "note": "Weryfikacja Ethereum wymaga potwierdzonej transakcji i odrebnego sprawdzenia RPC"}


class ConfirmAnchorRequest(BaseModel):
    tx_hash: str = Field(min_length=66, max_length=66)


@router.post("/partie/{batch_id}/potwierdz")
def confirm_anchor(batch_id: str, data: ConfirmAnchorRequest):
    """Verifies an EXISTING transaction on trusted RPC, then stores proof.
    Never sends tokens or signs with a private key.
    """
    import os
    try:
        uuid.UUID(batch_id)
    except ValueError:
        raise HTTPException(400, "Niepoprawny identyfikator partii")
    rpc = os.getenv("NOTARAI_ETH_RPC_URL", "")
    sender = os.getenv("NOTARAI_ETH_SENDER", "")
    recipient = os.getenv("NOTARAI_ETH_RECIPIENT", "")
    if not rpc or not sender or not recipient:
        raise HTTPException(503, "Nie skonfigurowano zaufanego Ethereum RPC i adresow")
    rows = _read_state().get("batches", [])
    match = next((r for r in rows if r["id"] == batch_id), None)
    if match is None:
        raise HTTPException(404, "Nie znaleziono partii")
    try:
        proof = proof_engine.verify_ethereum_anchor(
            rpc_url=rpc, tx_hash=data.tx_hash, root=match["root"],
            sender=sender, recipient=recipient, chain_id=int(match["chain_id"]),
        )
    except Exception as error:
        # No network error details or configured RPC URL in the response.
        raise HTTPException(502, "Nie udalo sie potwierdzic transakcji w Ethereum") from error
    if not proof.get("confirmed"):
        return {"confirmed": False, "reason": proof.get("reason"),
                "confirmations": proof.get("confirmations", 0)}

    def record(state):
        entry = next((r for r in state.get("batches", []) if r["id"] == batch_id), None)
        if not entry or entry["root"] != match["root"]:
            raise HTTPException(409, "Partia zmienila sie podczas weryfikacji")
        if entry.get("ethereum_tx_hash") not in (None, data.tx_hash):
            raise HTTPException(409, "Partia potwierdzona inna transakcja")
        entry.update({
            "ethereum_tx_hash": data.tx_hash,
            "status": "confirmed",
            "block_number": proof.get("blockNumber"),
            "confirmations_at_check": proof["confirmations"],
            "confirmed_at": proof_engine.utc_timestamp(),
        })
        return entry
    return magazyn.zmien_plik_kancelarii(
        REJESTR, record, {"proofs": [], "batches": []},
    )
