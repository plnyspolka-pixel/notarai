# Confidential Browser - pilot scheduler v1 (preview only)

Status: implementation and offline tests only. **No AWS deployment or
hardware Nitro validation.** The release switch is OFF by default.

## Why a separate scheduled dispatcher?

Existing flow:

1. Authenticated NotarAI API enqueues only opaque job identifiers into
   dedicated **FIFO SQS**. The plaintext is encrypted in an S3 envelope.
2. The verified one-shot confidential guest reads exactly one SQS message,
   decrypts inside Nitro through NSM -> AWS KMS Recipient, and prepares
   **only** the local fictional demonstration form without submission.
3. Successful guest deletes its SQS message and writes a minimal ciphertext-
   free result marker.

There was no automatic launch between steps (1) and (2).

The new `confidential/dispatch.py` adds an EventBridge tick (one minute)
that only observes `ApproximateNumberOfMessages` in SQS and launches a
separate ECS Managed Instances task when work is visible. **It never
receives or deletes any SQS message**. Therefore the guest remains the
only consumer, and both its entrypoint and environment can stay exactly
pinned by the Nitro attestation policy.

Do NOT use `containerOverrides` or `--allow-additional-env` to pass
individual jobs. AWS pins environment variables and process arguments
in the confidential container admission policy by default.

## Safety invariant

- Single **pilot** tenant only, fixed eu-central-1 account, task definition,
  capacity provider, cluster, FIFO queue, private subnet and security group.
- Reject mutable ECR tags, untrusted role, non-Nitro capacity, unexpected
  container settings, additional environment variables, or public IP.
- DynamoDB consistent-read lease with conditional reservation: only one
  scheduler invocation can reserve the 15-minute window.
- If a previous ECS worker is still RUNNING/PENDING, never launch a second.
- A held lease is released early **only** when ECS DescribeTasks independently
  reports the previous guest in STOPPED/STOPPED status.
- AWS RunTask uses a fresh opaque `clientToken` for API-level idempotency.
- Ambiguous AWS responses retain their lease and are not retried immediately.
- The worker SQS visibility timeout is increased to 900 seconds; one task
  continues to process one FIFO record without any submit functionality.
- Lambda logs only coarse non-sensitive status strings.
- Default `DispatchEnabled=false`: EventBridge Rule DISABLED and Lambda
  `NOTARAI_DISPATCH_ENABLED=false`, even after deploying IaC.
- Never add production data or run production tasks under this pilot.

## Files

- `confidential/dispatch.py`: deterministic dispatcher with injected
  ECS/SQS/Dynamo clients; no implicit cloud calls.
- `confidential/dispatch_lambda.py`: EventBridge handler with fail-closed
  enable switch and eu-central-1 session.
- `infra/notarai-confidential-dispatch.yaml`: standalone staging
  EventBridge schedule, disabled Lambda, DynamoDB lease, scoped IAM.
- `scripts/package_confidential_dispatch.py`: deterministic source-only ZIP.
- `test_confidential_dispatch.py`: synthetic tests including duplicates,
  concurrent tasks, incorrect attestation, failed ECS start, and release
  after STOPPED.

## Operator provisioning steps (not executed)

Before deploying, complete the existing confidential hardware preflight
in `docs/confidential-deployment.md` (real KMS PCR17, precise guest image,
network policy, dedicated AWS principal). The staging pilot cannot be used
with customer data.

1. Run offline:
   ```sh
   python -m pytest -q test_confidential_dispatch.py
   python scripts/package_confidential_dispatch.py \
      --output /tmp/notarai-confidential-dispatch.zip
   ```
2. Independently verify the ZIP SHA-256 printed by the packaging script.
   Upload to an approved versioned S3 artifact bucket in **eu-central-1**.
   Do not place secrets in the ZIP.
3. Deploy `infra/notarai-confidential-dispatch.yaml` with
   `DispatchEnabled=false`, exact stack outputs for the existing
   ECS task/roles/SQS queue, a **private** subnet, dedicated task security
   group, CodeBucket and immutable CodeKey.
4. Validate IAM and Lambda invocation on fictional data with the schedule
   still disabled. Check the DDB lease table for a synthetic tenant and
   ensure no second ECS task starts while the first is active.
5. Only after explicit authorized stage approval, update the stack with
   `DispatchEnabled=true`. The production application feature flag
   `PIECZAPP_CONFIDENTIAL_ENABLED` must remain OFF until separate
   sign-off of the complete path.

Rollback: update the CloudFormation stack with `DispatchEnabled=false`
to disable scheduled launches. Do not delete the working guest, queues,
KMS keys or production storage as part of scheduler rollback.

## Limitations and explicit blockers

This is a **conservative single-worker scheduler**, not an exactly-once
transaction processor. Approximate SQS depth can be stale; ECS and DynamoDB
may be temporarily inconsistent; a 15-minute lease may delay recovery.
A successfully launched task is not cryptographic proof of a successful
NSM/KMS decrypt. EC2 launch, IAM/S3 permissions, ECR image, KMS policy,
Nitro attestation and network egress must still be validated on AWS.

Before processing real documents or allowing irreversible actions:

1. Replace broad HTTPS egress from the pilot security group with
   verified VPC endpoints / tightly scoped proxy and test bypass paths.
2. Add durable job-level reconciliation, dead-letter handling, alerts,
   per-job state and an idempotent completion/receipt protocol.
3. Add robust per-action user-signed approval checked at the execution
   boundary, with replay defense and immutable binding to document hash,
   target portal and action.
4. Document access control boundaries, KMS key policy governance and
   key recovery/rotation.
5. Run real Nitro hardware positive/negative attestation and zero-plaintext
   leakage tests with fake data, and complete legal review for the official
   portal adapters.

### Official AWS references

- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_Idempotency.html
- https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ListTasks.html
- https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_RunTask.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-events-rule.html
