# SEC-06 — Evidence for PR #71

Date: 2026-11-22 (UTC). Region: eu-central-1. Synthetic data only.
Status: DRAFT / NOT DONE. No production deployment, no independent AWS account verification, no real Nitro attestation.

## Acceptance status (K1–K6)

| Criterion | State | Source/test | Missing evidence |
|---|---|---|---|
| K1 independent administration | BLOCKED | confidential/custody_ops.py (validate_governance_snapshot); scripts/verify_confidential_custody_independence.py; 12 synthetic denials | Independent legal/account owner, root/Organizations/SSO/CI/CFN/billing control audit with signed evidence |
| K2 KMS policies / grants | UNVERIFIED | Existing confidential/operator_boundary.py; five explicit denied policy/grant mutations in test_confidential_independent_custody_ops.py | Passing CI plus live KMS key policy, IAM, 0 grants from custody account |
| K3 two-tenant onboarding | UNVERIFIED | Signed ENROLL, validate_pilot_inventory, cross-tenant binding denials | Two real custody RSA keys, separate policies/PCR/release receipts and live review |
| K4 freeze / revocation | BLOCKED | Signed FREEZE/REVOKE, deny-only target policy and old-policy/grant denial | Custodian actually removes Decrypt or disables KMS key, revokes grants, supplies CloudTrail and live negative decrypt including bypass |
| K5 rotation / lost key | UNVERIFIED | ROTATE only after FREEZE, separate signed UNFREEZE, LOST terminal, signature/replay tests | Passing CI, independent ledger CAS, live key rotation and non-recovery demonstration |
| K6 independent read-only live verification | BLOCKED | Dual-account STS/Organizations/IAM audit CLI, existing KMS/ECS preflight CLI | Authorized real read-only access to two independent accounts and independently signed proof |

Hard DONE condition: K1–K6 all PASS with links, zero FAIL/BLOCKED/UNVERIFIED, zero critical skips, green CI for current head SHA, and independent real AWS evidence. Passing mocks/tests alone never changes a production or marketing claim.

## Offline checks (AWS access is NOT performed)

    python -m pytest -q test_confidential_independent_custody_ops.py
    python -m pytest -q test_confidential_operator_boundary.py test_confidential_release_approval.py test_confidential_custody_launch.py
    python scripts/verify_confidential_custody_independence.py --operator-profile WORKLOAD_READONLY --custody-profile CUSTODY_READONLY

Third command must return dry-run, aws_calls=0, status=BLOCKED. Test result counts, job URLs and timestamps are to be recorded only AFTER real execution. Do not fabricate success.

## Optional independent authorized live read-only checks

    python scripts/verify_confidential_custody_independence.py \
      --operator-profile WORKLOAD_READONLY \
      --custody-profile INDEPENDENT_CUSTODY_READONLY \
      --check --output /secure/evidence/SEC-06-org-iam.json

For both synthetic tenants, run the preexisting verifier:

    python scripts/verify_confidential_operator_boundary.py \
      --operator-profile WORKLOAD_READONLY \
      --custody-profile INDEPENDENT_CUSTODY_READONLY \
      --tenant pilot01 --task-definition-arn EXACT_VERSIONED_TASK_ARN \
      --kms-key-arn EXTERNAL_RSA_KEY_ARN \
      --pcr17 APPROVED_96_HEX --image-sha256 PINNED_64_HEX --check

Repeat for pilot02. Both tools are read-only. Neither proves real root/SSO ownership, negative KMS outcomes, or Nitro attestation. Missing permissions give BLOCKED.

## Independent custody change control

1. Customer chooses its own independent AWS custody account or an independent external custodian. NotarAI does not control its AWS Organizations management, root, IAM Identity Center, billing delegates, CI/OIDC or CloudFormation execution roles.
2. Review all custody IAM role trusts, permissions, Organizations and SSO delegated administration, SCP/RCP, KMS key policies, KMS grants and CloudTrail with independent identities. Two different account IDs alone are insufficient.
3. Custodian provisions separate RSA_3072 and ECDSA P-256 keys for pilot01 and pilot02 and accepts exact image SHA, task revision, PCR17, key policy and release; signs authorizations with a trust-root fingerprint pinned out-of-band.
4. Signed ENROLL/FREEZE/REVOKE/ROTATE/UNFREEZE/MARK_LOST events are stored with monotonic revision/compare-and-swap in an external custodian ledger. The operator-hosted state machine is NOT authoritative for KMS authorization.
5. For FREEZE/REVOKE, custodian independently applies the generated deny-only policy (remove attested Decrypt) or disables the key, removes any grants, verifies live hash/CloudTrail and attempts negative decrypt including direct ECS/task bypass. No old/operator fallback.
6. ROTATE requires FREEZE, fresh independently held RSA and signing keys, new measured PCR/task digest/policy and release, and a separate signed UNFREEZE after live approval. No automatic ability to recover lost plaintext. MARK_LOST is terminal; recovery only from separately authorized encrypted backups, if any.
7. Auditor stores timestamp UTC, exact source SHA, signed release approvals, sanitized key/task identifiers, KMS deny/allow outcomes and evidence references in independent tamper-resistant storage. Do not place PII, documents, plaintext, keys, access tokens or DEKs in CI/logs/PR.

