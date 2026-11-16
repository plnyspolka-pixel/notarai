package private_ai.guard

import rego.v1

# Reference Policy Decision Point, inspired by Frontier Lab PR #36.
# All fields such as relation.allowed, release.verified and runtime.checked
# MUST be minted by independently trusted backend components, not users or LLM.
default allow := false

base if {
  input.identity.authenticated == true
  input.identity.active == true
  input.identity.tenant_id == input.resource.tenant_id
  input.relation.allowed == true
  input.operation == "invoke"
  input.runtime.checked == true
  input.runtime.region == "eu-central-1"
  startswith(input.runtime.model, "eu.")
  input.runtime.egress_verified == true
  input.audit.available == true
  input.purpose in {"document_analysis", "document_extraction"}
}

classification_ok if {
  input.resource.classification in {"public", "internal"}
}

classification_ok if {
  input.resource.classification == "confidential"
  input.release.verified == true
  input.release.bound_resource == input.resource.id
  input.release.bound_tenant == input.resource.tenant_id
  input.release.bound_model == input.runtime.model
  input.release.expires_at > input.clock.now
}

human_ok if {
  input.actor.type == "human"
  input.actor.role in {"owner", "authorized_operator"}
}

agent_ok if {
  input.actor.type == "agent"
  input.delegation.verified == true
  input.delegation.active == true
  input.delegation.grantee == input.identity.id
  input.delegation.tenant_id == input.resource.tenant_id
  input.delegation.resource_id == input.resource.id
  input.delegation.expires_at > input.clock.now
  input.operation in input.delegation.operations
}

allow if {
  base
  classification_ok
  human_ok
}

allow if {
  base
  classification_ok
  agent_ok
}
