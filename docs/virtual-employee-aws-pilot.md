# NotarAI Virtual Employee - AWS Windows VM pilot

**Status: CloudFormation and code prepared, NOT deployed to AWS.** Synthetic data only. The existing production ECS/Fargate NotarAI application and Confidential Browser/Nitro project are unchanged.

## Architecture

- One dedicated Windows Server 2022 EC2 per tenant (first fictional tenant: `pilot01`), Windows GUI running on AWS, **no NotarAI installation on the notary's computer**.
- Region `eu-central-1` (Frankfurt). Dedicated VPC and a private subnet without Internet Gateway, NAT, public IP, public RDP or other inbound security-group ports.
- Two required private AWS Systems Manager endpoints plus an optional legacy third: `ssm`, `ssmmessages` and `ec2messages`. The VM's only network egress is HTTPS to these endpoints. No direct access yet to the production NotarAI API or RejNET servers.
- Official AWS Windows Server AMI, encrypted 100 GiB gp3 system disk, IMDSv2 required, EC2 IAM role with `AmazonSSMManagedInstanceCore`.
- Bootstrap creates protected `C:\ProgramData\NotarAI\VirtualEmployee` folders. **It does not install RejNET, create passwords, run RDP auto-logon or deploy an AI worker.**
- No real notarial files, customer database, PESEL, certificates, passwords or secrets in this pilot. EBS encryption and network isolation alone do not establish Zero Knowledge or Zero Operator Access.

## Files

- `infra/virtual-employee/notarai-virtual-employee-pilot.yaml`: isolated VPC, SSM endpoints, IAM, Windows EC2 and encrypted system disk.
- `infra/virtual-employee/deploy-pilot.ps1`: validates by default; deploys billable resources **only** with `-Apply`, after account and region checks.
- `infra/virtual-employee/check-windows-session.ps1`: Windows/SSM/RDP and interactive session smoke check, no user names in output.
- `agent/NotarAI.VirtualEmployee.Probe/`: read-only UIA3/FlaUI test for *Notepad only*.
- `tests/test_virtual_employee_iac.py`: offline infrastructure security assertions.
- `.github/workflows/virtual-employee-pilot-iac.yml`: AWS-free lint, offline tests, Windows PowerShell parser and .NET compilation.

## Deployment by an authorized AWS administrator

Requirements: an AWS profile with EC2/VPC/CloudFormation/IAM authority for this separate pilot, an EC2 key pair in Frankfurt, AWS CLI v2, Windows PowerShell, Session Manager plugin and cost approval. The existing GitHub OIDC deployment role only allows production `notarai-aplikacja` and must not be broadened silently.

```powershell
# Read-only checks by default, no stack created:
.\infra\virtual-employee\deploy-pilot.ps1 -Profile notarai-admin -KeyPairName <EC2-KEYPAIR>

# Paid creation only after review:
.\infra\virtual-employee\deploy-pilot.ps1 -Profile notarai-admin -KeyPairName <EC2-KEYPAIR> -Apply

aws cloudformation describe-stacks --stack-name notarai-ve-pilot01 --region eu-central-1 --profile notarai-admin --query 'Stacks[0].Outputs'
aws ssm describe-instance-information --region eu-central-1 --profile notarai-admin
```

Wait until the EC2 instance shows `PingStatus: Online` in SSM. If not, inspect endpoint Private DNS and endpoint security-group ingress, EC2 role and SSM Agent service. **Do not expose RDP to the internet.**

### Administrative GUI over SSM

```powershell
aws ssm start-session --target <INSTANCE-ID> `
  --document-name AWS-StartPortForwardingSession `
  --parameters 'portNumber=3389,localPortNumber=13389' `
  --region eu-central-1 --profile notarai-admin
