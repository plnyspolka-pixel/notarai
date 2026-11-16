package private_ai.guard_test

import rego.v1
import data.private_ai.guard.allow

valid := {
  "identity": {"authenticated": true, "active": true, "id": "user-1", "tenant_id": "tenant-1"},
  "resource": {"id": "doc-1", "tenant_id": "tenant-1", "classification": "internal"},
  "actor": {"type": "human", "role": "owner"},
  "relation": {"allowed": true},
  "operation": "invoke",
  "purpose": "document_analysis",
  "runtime": {"checked": true, "region": "eu-central-1",
              "model": "eu.anthropic.claude-opus-4-6-v1", "egress_verified": true},
  "audit": {"available": true},
  "clock": {"now": 1000}
}

test_owner_authorized if {
  allow with input as valid
}

test_cross_tenant_denied if {
  not allow with input as object.union(valid, {
    "resource": {"id": "doc-1", "tenant_id": "tenant-2", "classification": "internal"}
  })
}

test_no_runtime_attestation_denied if {
  not allow with input as object.union(valid, {
    "runtime": object.union(valid.runtime, {"checked": false})
  })
}

test_provider_egress_unverified_denied if {
  not allow with input as object.union(valid, {
    "runtime": object.union(valid.runtime, {"egress_verified": false})
  })
}

test_external_model_denied if {
  not allow with input as object.union(valid, {
    "runtime": object.union(valid.runtime, {"model": "anthropic.claude-opus"})
  })
}

test_restricted_denied if {
  not allow with input as object.union(valid, {
    "resource": object.union(valid.resource, {"classification": "restricted"})
  })
}

test_confidential_denied_without_release if {
  not allow with input as object.union(valid, {
    "resource": object.union(valid.resource, {"classification": "confidential"})
  })
}

test_confidential_time_bound_release if {
  request := object.union(valid, {
    "resource": object.union(valid.resource, {"classification": "confidential"}),
    "release": {"verified": true, "bound_resource": "doc-1", "bound_tenant": "tenant-1",
                "bound_model": "eu.anthropic.claude-opus-4-6-v1", "expires_at": 1001}
  })
  allow with input as request
}

test_confidential_expired_release_denied if {
  request := object.union(valid, {
    "resource": object.union(valid.resource, {"classification": "confidential"}),
    "release": {"verified": true, "bound_resource": "doc-1", "bound_tenant": "tenant-1",
                "bound_model": "eu.anthropic.claude-opus-4-6-v1", "expires_at": 999}
  })
  not allow with input as request
}

test_agent_without_delegation_denied if {
  not allow with input as object.union(valid, {"actor": {"type": "agent"}})
}

test_delegated_agent_allowed if {
  request := object.union(valid, {
    "actor": {"type": "agent"},
    "delegation": {"verified": true, "active": true, "grantee": "user-1",
      "tenant_id": "tenant-1", "resource_id": "doc-1", "expires_at": 1001,
      "operations": ["invoke"]}
  })
  allow with input as request
}

test_delegated_agent_expired_denied if {
  request := object.union(valid, {
    "actor": {"type": "agent"},
    "delegation": {"verified": true, "active": true, "grantee": "user-1",
      "tenant_id": "tenant-1", "resource_id": "doc-1", "expires_at": 999,
      "operations": ["invoke"]}
  })
  not allow with input as request
}

test_policy_service_missing_input_denied if {
  not allow with input as {"identity": {"authenticated": true}}
}
