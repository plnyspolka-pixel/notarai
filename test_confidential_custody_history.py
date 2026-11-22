"""SEC-06: synthetic full-history replay, key generation and evidence denials."""
import copy

import pytest

from confidential.custody_cas import compile_signed_cas
from confidential.custody_history import verify_history
from confidential.custody_ops import _IDENTITY_FIELDS, _ROTATION_FIELDS, apply_signed_action
from confidential.operator_boundary import BoundaryDenied, canonical_digest
from test_confidential_independent_custody_ops import (
    CUSTODY, NOW, signer, signed_event, state,
)

TABLE = (f"arn:aws:dynamodb:eu-central-1:{CUSTODY}:table/"
         "notarai-confidential-custody-ledger-pilot")


def make_history():
    first_private, first_pem, first_pin = signer()
    second_private, second_pem, second_pin = signer()
    base = state("pilot01", 1)
    envelopes = [
        signed_event(first_private, action="ENROLL",
                     changes={k: base[k] for k in _IDENTITY_FIELDS}),
    ]
    current = None
    events = []

    def commit(envelope, previous, pem, pin):
        package = compile_signed_cas(
            state=previous, envelope=envelope,
            trusted_public_key_pem=pem,
            pinned_public_key_sha256=pin,
            independently_pinned_previous_state_sha256=(
                canonical_digest(previous) if previous else "0" * 64),
            ledger_table_arn=TABLE, clock=NOW)
        write = package["proposed_transaction"]["TransactItems"]
        new_state = apply_signed_action(
            previous, envelope, trusted_public_key_pem=pem,
            pinned_public_key_sha256=pin, clock=NOW)
        return new_state, write[0]["Put"]["Item"], write[1]["Put"]["Item"]

    current, ledger_state, event = commit(
        envelopes[0], None, first_pem, first_pin)
    events.append(event)
    assert current["state"] == "FROZEN"

    new = state("pilot01", 2)
    rotate = signed_event(
        first_private, action="ROTATE", previous=current,
        changes={k: new[k] for k in _ROTATION_FIELDS})
    current, ledger_state, event = commit(
        rotate, current, first_pem, first_pin)
    events.append(event)
    assert current["generation"] == 2
    assert current["state"] == "FROZEN"

    terminal = signed_event(
        second_private, action="MARK_LOST", previous=current)
    current, ledger_state, event = commit(
        terminal, current, second_pem, second_pin)
    events.append(event)
    return {
        "tenant": "pilot01",
        "event_items": events,
        "state_item": ledger_state,
        "trust_roots": {1: (first_pem, first_pin),
                        2: (second_pem, second_pin)},
        "pinned_final_state_sha256": canonical_digest(current),
        "clock": NOW,
    }


def test_k5_replay_three_signed_events_and_retired_key_inventory():
    fixture = make_history()
    report = verify_history(**fixture)
    assert report["offline_chain_integrity_checked"] is True
    assert report["events_replayed"] == 3
    assert report["final_revision"] == 3
    assert report["final_generation"] == 2
    assert report["final_state"] == "LOST"
    assert report["distinct_signing_trust_roots_checked"] == 2
    assert len(report["historical_decrypt_key_arns"]) == 1
    assert report["historical_decrypt_key_arns"][0].endswith(
        "aaaaaaaa-0000-0000-0000-000000000001")
    assert report["current_decrypt_key_arn"].endswith(
        "aaaaaaaa-0000-0000-0000-000000000002")
    assert report["status"] == "BLOCKED_PENDING_INDEPENDENT_EVIDENCE"
    assert not report["independent_custody_verified"]
    assert not report["independent_ledger_export_completeness_verified"]
    assert not report["historical_keys_effectively_denied_verified"]
    assert not report["can_authorize_decrypt"]
    assert report["aws_calls"] == 0


@pytest.mark.parametrize("corrupt", [
    lambda f: f["event_items"].pop(1),
    lambda f: f["event_items"].reverse(),
    lambda f: f["event_items"].append(copy.deepcopy(f["event_items"][2])),
    lambda f: f["event_items"][1]["record"].update(
        S="EVENT#00000000000000000001"),
    lambda f: f["event_items"][1]["new_state_sha256"].update(S="f" * 64),
    lambda f: f["event_items"][1]["previous_state_sha256"].update(S="f" * 64),
    lambda f: f["event_items"][1]["retired_decrypt_key_arn"].update(
        S="arn:aws:kms:eu-central-1:444455556666:key/aaaaaaaa-0000-0000-0000-000000000099"),
    lambda f: f["event_items"][0]["tenant"].update(S="TENANT#pilot02"),
    lambda f: f["event_items"][2]["event_sha256"].update(S="f" * 64),
    lambda f: f["event_items"][0]["revision"].update(N="0"),
    lambda f: f["event_items"][0].update(unexpected_admin_override=True),
    lambda f: f["state_item"]["generation"].update(N="1"),
    lambda f: f["state_item"]["state_sha256"].update(S="0" * 64),
    lambda f: f.update(pinned_final_state_sha256="0" * 64),
    lambda f: f["trust_roots"].pop(2),
    lambda f: f["trust_roots"].update({3: f["trust_roots"][2]}),
    lambda f: f["trust_roots"].update({2: f["trust_roots"][1]}),
])
def test_k5_k6_replay_fails_closed_for_missing_records_forks_and_missing_pin(corrupt):
    f = make_history()
    corrupt(f)
    with pytest.raises(BoundaryDenied):
        verify_history(**f)


