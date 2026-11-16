# Private AI EU pilot: executable staging foundation

Status 2026-11-16: source exists on a DRAFT pull request, NOT deployed,
audited, certified or authorized for client documents.

## Next milestone

An end-to-end synthetic fixture: IAM-signed POST /v1/documents on a dedicated
API Gateway HTTP API; one role-to-tenant binding; private Lambda with no
general Internet egress; Bedrock EU inference profile; metadata-only audit
events stored in S3 Object Lock (COMPLIANCE 30 days) via S3 VPC gateway endpoint.

Implementation:
- private_ai/ingress.py: SHA-256 pinning of the ONE allowed synthetic fixture;
  reject any user-controlled prompt other than the exact hardcoded synthetic prompt;
  accept only image/png + document_analysis;
  reject absent/forged/mismatched API Gateway/IAM context,
  unexpected fields and caller-provided tenant/model/classification.
- private_ai/lambda_entry.py: gateway adapter and S3 metadata audit sink;
  no user prompts/responses/documents in S3 audit events or errors.
- infra/private-ai-pilot.yaml: AWS_IAM route, Lambda in private subnets,
  outbound security group allowlist for Bedrock PrivateLink + S3 prefix list,
  S3 audit bucket with Object Lock, IAM conditions on requested region and VPC
  endpoint. This template is an UNDEPLOYED proposal, not validated in an account.
- tools/private_ai/build_pilot_zip.py: offline packaging from an explicit
  file allowlist. No automatic cloud changes.
- private_ai_tests/test_ingress.py: negative route/tenant/IAM and audit tests.

## Deployment prerequisites (manual, security-reviewed)

1. Fresh isolated AWS account/environment in eu-central-1 (prefer separate
   account, not the NotarAI production account), and an isolated VPC.
2. Two private subnets, their route table IDs, DNS hostnames/resolution enabled,
   no 0.0.0.0/0 NAT or internet route in those subnets, verified route table.
3. Managed S3 regional prefix list ID; confirm with AWS EC2 APIs, not guesses.
4. One precreated restricted caller IAM role, no human permanent access keys;
   role may call execute-api:Invoke only on the exact pilot POST route.
5. Review CloudFormation by cfn-lint + AWS validate-template and inspect
   IAM/VPC/S3 access before approval.
6. Generate synthetic PNG: `python tools/private_ai/make_fixture.py`;
   pass printed hash as `FixtureSha256`. The pilot must reject all other files.
7. Build ZIP locally: python tools/private_ai/build_pilot_zip.py;
   inspect its SHA256, scan dependencies, upload immutable artifact to
   reviewed S3 code bucket, then deploy stack only after explicit approval.
8. Test signed AWS_IAM + negative canaries against a live staging endpoint,
   using only the hash-pinned synthetic PNG; run:
   `python tools/private_ai/smoke_pilot.py --api-url https://API_ID.execute-api.eu-central-1.amazonaws.com/v1/documents --expected-account ACCOUNT_ID`.
   The caller must first assume the exact role configured by CallerRoleName.
   Check VPC Flow Logs, S3 Object Lock retention, Bedrock destination Regions,
   endpoint/DNS routing and explicit Internet egress denial separately.
   A passing smoke alone is not residency evidence.
9. Verify actual S3 retention, separate-account backup, audit access rights,
   CloudTrail and key revocation; add externally witnessed signed checkpoints.

## Non-negotiable limitations

- The pilot accepts only one exact SHA-256-pinned synthetic image and labels it
  INTERNAL. It is NOT a generic data-loss-prevention classifier or protection
  for future general-purpose client uploads.
- Only one IAM role and one test tenant. Scale-out requires real identity
  lifecycle, OpenFGA resource-level authorization, and per-tenant encryption.
- S3 Object Lock is NOT a cryptographic or independent audit witness, and its
  30-day default is an engineering test parameter, NOT a legal retention rule.
- IAM permission to bedrock:InvokeModel currently uses wildcard resources
  with SourceVpce and region constraints. Before commercial release restrict
  exact profiles, all underlying foundation models and SCPs, and prove
  cross-region behavior.
- The API is synchronous; HTTP API/Lambda timeout means large scans need
  an async queue, idempotency and per-tenant metering.
- Not a validated security boundary against account/root administration,
  compromised CI, poisoned packages, forged Lambda events from privileged
  direct invoke, or cloud-provider operational access.
- No GPU TEE/HSM attestation, no external pen test, DORA/NIS2/AI Act/GDPR
  sector qualification, and no banking/healthcare use approval.

**Do not merge automatically**. The Finance You OCR-denial draft PR #389
also must not merge until a verified replacement OCR flow exists.

References:
- AWS IAM for HTTP APIs: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control-iam.html
- Bedrock PrivateLink: https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.html
- S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
