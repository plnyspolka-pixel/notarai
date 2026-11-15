package high_assurance.gateway

import rego.v1

test_valid_user_read if {
  allow with input as {
    "identity": {"authenticated": true, "active": true, "id": "u1", "tenant_id": "t1"},
    "resource": {"id": "case1", "tenant_id": "t1"},
    "openfga": {"allowed": true},
    "operation": "read",
    "is_agent": false
  }
}

test_wrong_tenant_denied if {
  not allow with input as {
    "identity": {"authenticated": true, "active": true, "id": "u1", "tenant_id": "t1"},
    "resource": {"id": "case1", "tenant_id": "t2"},
    "openfga": {"allowed": true},
    "operation": "read",
    "is_agent": false
  }
}

test_agent_without_scope_denied if {
  not allow with input as {
    "identity": {"authenticated": true, "active": true, "id": "u1", "tenant_id": "t1"},
    "resource": {"id": "case1", "tenant_id": "t1"},
    "openfga": {"allowed": true},
    "operation": "share_external",
    "is_agent": true,
    "task": {"verified": true, "active": true, "tenant_id": "t1", "delegated_from": "u1", "allowed_operations": ["read"]}
  }
}

test_sensitive_operation_requires_approval if {
  not allow with input as {
    "identity": {"authenticated": true, "active": true, "id": "u1", "tenant_id": "t1"},
    "resource": {"id": "case1", "tenant_id": "t1"},
    "openfga": {"allowed": true},
    "operation": "sign",
    "is_agent": false
  }
}
