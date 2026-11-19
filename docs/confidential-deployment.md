# NotarAI Confidential Browser — staging rollout (EU / fictional data)

Status on 2026-11-19: code and CloudFormation templates prepared in PR #50. No AWS
resources were created by ChatGPT and no hardware attestation was run. The existing
GitHub OIDC deployment role allows ONLY the production `notarai-aplikacja`
CloudFormation stack; it cannot provision this new Nitro/ECR/KMS environment.
Do not use live customer information at this stage.

## Deployment scope

Separate stacks and resources:
- `notarai-confidential-staging`: dedicated opaque S3 and SQS FIFO + DLQ, no IAM changes.
- `notarai-confidential-ecr`: private ECR image repository (immutable tags).
- `notarai-confidential-demo-kms`: staging asymmetric KMS RSA_3072 key,
  initial PCR17=all zeros (no guest can decrypt).
- `notarai-confidential-task`: ECS Managed Instances task definition with
  `CONFIDENTIAL_SANDBOX`, its dedicated execution/task IAM roles and
  attestation-gated KMS policy. Never uses the existing Fargate service.

All AWS calls MUST use `eu-central-1`. Use a fictional tenant, e.g. `pilot01`.
A separate AWS principal with administrative access for provisioning is needed.

## IaC bootstrap (manual execution in AWS-authenticated environment)

Check current credentials first:

```sh
aws sts get-caller-identity --profile notarai-admin
aws cloudformation validate-template --template-body file://infra/notarai-confidential-staging.yaml --region eu-central-1 --profile notarai-admin
aws cloudformation validate-template --template-body file://infra/notarai-confidential-demo-kms.yaml --region eu-central-1 --profile notarai-admin
aws cloudformation validate-template --template-body file://infra/notarai-confidential-ecr.yaml --region eu-central-1 --profile notarai-admin
aws cloudformation validate-template --template-body file://infra/notarai-confidential-task.yaml --region eu-central-1 --profile notarai-admin
```

Then create the three independent test stacks:

```sh
aws cloudformation deploy --stack-name notarai-confidential-staging \
  --template-file infra/notarai-confidential-staging.yaml \
  --parameter-overrides TenantId=pilot01 \
  --region eu-central-1 --profile notarai-admin

aws cloudformation deploy --stack-name notarai-confidential-ecr \
  --template-file infra/notarai-confidential-ecr.yaml \
  --parameter-overrides TenantId=pilot01 \
  --region eu-central-1 --profile notarai-admin

aws cloudformation deploy --stack-name notarai-confidential-demo-kms \
  --template-file infra/notarai-confidential-demo-kms.yaml \
  --parameter-overrides TenantId=pilot01 \
  --region eu-central-1 --profile notarai-admin
```

Read output bucket, queue URL/ARN, ECR repository URI and KMS KeyArn via
`aws cloudformation describe-stacks`. Do not send keys, tokens or customer
information to ChatGPT. Ensure that the KMS key and ECR account agree.

## Container image

Build independently of the application image:
```sh
docker build -f confidential/Dockerfile -t notarai-confidential:staging .
aws ecr get-login-password --region eu-central-1 --profile notarai-admin |
  docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.eu-central-1.amazonaws.com
docker tag notarai-confidential:staging <ECR_URI>:staging-20261119
docker push <ECR_URI>:staging-20261119
```

Resolve the resulting image digest with ECR `describe-images`.
Reference the image only by `<ECR_URI>@sha256:<DIGEST>`, never a mutable tag.

## Attestation and KMS

Use `scripts/render_confidential_taskdef.py` with account, tenant, exact image
digest, KMS ARN, bucket name and queue URL to generate
`confidential-taskdef.json`. It does not call AWS.

Get the official `ecs-nitro-sandbox-genpolicy` tool from the AWS
documentation and verify its provenance:
```sh
ecs-nitro-sandbox-genpolicy --task-definition confidential-taskdef.json
ecs-nitro-sandbox-genpolicy --task-definition confidential-taskdef.json --output pcrs
```

Review every Cedar admission pin. Save the base64 envelope and PCR17
from this exact task. First update the KMS stack's `ExpectedPCR17` parameter
to the measured value, then deploy `infra/notarai-confidential-task.yaml`
with ContainerImage, AttestationPolicyBase64, ExpectedPCR17,
ConfidentialKmsKeyArn, TenantId, EncryptedBucketName, JobQueueArn and JobQueueUrl.
Use `--capabilities CAPABILITY_NAMED_IAM`.

Verify with:
```sh
ecs-nitro-sandbox-genpolicy --check --task-definition <DEPLOYED_TASK_DEFINITION_ARN>
```

Do not expose KMS decrypt to an un-attested request or to the default app role.
Current root/account administrator can still modify the staging key policy;
this is not customer-held absolute Zero Knowledge.

## ECS capacity and execution

Create a separate `notarai-confidential-demo` ECS cluster and an
**ECS Managed Instances** capacity provider with
`InstanceLaunchTemplate.nitroEnclavesEnabled=true`, private deployment
subnets, dedicated security group, and approved instance types. As of
this verification, the AWS ECS API/CLI supports `nitroEnclavesEnabled`;
confirm CloudFormation's separate capacity provider schema before assuming
it can set this value. The dedicated instance profile role must use
`AmazonECSInstanceRolePolicyForManagedInstances`, while the infrastructure
role uses `AmazonECSInfrastructureRolePolicyForManagedInstances`.

Guest task supports one fictional tenant, no app login and no customer
credentials. The `confidential/worker.py` code reads one message from SQS,
fetches opaque envelope from S3, obtains DEK by attested KMS Recipient,
fills a localhost test form and exits without submission.
Trigger one standalone `aws ecs run-task` with dedicated capacity provider,
security group and task definition. No public ingress should be configured.
At present there is no automatic ECS task launcher from SQS.

## Evidence required before production enablement

1. Check `trustedExecutionSummary` is `CONFIDENTIAL_SANDBOX`
   and `attestationPolicyStatus=CONFIGURED`.
2. Observe KMS CloudTrail record of PCR17 for successful **synthetic** decrypt.
3. Change the task image digest/policy and verify KMS decrypt is denied.
4. Check that no plaintext, names, PESEL or browser screenshots reach S3,
   SQS, task logs, ECR or CI artifacts.
5. Verify no external domain access from the guest, in addition to the
   Playwright allowlist. Network policy must be enforced outside browser JS.
6. Add isolated job lifecycle, timeout, signed user approval and real portal
   adapters before real paperwork; the current worker only handles local demo.
7. Keep `PIECZAPP_CONFIDENTIAL_ENABLED` **unset** on the production Fargate
   service until the above is complete.

Official AWS references:
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-getting-started.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ecs-taskdefinition-trustedexecutionconfiguration.html
- https://docs.aws.amazon.com/kms/latest/developerguide/conditions-nitro-enclave.html
