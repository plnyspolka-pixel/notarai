# NotarAI Confidential Browser - AUTO first, no external submissions

Status: source code + fictional Chromium smoke tests, **NOT deployed to
production**. The existing `PIECZAPP_CONFIDENTIAL_ENABLED` flag remains OFF.
This policy applies to the opt-in confidential module, not the entire legacy
notarial application.

## Default user behavior

- **AUTO** is the only default mode: user starts a preparation, then the
  engine fills the form and returns its preview without unnecessary prompts.
- No deliberative/reasoning mode is enabled by default
  (`thinking_enabled=false`). This is a workflow-policy field, not a claim
  that every third-party AI call can be controlled from it; this pilot worker
  currently runs only deterministic `local-demo`.
- User input cannot change the mode to `supervised`, `send`, or enable
  `thinking`/approval in the preview API.
- AUTO never clicks Submit, signs a document, dispatches a declaration or
  intentionally makes HTTP requests using POST/PUT/PATCH/DELETE.
- **Starting a job still requires an authenticated request** to prevent
  accidental new AWS tasks on every page load. After queuing, the dispatcher
  works without intervention. No independent task submission happens on
  page render.
- The API is unavailable unless existing SaaS / allowed-tenant / KMS / S3
  / SQS restrictions all pass. The auto status badge appears only after
  an authenticated `GET /api/confidential/policy` returns a verified AUTO
  policy; otherwise it is hidden.

## API endpoints and behavior

- `GET /api/confidential/policy`: tenant-scoped, no-store, returns
  `mode=auto`, `thinking_enabled=false`, `can_submit=false`,
  `can_sign=false`, `external_writes_enabled=false`, permitted and
  blocked preparation stages.
- `POST /api/confidential/preview/{case_id}/{object_id}`: no body;
  no query string or ONLY `?mode=auto`. Refuses unknown/duplicate
  parameters and any body (including `{"submit":true}`). Existing SQS
  message shape remains metadata-only; worker consumes it in AUTO.
- `GET /api/confidential/jobs/{job_id}`: returns pending or completed
  preview with fixed AUTO / no-submit flags and no decrypted values.
- `static/confidential-auto.js`: restricted client helper for
  `queuePreview` and `jobStatus` plus authenticated sidebar status.
  It has NO submit, approve or sign method.

## Browser execution boundary

`confidential.form_engine.fill_form()` defaults to `execution_mode="auto"`
and `submit=False`. Even if an attacker passes `submit=True` and a
positive callback, AUTO rejects before any navigation.

Before navigation, the AUTO engine registers:

1. Browser-context-wide HTTP request routing to the trusted adapter's
   allowed origins, denying every method except GET and HEAD.
   Context routing also covers first-request popups.
2. WebSocket route rejection (all sockets closed).
3. A browser init script preventing native HTML form submission.

The worker launches Chromium with downloads disabled and service workers
blocked. The guest remains strictly `local-demo`; no official portal
adapter is connected. The example Chromium smoke sends a synthetic POST
and clicks the local form's submit button, verifying no HTTP POST reached
the test server.

**Limits:** Playwright routing is not a complete security boundary:
GET URLs can have side effects in badly designed portals; networking from
outside Chromium bypasses its routing; browsers can expose additional
protocols. Before real data/portals, use private VPC endpoints and an
independent network egress firewall/proxy, and approve each official
adapter's allowed endpoints and semantics.

## Supervised mode and signed consents

`execution_mode="supervised"` exists **only as a library-level R&D hook**
for the cryptographically signed approval tests; the AUTO API and real
Nitro worker cannot select it. The signed approval callback now receives
the browser-observed origin in addition to job/form/digest, and rejects
a mismatch against the exact reviewed destination.

Signed Ed25519 approval is a *workflow authorization*, not an eIDAS QES
or a notarial signature. No official document can be transmitted by the
present pilot worker. Preparing work automatically does not waive a
notary's legal responsibilities or remove obligatory identity/signature
ceremonies.

## Tests

```sh
python -m pytest -q test_confidential_auto.py
node --check static/confidential-auto.js
node test_confidential_auto_js.js
python -m confidential.demo_browser
```

The normal Confidential Browser GitHub Actions job includes these tests
and the existing unit/CloudFormation tests. They use synthetic input
and no AWS credentials.

## Next integration stages

1. Independently enforced egress at VPC/proxy with audited allowlists,
   including abuse of GET endpoints, DNS and IMDS.
2. Per-job durable lifecycle, SQS DLQ reconciliation, idempotency and
   telemetry of metadata only (never names/PESEL).
3. Confirm actual ECS Nitro Sandbox / KMS attestation with negative PCR17
   tests, then test automatic preparation on an approved simulated portal.
4. Enroll user-verified passkeys and show the exact reviewed document
   before any future separate supervised submission capability.
5. Keep signatures, filings, money movement and irrevocable actions
   disabled until formal security/legal release review.

Official Playwright docs:
- https://playwright.dev/python/docs/api/class-page#page-route
- https://playwright.dev/python/docs/api/class-browsercontext#browser-context-route-web-socket
AWS policy docs:
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html
