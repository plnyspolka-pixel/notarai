# SEC-03: operating procedure for independent notary-side encryption

**State: offline code prepared; live custody, distribution, attestation and audit NOT verified.**
This procedure does not authorize production or advertising strict Zero Knowledge.

## Two distinct origins and trust boundaries

1. **Independent custodian** (not controlled by NotarAI root, SSO, Organizations
   management, CloudFormation execution roles or CDN) selects and owns the
   approved RSA KMS key and Ed25519 client-release signing key. The custodian
   also selects the client release, pins the exact source/hash and issues the
   separately authenticated document-origin receipts.
2. **Notary** visits only the verified custodian-controlled HTTPS origin to
   encrypt in a signed single-file HTML client. No NotarAI JavaScript, fonts,
   analytics, CDN, or network calls run inside this client. On a properly
   configured release, plain document bytes stay in browser memory while
   AES-256-GCM encrypts; the resulting JSON contains ciphertext and a wrapped
   random data key, not plaintext.
3. **NotarAI operator** hosts `/static/confidential-courier.html` as a separate
   ciphertext-only uploader. The notary supplies only `*.encrypted.json`.
   Backend checks tenant, allowed KMS, public pin and v2 envelope, conditionally
   reserves the document in DynamoDB before upload, stores ciphertext in
   versioned S3 and atomically binds the resulting S3 VersionId.
4. **Nitro guest** gets a queued immutable S3 version and validates its
   registry hash and checks the independent Ed25519 origin receipt with
   its release-pinned issuer key **before** calling the Nitro KMS Recipient
   unwrap path. No API can override this guest root.
   The guest refuses all jobs if its independent issuer root is absent.
5. Any legal form may be **previewed only**. AUTO has no authority to submit,
   sign, send applications or make irreversible third-party changes.

## Build and sign under independent custodian control

The signing key is generated and held by the independent custodian, not in
NotarAI's GitHub, CI, AWS account, Secrets Manager, or support systems.
The key must not be committed to this repository or passed in shell arguments.

The custodian retrieves the exact approved release source/digest, verifies it
by independent review and exports their independently pinned KMS RSA SPKI as a
PEM public key. SHA-256 pin format is base64 of SPKI DER (32 bytes).

```sh
python -m scripts.build_custodian_browser_client \
  --tenant pilot01 \
  --kms-key-arn 'arn:aws:kms:eu-central-1:<CUSTODY_ACCOUNT>:key/<KEY_ID>' \
  --kms-public-pem /secure/custody/public.pem \
  --independent-pin '<BASE64_SHA256_OF_PINNED_SPKI_DER>' \
  --release-id '<32_LOWERCASE_HEX_RANDOM_RELEASE_ID>' \
  --expires-at <UNIX_EXPIRY_SECONDS> \
  --custodian-signing-key /secure/custody/release-ed25519.pem \
  --encrypted-key \
  --output-dir /secure/new-release-01
```

The output directory contains:
- `client.html` (entire standalone client including source, KMS public key
  and pin; no network access, CSP restricts connections).
- `manifest.json` (signed binding of tenant/KMS/public key fingerprint,
  artifact SHA-256 and expiry; field `javascript_sha256` is the hash of the
  **entire HTML artifact** for this legacy manifest schema).
- `manifest.sig` (Ed25519 signature).
- `CUSTODIAN_PUBLIC_KEY_UNTRUSTED.bin` (informational; **NOT** a trust root
  merely because included in this bundle).

**Independent deployment gate:** custodian or independent auditor must provide
the externally authenticated signing public key through a different trust
channel and publish `client.html` on a custodian-controlled HTTPS origin.
Do not link to NotarAI-controlled HTML or assume self-hosted signatures are
sufficient. No production custody origin or cert has been verified by PR #68.

## Recovery without a support backdoor

- Closing a browser tab or losing an unsaved local DEK does NOT by itself
  lose the data: each ciphertext envelope contains an RSA-OAEP-wrapped DEK,
  retrievable only with the approved external KMS decrypt path.
- If the original KMS key is **disabled**, independent custodian can restore
  permissions under an authorized change-control procedure. This requires
  live policy/hardware testing. If the KMS key is **permanently deleted**,
  currently encrypted documents are not recoverable with v2 alone unless an
  independently provisioned cryptographic recovery copy already exists.
- `confidential.zk_recovery` signs the exact source document version,
  old and new keys, replacement public-key fingerprint, destination tenant
  and NEW object ID, plus nonce and expiry. Two independent Ed25519
  authorities are mandatory; an operator-admin signature is not sufficient.
- `confidential.zk_migration` may reencrypt inside a genuine Nitro guest
  only with signed, unused authorization, the correct old attested unwrapper,
  and the approved new RSA key. The old ciphertext remains inaccessible to
  an operator but not automatically deleted/revoked. A separate custody
  policy update and retention decision are mandatory.
