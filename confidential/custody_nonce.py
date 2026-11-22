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
    def __init__(self, dynamodb, *, tenant: str, custody_account: str):
        if not isinstance(tenant, str) or not _TENANT.fullmatch(tenant):
            raise RecoveryNonceDenied("invalid custodian tenant")
        if not isinstance(custody_account, str) or not re.fullmatch(
            r"[0-9]{12}", custody_account
        ):
            raise RecoveryNonceDenied("missing independent custody account")
        self._ddb = dynamodb
        self._tenant = tenant
        self._custody_account = custody_account
        self._table = "notarai-custody-recovery-" + tenant

    def claim_once(self, request_id: str) -> None:
        if not isinstance(request_id, str) or not _TOKEN.fullmatch(request_id):
            raise RecoveryNonceDenied("invalid approval request")
        # Callers MUST externally validate that the DDB client is an assumed
        # custodian principal, not the operator account. A string account ID
        # alone is not AWS identity proof.
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
