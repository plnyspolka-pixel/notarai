# Policy-as-code reference

Reuses OPA/OpenFGA research from NotarAI Frontier Engineering Lab PR #36.
This PR adds tested OPA Rego rules for purpose, cross-tenant relations,
region/egress assertions, TTL-bound human/agent delegation, and tenant/model-
bound confidential release.

Important: OPA evaluates trusted evidence; it does NOT authenticate client
claims by itself. Never pass arbitrary JSON from the agent to the policy
decision point and treat 'verified' booleans as proof. Such assertions must be
created by an independent authorization/attestation service and protected
against replay, forgery and cross-tenant substitution.

Current Python adapter and this Rego policy are two separate REFERENCES,
not an integrated deployed PDP. P0 integration requires server-side evaluation
with fail-closed behavior on PDP outage, KMS-signed evidence, plus testing
actual network enforcement and storage/DB authorization. Rego tests are
automatically executed via pinned OPA setup action in GitHub Actions.
