# NotarAI Confidential Browser: AUTO Control Room

**Status: PR-only, not deployed.** Separate operator dashboard for an
authenticated notary or office owner. No new permissions to sign, file,
send, approve, edit, reconcile, or retry a job.

## Operator experience

A small sidebar panel appears on `static/index.html` only when
`GET /api/confidential/control/jobs?limit=10` succeeds for the current
tenant and logged-in user. The panel:
- shows recent AUTO preview jobs by an **abbreviated opaque ID**;
- indicates queued, running, retryable, preview_completed,
  queue_uncertain, needs_review;
- marks attention when jobs have expired leases, wait more than 15
  minutes, or explicitly require manual review;
- includes a **read-only** Refresh button, with no background polling
  and no automatic task or network operation;
- never shows names, PESEL, document contents, screenshots, case IDs,
  S3 object keys/versions, AWS roles, or cryptographic material.

Totals refer **only to the latest page**. It is not a global history,
audit archive, time-series analysis, legal receipt or real-time status
guarantee. DynamoDB GSI uses eventual consistency.

## Endpoints and authorization

`GET /api/confidential/control/jobs` accepts no query parameters
or exactly one `limit=5|10|20`; rejects duplicates, `tenant`,
`actor`, `submit` and any other parameter.

The route enforces the pre-existing Confidential Browser pilot scope
and separately confirms the authenticated team member is either:
- `rola=wlasciciel` in the server-side office roster; or
- `stanowisko=notariusz` in that same roster.

Service access, application agents, unassigned staff, secretariat
and applications are rejected before AWS. A claim like
`{"role":"notary"}` in a request has no effect.

Only the tenant-specific table
`notarai-confidential-jobs-<tenant>` is queried, through
`TenantCreatedAtIndex` with `KeyConditionExpression:
tenant_id = :tenant`. No Scan operations, no table-wide customer
listing, no cross-office result aggregation. API projects only:
`tenant_id`, `created_at`, `job_id`, `state`,
`attempts`, `updated_at`, `lease_until`, `submitted`.
The output is a stricter allowlist, omitting even unnecessary
metadata such as lease timestamps.

Changes are confined to the optional staging pilot and do not
toggle `PIECZAPP_CONFIDENTIAL_ENABLED`.

## AWS migration and IAM

The new `TenantCreatedAtIndex` GSI is declared in
`infra/notarai-confidential-job-ledger.yaml` with
`INCLUDE` projection limited to metadata, not case/object IDs
or S3 versions.

**Claude or the deploy operator must**:
1. Verify the synthetic tenant's `notarai-confidential-jobs-pilot01`
   stack is not in an update before applying this PR.
2. Apply the CloudFormation GSI update independently; monitor
   `IndexStatus=ACTIVE` before using the endpoint.
3. Add only `dynamodb:Query` on the **specific GSI ARN**
   `arn:aws:dynamodb:eu-central-1:<account>:table/notarai-confidential-jobs-pilot01/index/TenantCreatedAtIndex`
   to the scoped **pilot application role**, after verifying it.
   Never add global `Scan` permissions, or grant job writes for
   monitoring, or widen the Nitro worker permissions.
4. Check page load as owner/notary, confirm 403 for secretary
   and cross-tenant requests, and ensure no content appears in
   browser console or logs.
5. Do not replace `GetItem` / conditional writes with eventual
   GSI results for authorization. GSI is **not** a source of truth
   for job execution or irreversible legal actions.

## Offline verification

```sh
python -m pytest -q test_confidential_control_room.py
node --check static/confidential-control-room.js
node test_confidential_control_room_js.js
```

Follow-on stage: durable append-only operational event history and
authorized reconciliation of uncertain SQS outcomes. A status snapshot
is not an immutable audit trail. Neither of those should be confused
with a notarized act, an official transmission receipt, an eIDAS
qualified signature, or a safe automatic retry.
