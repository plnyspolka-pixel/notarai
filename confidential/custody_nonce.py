"""One-time recovery approval state owned by the independent custodian.

The supplied DynamoDB client MUST use credentials in an external custody
account. The operator's application account must not manage this table.
No secrets, case references, signatures or plaintext are recorded here.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_TOKEN = re.compile(r"^[a-f0-9]{32}$")


class RecoveryNonceDenied(ValueError):
    """Generic refusal without logging request identifiers or AWS details."""


class CustodyRecoveryNonceLedger:
    def __init__(self, custody_session, *, tenant: str, custody_account: str,
                 workload_account: str):
        if not isinstance(tenant, str) or not _TENANT.fullmatch(tenant):
            raise RecoveryNonceDenied("invalid custodian tenant")
        if not all(isinstance(v, str) and re.fullmatch(r"[0-9]{12}", v)
                   for v in (custody_account, workload_account)):
            raise RecoveryNonceDenied("invalid AWS account scope")
        if custody_account == workload_account:
            raise RecoveryNonceDenied("custody must be independently controlled")
        # STS and DynamoDB must be created from the SAME explicit AWS session.
        # Never accept two unrelated, caller-supplied cloud clients, since that
        # would allow a workload-owned DynamoDB table to masquerade as custody.
        try:
            principal = custody_session.client("sts").get_caller_identity()
            account = principal.get("Account")
            if account != custody_account:
                raise RecoveryNonceDenied("external custody identity mismatch")
            dynamodb = custody_session.client("dynamodb", region_name="eu-central-1")
        except RecoveryNonceDenied:
            raise
        except Exception:
            raise RecoveryNonceDenied("external custody identity unavailable") from None
        self._ddb = dynamodb
        self._tenant = tenant
        self._custody_account = custody_account
        self._table = "notarai-custody-recovery-" + tenant

    def claim_once(self, request_id: str) -> None:
        if not isinstance(request_id, str) or not _TOKEN.fullmatch(request_id):
            raise RecoveryNonceDenied("invalid approval request")
        # The custody session identity was verified before any DDB client
        # was obtained. Separate AWS root/Organizations governance and Nitro
        # key policy still need independent attestation and audit.
        try:
            self._ddb.put_item(
                TableName=self._table,
                Item={
                    "pk": {"S": "APPROVAL#" + request_id},
                    "state": {"S": "consumed"},
                    "claimed_at": {"S": datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )},
                },
                ConditionExpression="attribute_not_exists(pk)",
            )
        except Exception:
            raise RecoveryNonceDenied("approval already used or custody unavailable") from None
