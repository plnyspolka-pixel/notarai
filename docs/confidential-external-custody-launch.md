# NotarAI Confidential: signed external KMS custody launch

STATUS: source code and offline synthetic tests; NO AWS deployment, no customer documents.

This patch integrates:
- PR #61 (external independent KMS custody)
- PR #62 (independently signed release approval)
- existing synthetic Nitro pilot runner

The old pilot runner implicitly required a same-account KMS key and read its
policy through the operator's IAM profile. That is incompatible with Zero Operator
Access when the key is owned by an independent custodian.

## New safety path

If external-custody-key-arn is supplied, the pilot runner requires:
- explicit shared-compute mode, separate custody AWS profile, signature receipt,
  independent custody public PEM and its out-of-band SHA256 fingerprint;
- LIVE read-only checks in both accounts of exact ECS task revision, immutable
  image digest, KMS RSA key policy, missing wildcard grants and attestation PCR17;
- independent ECDSA P-256 signature with short expiry bound to tenant,
  task version, digest, exact external key, KMS policy and PCR17;
- legacy checks for private network, ECS sandbox, role, bucket and SQS;
- no ECS RunTask until all independent checks pass.

The external KMS policy is NOT fetched with the workload/admin profile.
The signer and key custodian MUST be institutionally independent from
the NotarAI owner/operator and their AWS Organizations/SSO control.

## CLI (fictional data only)

First invoke without --apply (no AWS calls), after separate independent key
custody and signed release setup:

    python scripts/confidential_pilot_run.py \
      --profile WORKLOAD_AUTHORIZED_PROFILE \
      --account WORKLOAD_ACCOUNT_ID \
      --tenant pilot01 --shared-compute \
      --subnet SHARED_PRIVATE_SUBNET_ID --vpc SHARED_VPC_ID \
      --route-table SHARED_ROUTE_TABLE_ID \
      --guest-sg SHARED_RUNTIME_SG_ID \
      --endpoint-sg SHARED_ENDPOINT_SG_ID \
      --s3-prefix AWS_S3_PREFIX_LIST_ID \
      --dynamodb-prefix AWS_DDB_PREFIX_LIST_ID \
      --job-id EXISTING_SYNTHETIC_32_HEX_JOB \
      --external-custody-key-arn EXTERNAL_RSA_KMS_KEY_ARN \
      --custody-profile INDEPENDENT_READONLY_CUSTODY_PROFILE \
      --custody-release-file /secure/approved-pilot01.json \
      --custodian-public-key-file /secure/custody-public.pem \
      --custodian-public-key-sha256 OUT_OF_BAND_PINNED_SHA256

Only after explicit operator authorization and independent approval,
add --apply to launch ONE synthetic Nitro test task. Do not give the
NotarAI workload team admin access to the custody account.

Offline tests:

    python -m pytest -q test_confidential_custody_launch.py test_confidential_preflight.py test_confidential_release_approval.py test_confidential_operator_boundary.py

## Claims and remaining proof

This is a safety gate for the synthetic pilot, NOT certification or
proof of zero operator access. It does not itself prove:
- Nitro hardware-attested decrypt or negative KMS tests;
- custody account Organizations/SSO independence in the real world;
- no plaintext leakage via output, log, browser/AI egress, or future code;
- independent release authorization in production applications.

Commercial activation requires all these live tests and independent
signed evidence. AUTO remains preview-only and cannot submit/sign.

Running without external custody still uses the old operator-controlled
synthetic key. Do NOT use that legacy mode for a commercial ZOA claim.
