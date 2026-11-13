"""NotarAI: privacy-preserving evidence commitments and Ethereum anchoring verifier.

This is a technical integrity proof, NOT a qualified eIDAS trust service.
Only random-salted Merkle roots may be broadcast publicly; tenant payloads,
document hashes, witness paths, filenames and salts stay private.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone

DOMAIN = b"FY-EVIDENCE-V1"
ETH_PREFIX = "46595031"  # ASCII FYP1; matches Finance You
HEX32 = __import__("re").compile(r"^[0-9a-fA-F]{64}$")
ETH_ADDRESS = __import__("re").compile(r"^0x[0-9a-fA-F]{40}$")
TX_HASH = __import__("re").compile(r"^0x[0-9a-fA-F]{64}$")


def _hex32(value: str) -> bytes:
    if not isinstance(value, str) or not HEX32.fullmatch(value):
        raise ValueError("Oczekiwano 32 bajtow w zapisie HEX")
    return bytes.fromhex(value)


def canonical_json(payload: dict) -> bytes:
    """Canonical for JSON objects with strings, booleans and integer fields.

    Protocol callers must not use floats, NaN, dates or undefined values.
    """
    def check(value):
        if value is None or isinstance(value, (str, bool, int)):
            return
        if isinstance(value, list):
            for item in value:
                check(item)
            return
        if isinstance(value, dict) and all(isinstance(k, str) for k in value):
            for item in value.values():
                check(item)
            return
        raise ValueError("Nieobslugiwany typ w dowodzie JSON")
    check(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def new_salt() -> str:
    return secrets.token_hex(32)


def commitment(payload: dict, salt: str) -> str:
    return hashlib.sha256(DOMAIN + _hex32(salt) + hashlib.sha256(canonical_json(payload)).digest()).hexdigest()


def _leaf(digest_hex: str) -> str:
    return hashlib.sha256(b"\x00" + _hex32(digest_hex)).hexdigest()


def _parent(left: str, right: str) -> str:
    return hashlib.sha256(b"\x01" + _hex32(left) + _hex32(right)).hexdigest()


def merkle_batch(commits: list[str]) -> dict:
    if not commits:
        raise ValueError("Partia musi zawierac dowody")
    commits = [bytes(_hex32(h)).hex() for h in commits]
    if len(set(commits)) != len(commits):
        raise ValueError("Powtorzony commitment")
    levels = [[_leaf(value) for value in commits]]
    while len(levels[-1]) > 1:
        layer = levels[-1]
        levels.append([_parent(layer[i], layer[i + 1] if i + 1 < len(layer) else layer[i])
                       for i in range(0, len(layer), 2)])
    root = levels[-1][0]
    witnesses = []
    for ordinal, value in enumerate(commits):
        cursor = ordinal
        steps = []
        for level in levels[:-1]:
            sibling = cursor ^ 1
            steps.append({"side": "left" if cursor & 1 else "right",
                          "hash": level[sibling] if sibling < len(level) else level[cursor]})
            cursor //= 2
        witnesses.append({"commitment": value, "root": root, "steps": steps})
    return {"root": root, "witnesses": witnesses}


def verify_receipt(receipt: dict) -> bool:
    """Check witness and payload integrity. Chain proof is a SEPARATE check."""
    try:
        if commitment(receipt["payload"], receipt["salt"]) != _hex32(receipt["commitment"]).hex():
            return False
        current = _leaf(receipt["commitment"])
        steps = receipt["steps"]
        if not isinstance(steps, list) or len(steps) > 64:
            return False
        for step in steps:
            side, sibling = step["side"], step["hash"]
            if side == "left":
                current = _parent(sibling, current)
            elif side == "right":
                current = _parent(current, sibling)
            else:
                return False
        return current == _hex32(receipt["root"]).hex()
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def anchor_calldata(root: str) -> str:
    return "0x" + ETH_PREFIX + _hex32(root).hex()


def verify_ethereum_anchor(*, rpc_url: str, tx_hash: str, root: str,
                           sender: str, recipient: str, minimum_confirmations: int = 12,
                           chain_id: int = 1) -> dict:
    """Read-only check via trusted HTTPS RPC, never submits or signs a transaction."""
    import httpx
    if not rpc_url.startswith("https://") or not TX_HASH.fullmatch(tx_hash):
        raise ValueError("Niepoprawny RPC lub hash transakcji")
    if not ETH_ADDRESS.fullmatch(sender) or not ETH_ADDRESS.fullmatch(recipient):
        raise ValueError("Niepoprawne adresy Ethereum")
    def rpc(method, params=None):
        response = httpx.post(rpc_url, json={"jsonrpc": "2.0", "id": 1,
                                             "method": method, "params": params or []}, timeout=15)
        response.raise_for_status()
        result = response.json()
        if result.get("error"):
            raise RuntimeError("Ethereum RPC error")
        return result.get("result")
    if int(rpc("eth_chainId"), 16) != chain_id:
        return {"confirmed": False, "reason": "wrong_chain"}
    tx = rpc("eth_getTransactionByHash", [tx_hash])
    receipt = rpc("eth_getTransactionReceipt", [tx_hash])
    if not tx or not receipt or not receipt.get("blockNumber"):
        return {"confirmed": False, "reason": "pending"}
    if (tx.get("from", "").lower() != sender.lower() or
        (tx.get("to") or "").lower() != recipient.lower() or
        tx.get("input", "").lower() != anchor_calldata(root) or
        int(tx.get("value", "0x0"), 16) != 0 or
        int(receipt.get("status", "0x0"), 16) != 1 or
        receipt.get("transactionHash", "").lower() != tx_hash.lower()):
        return {"confirmed": False, "reason": "anchor_mismatch"}
    block = int(receipt["blockNumber"], 16)
    depth = max(0, int(rpc("eth_blockNumber"), 16) - block + 1)
    return {"confirmed": depth >= minimum_confirmations, "confirmations": depth,
            "blockNumber": block, **({"reason": "insufficient_confirmations"}
                                     if depth < minimum_confirmations else {})}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
