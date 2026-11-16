"""Experimental AWS_IAM API Gateway ingress; never public directly.

All IDs used for authorization come from IAM-verified requestContext, not
untrusted JSON. On direct Lambda invoke the event could be forged: deployment
must restrict invocation to IAM-authenticated API Gateway.
"""
import base64
import binascii
import hashlib
import hmac
import json
import re
from .gateway import DocumentGateway, DocumentRequest
from .policy import Principal, Classification, PolicyDenied

VALID_ROLE = re.compile(r"^arn:aws:iam::([0-9]{12}):role/([A-Za-z0-9+=,.@_-]{1,64})$")
ALLOWED_FIELDS = {"request_id", "purpose", "prompt", "media_type", "document_base64"}
MAX_BODY = 9 * 1024 * 1024


def verified_caller(event, *, allowed_role, api_id, tenant_id):
    role = VALID_ROLE.fullmatch(allowed_role)
    if not role:
        raise PolicyDenied("Invalid trusted role config")
    if event.get("version") != "2.0" or event.get("routeKey") != "POST /v1/documents":
        raise PolicyDenied("Invalid event route")
    ctx = event.get("requestContext")
    if not isinstance(ctx, dict) or not api_id or ctx.get("apiId") != api_id:
        raise PolicyDenied("Wrong API Gateway")
    if (ctx.get("http") or {}).get("method") != "POST":
        raise PolicyDenied("Invalid method")
    arn = ((ctx.get("authorizer") or {}).get("iam") or {}).get("userArn")
    expected = "arn:aws:sts::" + role.group(1) + ":assumed-role/" + role.group(2) + "/"
    if not isinstance(arn, str) or not arn.startswith(expected):
        raise PolicyDenied("Untrusted caller")
    if not 1 <= len(arn[len(expected):]) <= 128:
        raise PolicyDenied("Invalid session")
    return Principal(arn, tenant_id, frozenset({"private_ai:invoke"}))


def parse_request(event):
    raw = event.get("body")
    if not isinstance(raw, str) or not 1 <= len(raw) <= MAX_BODY:
        raise PolicyDenied("Invalid request length")
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        except (ValueError, UnicodeError, binascii.Error) as exc:
            raise PolicyDenied("Malformed encoded request") from exc
    try:
        body = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise PolicyDenied("Malformed JSON") from exc
    if not isinstance(body, dict) or set(body) != ALLOWED_FIELDS:
        raise PolicyDenied("Unexpected fields")
    encoded = body["document_base64"]
    if not isinstance(encoded, str) or len(encoded) > MAX_BODY:
        raise PolicyDenied("Invalid document")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PolicyDenied("Invalid document encoding") from exc
    return body, content


def process_event(event, *, allowed_role, api_id, tenant_id, gateway, expected_fixture_sha256):
    identity = verified_caller(event, allowed_role=allowed_role, api_id=api_id, tenant_id=tenant_id)
    body, content = parse_request(event)
    # Exactly one SHA256-pinned synthetic image can reach the pilot model.
    # This is a containment gate, not a generic document classifier.
    if (not isinstance(expected_fixture_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_fixture_sha256)
            or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), expected_fixture_sha256)):
        raise PolicyDenied("Document is not the pinned synthetic pilot fixture")
    req = DocumentRequest(
        tenant_id=identity.tenant_id,
        request_id=body["request_id"],
        purpose=body["purpose"],
        classification=Classification.INTERNAL,  # Client cannot override.
        prompt=body["prompt"],
        media_type=body["media_type"],
        content=content,
    )
    result = gateway.process(identity, req)
    return {"request_id": result.request_id, "result": result.text,
            "input_tokens": result.input_tokens, "output_tokens": result.output_tokens}
