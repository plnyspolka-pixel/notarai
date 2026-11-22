# SEC-86 — customer-owned Nitro attestation and one-job DEK release

**Status: DRAFT / synthetic and offline only / not deployed.** This is a
stacked PR on #86 (itself stacked on #68). The existing KMS v2 pilot and
production Fargate are not modified. No live hardware claim is made.

## Components

- confidential/customer_nitro_attestation.py: local verifier for the AWS Nitro
  COSE_Sign1 attestation. Pins the AWS Nitro root certificate; verifies X.509
  chain signatures and validity, ES384, 180-second timestamp freshness,
  customer nonce, exact job-bound user_data, PCR8/PCR17 approved hashes,
  denies debug enclaves and requires an RSA-3072 SPKI recipient.
- confidential/customer_attested_release.py: SHA-256 binding of envelope,
  job ID and customer-generated challenge, followed by RSA DEK rewrap ONLY
  after verifying an authentic NSM report. No operator-provided key fallback.
- confidential/customer_guest_v3.py: one-job RSA-3072 guest key generated
  after /dev/nsm check. NSM signs nonce, job/document binding and guest key.
  One attempted preview consumes the capability, even on failed origin
  signature. The whole process must terminate after processing.
- confidential/nsm_recipient.py: preserves legacy KMS Recipient flow but
  additionally supports NSM nonce and user_data.
- scripts/customer_attested_release.py: offline independent Python workstation
  challenge/release CLI. Signed PCR policy, exclusive 0600 output, no AWS
  API calls, no plaintext or private key in outputs.
- test_customer_attestation.py and test_customer_guest_v3.py: synthetic
  negative scenarios for forged roots, tampered COSE/signature, wrong
  PCR8/PCR17, debug, wrong nonce or job, wrong RSA key, timestamps,
  unsigned/mutated policy, invalid document origin, guest reuse.

Source format and public pinned AWS Nitro root adapted from the
MIT-0 AWS sample:
https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp
License:
https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/LICENSE

## Independent workstation flow (prototype)

Never supply the RSA private key to operator-controlled NotarAI APIs,
browser pages or servers. Obtain the trusted CLI, signed PCR/image
manifest and the manifest signer's trusted Ed25519 public key from an
independently authenticated channel.

1. With an already encrypted customer-envelope file, run:

    python -m scripts.customer_attested_release challenge --envelope envelope.json --job-id job01 --output challenge.json

2. Transmit nonce_b64 and user_data_b64 from challenge.json as raw bytes
   through an untrusted channel to the Nitro guest. The guest recomputes
   the user_data from the exact envelope, job ID and nonce. It signs
   both values together with its ephemeral RSA-3072 SPKI via /dev/nsm.

3. Obtain the raw binary NSM COSE report. NEVER trust a result flag or
   operator-supplied public key. Independently verify a signed PCR
   manifest, then run:

    python -m scripts.customer_attested_release release --envelope envelope.json --challenge challenge.json --attestation report.cbor --owner-private-key owner.pem --pcr-manifest approved-pcr.json --pcr-manifest-sig approved-pcr.sig --trusted-policy-public-key trusted-ed25519.raw --output grant.json

4. The result is a preview-only DEK grant encrypted to the guest key
   embedded in the verified report, scoped to one job and exact envelope.
   Guest origin receipt must independently bind the exact ciphertext and
   S3 version before decryption.

Signed PCR manifest is a canonical UTF-8 JSON with fields:

    schema: "notarai.nitro-pcr-policy.v1"
    tenant_id: "pilot01"
    pcrs: {"8":"<96 lowercase hex>","17":"<96 lowercase hex>"}
    image_digest: "sha256:<64 lowercase hex>"
    expires_at: <Unix timestamp seconds>

Signature uses Ed25519 over json.dumps(manifest, sort_keys=True,
separators=(",",":"), ensure_ascii=True, allow_nan=False).

The image digest is SIGNED but not independently compared against the
live ECS task by this offline module. Exact PCR values are checked;
image-to-PCR provenance requires a separate real-hardware proof.

## Hard release gates, still BLOCKED

1. **Real NSM/ECS hardware**: no live AWS-generated COSE report or
   negative hardware proof has been produced in this PR. The test's
   alternate root is a synthetic fixture only; production code pins
   the AWS root.
2. **Independent browser client**: #68 creates an offline signed HTML
   encryptor, but this release CLI is Python and not yet integrated
   into that HTML or independently distributed as its own signed build.
   It must not be embedded in an operator-controlled webpage.
3. **Full v3 guest worker**: existing worker.py/S3/SQS currently handles
   KMS Envelope v2. The new guest is a library, not a deployed
   dispatcher or authorized ECS task. Exact pinned S3 version, tenant,
   job and output binding must be integrated and verified live.
4. **Durable replay prevention**: guest single-use state is per process,
   not persistent across parallel workers or restarts. The production
   job ledger must atomically consume grants and refuse races.
5. **Trusted time**: client wall-clock and the 180-second freshness
   window do not prove an enclave has a tamper-resistant clock.
6. **Full product scope**: Bedrock AI, OCR, model outputs, browser
   network egress, external portals, logs and Windows/RejNET remain
   outside this module's proof. No strict all-product ZOA claim.
7. **Independent review**: exact PCR manifest, issuer pin, supply chain,
   release provenance and live tenant isolation require review before
   processing any real notarial record.

## Test command

    python -m pip install 'cryptography>=42,<51' cbor2==6.1.5 'pytest>=8,<10' asn1crypto==1.5.1
    python -m pytest -q --noconftest test_customer_release.py test_customer_attestation.py test_customer_guest_v3.py

All included tests run with fictional keys and NO AWS calls.
A synthetic PASS must NEVER be described as hardware attestation PASS.
