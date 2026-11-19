"""Deny-by-default Private AI policy inspired by OpenFGA/OPA research.

Principal MUST come from trusted middleware. Region and provider claims require
external AWS/infra validation: this Python code is not an attestation system.
"""
from dataclasses import dataclass
from enum import Enum
import re

EU_PROFILE = re.compile(r"^eu\.[a-z0-9][a-z0-9.-]{3,120}$")
ID = re.compile(r"^[a-zA-Z0-9_-]{3,64}$")
REQUEST_ID = re.compile(r"^[a-zA-Z0-9_-]{8,100}$")
ALLOWED_PURPOSES = frozenset({"document_extraction", "document_analysis"})


class PolicyDenied(PermissionError):
    pass


class Classification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class Backend(str, Enum):
    EU_BEDROCK = "eu_bedrock"
    DEDICATED_VLLM = "eu_dedicated_vllm"


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    scopes: frozenset[str]
    active: bool = True


@dataclass(frozen=True)
class Deployment:
    region: str
    model_id: str
    backend: Backend = Backend.EU_BEDROCK
    confidential_release_approved: bool = False


def enforce(principal: Principal, tenant_id: str, request_id: str,
            purpose: str, classification: Classification, dep: Deployment) -> None:
    if not isinstance(principal, Principal) or not principal.active:
        raise PolicyDenied("Inactive identity")
    if not isinstance(tenant_id, str) or not ID.fullmatch(tenant_id):
        raise PolicyDenied("Malformed tenant")
    if not isinstance(principal.tenant_id, str) or not ID.fullmatch(principal.tenant_id):
        raise PolicyDenied("Malformed identity")
    if principal.tenant_id != tenant_id or not principal.subject:
        raise PolicyDenied("Cross-tenant or anonymous")
    if "private_ai:invoke" not in principal.scopes:
        raise PolicyDenied("Missing capability")
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise PolicyDenied("Malformed correlation ID")
    if purpose not in ALLOWED_PURPOSES or not isinstance(classification, Classification):
        raise PolicyDenied("Unknown purpose or classification")
    if dep.backend != Backend.EU_BEDROCK:
        raise PolicyDenied("Dedicated/unrecognized backend not attested")
    if dep.region != "eu-central-1" or not EU_PROFILE.fullmatch(dep.model_id):
        raise PolicyDenied("Unsupported region or model profile")
    if classification is Classification.RESTRICTED:
        raise PolicyDenied("Restricted workloads require independently verified deployment")
    if classification is Classification.CONFIDENTIAL and not dep.confidential_release_approved:
        raise PolicyDenied("Confidential workloads not released")
