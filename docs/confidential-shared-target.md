# NotarAI Confidential — ARCHITEKTURA DOCELOWA: jeden wspólny fabric

Status: przygotowane źródła + negatywne testy. **Nie wdrożono AWS ani
nie uruchomiono operacji na prawdziwych dokumentach.** Ten projekt zastępuje
w planie tworzenie sieci endpointów osobno dla pilota/każdej kancelarii.
Pilotaż odbywa się **na architekturze docelowej**, a nie na jednorazowej
VPC przeznaczonej później do usunięcia.

## Model regionalny

```text
NotarAI SaaS — autoryzacja użytkownika, routing, encrypted data store
   |
   | tenant-scoped metadata-only SQS FIFO (per kancelaria)
   |
   +--------- eu-central-1: ONE NotarAI Confidential Fabric VPC --------+
   |  Private subnet(s); no NAT/IGW or public IP; shared AWS endpoints   |
   |  AWS PrivateLink (one set per service per enabled AZ):             |
   |  ECS(3), ECR(2), KMS(1), SQS(1) = 7 base interface endpoints       |
   |  optional: STS, Logs, Signer if runtime/attestation requires       |
   |  S3 + DynamoDB Gateway endpoints (no per-hour endpoint fee)       |
   |                                                                     |
   |  ONE ECS Managed Instances cluster + ONE capacity provider        |
   |      Nitro Sandbox task #1: kancelaria A — task IAM A, KMS A        |
   |      Nitro Sandbox task #2: kancelaria B — task IAM B, KMS B        |
   |      Nitro Sandbox task #3: kancelaria A — task IAM A, KMS A        |
   |                                                                     |
   |  ONE immutable shared ECR image @sha256                             |
   +---------------------------------------------------------------------+
```

AWS ECS `CONFIDENTIAL_SANDBOX` isolates each task in an independent
Nitro microVM with its own task ENI; a common EC2 host and VPC do NOT
imply shared memory or credentials. Confidential execution still needs
cryptographic attestation and KMS key policy before any actual decrypt.

**Not a per-tenant endpoint design:** onboarding tenant N must not create
additional `AWS::EC2::VPCEndpoint`, EC2 instance security groups, cluster,
capacity provider or ECR repository. It creates scoped task/permissions,
SQS queue, work ledger and data encryption resources only.

## Implemented reusable infrastructure

- `infra/notarai-confidential-shared-fabric.yaml`: one VPC, private subnet,
  route table, shared runtime/endpoint security groups; 7 mandatory
  interface endpoints and 3 optional; Gateway endpoints S3/DynamoDB.
  No public route, NAT, IGW, connected office or deployed task.
- `infra/notarai-confidential-shared-capacity.yaml`: one regional ECS
  cluster, IAM instance/infrastructure roles, no on-demand EC2 running
  at stack creation.
- `infra/notarai-confidential-shared-ecr.yaml`: one immutable, scanned
  ECR image; tenant-specific task definitions still bind independently.
- `scripts/render_confidential_shared_capacity.py`: offline AWS
  `create-capacity-provider` request with Nitro enabled and private SG.
- `scripts/render_confidential_taskdef.py --shared-image`: same image digest
  for all tenants, but separate queue, KMS key, task IAM and tenant ID.
- `confidential/dispatch.py` + `confidential/dispatch_lambda.py`:
  `shared_pool` with exact cluster/provider `notarai-confidential-shared`,
  while retaining strict tenant job family, ciphertext, queue and IAM.
- `infra/notarai-confidential-dispatch.yaml` accepts
  `SharedCompute=true` to select shared cluster with exact IAM resource
  scope. Both `DispatchEnabled=false` and `SharedCompute=false` are
  legacy-safe defaults; **new shared deployments explicitly select
  `SharedCompute=true`**.
- `scripts/verify_confidential_shared_fabric.py --check`: read-only
  regional AWS account/stack, S3+DynamoDB prefix ownership, VPC, subnet,
  route, SG and actual VPCE verification. No `--check` means zero AWS calls.
- `scripts/confidential_pilot_run.py --shared-compute`: requires
  shared-fabric verification and rejects task launches outside the
  exact SG/subnet/cluster.
- All previous AUTO no-submit, signed-approval and job-ledger restrictions
  remain mandatory. The new code DOES NOT enable live submits.

