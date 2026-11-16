# High-Assurance AI: adversarial engineering threat model

Research basis: Frontier Engineering Lab, draft PR #36, plus DARPA AIxCC
security evaluation, NIST AI RMF generative AI profile, OpenFGA/OPA,
SPIFFE/SPIRE, TLA+, Nitro/TEE and NVIDIA Confidential GPU attestation.

## Trust boundaries (never use prompts as policy)

1. Human identity -> API gateway: verified session, tenant, scopes, authorization.
2. API gateway -> Policy Decision Point: OpenFGA object relationship and OPA/Cedar
   purpose/context; PDP unavailable means fail closed.
3. Policy -> workflow: delegated short-lived workload identity; capabilities
   constrained by document, resource, time and purpose. Model cannot authorize itself.
4. Workflow -> inference: egress enforcement on network and process boundaries,
   explicit EU runtime/model, no unapproved fallback, dedicated CPU/GPU only
   after independent attestation, verified software measurements and key broker.
5. Workflow -> data: per-tenant storage authorization and key separation;
   encryption in transit, at rest, in use where feasible, deny cross-tenant IDs.
6. Audit -> evidence: sanitized immutable metadata, independently signed and
   witnessed checkpoints, rollback detection and key revocation.
7. Build -> production: reviewed dependencies, signed images, SBOM, in-toto
   build attestations, no self-approval and no auto-deploy from agent changes.

## Attack matrix and non-negotiable expected behavior

| Threat | Preventive control | Evidence required |
| --- | --- | --- |
| Prompt injection hidden inside PDF | document as untrusted data, tool-less inference, tool broker | synthetic hostile-document eval |
| Cross-tenant IDOR / RAG bleed | OpenFGA + DB RLS + S3 prefixes and KMS grants | negative end-to-end suite |
| Forged/expired delegation | SPIFFE identity, audience and bounded TTL | token fuzzing + revocation |
| Provider-side copy/egress | VPC deny-by-default egress + approved EU endpoint | packet capture + flow logs + billing |
| Stolen agent credentials | scoped ephemeral token, no secret mount | container escape/secret denial drill |
| Compromised GPU host | TEE CPU/GPU attestation, KBS denies secret before verified | signed attestation quote + policy test |
| Insider edits audit log | SHA-384 chain, external HSM signature, WORM witness | tamper/truncation/split-view tests |
| Compromised build pipeline | pinned image digest, SBOM, Sigstore/in-toto | independently verifiable provenance |
| Backup loss/ransomware | segregated immutable backup, separate account, restore drills | timestamped restoration exercise |
| PDP/identity outage | fail closed; no cached perpetual authorization | chaos test under service outage |

## Applied in current PR

Private AI reference: tenant/scope/purpose enforcement, EU Bedrock routing,
document size/signature check, no external fallback, mandatory sanitized audit,
synthetic adversarial tests.

Evidence protocol: SHA-384 chain and verification of externally-signed
checkpoint; deliberately uses a fake in-memory ledger and test HMAC callbacks.
No production signer, WORM witness, multiwriter atomic commit or attested
hardware. The earlier Ed25519 laboratory reference is in the PR #36.

## What is still NOT proven

No live EU-only network egress proof; no ISO/IEC 27001, SOC 2, DORA, NIS2 or
GDPR compliance determination; no independent pen test, no contractual DPA
or dedicated medical/financial deployment. CPU/GPU attestation is a planned
control, NOT present. Not qualified trust service or classified system.
