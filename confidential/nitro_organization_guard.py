"""SEC-07 AWS Organizations structural separation: read-only independent check.

Different AWS account IDs are NOT evidence that different administrators
control them. Two accounts inside the same Organization fail this conservative
gate. Different Organizations are necessary evidence for this deployment's
independent-custody design, but are not sufficient proof of independent root,
legal or delegated administrative control.
"""
from __future__ import annotations

import hashlib
import re

_ACCOUNT = re.compile(r"[0-9]{12}\Z")
_ORG_ID = re.compile(r"o-[a-z0-9]{10,32}\Z")


class OrgBoundaryRejected(ValueError):
    """Only generic errors; do not print organizational AWS data."""


def _org_of(session) -> str | None:
    try:
        value = session.client("organizations").describe_organization()
    except Exception as exc:
        response = getattr(exc, "response", None)
        code = (
            (response.get("Error") or {}).get("Code")
            if isinstance(response, dict) else None
        )
        # AWS Organizations is optional for a stand-alone account. The known
        # service error is the only safe way to infer that state.
        if code == "AWSOrganizationsNotInUseException":
            return None
        raise OrgBoundaryRejected("AWS Organizations scope unavailable") from None
    org = value.get("Organization") if isinstance(value, dict) else None
    oid = org.get("Id") if isinstance(org, dict) else None
    if not isinstance(oid, str) or not _ORG_ID.fullmatch(oid):
        raise OrgBoundaryRejected("AWS Organizations identifier invalid")
    return oid


def audit_organization_separation(*, operator_profile: str,
                                  custody_profile: str,
                                  workload_account: str,
                                  custody_account: str,
                                  session_factory=None) -> dict:
    if (not operator_profile or not custody_profile or
            operator_profile == custody_profile or
            not isinstance(workload_account, str) or
            not isinstance(custody_account, str) or
            not _ACCOUNT.fullmatch(workload_account) or
            not _ACCOUNT.fullmatch(custody_account) or
            workload_account == custody_account):
        raise OrgBoundaryRejected("distinct AWS profiles/account scope required")
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    workload = session_factory(
        profile_name=operator_profile, region_name="eu-central-1",
    )
    custody = session_factory(
        profile_name=custody_profile, region_name="eu-central-1",
    )
    if (workload.client("sts").get_caller_identity().get("Account") !=
            workload_account or
            custody.client("sts").get_caller_identity().get("Account") !=
            custody_account):
        raise OrgBoundaryRejected("AWS account identity mismatch")
    op_org, custody_org = _org_of(workload), _org_of(custody)
    if op_org is not None and custody_org is not None and op_org == custody_org:
        raise OrgBoundaryRejected("both accounts share AWS Organizations control")
    # Hash identifiers to make cross-run matching possible without publishing
    # the actual AWS Organizations IDs in evidence metadata.
    fingerprint = lambda oid: (
        hashlib.sha256(oid.encode("ascii")).hexdigest() if oid else None
    )
    return {
        "status": "PARTIAL_READ_ONLY",
        "workload_org_sha256": fingerprint(op_org),
        "custody_org_sha256": fingerprint(custody_org),
        "workload_is_standalone": op_org is None,
        "custody_is_standalone": custody_org is None,
        "shared_aws_organization_detected": False,
        "distinct_organizations_observed": True,
        "administrative_independence_proven": False,
        "zero_operator_access_proven": False,
        "hardware_attestation_verified": False,
        "production_enabled": False,
    }
