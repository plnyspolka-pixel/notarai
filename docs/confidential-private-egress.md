# Confidential Browser - private-only network pilot (NO AWS deployment)

Status: standalone CloudFormation template, read-only validation script and
offline security tests. All resources are **unprovisioned**. No production
security group or route table was edited. The existing staging
`infra/notarai-confidential-capacity-base.yaml` STILL allows outgoing
443 to 0.0.0.0/0; that staging SG must **never** be considered production
egress isolation.

## New restricted staging network

`infra/notarai-confidential-private-egress.yaml` builds a distinct
`GuestPrivateSecurityGroup` with **exactly** three egress rules:

1. HTTPS 443 to an interface-endpoint SG containing approved AWS
   PrivateLink services (KMS, SQS, ECR API/DKR, ECS, ECS Agent,
   ECS Telemetry, STS, CloudWatch Logs).
2. HTTPS 443 to the AWS-managed S3 PrefixList through a Gateway endpoint
   whose route is installed in an isolated pilot route table.
3. HTTPS 443 to AWS-managed DynamoDB PrefixList through a dedicated Gateway
   endpoint, used for one-time job claims and result status. This is not
   public internet egress.

There are no guest inbound rules, NAT, internet gateways, public CIDR
outbound rules, or running ECS resources created by this template.
Interface endpoints use private DNS with a dedicated SG restricted to
HTTPS initiated by the pilot guest SG. The S3 route table is mutated
ONLY if an authorized operator actually deploys the new stack.

The new `confidential/private_egress.py` rejects:
- A public-IP-capable subnet or wrong VPC/subnet route association.
- 0.0.0.0/0 or ::/0 default routes, including through NAT or Transit Gateway.
- Guest inbound rules or outbound rules broader than the two HTTPS targets.
- Unapproved outbound security groups or S3 prefix-list changes.
- Unexpected endpoint access or missing/unavailable private DNS services.

`scripts/verify_confidential_private_network.py` defaults to dry-run with
**zero AWS calls**. `--check` executes read-only Describe* operations
after explicit account verification. No secrets are fetched.

## Operator prerequisites (NOT executed)

1. Use a **dedicated non-production VPC/private subnet and route table**
   in `eu-central-1`; verify no production service uses that route table.
2. Confirm endpoint service availability/Private DNS support for the selected
   availability zone and account, DNS support and hostnames in that VPC.
3. Identify the AWS-managed S3 prefix list (NOT one entered arbitrarily)
   and check the full endpoint connectivity needed by **ECS Managed Instances
   and Nitro** including the new ECS data-plane service endpoints.
4. Validate the CloudFormation template and deploy it only from an approved
   provisioning principal, keeping all existing production SGs unchanged.
5. On an authorized machine, check:
   ```sh
   python scripts/verify_confidential_private_network.py \
     --account <ACCOUNT_ID> --profile notarai-admin \
     --vpc vpc-... --subnet subnet-... --route-table rtb-... \
     --guest-sg sg-... --endpoint-sg sg-... --s3-prefix pl-... \\
     --dynamodb-prefix pl-... --check
   ```
6. Pass **only** the validated `PilotGuestSecurityGroupId` to the
   separate private pilot task/managed-instance capacity provider;
   do not rely on the old broad SG.
7. Verify ECS startup, ECR image pulling, SQS/KMS/S3/DynamoDB operations, effective
   attested measurements (PCR17), and denied outbound attempts with
   fictional data. If any required AWS data-plane connection fails, do
   not silently restore Internet egress.

## Important limitations

This is a network **preflight template** and an offline validator, not a
verified deployment. AWS documentation notes that ECS Managed Instances
also need data-plane endpoints, so the listed endpoints may not be
complete for the exact current platform in this account. Validate
availability and required network paths on real infrastructure.

Security groups cannot by themselves block DNS lookups through the VPC
resolver, traffic tunneled through authorized AWS APIs, malicious GET
requests to permissive third-party portals, or traffic from another ENI
with different SG policies. The next stage needs Route 53 Resolver DNS
Firewall, endpoint policies scoped to specific S3 buckets/SQS queues/KMS
keys/ECR repositories, Network Firewall/flow logs, and workload/host
ENI audit. Do not route actual government portal traffic through this
AWS-only egress path until a separately reviewed proxy is designed.

No real document or submission can be processed in this pilot. The AUTO
preparation workflow remains no-submit and disabled at production.

## Offline tests

```sh
python -m pytest -q test_confidential_egress.py
python scripts/verify_confidential_private_network.py --help
```

Official AWS sources:
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-network.html
- https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/vpc-endpoints.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/managed-instances-awsvpc-mode.html


## Follow-on PR #57: production-unsafe bootstrap is disabled

The older `scripts/confidential_pilot_bootstrap.py --apply` is now a hard
error to prevent generating a provider from its original outbound 0/0 SG.
Use `docs/claude-aws-confidential-handoff.md` and the separate private
network CloudFormation stack. The synthetic worker now uses a new DynamoDB
lifecycle ledger, requiring DynamoDB Gateway VPCE, its managed prefix
list and least-privilege IAM on the exact tenant table.
