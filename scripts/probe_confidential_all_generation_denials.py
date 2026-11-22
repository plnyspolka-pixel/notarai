"""SEC-06: operator negative KMS decrypt probes for EVERY signed key generation.

Default: zero AWS calls. Explicit double opt-in: replay independently pinned
custody history, then for each retired/current RSA KMS decrypt key perform ONE
synthetic OAEP ciphertext decrypt attempt without Recipient attestation from
the operator account. Every request must return genuine AccessDenied.

Never accepts supplied customer ciphertext. Never stores, logs, returns,
hashes or uploads plaintext. A successful Decrypt is FAIL_OPEN; any other
error is inconclusive. Even all denied attempts prove ONLY one workload IAM
identity, not system-wide effective revocation, ZK or zero-operator access.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidential.custody_history import _json_object, _s, verify_history
from confidential.custody_ops import validate_state
from confidential.operator_boundary import BoundaryDenied
from scripts.probe_confidential_operator_kms_denial import probe_operator_denial


def probe_all_generations(
    *,
    tenant: str,
    event_items: list[dict],
    state_item: dict,
    trust_roots: dict[int, tuple[bytes, str]],
    pinned_final_state_sha256: str,
    operator_profile: str,
    execute: bool = False,
    synthetic_only_ack: bool = False,
    clock: datetime | None = None,
    session_factory=None,
) -> dict:
    """Replay signed ledger BEFORE any AWS access, deny on any failing key."""
    history = verify_history(
        tenant=tenant, event_items=event_items, state_item=state_item,
        trust_roots=trust_roots,
        pinned_final_state_sha256=pinned_final_state_sha256, clock=clock)
    if not isinstance(operator_profile, str) or not operator_profile.strip():
        raise BoundaryDenied("dedicated operator test profile required")
    final = validate_state(_json_object(_s(state_item, "state_json")))
    all_keys = history["historical_decrypt_key_arns"] + [
        history["current_decrypt_key_arn"]]
    if (
        len(all_keys) != final["generation"]
        or len(all_keys) != len(set(all_keys))
        or all_keys[-1] != final["decrypt_key_arn"]
    ):
        raise BoundaryDenied("complete signed historical key list required")
    if not execute:
        return {
            "schema": "notarai.confidential.all-key-decrypt-denial.v1",
            "status": "BLOCKED_DRY_RUN",
            "tenant": tenant,
            "expected_key_count": len(all_keys),
            "verified_denial_count": 0,
            "aws_calls": 0,
            "independent_custody_verified": False,
            "effective_revocation_verified": False,
            "customer_data_used": False,
        }
    if synthetic_only_ack is not True:
        raise BoundaryDenied("explicit synthetic-only negative-test approval required")
    observations = []
    for generation, arn in enumerate(all_keys, 1):
        scoped_state = {
            **final,
            "decrypt_key_arn": arn,
            "state": "FROZEN" if generation < len(all_keys)
                     else final["state"],
        }
        observed = probe_operator_denial(
            state=scoped_state, operator_profile=operator_profile,
            execute=True, synthetic_only_ack=True,
            session_factory=session_factory)
        if (
            observed.get("single_operator_identity_denied") is not True
            or observed.get("status") !=
                "OPERATOR_DECRYPT_DENIED_FOR_ONE_IDENTITY"
            or observed.get("customer_data_used") is not False
            or observed.get("nitro_attestation_presented") is not False
            or observed.get("independent_custody_verified") is not False
        ):
            raise BoundaryDenied("incomplete negative KMS denial observation")
        observations.append({
            "generation": generation,
            "key_arn": arn,
            "operator_identity_denied_without_attestation": True,
        })
    return {
        "schema": "notarai.confidential.all-key-decrypt-denial.v1",
        "status": "BLOCKED_ONE_IDENTITY_NEGATIVE_TESTS_ONLY",
        "tenant": tenant,
        "final_generation": final["generation"],
        "expected_key_count": len(all_keys),
        "verified_denial_count": len(observations),
        "negative_test_observations": observations,
        "single_operator_identity_denied_all_generations": True,
        "other_operator_identities_tested": False,
        "all_historical_grants_checked": False,
        "effective_revocation_verified": False,
        "independent_custody_verified": False,
        "plaintext_logged_or_returned": False,
        "customer_data_used": False,
        "aws_calls": 3 * len(observations),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True,
                        choices=("pilot01", "pilot02"))
    parser.add_argument("--history-file", required=True)
    parser.add_argument("--trust-roots-file", required=True)
    parser.add_argument("--pinned-final-sha256", required=True)
    parser.add_argument("--operator-profile", required=True)
    parser.add_argument("--execute-negative-probes", action="store_true")
    parser.add_argument("--acknowledge-synthetic-only", action="store_true")
    parser.add_argument("--output", required=True,
                        help="Create-only report, 0600; not plaintext")
    args = parser.parse_args(argv)
    try:
        from scripts.verify_confidential_tenant_history_isolation import _load_history
        evidence = _load_history(
            args.history_file, args.trust_roots_file,
            args.pinned_final_sha256)
        report = probe_all_generations(
            tenant=args.tenant,
            event_items=evidence["event_items"],
            state_item=evidence["state_item"],
            trust_roots=evidence["trust_roots"],
            pinned_final_state_sha256=evidence["pinned_final_state_sha256"],
            operator_profile=args.operator_profile,
            execute=args.execute_negative_probes,
            synthetic_only_ack=args.acknowledge_synthetic_only)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, sort_keys=True, indent=2)
            f.write("\n")
    except (OSError, ValueError, TypeError, BoundaryDenied) as exc:
        reason = (str(exc) if isinstance(exc, BoundaryDenied)
                  else "custody synthetic negative test unavailable")
        print(json.dumps({
            "status": "BLOCKED", "reason": reason,
            "independent_custody_verified": False,
        }))
        return 4 if reason.startswith("FAIL_OPEN") else 2
    print(json.dumps({
        "status": report["status"],
        "verified_denial_count": report["verified_denial_count"],
        "customer_data_used": False,
        "independent_custody_verified": False,
    }))
    return 3 if args.execute_negative_probes else 0


if __name__ == "__main__":
    raise SystemExit(main())
