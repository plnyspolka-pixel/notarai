"""Fail-closed local verification of genuine AWS Nitro NSM attestation documents.

Derived from the public Nitro attestation format and the AWS MIT-0 sample:
https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp
The published AWS root is pinned in this signed, independently distributed client.

Not a remote API. It must run on a customer-controlled host and MUST NOT
download PCR policies or signing roots from an operator-controlled endpoint.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

import cbor2
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa, utils
from cryptography.x509.oid import ExtensionOID

AWS_NITRO_ROOT_PEM = b"""-----BEGIN CERTIFICATE-----
MIICETCCAZagAwIBAgIRAPkxdWgbkK/hHUbMtOTn+FYwCgYIKoZIzj0EAwMwSTEL
MAkGA1UEBhMCVVMxDzANBgNVBAoMBkFtYXpvbjEMMAoGA1UECwwDQVdTMRswGQYD
VQQDDBJhd3Mubml0cm8tZW5jbGF2ZXMwHhcNMTkxMDI4MTMyODA1WhcNNDkxMDI4
MTQyODA1WjBJMQswCQYDVQQGEwJVUzEPMA0GA1UECgwGQW1hem9uMQwwCgYDVQQL
DANBV1MxGzAZBgNVBAMMEmF3cy5uaXRyby1lbmNsYXZlczB2MBAGByqGSM49AgEG
BSuBBAAiA2IABPwCVOumCMHzaHDimtqQvkY4MpJzbolL//Zy2YlES1BR5TSksfbb
48C8WBoyt7F2Bw7eEtaaP+ohG2bnUs990d0JX28TcPQXCEPZ3BABIeTPYwEoCWZE
h8l5YoQwTcU/9KNCMEAwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUkCW1DdkF
R+eWw5b6cp3PmanfS5YwDgYDVR0PAQH/BAQDAgGGMAoGCCqGSM49BAMDA2kAMGYC
MQCjfy+Rocm9Xue4YnwWmNJVA44fA0P5W2OpYow9OYCVRaEevL8uO1XYru5xtMPW
rfMCMQCi85sWBbJwKKXdS6BptQFuZbT73o/gBh1qUxl/nNr12UO8Yfwr6wPLb+6N
IwLz3/Y=
-----END CERTIFICATE-----"""
_MAX_DOCUMENT_BYTES = 32768
_MAX_AGE_SECONDS = 180
_MIN_NONCE_BYTES = 32


class NitroAttestationDenied(ValueError):
    """Non-sensitive error; never interpolate untrusted attestation fields."""


@dataclass(frozen=True)
class VerifiedNitroRecipient:
    """A validated *RSA* public key bound to an authentic, fresh AWS NSM report."""

    public_key_pem: bytes
    attestation_sha256: str
    timestamp_ms: int
    pcrs: tuple[tuple[int, str], ...]


def _deny() -> None:
    raise NitroAttestationDenied("Nitro attestation denied")


def _decode_exact(blob: bytes):
    stream = io.BytesIO(blob)
    value = cbor2.CBORDecoder(stream).decode()
    if stream.read(1):
        _deny()
    return value


def _valid_at(cert: x509.Certificate, now: datetime) -> bool:
    return cert.not_valid_before_utc <= now <= cert.not_valid_after_utc


def _verify_chain(certificate: bytes, bundle: object, *, now: datetime,
                  pinned_root_der: bytes) -> x509.Certificate:
    if not isinstance(bundle, list) or not 1 <= len(bundle) <= 6:
        _deny()
    if any(type(value) is not bytes or len(value) > 8192 for value in bundle):
        _deny()
    if type(certificate) is not bytes or len(certificate) > 8192:
        _deny()
    root = x509.load_der_x509_certificate(pinned_root_der)
    parsed = [x509.load_der_x509_certificate(item) for item in bundle]
    # The attestation cabundle is usually root -> intermediates, but support
    # the reversed representation without trusting a substituted root.
    if parsed[0].public_bytes(serialization.Encoding.DER) == pinned_root_der:
        chain = parsed
    elif parsed[-1].public_bytes(serialization.Encoding.DER) == pinned_root_der:
        chain = list(reversed(parsed))
    else:
        _deny()
    leaf = x509.load_der_x509_certificate(certificate)
    chain.append(leaf)
    if any(not _valid_at(item, now) for item in chain):
        _deny()
    if not isinstance(root.public_key(), ec.EllipticCurvePublicKey):
        _deny()
    # Validate the pinned root against its own signature as defense in depth.
    root.public_key().verify(root.signature, root.tbs_certificate_bytes,
                             ec.ECDSA(root.signature_hash_algorithm))
    for i in range(1, len(chain)):
        child, issuer = chain[i], chain[i - 1]
        if child.issuer != issuer.subject:
            _deny()
        if not isinstance(issuer.public_key(), ec.EllipticCurvePublicKey):
            _deny()
        bc = issuer.extensions.get_extension_for_oid(
            ExtensionOID.BASIC_CONSTRAINTS).value
        if not bc.ca:
            _deny()
        issuer.public_key().verify(child.signature, child.tbs_certificate_bytes,
                                   ec.ECDSA(child.signature_hash_algorithm))
    # The leaf must be a signing certificate, not an intermediate CA.
    try:
        if leaf.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value.ca:
            _deny()
    except x509.ExtensionNotFound:
        pass
    return leaf


def _pcrs(value: object, pinned: Mapping[int, str]) -> tuple[tuple[int, str], ...]:
    if type(value) is not dict or type(pinned) is not dict:
        _deny()
    if any(type(k) is not int or type(v) is not bytes or len(v) != 48
           for k, v in value.items()):
        _deny()
    # ECS Nitro Sandbox PCR17 + PCR8 must BOTH be pinned by a customer-
    # authenticated manifest. Missing/empty pins never fall back to trust.
    if 8 not in pinned or 17 not in pinned or len(pinned) < 2:
        _deny()
    for index, expected in pinned.items():
        if (type(index) is not int or not 0 <= index <= 31
                or type(expected) is not str or len(expected) != 96
                or any(ch not in "0123456789abcdef" for ch in expected)
                or index not in value or value[index].hex() != expected):
            _deny()
    if not all(k in value for k in (0, 1, 2)):
        _deny()
    if all(value[index] == bytes(48) for index in (0, 1, 2)):
        _deny()  # Debug enclave is NEVER a release recipient.
    return tuple(sorted((i, raw.hex()) for i, raw in value.items()))


def _verify_with_pinned_root(
    document: bytes, *, expected_nonce: bytes,
    expected_user_data: bytes, expected_pcrs: Mapping[int, str],
    now: datetime, pinned_root_der: bytes,
) -> VerifiedNitroRecipient:
    """Internal test seam: production callers cannot replace the AWS root."""
    try:
        if (type(document) is not bytes
                or not 1 <= len(document) <= _MAX_DOCUMENT_BYTES
                or type(expected_nonce) is not bytes
                or not _MIN_NONCE_BYTES <= len(expected_nonce) <= 512
                or type(expected_user_data) is not bytes
                or len(expected_user_data) != 32
                or now.tzinfo is None or now.utcoffset() is None):
            _deny()
        envelope = _decode_exact(document)
        if isinstance(envelope, cbor2.CBORTag):
            if envelope.tag != 18:
                _deny()
            envelope = envelope.value
        if not isinstance(envelope, list) or len(envelope) != 4:
            _deny()
        protected, unprotected, payload, signature = envelope
        if (type(protected) is not bytes or type(unprotected) is not dict
                or type(payload) is not bytes or type(signature) is not bytes
                or len(signature) != 96 or 1 in unprotected):
            _deny()
        headers = _decode_exact(protected)
        if type(headers) is not dict or headers.get(1) != -35:
            _deny()  # Nitro's COSE ES384 ONLY.
        body = _decode_exact(payload)
        if (type(body) is not dict or body.get("digest") != "SHA384"
                or type(body.get("nonce")) is not bytes
                or not hmac.compare_digest(body["nonce"], expected_nonce)
                or type(body.get("user_data")) is not bytes
                or not hmac.compare_digest(body["user_data"], expected_user_data)):
            _deny()
        stamp = body.get("timestamp")
        if type(stamp) is not int or stamp <= 0:
            _deny()
        observed_at = datetime.fromtimestamp(stamp / 1000, tz=timezone.utc)
        if abs((now - observed_at).total_seconds()) > _MAX_AGE_SECONDS:
            _deny()
        measurements = _pcrs(body.get("pcrs"), expected_pcrs)
        leaf = _verify_chain(body.get("certificate"), body.get("cabundle"),
                             now=now, pinned_root_der=pinned_root_der)
        if not isinstance(leaf.public_key(), ec.EllipticCurvePublicKey):
            _deny()
        signed = cbor2.dumps(["Signature1", protected, b"", payload])
        r = int.from_bytes(signature[:48], "big")
        s = int.from_bytes(signature[48:], "big")
        leaf.public_key().verify(utils.encode_dss_signature(r, s),
                                 signed, ec.ECDSA(hashes.SHA384()))
        public_key_der = body.get("public_key")
        if type(public_key_der) is not bytes or len(public_key_der) > 2048:
            _deny()
        recipient = serialization.load_der_public_key(public_key_der)
        if (not isinstance(recipient, rsa.RSAPublicKey)
                or recipient.key_size != 3072
                or recipient.public_numbers().e != 65537):
            _deny()
        pem = recipient.public_bytes(serialization.Encoding.PEM,
                                     serialization.PublicFormat.SubjectPublicKeyInfo)
        return VerifiedNitroRecipient(
            public_key_pem=pem,
            attestation_sha256=hashlib.sha256(document).hexdigest(),
            timestamp_ms=stamp, pcrs=measurements,
        )
    except NitroAttestationDenied:
        raise
    except Exception:
        # No detailed certificate, key, nonce or customer data in logs.
        _deny()


def verify_aws_nitro_attestation(
    document: bytes, *, expected_nonce: bytes,
    expected_user_data: bytes, expected_pcrs: Mapping[int, str],
    now: datetime | None = None,
) -> VerifiedNitroRecipient:
    """Only accepts genuine AWS-rooted, measured, fresh RSA-3072 recipients."""
    instant = now or datetime.now(timezone.utc)
    root = x509.load_pem_x509_certificate(AWS_NITRO_ROOT_PEM)
    return _verify_with_pinned_root(
        document, expected_nonce=expected_nonce, expected_user_data=expected_user_data,
        expected_pcrs=expected_pcrs, now=instant,
        pinned_root_der=root.public_bytes(serialization.Encoding.DER),
    )
