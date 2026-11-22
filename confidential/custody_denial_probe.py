"""SEC-11 optional live AWS *negative* permission probes.

Never used by CI. This can call PutObject and DeleteObjectVersion ONLY after
explicit independent authorization, on synthetic evidence fixtures. It does
not deploy, delete infrastructure, inspect customer objects or output IDs.
"""
from __future__ import annotations

import re

ACCOUNT = re.compile(r"^[0-9]{12}$")
BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{2,62}$")
SYNTHETIC_KEY = re.compile(r"^sec11-fixture/[a-z0-9-]{8,64}$")
VERSION = re.compile(r"^[A-Za-z0-9._~+/=-]{1,1024}$")
DENY_CODES = frozenset({"AccessDenied", "AccessDeniedException"})


class ProbeDenied(ValueError):
    """Fixed messages prevent accidental disclosure of AWS exception details."""


def _denied(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    return (isinstance(response, dict) and
            isinstance(response.get("Error"), dict) and
            response["Error"].get("Code") in DENY_CODES)


def probe_operator_denials(*, session, operator_account: str,
                           custody_account: str, bucket: str,
                           fixture_key: str, fixture_version: str,
                           authorized: bool = False) -> dict:
    """Safely exercise two exact API denials with an operator principal.

    Existing fixture version must have been created by custodian in
    compliance-locked independent bucket. A successful request is a FAIL,
    not an occasion for automatic cleanup.
    """
    if authorized is not True:
        raise ProbeDenied("synthetic permission probe not authorized")
    if not all(isinstance(v, str) and ACCOUNT.fullmatch(v) for v in
               (operator_account, custody_account)):
        raise ProbeDenied("invalid AWS accounts")
    if operator_account == custody_account:
        raise ProbeDenied("custody account not independent")
    if not isinstance(bucket, str) or not BUCKET.fullmatch(bucket):
        raise ProbeDenied("invalid synthetic bucket")
    if not isinstance(fixture_key, str) or not SYNTHETIC_KEY.fullmatch(fixture_key):
        raise ProbeDenied("test key is outside synthetic namespace")
    if not isinstance(fixture_version, str) or not VERSION.fullmatch(
        fixture_version
    ) or fixture_version == "null":
        raise ProbeDenied("existing synthetic version required")
    try:
        caller = session.client("sts").get_caller_identity()
    except Exception:
        raise ProbeDenied("cannot verify operator identity") from None
    if caller.get("Account") != operator_account:
        raise ProbeDenied("operator account identity mismatch")
    s3 = session.client("s3", region_name="eu-central-1")
    results = {}
    probes = (
        ("operator_overwrite_deny", "put_object", {
            "Bucket": bucket, "ExpectedBucketOwner": custody_account,
            "Key": fixture_key, "Body": b"NOTARAI_SEC11_SYNTHETIC_ONLY",
        }),
        ("operator_delete_deny", "delete_object", {
            "Bucket": bucket, "ExpectedBucketOwner": custody_account,
            "Key": fixture_key, "VersionId": fixture_version,
        }),
    )
    for name, method, kwargs in probes:
        try:
            getattr(s3, method)(**kwargs)
        except Exception as exc:
            results[name] = "PASS" if _denied(exc) else "BLOCKED"
        else:
            results[name] = "FAIL"
    return {
        "results": results,
        "permission_denials_verified": all(
            v == "PASS" for v in results.values()
        ),
        "zero_operator_access_proven": False,
    }