## What remains PER TENANT and must NEVER be pooled

**Tenant identity is established by the trusted server**, never arbitrary
user-supplied tenant values. Scope:
- separate ECS task definition with pinned `NOTARAI_CONFIDENTIAL_TENANT`,
  queue URL, bucket and KMS key; **distinct task IAM role**;
- separate KMS decrypt authorization restricted to task principal,
  exact validated PCR17 and PCR8:ServiceName, and own ciphertext key;
- SQS FIFO per tenant and metadata-only job messages;
- encrypted object-prefix scope `kancelarie/<tenant>/...` in S3 with
  version-pinned input, segregated per-tenant resources where appropriate;
- job/lease tables and single-task-per-tenant scheduling.

Task roles must not access another tenant's queue, S3 prefix or KMS key.
The shared AWS endpoint is only a network transport, NOT a shared IAM
authorization. An owner or employee of tenant A must never choose tenant B
through UI/API/query parameters or by changing an ECS task override.
No ECS Exec, container overrides, host-mounted customer volumes, public
service endpoint or global KMS decrypt grant.

## Cost model (Frankfurt, 1 AZ, report from AWS Pricing API)

Current observed estimate per interface endpoint: **$0.012/hour**, plus
about **$0.01/GB** for traffic at the reported pricing tier.
Core 7 services in 1 AZ: `7 × $0.012 × 730 = $61.32 / month`.
7+optional STS+Logs: 9 services = `$78.84/month`.
AWS Signer adds a tenth interface endpoint when explicitly used.
Two AZs generally double interface endpoint-hour costs; a second AZ
requires its own subnet and end-to-end availability tests. S3+DynamoDB
Gateway endpoint access itself has no hourly endpoint charge.

These figures are estimates for a continuously provisioned 730-hour month,
not a new bill, and exclude compute/ECS, bytes transferred, KMS keys,
DynamoDB/S3/SQS, logging, CI and network security services.
**None of the endpoint counts multiply by number of kancelarie** in
the same VPC and AZ. Nitro Managed Instances hosts run only when the
capacity provider starts them; verify actual scale-to-zero before claiming
that compute cost is zero when idle.

## Future document portal navigation

A VPC with no NAT/IGW and only AWS PrivateLink **cannot load public
notarial or governmental portals**. That is deliberate for the offline
pilot, NOT proof that NotarAI can already complete real browser work.

Before enabling external navigation, design ONE shared, separately audited
outbound connector (domain+method allowlist, signed state-changing-action
gate, DNS protection, logging with no PII and E2E no-submit tests).
DNS names and GET/HEAD alone do not guarantee harmless operations.
Do NOT open NAT/0.0.0.0/0 simply to make the browser navigate.

## Availability

Initial production-shaped topology intentionally uses one AZ to bound
fixed PrivateLink cost during hardware validation; the *same shared VPC*
can add a second AZ subnet and another endpoint ENI per service in a
subsequent CloudFormation update — it does NOT require redesigning
per-tenant networks. Prior to HA release, add and test multi-AZ support
in the verifier and capacity scheduler. Failover is not yet implemented.

## Release gates

1. Complete this PR's offline tests and cfn-lint.
2. Use direct owner-approved Claude AWS session: no role-guard bypass.
3. Deploy one shared VPC/compute/ECR set (not old pilot network stacks).
4. Validate actual ECS-managed-instance private routes, DNS, Signer
   requirement, STS and CloudWatch requirements. Enable optional endpoints
   only when proven necessary by traffic and AWS APIs.
5. Launch exactly one fictional tenant `pilot01`, verify Nitro PCR/KMS and
   SQS/DDB, no HTTP submit. Repeat with **second fictional tenant**;
   confirm different task roles/queues/keys use the SAME VPC and capacity
   provider and cannot read each other's ciphertext or job.
6. Leave production confidentiality feature OFF, no real portal traffic
   and no permanently running EC2 during pilot.
7. Only after security and legal review enable new-tenant provisioning and
   user-visible AUTO preview. The no-submit barrier remains unconditional.

## AWS technical references

- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-overview.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-getting-started.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html
- https://docs.aws.amazon.com/vpc/latest/privatelink/interface-endpoints.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/vpc-endpoints.html