```

Use your local Remote Desktop client to connect to `127.0.0.1:13389`. Decrypt the initial Windows Administrator password locally with the private EC2 key. Never paste credentials into chat, logs, git, documentation, or cloud command output. Provision a dedicated non-admin operator identity separately, using an approved secret-management and access process. Do not enable Windows auto-logon.

**Important:** SSM/RDP tunnel is administrative access, not end-user remote desktop. SSM tunnel contents are not recorded as a full application-action audit. Real notarial operations require a separate, minimal audit design.

### RejNET Office qualification and GUI test

1. Obtain the official installer and vendor confirmation for **RejNET Office (rejnet.pl)** support and licensing for Windows Server on AWS. This is different from KRN's `Rejestry Notarialne` and `appRejnetSign`.
2. Deliver the signed installer through an explicitly approved controlled channel (e.g. RDP drive redirection where allowed); this VPC intentionally has no general Internet egress. Verify publisher signature and package checksum.
3. Install RejNET with a *fictional* test database and a dedicated non-admin operator; test login and local storage, without real client data.
4. Run `check-windows-session.ps1`. Test first with the read-only FlaUI probe: `dotnet run --project agent/NotarAI.VirtualEmployee.Probe -- --inspect-notepad` (requires .NET 8 SDK and NuGet access at build time; run the compiled binary on the isolated VM).
5. Implement a limited RejNET adapter only after confirming its actual UI Automation control tree. Test opening a fictitious case, reading non-sensitive fields, entering a draft, saving and recovering after disconnect/reboot.
6. Stop before any `sign`, `send`, `submit`, `delete`, or irreversible step. Require an explicit notary approval gate for production.

**GUI warning:** UI Automation must run in an *authenticated interactive Windows desktop session*. A standard Windows Service executes in Session 0 and cannot reliably click GUI controls. An SSM command by itself does not create a suitable desktop. A disconnected RDP session may also change UI behaviour. This pilot does not solve unattended session lifecycle; test and design that next.

## Production connection not implemented yet

Planned: authenticated `app.notarai.pl` tenant-scoped API -> private job queue -> VM-bound Windows agent in an interactive session -> FlaUI/UIA3 -> RejNET -> tenant-scoped result. Require job signatures, expiry/idempotency, per-tenant authorization, operation allowlist, consent/approval for irreversible acts, network egress allowlist and audit logs without document contents. No new public API or permissive NAT should be opened just to make the VM connect.

Production hardening: key ownership and operator access boundaries, credential provisioning through Secrets Manager, OS/session lifecycle, vendor license proof, vendor update delivery, patching without general Internet, backup/retention/tenant deletion, emergency access logs, Windows Defender active, Windows/Office/RDS license verification, and independent security review. **Do not market this as zero-operator-access or zero-knowledge while those controls are unimplemented.**

## Billing and cleanup

The stack creates a billed Windows EC2, encrypted gp3 volume, 2 default billed PrivateLink interfaces (legacy third optional) and monitoring. EC2 can be stopped when idle but EBS and VPC endpoint charges persist. This synthetic single-AZ pilot has no HA or automatic shutdown.

```powershell
aws ec2 stop-instances --instance-ids <INSTANCE-ID> --region eu-central-1 --profile notarai-admin
# Once done, remove the pilot stack (only after confirming no customer data exists):
aws cloudformation delete-stack --stack-name notarai-ve-pilot01 --region eu-central-1 --profile notarai-admin
```

## Acceptance criteria

- [ ] Stack validated locally with `cfn-lint` and through real AWS `validate-template`
- [ ] No public IP, no Internet Gateway/NAT, no inbound SG rules, IMDSv2 and encrypted disk
- [ ] SSM online through private endpoints; local RDP tunnel works
- [ ] Defender remains enabled, no antivirus exclusions
- [ ] Signed RejNET installer/licensing verified; GUI/Session 0 and disconnect behavior tested
- [ ] No real case data; staff approvals and audit plan in place before production
- [ ] VM stopped or stack removed after testing; costs reviewed

Sources: [AWS SSM PrivateLink](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-create-vpc.html), [Windows EC2 user data](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html), [official Windows AMI SSM parameter](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/finding-an-ami-parameter-store.html).


### Endpoint cost optimization

On current SSM Agent versions (>=3.3.40.0), `ssmmessages` is preferred; the legacy `ec2messages` endpoint is **disabled by default** to avoid unnecessary per-hour charges. To enable only when genuinely needed, use `-LegacyEc2Messages` with `deploy-pilot.ps1`. See [AWS Message API precedence](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-setting-up-messageAPIs.html).

## Signed local worker - second pilot increment (not deployed)

The prototype now includes a **local-only signed job protocol** shared by a
Python offline fixture generator and the Windows .NET worker. This is an
authentication/transport building block, **not** a live production bridge.

Exactly two diagnostic operations are allowed: `probe.session` and
`probe.notepad` (read-only UI Automation). Every job must contain eight
strictly typed fields: `schema=1`, `tenantId`, `jobId`, `operation`,
`issuedAtUnix`, `expiresAtUnix`, `nonce` and lowercase hex `signature`.
Unknown or repeated JSON keys, extra payloads, cross-tenant jobs and
unknown operations are rejected. A 32+ byte HMAC-SHA256 signing key authenticates
the canonical newline-joined fields:
`notarai-ve/v1\n1\nTENANT\nJOBID\nOPERATION\nISSUED\nEXPIRES\nNONCE`.
TTL is max 300 seconds, tolerance for issuer clock skew 60 seconds, and
single-use job IDs are claimed with create-new durable marker files.
The response contains only `jobId`, generic `status`/`code`, and a UTC
timestamp; **not** screen text, document contents or credentials.

### Pilot walkthrough on the isolated Windows VM

1. Download the CI artifact `notarai-ve-windows-pilot-unsigned` from the PR
   checks and its published SHA256. Transfer it through an approved,
   authenticated, manually supervised channel to the VM. This is deliberately
   **unsigned synthetic pilot code**; no production distribution yet.
   Ensure Windows Defender remains enabled, and do not add exclusions.
2. As VM administrator, create a dedicated **non-admin** Windows operator
   account through an approved local-account process (do not put its password
   in scripts). Place the verified executable under
   `C:\ProgramData\NotarAI\VirtualEmployee\bin` and restrict write access
   to admins; confirm SHA256 again on the VM.
3. Still as administrator, run
   `infra/virtual-employee/prepare-local-operator.ps1 -OperatorAccount '<MACHINE>\<OPERATOR>'`.
   It generates a **disposable test key** on the VM and explicitly restricts
   ACLs for system/admin/operator in `keys` and `work`; do not reuse it
   for customers.
4. Log in as that dedicated non-admin operator. Run
   `infra/virtual-employee/configure-operator-session.ps1 -TenantId pilot01`.
   It saves only paths and tenant ID in the user's environment, never the key
   value. Log off and back in to refresh the Scheduled Task environment.
5. With the operator's PowerShell 5.1 prompt, create a diagnostic test:
   `infra/virtual-employee/make-local-diagnostic-job.ps1 -Operation probe.session`.
   In the same interactive session, execute
   `NotarAI.VirtualEmployee.Probe.exe --once-local-inbox`. Verify a
   `*.status.json` was created in the private `work\outbox` and says
   `completed` with `probe_success`. Run a second time: no second
   execution. Change the signed message without recomputing the signature:
   it must be rejected. Never test with real notary files.
6. For a second test, open ordinary Windows Notepad, generate
   `probe.notepad`, then run `--once-local-inbox`. The agent counts only
   matching Notepad windows; **it does not read their text**. For the manual
   RejNET Office qualification, with a **fake** test database, obtain its
   process PID and execute `NotarAI.VirtualEmployee.Probe.exe --survey-ui <PID>`
   from the same desktop. The read-only survey displays a bounded histogram
   of UI Automation control types (maximum 400 controls, depth 4), with **no**
   window titles, automation IDs, names, values, or text. It does not write
   into RejNET or establish that a functional adapter exists.
7. Optional, after manual tests, register the resident *diagnostic* worker
   for the current interactive operator:
   `infra/virtual-employee/register-interactive-session-probe.ps1 -ExecutablePath '<FULL_PATH_TO_EXE>' -ExpectedSha256 '<CI_SHA256>' -StartWorker`.
   This uses Task Scheduler `Interactive` logon (not Session 0), never
   Windows auto-logon, and stops when the user logs out. Without
   `-StartWorker`, the task only runs a one-shot `--session-health` check.
   Unregister it with `-Remove`.
8. Monitor only generic results; remove the disposable key and test job
   folders when retiring this synthetic pilot.

### Still required before any real RejNET operations

- Interactive-session lifecycle and recovery after RDP disconnect/reboot
  **without** storing Windows passwords or weakening screen-lock policy.
- Vendor permission/licence verification and Windows Server compatibility
  of **RejNET Office**; test UIA3/FlaUI control identifiers on a fake case.
- A private authenticated bridge from `app.notarai.pl`: per-tenant identity,
  key lifecycle (AWS Secrets Manager/KMS or stronger), authorization,
  idempotency, queue/endpoint policy, attested artifact delivery, rate limits,
  audit, customer-side approvals for irreversible actions and egress control.
- This HMAC proof-of-concept is **not** Zero Knowledge or Zero Operator Access:
  an authorized operator who can read the VM's local test key can authenticate
  a diagnostic job, and account admins control the Windows VM.

Validation: the PR CI includes Python/C# deterministic HMAC interop,
adversarial schema/replay/tenant tests, local-inbox tests, Windows PowerShell
fixture-signing validation, Windows compilation and an unsigned self-contained
release artifact. None of those replace a real EC2/GUI/RejNET live trial.

## Optional private SQS transport (synthetic diagnostics only)

The previous file-spool prototype can now be connected to a **separate**
Amazon SQS FIFO queue through an AWS PrivateLink interface endpoint.
The CloudFormation bridge is defined in
`infra/virtual-employee/notarai-ve-sqs-pilot.yaml`. It is **not deployed**
and is disabled until an authorized AWS administrator explicitly uses
`infra/virtual-employee/deploy-sqs-pilot.ps1 -Apply`.

The bridge creates **one additional paid SQS VPC Endpoint**, a private
tenant-scoped FIFO queue with SQS-managed encryption, a dead-letter FIFO
queue, and a least-privilege EC2 IAM policy. The Windows instance
can receive/acknowledge messages **only from the tenant queue via the
specific VPC endpoint**. It has no `sqs:SendMessage` permission. The
queue policy denies insecure transport and receipt/deletion outside the
private VPC endpoint.

### Pilot sequence

1. Deploy the original Windows pilot stack first (with explicit approval).
   Without `-Apply`, the next command validates but does not create SQS:
   ```powershell
   ./infra/virtual-employee/deploy-sqs-pilot.ps1 -Profile notarai-admin
   ```
   To create the **paid optional** SQS bridge:
   ```powershell
   ./infra/virtual-employee/deploy-sqs-pilot.ps1 -Profile notarai-admin -Apply
   ```
   Record its `QueueUrl`; no signing key or customer data is an output.

2. Download the **CI-built signed-by-HMAC-job-compatible but unsigned EXE**
   artifact, verify its SHA256 hash, and place it in the VM's protected
   `bin` directory. The agent uses AWS SDK for .NET v4 with
   `InstanceProfileAWSCredentials`, never static AWS keys.

3. Log in as the dedicated non-admin Windows operator and configure paths
   plus queue URL:
   ```powershell
   ./infra/virtual-employee/configure-operator-session.ps1 -TenantId pilot01 -SqsQueueUrl 'https://sqs.eu-central-1.amazonaws.com/ACCOUNT_ID/notarai-ve-pilot01-jobs.fifo'
   ```
   Use the real `QueueUrl` returned by CloudFormation, not the placeholder.
   Confirm that queue URL, tenant ID and region match. Log off/in to refresh
   the current-user environment.

4. **Diagnostic only:** generate a signed job on the VM with
   `make-local-diagnostic-job.ps1 -Operation probe.session`. The private
   inbox now contains a single `<jobId>.json` envelope with no case data.
   Transfer only this short-lived signed envelope (NOT the HMAC key) to an
   authorized AWS administrator over an approved supervised channel.

5. In the authorized administrator's AWS environment, dry-run then send
   **one** synthetic job:
   ```powershell
   ./infra/virtual-employee/send-sqs-diagnostic.ps1 -JobFile 'PATH_TO_SYNTHETIC_JSON' -QueueUrl 'QUEUE_URL'
   ./infra/virtual-employee/send-sqs-diagnostic.ps1 -JobFile 'PATH_TO_SYNTHETIC_JSON' -QueueUrl 'QUEUE_URL' -Apply
   ```
   A short-lived job may expire while being transferred; if so, regenerate.
   The admin needs a narrowly delegated `sqs:SendMessage` permission to
   this pilot queue. The EC2 VM consumer role does **not** have that action.

6. Back in the **interactive** Windows operator session, run
   `NotarAI.VirtualEmployee.Probe.exe --once-sqs`. A single message is
   long-polled, HMAC-verified, checked for correct tenant/expiry/replay,
   processed only if it matches the diagnostic allowlist, and written as
   a metadata-only outcome to private `work/outbox`. **SQS DeleteMessage
   happens only after the outcome file is persisted.** The message body is
   never included in logs or stored in the outcome.

7. After confirming manual behavior, optionally register the persistent
   diagnostic SQS consumer for a *manually logged-in* non-admin operator:
   ```powershell
   ./infra/virtual-employee/register-interactive-session-probe.ps1 -ExecutablePath 'PATH_TO_VERIFIED_EXE' -ExpectedSha256 'EXPECTED_64_HEX_SHA256' -StartSqsWorker
   ```
   This registers `--serve-sqs` using Task Scheduler's interactive logon
   principal, **not** Windows auto-logon, an unattended session or Session 0.
   Remove it using `-Remove` from that same operator account.

### At-most-once diagnostic contract

The durable replay marker is written *before* execution. An OS crash between
marking the job and persisting the status may cause a later delivery to be
rejected as `duplicate`. This is therefore a conservative **at-most-once**
diagnostic mechanism, **not transactional exactly-once execution**. Production
RejNET writes require a job state machine, recoverable checkpoints,
idempotency at the target-system boundary, operator approval, explicit
results reconciliation and manual failure recovery.

For cleanup, delete the optional `notarai-ve-pilot01-sqs` stack **before**
deleting the original EC2 stack; its IAM policy references the VM role.
Stopping EC2 does not stop the additional VPC endpoint's hourly charges.

### Unfinished security dependencies

- No backend publisher exists yet. The pilot sender is an authorized
  administrative CLI command, **not** a production NotarAI feature.
- The disposable HMAC signing key currently exists on the VM and can be
  accessed by authorized Windows operators. It is **not** a production
  Zero Operator Access or Zero Knowledge architecture.
- For a production publisher, use an asymmetric signing design (backend KMS
  private key; agent validates a pinned public key), tenant identity and
  authorization in `app.notarai.pl`, with an authenticated result channel.
- Local SQS result files are metadata only; they are not automatically
  uploaded to the web app. The VM must still have an interactive
  user session to perform UI Automation. RejNET Office itself has not
  been tested or installed.

AWS references: [SQS over VPC PrivateLink](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-sending-messages-from-vpc.html),
[SQS least-privilege queue policies](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-least-privilege-policy.html)
and [AWS SDK for .NET v4 SQS receive](https://docs.aws.amazon.com/sdk-for-net/v4/developer-guide/ReceiveMessage.html).
