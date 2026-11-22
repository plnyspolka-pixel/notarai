"""Offline customer workstation CLI: generate challenge, verify Nitro, issue ONE grant.

Runs independently of the NotarAI application. Never upload the owner private
key or this CLI to a remotely served operator web page. NO AWS calls here.
Actual guest v3 admission + one-use consumption are separate release gates.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from confidential.customer_release import (
    ReleaseDenied, envelope_sha256, parse_envelope,
)
from confidential.customer_attested_release import (
    challenge_user_data, issue_attested_job_release,
)
from confidential.customer_origin import sign_customer_origin

_MAX_JSON = 36 * 1024 * 1024
_MAX_POLICY = 8192
_MAX_ATTESTATION = 32768


def _read(path: Path, limit: int) -> bytes:
    if not path.is_file() or path.stat().st_size > limit:
        raise ReleaseDenied("customer release denied")
    raw = path.read_bytes()
    if not raw or len(raw) > limit:
        raise ReleaseDenied("customer release denied")
    return raw


def _unique(pairs):
    value = {}
    for k, v in pairs:
        if k in value:
            raise ReleaseDenied("customer release denied")
        value[k] = v
    return value


def _json_file(path: Path, limit: int) -> dict:
    value = json.loads(_read(path, limit), object_pairs_hook=_unique)
    if type(value) is not dict:
        raise ReleaseDenied("customer release denied")
    return value


def _canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _write_new(path: Path, data: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def _strict_b64(value: object) -> bytes:
    if type(value) is not str:
        raise ReleaseDenied("customer release denied")
    raw = base64.b64decode(value, validate=True)
    if base64.b64encode(raw).decode("ascii") != value:
        raise ReleaseDenied("customer release denied")
    return raw


def _pinned_policy(args, *, tenant: str, now: int) -> dict[int, str]:
    # The trusted public key MUST be pinned outside operator infrastructure;
    # it must NOT be loaded from the policy document itself.
    signer = _read(args.trusted_policy_public_key, 32)
    if len(signer) != 32:
        raise ReleaseDenied("customer release denied")
    manifest = _json_file(args.pcr_manifest, _MAX_POLICY)
    if (set(manifest) != {"schema", "tenant_id", "pcrs", "expires_at", "image_digest"}
            or manifest["schema"] != "notarai.nitro-pcr-policy.v1"
            or manifest["tenant_id"] != tenant
            or type(manifest["expires_at"]) is not int
            or not now < manifest["expires_at"] <= now + 86400 * 30
            or type(manifest["image_digest"]) is not str
            or not manifest["image_digest"].startswith("sha256:")
            or len(manifest["image_digest"]) != 71
            or any(ch not in "0123456789abcdef" for ch in manifest["image_digest"][7:])):
        raise ReleaseDenied("customer release denied")
    signature = _read(args.pcr_manifest_sig, 64)
    if len(signature) != 64:
        raise ReleaseDenied("customer release denied")
    Ed25519PublicKey.from_public_bytes(signer).verify(signature, _canonical(manifest))
    raw_pcrs = manifest["pcrs"]
    if (type(raw_pcrs) is not dict or not {"8", "17"} <= set(raw_pcrs)
            or any(type(k) is not str or not k.isdigit()
                   for k in raw_pcrs)):
        raise ReleaseDenied("customer release denied")
    return {int(k): v for k, v in raw_pcrs.items()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    challenge = sub.add_parser("challenge", help="produce fresh nonce + job-bound NSM user_data")
    challenge.add_argument("--envelope", type=Path, required=True)
    challenge.add_argument("--job-id", required=True)
    challenge.add_argument("--output", type=Path, required=True)
    origin = sub.add_parser("origin", help="sign immutable S3 VersionId outside operator app")
    origin.add_argument("--envelope", type=Path, required=True)
    origin.add_argument("--s3-version", required=True)
    origin.add_argument("--issuer-id", required=True)
    origin.add_argument("--signing-private-key", type=Path, required=True)
    origin.add_argument("--expires-at", type=int, required=True)
    origin.add_argument("--output", type=Path, required=True)
    release = sub.add_parser("release", help="verify hardware evidence before RSA rewrap")
    release.add_argument("--envelope", type=Path, required=True)
    release.add_argument("--challenge", type=Path, required=True)
    release.add_argument("--attestation", type=Path, required=True)
    release.add_argument("--owner-private-key", type=Path, required=True)
    release.add_argument("--pcr-manifest", type=Path, required=True)
    release.add_argument("--pcr-manifest-sig", type=Path, required=True)
    release.add_argument("--trusted-policy-public-key", type=Path, required=True)
    release.add_argument("--validity-seconds", type=int, default=300)
    release.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        env = parse_envelope(_json_file(args.envelope, _MAX_JSON))
        now = int(time.time())
        if args.command == "origin":
            if not now < args.expires_at <= now + 86400:
                raise ReleaseDenied("customer origin denied")
            receipt, signature = sign_customer_origin(
                env, s3_version=args.s3_version, issuer_id=args.issuer_id,
                expires_at=args.expires_at,
                trusted_client_signing_private_pem=_read(args.signing_private_key, 8192),
            )
            _write_new(args.output, _canonical({
                "schema": "notarai.customer-origin-bundle.v1",
                "receipt": receipt,
                "signature_b64": base64.b64encode(signature).decode("ascii"),
            }) + b"\n")
            print("Signed document origin saved; no private key exported.")
            return 0
        if args.command == "challenge":
            nonce = os.urandom(32)
            ctx = {
                "schema": "notarai.customer-nitro-challenge.v1",
                "job_id": args.job_id,
                "envelope_sha256": envelope_sha256(env),
                "created_at": now, "expires_at": now + 180,
                "nonce_b64": base64.b64encode(nonce).decode("ascii"),
                "user_data_b64": base64.b64encode(
                    challenge_user_data(env, job_id=args.job_id, nonce=nonce)
                ).decode("ascii"),
            }
            _write_new(args.output, _canonical(ctx) + b"\n")
            print("Challenge saved; send nonce + user_data to the enclave using an untrusted transport.")
            return 0
        ctx = _json_file(args.challenge, _MAX_POLICY)
        if (set(ctx) != {"schema", "job_id", "envelope_sha256", "created_at",
                         "expires_at", "nonce_b64", "user_data_b64"}
                or ctx["schema"] != "notarai.customer-nitro-challenge.v1"
                or ctx["envelope_sha256"] != envelope_sha256(env)
                or type(ctx["created_at"]) is not int
                or type(ctx["expires_at"]) is not int
                or not ctx["created_at"] <= now < ctx["expires_at"]
                or ctx["expires_at"] - ctx["created_at"] > 180):
            raise ReleaseDenied("customer release denied")
        nonce = _strict_b64(ctx["nonce_b64"])
        if (len(nonce) != 32 or
                _strict_b64(ctx["user_data_b64"]) !=
                challenge_user_data(env, job_id=ctx["job_id"], nonce=nonce)):
            raise ReleaseDenied("customer release denied")
        pins = _pinned_policy(args, tenant=env["tenant_id"], now=now)
        grant, proof = issue_attested_job_release(
            env, _read(args.owner_private_key, 8192),
            _read(args.attestation, _MAX_ATTESTATION),
            expected_nonce=nonce, expected_pcrs=pins,
            job_id=ctx["job_id"], now=datetime.now(timezone.utc),
            validity_seconds=args.validity_seconds,
        )
        _write_new(args.output, _canonical(grant) + b"\n")
        # Metadata only; NEVER print owner secret, grant or document contents.
        print("One encrypted preview-only grant saved; attestation SHA-256: " +
              proof.attestation_sha256)
        return 0
    except (ReleaseDenied, InvalidSignature, ValueError, OSError, TypeError, KeyError):
        print("Customer release denied. No grant issued.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