- `confidential.custody_nonce.CustodyRecoveryNonceLedger` consumes the
  authorization ID once. The backing DDB table is created by
  `infra/notarai-confidential-custody-recovery.yaml` **inside the separate
  custodian account**. Its existence alone does not prove independent root
  ownership; that requires external audit. No automatic operator grants
  are created.
- Legal holds, notarial record-keeping periods, succession to a different
  kancelaria and evidence-preserving deletion require an approved policy.
  There is no promise of erasing every backup or cryptographic copy.

## Physical test and evidence gates

```sh
python -m pytest -q test_confidential_zk_client_encryption.py test_confidential_client_bundle.py
node test_confidential_courier_js.js
python -m scripts.verify_custodian_client_browser
python -m scripts.verify_sec03_operator_denial --help
```

After independent custody credentials exist, a designated operator and
custodian may run the synthetic-only read-only-by-default probe using
`python -m scripts.verify_sec03_operator_denial` with distinct profiles,
exact 12-digit account IDs, the approved KMS key and an OUT-OF-BAND public
key pin. **AWS calls occur only with `--check`**. A denial for one principal
is not enough for an unrestricted Zero Operator Access claim. Independent
review must also confirm root/Organizations independence, no KMS key-policy
mutation path, actual Nitro PCR17/8 and Recipient ciphertext behavior,
client origin signing, cross-tenant isolation and egress controls.

Actual evidence and unresolved K1–K6 statuses are in
`docs/security-evidence/SEC-03.md`. Do not set PASS when any live dependency
is missing.


## Signed document origin: exact release and pilot sequence (SEC-03 continuation)

### Release-custody prerequisite (no operator-created trust roots)

The independently controlled custodian/notary keeps the origin issuer
**Ed25519 private key** outside the NotarAI operator account and GitHub.
The corresponding PEM public key and its SHA-256 SPKI DER fingerprint must
be independently obtained and pinned by the custodian. Before measuring an
attested guest image, the custodian generates a root file:

```sh
python -m scripts.package_confidential_origin_root \
  --tenant pilot01 --issuer <AUTHENTICATED_EXTERNAL_ISSUER_ID> \
  --issuer-public-key /secure/issuer-public.pem \
  --independent-issuer-spki-sha256 <64_HEX_SHA256_OF_SPKI_DER> \
  --kms-key-arn 'arn:aws:kms:eu-central-1:<ACCOUNT>:key/<KEY_ID>' \
  --kms-key-pin '<PIN_BASE64_SHA256_KMS_SPKI>' \
  --expires-at <UNIX_EXPIRY_SECONDS> \
  --output /secure/release/trusted-origin-root.json
```

Copy this exact public root to `confidential/trusted-origin-root.json`
**only in a custodian-reviewed isolated image build** (never the public
repository). Build the guest with
`--build-arg NOTARAI_TRUSTED_ORIGIN_ROOT_SHA256=<SHA256_OF_ROOT_FILE>`.
Independently inspect the final image digest/PCR and configure the *external*
KMS key policy/attestation based on the approved digest and PCR. Passing a
SHA-256 build argument alone does not prove independent custody.

**Without the trust-root file, the guest now fails closed at startup before
SQS reception and never unwraps a DEK.** Standard CI guest image lacks the
custodian root by design. It is not a usable live pilot image.

### Fictional AWS pilot: two discrete steps

1. Stage a hardcoded fictional ciphertext document without enqueueing:

```sh
python -m scripts.confidential_pilot_fixture \
  --account <OPERATOR_ACCOUNT> --profile <OPERATOR_PROFILE> \
  --tenant pilot01 \
  --ciphertext-output /secure/out/synthetic.encrypted.json --apply
```

Record the printed exact `ciphertext_sha256` and `s3_version`.
The same encrypted bytes are written locally for independent review.
**No message is sent to SQS at this stage.** Never reuse the object ID
`synthetic01` after a failed or ambiguous staging operation.

2. An authenticated notary/independent custodian reviews the encrypted
file and S3 VersionId out of band. They issue an Ed25519-signed receipt
on a separate trusted device, without contacting NotarAI:

```sh
python -m scripts.sign_confidential_origin_receipt \
  --ciphertext-file /secure/out/synthetic.encrypted.json \
  --output-file /secure/out/synthetic.origin.json \
  --expected-sha256 <INDEPENDENTLY_VERIFIED_64_HEX_DIGEST> \
  --verified-s3-version '<INDEPENDENTLY_VERIFIED_VERSION>' \
  --issuer-id <AUTHENTICATED_EXTERNAL_ISSUER_ID> \
  --expires-at <UNIX_EXPIRY_SECONDS> \
  --signing-key /secure/issuer-private-ed25519.pem --encrypted-signing-key \
  --approved-tenant pilot01 \
  --approved-kms-key-arn 'arn:aws:kms:eu-central-1:<ACCOUNT>:key/<KEY_ID>' \
  --approved-key-pin '<BASE64_SHA256_OF_APPROVED_KMS_PUBLIC_SPKI>'
```

