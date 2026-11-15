package high_assurance.gateway

import rego.v1

default allow := false

# All input values below MUST come from server-verified sources,
# not from an LLM's tool arguments or user-provided JSON.
base_checks if {
  input.identity.authenticated == true
  input.identity.active == true
  input.resource.tenant_id == input.identity.tenant_id
  input.openfga.allowed == true
}

sensitive_op if {
  input.operation in {"sign", "release_funds", "share_external", "delete_record"}
}

approval_ok if {
  not sensitive_op
}
approval_ok if {
  sensitive_op
  input.approval.human_verified == true
  input.approval.bound_operation == input.operation
  input.approval.bound_resource == input.resource.id
}

allow if {
  base_checks
  input.is_agent == false
  approval_ok
}

allow if {
  base_checks
  input.is_agent == true
  input.task.verified == true
  input.task.active == true
  input.task.tenant_id == input.resource.tenant_id
  input.task.delegated_from == input.identity.id
  input.operation in input.task.allowed_operations
  approval_ok
}