## Exact negative evidence map

K1: shared AWS account/org, operator Organizations manager, root control, GitHub OIDC, role assume, SSO, billing and CloudFormation delegated control.
K2: PutKeyPolicy, CreateGrant, unrestricted Decrypt, wildcard principal, rogue grant.
K3: duplicate keys/approvals, wrong tenant/task/PCR/digest.
K4: frozen/revoked old allow policy, unexpected grants and direct KMS bypass (live outstanding).
K5: invalid/expired/wrong-custodian signature, replay, stale revision, unsafe rotation, old key reuse, illegal recovery after loss.
K6: missing Organizations evidence, IAM role trust bypass and unsigned independent ownership (live outstanding).

Limitations: These files implement an offline custody control-plane preview and do NOT wire enforcement to the production scheduler or perform actual AWS mutations. A workload administrator can bypass a metadata preview without separate KMS policy and mandatory release gates. Production confidential mode remains OFF and AUTO no-submit/no-sign. No unconditional Zero Trust, Zero Operator Access or Zero Knowledge claim is warranted.


## Custodian-side signed event CLI (synthetic; no key mutations)

The external custodian can sign a locally reviewed event via its KMS
SIGN_VERIFY P-256 key. Separate customer-approved action, current
versioned state and out-of-band pinned public key SHA256 are mandatory.

    python scripts/custodian_sign_confidential_operation.py \
      --payload-file /secure/custody-action.json \
      --current-state-file /secure/pilot01-state.json \
      --custody-profile INDEPENDENT_CUSTODY_SIGNER \
      --signing-key-arn EXTERNAL_CUSTODY_SIGNING_KEY_ARN \
      --pinned-public-key-sha256 INDEPENDENTLY_PINNED_SHA256 \
      --pinned-current-state-sha256 EXTERNALLY_PINNED_CUSTODY_LEDGER_STATE_HASH

This is a dry-run: zero AWS calls, no signature. An authorized custodian may add
--approve-action --output /secure/signed-pilot01-action.json; the tool
checks custody STS identity, signing-key metadata, separately pinned
public-key fingerprint, event schema, time, state hash and monotonic revision,
then calls KMS Sign. It NEVER calls KMS Decrypt, PutKeyPolicy or CreateGrant.
The actual policy update, grant inventory and independent ledger remain
separate controlled actions. Do not place output receipts in GitHub/CI.


## Offline custody change-package generator (added in PR #71)

For an independently approved and previously stored fictional custody state:

    python scripts/plan_confidential_custody_operation.py \
      --state /secure/pilot01-state.json --action FREEZE \
      --output /secure/pilot01-freeze-plan.json

The resulting package is NOT authorization. It contains an unsigned
tenant-bound event, previous-state SHA256, next revision, expected
post-state digest, proposed KMS key policy hash and a mandatory independent
CAS/policy-apply checklist. It has aws_calls=0, authorized_for_decrypt=false,
kms_policy_write_performed=false. A package cannot be passed directly to
the signed-event reducer as an approval.

For a new enrollment (pilot01/pilot02), independently review a JSON
object containing exactly the identity/binding fields listed in
confidential/custody_ops.py (_IDENTITY_FIELDS). Then invoke the planner with
--action ENROLL --tenant pilot01 --changes /secure/pilot01-binding.json.
For ROTATE, use --state, --changes containing ALL _ROTATION_FIELDS, and
a previously frozen state. After independent KMS policy application, require a
separately signed UNFREEZE.

The custodian signer CLI accepts the unsigned_event_payload object,
NOT the entire plan JSON. Extraction and policy change require the external
custodian's review. Do not publish the plan as an AWS/zero-operator proof.

