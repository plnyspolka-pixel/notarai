"""SEC-06: offline compiler for custodian-owned atomic DynamoDB CAS writes.

Never imports boto3, connects to AWS, or writes a ledger. The only output is
a proposed TransactWriteItems request for an INDEPENDENT custodian to audit.
Requires a valid ECDSA P-256 signed operation and independently pinned signer.
The external, separately audited custodian must perform account checks and
apply KMS denial BEFORE accepting a state change as effective. In particular
UNFREEZE is not compiled without an independently verified live release gate.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidential.custody_ops import apply_signed_action, validate_state
from confidential.operator_boundary import BoundaryDenied, canonical_digest

_TABLE = re.compile(
    r"arn:aws:dynamodb:eu-central-1:([0-9]{12}):table/"
    r"notarai-confidential-custody-ledger-pilot\Z"
)
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def compile_signed_cas(*, state: dict | None, envelope: dict,
                       trusted_public_key_pem: bytes, pinned_public_key_sha256: str,
                       ledger_table_arn: str,
                       independently_pinned_previous_state_sha256: str,
                       clock: datetime | None = None) -> dict:
    """Emit immutable-event and current-state CAS puts in ONE transaction.

    ClientRequestToken is a deterministic UUIDv5 of the signed envelope.
    Both puts use an exact key and a conditional expression; a concurrent
    approval cannot overwrite an independently committed transition.
    """
    if not isinstance(envelope, dict) or not isinstance(
        independently_pinned_previous_state_sha256, str
    ) or _HASH.fullmatch(independently_pinned_previous_state_sha256) is None:
        raise BoundaryDenied("custody CAS envelope or independent state pin invalid")
    table_match = (_TABLE.fullmatch(ledger_table_arn)
                   if isinstance(ledger_table_arn, str) else None)
    if table_match is None:
        raise BoundaryDenied("custody CAS must target pinned EU pilot ledger ARN")
    before = validate_state(state) if state is not None else None
    payload = envelope.get("payload")
    changes = (payload.get("changes") if isinstance(payload, dict) else None)
    if not isinstance(changes, dict):
        raise BoundaryDenied("custody CAS envelope changes invalid")
    account = (before if before is not None else changes).get(
        "custody_account")
    if not isinstance(account, str) or table_match.group(1) != account:
        raise BoundaryDenied("custody CAS ledger must belong to custodian account")
    previous_sha = canonical_digest(before) if before is not None else "0" * 64
    if previous_sha != independently_pinned_previous_state_sha256:
        raise BoundaryDenied("stale or operator-supplied custody state")
    next_state = apply_signed_action(
        before, envelope, trusted_public_key_pem=trusted_public_key_pem,
        pinned_public_key_sha256=pinned_public_key_sha256, clock=clock)
    if next_state["state"] == "ACTIVE":
        # The offline compiler cannot verify KMS policy application, complete
        # grant revocation, historical key denials or live Nitro attestation.
        # Releasing a key based on a signed envelope alone is forbidden.
        raise BoundaryDenied("UNFREEZE needs independent live KMS release proof")
    action = envelope["payload"]["action"]
    tenant = next_state["tenant"]
    new_sha = canonical_digest(next_state)
    event_sha = canonical_digest(envelope)
    transaction_token = str(uuid.uuid5(
        uuid.NAMESPACE_URL, "notarai:sec06:custody-cas:" + event_sha))
    partition = "TENANT#" + tenant
    revision = next_state["revision"]
    key_attrs = {
        "tenant": {"S": partition},
        "record": {"S": "STATE"},
    }
    state_item = {
        **key_attrs,
        "state_json": {"S": json.dumps(
            next_state, ensure_ascii=True, sort_keys=True,
            separators=(",", ":"), allow_nan=False)},
        "state_sha256": {"S": new_sha},
        "revision": {"N": str(revision)},
        "generation": {"N": str(next_state["generation"])},
    }
    if before is None:
        condition = "attribute_not_exists(#tenant)"
        names = {"#tenant": "tenant"}
        values = None
    else:
        condition = "#sha = :previous AND #revision = :old_revision"
        names = {"#sha": "state_sha256", "#revision": "revision"}
        values = {
            ":previous": {"S": previous_sha},
            ":old_revision": {"N": str(before["revision"])},
        }
    put_state = {
        "TableName": ledger_table_arn,
        "Item": state_item,
        "ConditionExpression": condition,
        "ExpressionAttributeNames": names,
    }
    if values is not None:
        put_state["ExpressionAttributeValues"] = values
    event_item = {
        "tenant": {"S": partition},
        "record": {"S": f"EVENT#{revision:020d}"},
        "event_json": {"S": json.dumps(
            envelope, ensure_ascii=True, sort_keys=True,
            separators=(",", ":"), allow_nan=False)},
        "event_sha256": {"S": event_sha},
        "previous_state_sha256": {"S": previous_sha},
        "new_state_sha256": {"S": new_sha},
        "revision": {"N": str(revision)},
        "action": {"S": action},
        "retired_decrypt_key_arn": (
            {"S": before["decrypt_key_arn"]}
            if action == "ROTATE" else {"NULL": True}),
    }
    return {
        "schema": "notarai.confidential.custody-cas-plan.v1",
        "tenant": tenant,
        "action": action,
        "pre_state_sha256": previous_sha,
        "post_state_sha256": new_sha,
        "previous_state_revision": before["revision"] if before else 0,
        "new_state_revision": revision,
        "proposed_transaction": {
            "ClientRequestToken": transaction_token,
            "TransactItems": [
                {"Put": put_state},
                {"Put": {
                    "TableName": ledger_table_arn,
                    "Item": event_item,
                    "ConditionExpression": "attribute_not_exists(#tenant)",
                    "ExpressionAttributeNames": {"#tenant": "tenant"},
                }},
            ],
        },
        "requires_separate_custody_aws_identity_check": True,
        "requires_live_kms_policy_and_grant_proof": True,
        "requires_historical_decrypt_key_audit": True,
        "dynamodb_atomic_write_performed": False,
        "aws_calls": 0,
        "independent_custody_verified": False,
        "effective_revocation_verified": False,
        "status": "BLOCKED_PENDING_EXTERNAL_CUSTODY_EXECUTION",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", help="Approved prior custody state JSON")
    parser.add_argument("--signed-envelope-file", required=True)
    parser.add_argument("--trusted-public-key-file", required=True)
    parser.add_argument("--pinned-public-key-sha256", required=True)
    parser.add_argument("--independent-current-state-sha256", required=True)
    parser.add_argument("--ledger-table-arn", required=True)
    parser.add_argument("--output", required=True,
                        help="Create-only JSON plan with 0600 permissions")
    args = parser.parse_args(argv)
    try:
        before = (json.loads(Path(args.state_file).read_text("utf-8"))
                  if args.state_file else None)
        envelope = json.loads(
            Path(args.signed_envelope_file).read_text("utf-8"))
        public_pem = Path(args.trusted_public_key_file).read_bytes()
        result = compile_signed_cas(
            state=before, envelope=envelope,
            trusted_public_key_pem=public_pem,
            pinned_public_key_sha256=args.pinned_public_key_sha256,
            independently_pinned_previous_state_sha256=(
                args.independent_current_state_sha256),
            ledger_table_arn=args.ledger_table_arn)
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, sort_keys=True, indent=2)
            f.write("\n")
    except (OSError, json.JSONDecodeError, BoundaryDenied) as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": str(exc) if isinstance(
                exc, BoundaryDenied) else "custody CAS input/output unavailable",
            "aws_calls": 0,
        }))
        return 2
    print(json.dumps({
        "status": result["status"], "aws_calls": 0,
        "dynamodb_atomic_write_performed": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