The private signing key never goes to the web app, S3, SQS, a GitHub
artifact, ChatGPT or the Nitro guest.

3. Admit the independently signed synthetic receipt and enqueue one
preview only after comparing the real S3 bytes and exact VersionId:

```sh
python -m scripts.confidential_pilot_origin_queue \
  --account <OPERATOR_ACCOUNT> --profile <OPERATOR_PROFILE> \
  --tenant pilot01 --ciphertext-file /secure/out/synthetic.encrypted.json \
  --signed-origin /secure/out/synthetic.origin.json \
  --immutable-s3-version '<S3_VERSION>' \
  --trusted-issuer-pem /secure/issuer-public.pem \
  --trusted-issuer-id <AUTHENTICATED_EXTERNAL_ISSUER_ID> \
  --independent-issuer-spki-sha256 <64_HEX_SHA256_OF_SPKI_DER> --apply
```

The two-stage CLI requires explicit `--apply`; without it the second
stage performs **zero AWS calls**. Ambiguous S3/ledger/SQS outcomes
require human reconciliation, never automatic retries.

4. The runtime guest reads the exact immutable S3 version, verifies its
recorded SHA-256, fetches the signed `.origin.json` sidecar, and verifies
the issuer Ed25519 signature using its **image-bundled pinned public key**.
Only then may it invoke attested KMS Decrypt. No submit, send or signature
to a third-party notarial portal is authorized.

### Normal notary workflow

The notary uses the independent no-network `client.html` to encrypt
locally, then the operator-hosted
`/static/confidential-courier.html` to upload ciphertext **only**.
The web app displays SHA-256 and S3 VersionId, which must be independently
checked and signed off-site by the authorized issuer. The notary then
imports the signed `.origin.json` receipt; only then does the
UI expose the optional preview queue action. The SaaS API reports
`signature_verified: false`: verification authority remains in the
attested guest with the independent root.

**Live trust limitation:** the issuer must authenticate the notary and
approve the exact ciphertext hash, object and version outside the operator's
control. Merely running the included signing CLI, using an operator-provided
public key or accepting a GitHub CI result does not establish this.
Zero Knowledge and Zero Operator Access remain **BLOCKED** until
external custody and hardware evidence pass.

## Recovery release — two separately pinned signers

The recovery request schema is notarai.recovery.v2 (not v1). Its two
independent Ed25519 signatures authorize ONLY the EXACT original
ciphertext SHA-256, original S3 VersionId, original KMS public key pin,
source tenant/case/object/version, target tenant/new object/new key pin,
request nonce and expiry. Two valid signatures from keys supplied by the
NotarAI operator are NOT sufficient: the public verification keys must be
baked into a separately authorized, measured Nitro image.

The independent custody party prepares the two-key root outside the
operator repository using the new tool:

- python -m scripts.package_confidential_recovery_root --help
- Supply separately reviewed custody/trustee Ed25519 public PEM files,
  their TWO different SHA-256 SPKI DER fingerprints, exact old KMS
  ARN and old RSA public pin, tenant and root expiry.
- Place the output at confidential/trusted-recovery-root.json only in
  an independent isolated release build, pass Docker build arg
  NOTARAI_TRUSTED_RECOVERY_ROOT_SHA256 as the independently checked
  SHA-256 hash. Check final immutable container digest and Nitro PCR.
- No operator account, GitHub CI or NotarAI support can issue/rewrite
  the release root. Without it the migration rejects before KMS unwrap.

The one-time authorization ledger must use a genuinely separate AWS
account: CustodyRecoveryNonceLedger verifies STS caller Account before
acquiring a DynamoDB client from that SAME account-scoped boto3 session.
Never put independent-custody long-lived credentials or administrative
roles inside the NotarAI workload account. A secure, attested provision
of the custody session/one-time approval capability is still missing;
software tests with mock STS alone cannot prove this boundary.

Key revocation is NOT the same as deleting one ciphertext. The 'revoke'
signature is authorization data only and does not call AWS KMS.
Disabling an RSA KMS key used for many documents blocks all of them.
Introduce independently approved key-wide scope, legal retention review,
audited custody administration, and verified backout before enabling such
an operation. Never label K5 PASS on this implementation alone.

Offline regression commands:

- python -m pytest -q test_confidential_recovery_trust.py
- python -m pytest -q test_confidential_zk_client_encryption.py
- python -m scripts.package_confidential_recovery_root --help

Actual attested Nitro and independent KMS tests remain BLOCKED.
