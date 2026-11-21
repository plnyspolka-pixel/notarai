# Confidential Browser - one-time signed notary approval (R&D, no submit)

## Current status

This module is **implemented as a verifiable library and offline tests only**.
It is NOT connected to the live NotarAI API, notary account onboarding,
the Nitro guest worker, and certainly not a real government portal. The
production app feature flag remains OFF. The new CloudFormation resources
do not change any existing IAM roles or permit form submission.

Files:
- `confidential/signed_approval.py`: versioned Ed25519 signature verification,
  strict scope/expiry checks, read-only signing credential registry,
  transactional one-time approval ledger, async `fill_form` adapter.
- `infra/notarai-confidential-approval-ledger.yaml`: separate DynamoDB tables
  per synthetic tenant, retained with PITR and encryption, **no IAM grants**.
- `test_confidential_approval.py`: synthetic tests for forgery, expiry,
  wrong tenant/actor/target/form/document, wrong role or revoked key,
  replay with same or new nonce, database outages and `fill_form` callback.

## Exact approval signed by the user

The user signs a domain-separated canonical JSON object of version 1 with
**all** of these required fields:

```json
{
  "version": 1,
  "tenant_id": "pilot01",
  "actor_id": "notary_demo",
  "key_id": "demo_public_key_0001",
  "job_id": "synthetic_job",
  "form_id": "fixture",
  "action": "submit-form",
  "origin": "https://forms.example.test",
  "form_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "document_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "nonce": "0123456789abcdef0123456789abcdef",
  "issued_at": 1800000000,
  "expires_at": 1800000300
}
```

This is a **sample protocol schema**, never a real consent record.

Signature input: ASCII bytes
`b"notarai.confidential.approval.v1\\n" + json.dumps(intent, sort_keys=True,
ensure_ascii=True, separators=(",", ":"))`. Signature: Ed25519 64 bytes,
RFC 4648 strict Base64. The output envelope has exactly the keys
`{"intent": <object>, "signature": <base64>}`. Validity <= 300 seconds,
issued-at skew <= 60 seconds. Signed scope is not accepted unless it equals
**independently derived** expected tenant, actor, job, form ID, HTTPS origin,
hash of the actual form values and hash of the precise reviewed document.
The `fill_form` callback computes the form hash before the final click.

Do not derive these expected values from the same untrusted signed request.
The approved document must be rendered to and reviewed by the notary in a
trusted UI; the actual execution boundary must independently hash the
identical immutable document version. Neither user consent nor the blob's
SHA-256 implies that the notary saw the right content; the UX and binding
remain to be built.

## Trust boundary and what the signed approval is NOT

- A user-held private key is needed. This repo does not create, persist,
  reveal, import or enroll signing private keys. Test keys are ephemeral.
- The signing key public half MUST be enrolled in an independent
  authentication/identity-verification ceremony and placed into the separate
  registry by a privileged enrollment service; the normal submit API must
  never be allowed to add or change credential records.
- The registry must confirm tenant/actor, notary role, active status and a
  32-byte enrolled public key; a user-supplied role or `approved=true` is
  not an authorization.
- This Ed25519 signature is an **internal workflow authorization**, not a
  qualified electronic signature under eIDAS, proof of user presence,
  hardware-backed user verification, or legal delegation. Production should
  bind a phishing-resistant WebAuthn/passkey user-verification ceremony and
  required notarial/legal signature to the same exact intent.
- The operator's NotarAI front-end could maliciously ask for a signature of a
  different intent. A separate trusted approval surface and user-visible
  summary are prerequisites for real customers.
- Do not connect this to a real portal before the independent review,
  single-job idempotency, network policy and live Nitro tests succeed.

## Replay defense and ambiguous outcomes

`DynamoApprovalLedger.consume` calls DynamoDB `TransactWriteItems`
with **two** conditional `Put` operations. Both must succeed:

- `N#tenant#nonce`: blocks signing the same challenge more than once;
- `O#tenant#job#form#submit-form`: blocks creating another nonce to
  execute the same job/form/action twice.

Only SHA-256 of the canonical intent and minimal metadata are saved.
There is no automatic TTL: nonce and operation reservations remain,
including after unknown network or external portal outcomes. The ledger
contains a reserved/pending marker, **not evidence of successful submission**.
Operational reconciliation of external portal receipts and an audit retention
policy still need to be implemented.

Critically: a click may succeed remotely even if the local call times out.
Do not automatically retry an irreversible operation, release an approval
reservation, or assume a failure equals no legal effect. Reconcile the
remote portal state before a new human-authorized request.

## Deployment boundary (not performed)

The separate CloudFormation template creates two DynamoDB tables with no
consumer IAM grants. Before any test invocation involving the guest:

1. Provision only in `eu-central-1` and only under synthetic tenant.
2. Configure a **read-only** signing key registry backed by trusted enrollment.
3. Grant only the authorized, attested task role the minimal
   `dynamodb:TransactWriteItems` for the approvals table and
   `dynamodb:GetItem` for the credentials table; these IAM grants are
   **deliberately absent** from the current PR.
4. Validate KMS attestation, immutable ECS image/PCR17, private-network
   egress, job lifecycle and portal adapter per the other confidential docs.
5. Test expired, forged, double-use, wrong-origin, wrong-user and
   network-failure behavior with fictional data.
6. Implement user-verified enrollment, user-facing intent display, full
   receipt/reconciliation protocol and authorized portal adapter before
   considering a production submit integration.

Local offline tests:

```sh
python -m pytest -q test_confidential_approval.py
```

No live AWS access, customer records or signing keys are required for tests.
