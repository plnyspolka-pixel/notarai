"""Live canary for separately approved EU staging API, synthetic inputs ONLY.

Read-only caller permissions; POST only to explicitly validated regional
execute-api endpoint. Does not deploy, create IAM credentials or print model
answers. Use a short-lived AWS role with execute-api:Invoke for this route.
"""
from __future__ import annotations
import argparse
import base64
import json
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from private_ai.ingress import PILOT_PROMPT
from private_ai.synthetic import png_fixture

URL_RE = re.compile(r"^https://[a-z0-9]+\.execute-api\.eu-central-1\.amazonaws\.com/v1/documents$")


def synthetic_request() -> dict:
    return {
        "request_id": "request_syn0001",
        "purpose": "document_analysis",
        "prompt": PILOT_PROMPT,
        "media_type": "image/png",
        "document_base64": base64.b64encode(png_fixture()).decode("ascii"),
    }


def sigv4_headers(url: str, data: bytes, session) -> dict:
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("No short-lived AWS credentials")
    request = AWSRequest(
        method="POST", url=url,
        data=data,
        headers={"content-type": "application/json"},
    )
    SigV4Auth(credentials.get_frozen_credentials(), "execute-api", "eu-central-1").add_auth(request)
    return dict(request.headers.items())


def post_status(url: str, payload: dict, session, signed=True) -> tuple[int, dict]:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = sigv4_headers(url, encoded, session) if signed else {"content-type": "application/json"}
    try:
        with urlopen(Request(url, data=encoded, headers=headers, method="POST"), timeout=31) as res:
            response = res.read(256 * 1024)
            return res.status, json.loads(response)
    except HTTPError as error:
        # Do not expose server error bodies or log content.
        error.close()
        return error.code, {}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", required=True)
    p.add_argument("--expected-account", required=True)
    p.add_argument("--profile", help="Optional AWS credentials profile")
    args = p.parse_args()
    if not URL_RE.fullmatch(args.api_url):
        raise SystemExit("Only eu-central-1 execute-api pilot URL allowed")
    if not re.fullmatch(r"[0-9]{12}", args.expected_account):
        raise SystemExit("Expected AWS account must be 12 digits")
    import boto3
    session = boto3.Session(profile_name=args.profile, region_name="eu-central-1")
    if session.client("sts").get_caller_identity().get("Account") != args.expected_account:
        raise SystemExit("Wrong account; refusing network operation")
    fixture = synthetic_request()
    results = {}
    status, response = post_status(args.api_url, fixture, session)
    results["authorized_synthetic"] = status
    if status != 200 or response.get("request_id") != fixture["request_id"]:
        raise SystemExit("Synthetic test failed; see AWS audit metadata (no output disclosed)")
    bad_file = dict(fixture)
    bad_file["document_base64"] = base64.b64encode(b"invalid-attachment").decode()
    results["unknown_attachment_denied"] = post_status(args.api_url, bad_file, session)[0]
    bad_prompt = dict(fixture)
    bad_prompt["prompt"] = PILOT_PROMPT + " REAL CUSTOMER SECRET MUST NOT LEAVE"
    results["unapproved_prompt_denied"] = post_status(args.api_url, bad_prompt, session)[0]
    bad_tenant = dict(fixture)
    bad_tenant["tenant_id"] = "tenant_other"
    results["tenant_claim_denied"] = post_status(args.api_url, bad_tenant, session)[0]
    results["unsigned_request_denied"] = post_status(args.api_url, fixture, session, signed=False)[0]
    # Intentionally don't print model text, documents, API credentials or signed request headers.
    print(json.dumps(results, sort_keys=True))
    if any(v != 403 for k, v in results.items() if k != "authorized_synthetic"):
        raise SystemExit("Security canary FAILED; do not release or use customer data")
    print("Synthetic-only API authorization canary PASSED. No production assurance implied.")


if __name__ == "__main__":
    main()
