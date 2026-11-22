"""Fail-closed tenant bindings for the synthetic shared Nitro preview pilot.

This is a control-plane configuration gate, NOT a substitute for AWS IAM
authorization, Nitro attestation, or actual cross-account denial probes.
The tenant passed to a TenantBoundary must originate from authenticated
server-side context, never HTTP input, SQS payload or ECS overrides.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_REGION = "eu-central-1"
_TENANT = re.compile(r"[a-z0-9]{1,12}\Z")
_ACCOUNT = re.compile(r"[0-9]{12}\Z")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{2,62}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_KMS = re.compile(r"arn:aws:kms:eu-central-1:[0-9]{12}:key/[A-Za-z0-9-]+\Z")


class TenantIsolationRejected(ValueError):
    """Generic denial: no client identifiers, secrets or raw events in errors."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise TenantIsolationRejected(reason)


def validate_worker_binding(*, tenant: str, bucket: str, queue_url: str,
                            kms_key_arn: str) -> None:
    """Pin guest configuration before it makes its first AWS request.

    The account is derived from the *configured* queue, not an incoming
    message. A key in a separately governed custody account is permitted.
    """
    _require(isinstance(tenant, str) and bool(_TENANT.fullmatch(tenant)),
             "invalid server tenant")
    _require(isinstance(bucket, str) and bool(_BUCKET.fullmatch(bucket)) and
             ".." not in bucket and not bucket.startswith("xn--"),
             "invalid ciphertext bucket")
    _require(isinstance(queue_url, str) and bool(re.fullmatch(
        rf"https://sqs\.eu-central-1\.amazonaws\.com/[0-9]{{12}}/"
        rf"notarai-confidential-{tenant}\.fifo", queue_url
    )), "queue is not pinned to server tenant")
    _require(isinstance(kms_key_arn, str) and bool(_KMS.fullmatch(kms_key_arn)),
             "invalid regional KMS key")


@dataclass(frozen=True)
class TenantBoundary:
    """Metadata-only manifest; must be built from trusted, verified AWS state."""

    tenant: str
    account: str
    session_tenant: str
    cluster: str
    capacity_provider: str
    task_definition_arn: str
    task_role_arn: str
    execution_role_arn: str
    image_digest: str
    kms_key_arn: str
    bucket: str
    queue_url: str
    jobs_table: str
    dispatch_table: str
    s3_namespace: str

    def validate(self) -> None:
        _require(isinstance(self.account, str) and bool(_ACCOUNT.fullmatch(self.account)),
                 "invalid AWS account")
        validate_worker_binding(
            tenant=self.tenant, bucket=self.bucket,
            queue_url=self.queue_url, kms_key_arn=self.kms_key_arn,
        )
        _require(self.session_tenant == self.tenant,
                 "API session is not server tenant")
        _require(
            self.cluster == "notarai-confidential-shared" and
            self.capacity_provider == self.cluster,
            "not a pinned shared Nitro pool",
        )
        family = "notarai-confidential-" + self.tenant
        task_prefix = f"arn:aws:ecs:{_REGION}:{self.account}:task-definition/{family}:"
        _require(
            isinstance(self.task_definition_arn, str) and
            self.task_definition_arn.startswith(task_prefix) and
            self.task_definition_arn[len(task_prefix):].isdigit(),
            "wrong tenant task definition",
        )
        _require(self.task_role_arn ==
                 f"arn:aws:iam::{self.account}:role/{family}",
                 "wrong guest task role")
        _require(self.execution_role_arn ==
                 f"arn:aws:iam::{self.account}:role/notarai-confidential-execution-{self.tenant}",
                 "wrong guest execution role")
        _require(isinstance(self.image_digest, str) and
                 bool(_DIGEST.fullmatch(self.image_digest)),
                 "image is not pinned by sha256")
        _require(self.queue_url ==
                 f"https://sqs.{_REGION}.amazonaws.com/{self.account}/{family}.fifo",
                 "queue belongs to another account")
        _require(self.jobs_table == f"notarai-confidential-jobs-{self.tenant}" and
                 self.dispatch_table == f"notarai-confidential-dispatch-{self.tenant}",
                 "ledger belongs to another tenant")
        _require(self.s3_namespace == f"kancelarie/{self.tenant}/confidential/",
                 "S3 namespace belongs to another tenant")


def validate_pair(left: TenantBoundary, right: TenantBoundary) -> None:
    """Fail closed on accidental shared identity, role, key or queue.

    A shared ciphertext bucket is allowed ONLY with distinct tenant prefixes
    and independently enforced IAM resource policies.
    """
    left.validate()
    right.validate()
    _require(left.tenant != right.tenant, "pilot identities overlap")
    _require(left.account == right.account and left.cluster == right.cluster and
             left.capacity_provider == right.capacity_provider,
             "pilots are not in one audited AWS runtime")
    _require(left.image_digest == right.image_digest,
             "pilots do not run the same approved image digest")
    for attr in ("task_definition_arn", "task_role_arn", "execution_role_arn",
                 "kms_key_arn", "queue_url", "jobs_table", "dispatch_table",
                 "s3_namespace"):
        _require(getattr(left, attr) != getattr(right, attr),
                 "cross-tenant resource overlap: " + attr)
