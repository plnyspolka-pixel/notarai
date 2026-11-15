# Security, cryptography and blockchain research-to-design map

## Scope and threat actors
External prompt-injector, compromised browsing page or MCP server, malicious package/supply-chain publisher, stolen agent token, compromised GPU host, insider with elevated privileges, key exfiltration, tampered log, forged evidence, cross-tenant document access. Assume a compromised agent cannot be a trusted authorizer.

## Enforcement chain (build order)
1. **Authorize:** short-lived identity for each agent/task; OpenFGA for object relationships; contextual policy using OPA or Cedar with default deny. Use server-side checks on every data return, action, worker and tool call. No implicit tool access on user prompt alone.
2. **Constrain:** broker tool invocation (typed requests with purpose/scope), resource quotas, strict outbound network allowlists *plus* container/VM egress enforcement, filesystem mount policy and isolated browser profiles.
3. **Protect keys:** KMS/HSM-backed keys under a *different* security principal from the agent runtime. Attestation (AWS Nitro Enclaves/TEE/SEV-SNP/TDX) is useful for an approved attested workload; GPU provider marketing is not proof of an attested end-to-end pipeline.
4. **Record:** signed payload/event digests and build provenance with witness / Sigstore / in-toto / SCITT-style records. Push checkpoint roots to an independent witness and immutable/WORM store; consider on-chain anchoring only as an optional *public timestamp* for hashes, never customer data.
5. **Verify:** independent worker re-computes Merkle/hash commitments and provenance, audits revocations, replays attack tests; deny promotion on policy violation even when task score is high.
6. **Recover:** incident response for key compromise: revoke delegated credentials, roll keys, quarantine records, cross-check independent witness, rebuild from clean sources and report affected scope.

## Direct implementation candidates
- OpenFGA: https://github.com/openfga/openfga — fine-grained relations.
- OPA: https://github.com/open-policy-agent/opa — policy-as-code.
- Cedar: https://github.com/cedar-policy/cedar — contextual authorization.
- Sigstore Cosign: https://github.com/sigstore/cosign — artifact signing.
- in-toto Witness: https://github.com/in-toto/witness — software supply-chain attestations.
- SCITT: https://datatracker.ietf.org/wg/scitt/about/ — transparency protocol standardization.
- Trillian: https://github.com/google/trillian — verifiable transparency logs.
- SPIRE: https://github.com/spiffe/spire — workload identity.
- TLA+/Apalache: https://github.com/apalache-mc/apalache — model checking.
- PyRIT + AgentDojo: https://github.com/Azure/PyRIT and https://github.com/ethz-spylab/agentdojo — defensive evaluations of agent security.

## Experimental integrity log
tools/hashchain.py is intentionally a **non-cryptographically signed** toy chain for tamper detection in an unchanged snapshot. Anyone who can rewrite both the log and its head can forge a fresh valid history. It gives *no* transparency, non-repudiation or legal signature assurance. To elevate it, add externally witnessed, Ed25519/KMS signed checkpoints and independent verification, test rollback/fork detection and key rotation.

## Negative tests
- Attempt prompt injection from documents and public web pages; the agent must not execute instructions from untrusted data.
- Attempt tool argument substitution: denied if purpose, tenant, document ownership or approval missing.
- Inject expired or forged delegation tokens; deny.
- Deny network, poison supply-chain dependencies, fuzz policy interfaces, roll back the checkpoint, test fork/split-view with two witnesses.
- Compromise worker container and check that it still cannot request signing or customer-secret decryption.
- Chaos: outage of policy server, KMS, audit store and identity provider must fail closed where protected operations are concerned.

## Regulatory/operational boundaries
RODO, trade secrets, notarial secrecy, financial/regulatory restrictions, lawful document signature and QTSP/eIDAS questions need qualified specialist review. Immutable on-chain *personal* data is generally unsuitable; hash commitments can also raise linkability concerns. No deployment or qualification claimed.