def test_k5_replay_detects_signed_event_mutation_and_wrong_generation_signer():
    import json
    f = make_history()
    item = f["event_items"][2]
    bad = json.loads(item["event_json"]["S"])
    bad["payload"]["action"] = "REVOKE"
    item["event_json"]["S"] = json.dumps(bad)
    item["event_sha256"]["S"] = canonical_digest(bad)
    item["action"]["S"] = "REVOKE"
    with pytest.raises(BoundaryDenied):
        verify_history(**f)


def test_k5_replay_rejects_duplicate_json_fields_and_nonnumeric_revisions():
    f = make_history()
    f["event_items"][0]["event_json"]["S"] = (
        '{"payload":{},"payload":{},"signature_b64":"AA=="}')
    with pytest.raises(BoundaryDenied, match="duplicate"):
        verify_history(**f)
    f = make_history()
    f["event_items"][0]["revision"]["N"] = "01"
    with pytest.raises(BoundaryDenied):
        verify_history(**f)


def test_k6_history_is_not_live_proof_even_with_independent_roots():
    f = make_history()
    result = verify_history(**f)
    for field in (
        "independent_ledger_export_completeness_verified",
        "independent_trust_root_provenance_verified",
        "historical_keys_effectively_denied_verified",
        "historical_event_commit_times_verified",
        "can_authorize_decrypt",
        "independent_custody_verified",
    ):
        assert result[field] is False


def test_k5_old_generation_key_cannot_reenter_after_multiple_rotations():
    from confidential.custody_history import _json_object
    f = make_history()
    # History after MARK_LOST is terminal. Build an alternative:
    # keep ENROLL -> ROTATE, then ROTATE back to initial key. It is different
    # from the immediately previous key but was used in generation 1.
    original = f["event_items"][:2]
    current = _json_object(f["state_item"]["state_json"]["S"])
    assert current["state"] == "LOST"
    state_after_rotation = state("pilot01", 2)
    state_after_rotation["state"] = "FROZEN"
    state_after_rotation["generation"] = 2
    state_after_rotation["revision"] = 2
    private3, public3, pin3 = signer()
    # The second-generation private key is not available from the returned
    # manifest; create a new independently signed generation-2 history.
    private1, pem1, root1 = signer()
    private2, pem2, root2 = signer()
    initial = state("pilot01", 1)
    enroll = signed_event(private1, action="ENROLL",
                          changes={k: initial[k] for k in _IDENTITY_FIELDS})
    from confidential.custody_ops import apply_signed_action
    one = apply_signed_action(
        None, enroll, trusted_public_key_pem=pem1,
        pinned_public_key_sha256=root1, clock=NOW)
    second = state("pilot01", 2)
    rotate1 = signed_event(
        private1, action="ROTATE", previous=one,
        changes={k: second[k] for k in _ROTATION_FIELDS})
    two = apply_signed_action(
        one, rotate1, trusted_public_key_pem=pem1,
        pinned_public_key_sha256=root1, clock=NOW)
    third = state("pilot01", 3)
    third["decrypt_key_arn"] = initial["decrypt_key_arn"]  # retired!
    rotate2 = signed_event(private2, action="ROTATE", previous=two,
                           changes={k: third[k] for k in _ROTATION_FIELDS})
    three = apply_signed_action(
        two, rotate2, trusted_public_key_pem=pem2,
        pinned_public_key_sha256=root2, clock=NOW)
    def event_item(envelope, previous, next_state, revision):
        import json
        p = envelope["payload"]
        old = previous["decrypt_key_arn"] if previous else None
        return {
            "tenant": {"S": "TENANT#pilot01"},
            "record": {"S": f"EVENT#{revision:020d}"},
            "event_json": {"S": json.dumps(envelope)},
            "event_sha256": {"S": canonical_digest(envelope)},
            "previous_state_sha256": {"S": (
                canonical_digest(previous) if previous else "0" * 64)},
            "new_state_sha256": {"S": canonical_digest(next_state)},
            "revision": {"N": str(revision)},
            "action": {"S": p["action"]},
            "retired_decrypt_key_arn": (
                {"S": old} if p["action"] == "ROTATE" else {"NULL": True}),
        }
    state_item = {
        "tenant": {"S": "TENANT#pilot01"},
        "record": {"S": "STATE"},
        "state_json": {"S": __import__("json").dumps(three)},
        "state_sha256": {"S": canonical_digest(three)},
        "revision": {"N": "3"},
        "generation": {"N": "3"},
    }
    with pytest.raises(BoundaryDenied, match="old custody key reused"):
        verify_history(
            tenant="pilot01",
            event_items=[
                event_item(enroll, None, one, 1),
                event_item(rotate1, one, two, 2),
                event_item(rotate2, two, three, 3),
            ],
            state_item=state_item,
            trust_roots={1: (pem1, root1), 2: (pem2, root2),
                         3: (public3, pin3)},
            pinned_final_state_sha256=canonical_digest(three), clock=NOW)
