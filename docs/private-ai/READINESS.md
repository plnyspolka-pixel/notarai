# European Private AI — High-Assurance evidence gates

Status 2026-11-16: isolated research foundation, NOT production or certified.
No production/customer data, no model calls in tests, no automatic merge/deploy.

Research reused: NotarAI draft PR #36 (Frontier Engineering Lab):
https://github.com/plnyspolka-pixel/notarai/pull/36
- OpenFGA object relationships, OPA default deny, human approval for sensitive acts.
- SHA-384 / Ed25519 signed audit checkpoints (lab, not transactional nor witnessed).
- SPIFFE/SPIRE workload identity, Cedar, Sigstore/in-toto/SCITT, immutable WORM,
  KMS/HSM under an independent principal, Confidential Containers + Trustee.
- DARPA AIxCC as an approach to independent vulnerability discovery and repair,
  NOT as an endorsement, certification or proven security level.
Source: https://www.darpa.mil/news/2025/aixcc-results
Source: https://docs.nvidia.com/confidential-computing/overview
Source: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence

Implemented: synthetic-data EU Bedrock adapter, server-trusted Principal,
tenant/scope/purpose checking, no external provider fallback, bounded PDF and
images, mandatory sanitized audit, denied unknown provider, region, tenant
and restricted classification, CI regression.

Caution: confidentiality release switch is an OPERATOR gate, not verifiable
cryptographic evidence. No inference endpoint is currently exposed; real
authentication and tenant data paths are not connected. Runtime region claims
require validation in AWS. This is NOT a bank/hospital-ready product.

Mandatory future gates:
P0 Inventory ALL Finance You and NotarAI client document, voice, OCR, RAG and
embedding flows. Stop confidential data in unapproved Anthropic, Gemini,
OpenAI, ElevenLabs and Lovable paths. Do not automatically deploy breaking changes.
P1 Authorizer (OpenFGA + OPA/Cedar); opaque task capabilities with TTL, audience,
purpose and tenant binding; SPIFFE IDs; negative tests for forged/expired tokens.
P1 AWS SCP/IAM region boundaries, private subnet, VPC endpoints, egress firewall,
audited Bedrock model routing, backup/logging residency, provider contracts.
P2 vLLM dedicated GPU only after verified EU location AND attested CPU+GPU
confidential-computing chain, KBS/Trustee key-release policy. SaladCloud
distributed nodes must NOT process regulated data merely on a locality claim.
P2 Production auditing: HSM/KMS signer separated from runtime, signed checkpoints
to independent WORM witness, rollback/fork/truncation detection, key rotation.
P2 Supply-chain provenance: immutable digests, pinned build actions/images,
Sigstore/in-toto, signed releases. Chaos and prompt-injection red-team.
P3 External security assessment, ISO/SOC control evidence, DPIA/DPA and
subprocessors, DORA/NIS2/AI Act analysis as applicable, BCP/DR drills, test
restoration, tenant-specific NDA and audit rights.

Acceptance criteria: prove no external egress from a deployed confidential
worker (not just unit tests); deny tenant-cross access at API, S3, vectors,
logs; disallow key release before attestation; validate witnessed evidence
from independent verifier; generate attested bill of materials and a
customer-verifiable evidence package. Only then claim regulatory readiness.
