"""SEC-10 offline KMS policy risk screen; NEVER a proof of effective denial.

Input is a separately obtained, validated JSON key-policy document. The
output is metadata only. Does not call AWS, decrypt, change keys or return
principal identifiers. IAM, SCPs, grant state, access analyzer and independent
custody MUST be reviewed live before making any zero-operator-access claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
import re


_PCR = re.compile(r"^[0-9a-fA-F]{96}$")
_ROLE = re.compile(
    r"^arn:aws:iam::[0-9]{12}:role/notarai-confidential-[a-z0-9]{1,12}$"
)
_SENSITIVE_ACTIONS = (
    "kms:PutKeyPolicy", "kms:CreateGrant", "kms:DisableKey",
    "kms:ScheduleKeyDeletion", "kms:ReplicateKey",
)


class KmsPolicyNotAuditable(ValueError):
    """Do not include policy contents, principals or identifiers in errors."""


@dataclass(frozen=True)
class KmsPolicyScreen:
    # Describes only a syntactic risk screen, NEVER full IAM evaluation.
    status: str
    attestation_gated_decrypt_statement_count: int
    unscoped_decrypt_allow_count: int
    policy_mutation_allow_count: int
    unfamiliar_allow_statement_count: int
    findings: tuple[str, ...]
    zero_operator_access_verified: bool = False


def _actions(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if (type(value) is list and bool(value)
            and all(isinstance(x, str) and x for x in value)):
        return tuple(value)
    raise KmsPolicyNotAuditable("KMS policy cannot be screened")


def _matches(actions: tuple[str, ...], target: str) -> bool:
    return any(fnmatchcase(target.lower(), action.lower()) for action in actions)


def _role_pinned(stmt: dict, expected_role: str) -> bool:
    principal = stmt.get("Principal")
    if isinstance(principal, dict) and principal.get("AWS") == expected_role:
        return True
    condition = stmt.get("Condition")
    if not isinstance(condition, dict):
        return False
    arn = condition.get("ArnEquals")
    return (isinstance(arn, dict)
            and arn.get("aws:PrincipalArn") == expected_role)


def _attestation_pinned(stmt: dict, *, pcr17: str, role: str) -> bool:
    if not _role_pinned(stmt, role):
        return False
    conditions = stmt.get("Condition")
    if not isinstance(conditions, dict):
        return False
    # Accept only a non-set, exact-match operator; refuse ForAnyValue,
    # StringLike, IfExists and ambiguous multi-value PCR conditions.
    for operator in ("StringEqualsIgnoreCase", "StringEquals"):
        check = conditions.get(operator)
        if not isinstance(check, dict):
            continue
        pcr = check.get("kms:RecipientAttestation:PCR17")
        service = check.get("kms:RecipientAttestation:PCR8:ServiceName")
        if (type(pcr) is str and pcr.lower() == pcr17.lower()
                and type(service) is str
                and service.lower() == "ecs.amazonaws.com"):
            return True
    return False


def screen_kms_policy(
    policy: dict, *, expected_pcr17: str, expected_role_arn: str,
) -> KmsPolicyScreen:
    """Classify explicit Allow statements, fail closed for unknown shapes.

    We do NOT claim full IAM/key-policy evaluation, do not account for every
    identity policy or SCP, and cannot verify operator access or policy
    immutability. This report must remain BLOCKED even for a clean screen.
    """
    if (type(policy) is not dict
            or type(expected_pcr17) is not str
            or not _PCR.fullmatch(expected_pcr17)
            or type(expected_role_arn) is not str
            or not _ROLE.fullmatch(expected_role_arn)):
        raise KmsPolicyNotAuditable("KMS policy cannot be screened")
    statement = policy.get("Statement")
    if type(statement) is dict:
        statement = [statement]
    if type(statement) is not list or not statement:
        raise KmsPolicyNotAuditable("KMS policy cannot be screened")
    gated = 0
    unscoped = 0
    admin = 0
    unfamiliar = 0
    for st in statement:
        if type(st) is not dict or st.get("Effect") not in ("Allow", "Deny"):
            raise KmsPolicyNotAuditable("KMS policy cannot be screened")
        if st["Effect"] == "Deny":
            continue
        # NotAction and NotPrincipal are hard to classify safely. An Allow
        # with either is conservatively treated as a potential decrypt path.
        if "NotAction" in st or "NotPrincipal" in st or "NotResource" in st:
            unfamiliar += 1
            unscoped += 1
            admin += 1
            continue
        actions = _actions(st.get("Action"))
        if "Principal" not in st:
            raise KmsPolicyNotAuditable("KMS policy cannot be screened")
        if _matches(actions, "kms:Decrypt"):
            if _attestation_pinned(
                st, pcr17=expected_pcr17, role=expected_role_arn
            ):
                gated += 1
            else:
                unscoped += 1
        if any(_matches(actions, action) for action in _SENSITIVE_ACTIONS):
            admin += 1
    findings: list[str] = []
    if not gated:
        findings.append("ATTESTATION_GATED_KMS_DECRYPT_MISSING")
    if unscoped:
        findings.append("KMS_DECRYPT_ALLOW_OUTSIDE_ATTESTED_ROLE")
    if admin:
        findings.append("KMS_POLICY_OR_KEY_ADMIN_MUTATION_PATH")
    if unfamiliar:
        findings.append("KMS_UNSCOPED_POLICY_CONSTRUCT")
    findings.extend((
        "EFFECTIVE_IAM_SCP_GRANTS_UNVERIFIED",
        "INDEPENDENT_KMS_CUSTODY_UNVERIFIED",
        "KMS_POLICY_CHANGE_CONTROL_UNVERIFIED",
    ))
    return KmsPolicyScreen(
        status="BLOCKED_PENDING_INDEPENDENT_KMS_REVIEW",
        attestation_gated_decrypt_statement_count=gated,
        unscoped_decrypt_allow_count=unscoped,
        policy_mutation_allow_count=admin,
        unfamiliar_allow_statement_count=unfamiliar,
        findings=tuple(findings),
    )