## Trust-graph discovery tightened

Read-only Organizations/IAM scanner now treats any WebIdentity/SAML
(Federated) role trust, custom Service trust, a foreign AWS account principal,
unreviewed trust action or incomplete role pagination as BLOCKED, even when
the custody and workload account IDs differ. This specifically prevents a
NotarAI-controlled GitHub OIDC trust in the custody account from being
misrepresented as independent custody. AWS-managed service-linked roles can
pass the limited static filter; ownership and permission checks still need
a separate independent assessor and never become VERIFIED automatically.

## Mandatory state pin before KMS signing

The signing tool refuses `--approve-action` unless the custodian explicitly supplies `--pinned-current-state-sha256` matching the canonical digest of the current state, obtained from the independent custodian ledger rather than the operator-provided JSON. For first ENROLL this is 64 zeros, representing no prior approved record; creation still requires conditional put in the independent ledger. A mismatched/stale/missing pin is rejected **before any AWS call**. This is an out-of-band precondition, **not** an implemented live CAS ledger or evidence of institutional independence.

## Offline two-tenant onboarding

Use `scripts/prepare_confidential_custody_onboarding.py --pilot01-binding /secure/pilot01.json --pilot02-binding /secure/pilot02.json --output /secure/onboarding-plan.json`. It validates distinct keys, task ARN, PCR17, release and policy SHA for both synthetic tenants and produces unsigned, tenant-bound ENROLL plans. It performs zero AWS calls and creates no KMS resources or grants. The external custodian must provision, audit, sign and activate each tenant separately, including a real conditional state ledger and hardware negative tests.

## K2/K4 read-only KMS policy and grant inventory

Default audit makes zero AWS calls:

    python scripts/verify_confidential_custody_kms.py \
      --state-file /secure/pilot01-state.json \
      --custody-profile external-audit

Explicit independent read-only KMS inventory:

    python scripts/verify_confidential_custody_kms.py \
      --state-file /secure/pilot01-state.json \
      --custody-profile external-audit --check \
      --output /secure/pilot01-kms-snapshot-report.json

Required permissions in custodian key policy, without granting NotarAI any new rights:
`kms:DescribeKey`, `kms:GetKeyPolicy`, `kms:ListKeyPolicies`, `kms:ListGrants`.
This PR grants the last two ONLY in the custodian statement in the
CloudFormation template and updates the offline policy checker and fixtures.

The auditor verifies custody account, region, RSA_3072, key state, exactly
one policy name (default), strict canonical policy and all KMS grants with
NextMarker pagination. Duplicate JSON keys, foreign/extra policy, incomplete
pagination, any grant, wrong key type/account all block.

A structurally valid snapshot STILL returns status BLOCKED and CLI exit 3:
independent_custody_verified=false and effective_revocation_verified=false.
AWS KMS inventories are eventually consistent. No live negative decrypt,
Nitro attestation, root/SSO verification or signed CloudTrail proof is run.

## K5 historical KMS key retirement

ROTATE offline plans now contain required_kms_key_policy_targets for
both outgoing and incoming decrypt keys, deny-only before any UNFREEZE.
Pointing application state to a new ARN does not revoke the old key.
historical_decrypt_key_inventory_complete=false and
historical_keys_effectively_denied_verified=false remain hard blockers.
The independent custodian must enumerate every prior key generation
from its immutable ledger, deny old keys, remove all grants and repeat
real negative decrypt attempts before approving the new key.

Official AWS API references:
- https://docs.aws.amazon.com/kms/latest/APIReference/API_ListGrants.html
- https://docs.aws.amazon.com/kms/latest/APIReference/API_ListKeyPolicies.html
- https://docs.aws.amazon.com/kms/latest/developerguide/conditions-nitro-enclave.html

## K3 first enrollment: deny by default

The synthetic ENROLL operation produces custody state FROZEN, revision 1,
and a KMS policy with **no kms:Decrypt** for any role. It does not activate
the tenant. The independent custodian must later authorize a separate signed
UNFREEZE event (revision 2) only after the correct KMS policy and attested
release have been verified out of band. No operator-controlled bootstrap
or temporary access to plaintext is permitted. This offline reducer does
not implement the live KMS proof prerequisite or actually block AWS requests.

Test: test_k4_enroll_freeze_revoke_fail_closed_without_old_operator_fallback;
dual-tenant onboarding tests assert both proposed enrollment policies deny
Decrypt. Live activation and KMS denial remain BLOCKED.
