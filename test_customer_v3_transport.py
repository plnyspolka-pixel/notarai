"""Synthetic S3/SQS/DDB integration for customer-owned v3 transport.

No AWS resources, no real documents, no client private key on server.
"""
import base64
import copy
import io
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from confidential.customer_origin import sign_customer_origin
from confidential.customer_release import seal_document
from confidential.customer_v3_transport import CustomerCiphertextTransport, CustomerTransportDenied


class FailedCondition(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class FakeDdb:
    def __init__(self):
        self.rows = {}

    def put_item(self, **k):
        key = k["Item"]["pk"]["S"]
        if key in self.rows:
            raise FailedCondition()
        assert k["ConditionExpression"] == "attribute_not_exists(pk)"
        self.rows[key] = copy.deepcopy(k["Item"])

    def get_item(self, **k):
        key = k["Key"]["pk"]["S"]
        return {"Item": copy.deepcopy(self.rows[key])} if key in self.rows else {}

    def update_item(self, **k):
        key = k["Key"]["pk"]["S"]
        row = self.rows.get(key)
        if row is None:
            raise FailedCondition()
        values = k["ExpressionAttributeValues"]
        cmd = k["UpdateExpression"]
        if "#state = :stored" in cmd:
            if (row["state"]["S"] != "reserved"
                    or row["document_version"] != values[":logical"]
                    or row["sha256"] != values[":digest"]
                    or "s3_version" in row):
                raise FailedCondition()
            row["state"] = values[":stored"]
            row["s3_version"] = values[":version"]
            return {}
        if "#state = :queued" in cmd:
            if (row["state"]["S"] != "stored"
                    or row["s3_version"] != values[":version"]
                    or row["document_version"] != values[":logical"]
                    or row["sha256"] != values[":digest"]
                    or row["key_pin"] != values[":pin"]
                    or row["submitted"]["BOOL"] is not False):
                raise FailedCondition()
            row["state"] = values[":queued"]
            return {}
        if ":uncertain" in values:
            if row["state"]["S"] != "queued":
                raise FailedCondition()
            row["state"] = values[":uncertain"]
            return {}
        raise AssertionError("unmocked DynamoDB state transition")


class FakeS3:
    def __init__(self):
        self.items = {}
        self.overwrite_first = False

    def put_object(self, **k):
        assert k["ServerSideEncryption"] == "AES256"
        assert k["IfNoneMatch"] == "*"
        key = k["Key"]
        if key in self.items:
            raise FailedCondition()
        self.items[key] = {"version": "v000001", "bytes": k["Body"]}
        return {"VersionId": "v000001"}

    def get_object(self, **k):
        row = self.items[k["Key"]]
        if row["version"] != k.get("VersionId"):
            raise FailedCondition()
        return {"Body": io.BytesIO(row["bytes"])}


class FakeSqs:
    def __init__(self):
        self.messages = []
        self.fail = False

    def send_message(self, **k):
        if self.fail:
            raise RuntimeError("untrusted remote error")
        self.messages.append(k)


def fixture():
    owner = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pub = owner.public_key().public_bytes(serialization.Encoding.PEM,
                                         serialization.PublicFormat.SubjectPublicKeyInfo)
    env = seal_document(b"FAKE-CLIENT-SECRET-CANARY",
                        pub, tenant_id="pilot01", case_id="case01",
                        object_id="object01", document_version="a"*32)
    signer = ed25519.Ed25519PrivateKey.generate()
    signer_pem = signer.private_bytes(serialization.Encoding.PEM,
                                     serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption())
    signer_pub = signer.public_key().public_bytes(serialization.Encoding.Raw,
                                                  serialization.PublicFormat.Raw)
    ddb, s3, sqs = FakeDdb(), FakeS3(), FakeSqs()
    t = CustomerCiphertextTransport(
        s3=s3, sqs=sqs, ddb=ddb, tenant="pilot01",
        bucket="synthetic-three-zero",
        queue_url="https://sqs.eu-central-1.amazonaws.com/111122223333/notarai-confidential-pilot01.fifo",
        account="111122223333",
    )
    return t, env, signer_pem, signer_pub, ddb, s3, sqs


def queue(t, env, signer_pem, signer_pub, stored, *, job_id="job01",
          signature_override=None):
    receipt, sig = sign_customer_origin(
        env, s3_version=stored["s3_version"], issuer_id="notary01",
        expires_at=2000, trusted_client_signing_private_pem=signer_pem)
    return t.enqueue_signed_preview(
        env, s3_version=stored["s3_version"],
        ciphertext_sha256=stored["ciphertext_sha256"], job_id=job_id,
        origin_receipt=receipt,
        origin_signature=sig if signature_override is None else signature_override,
        pinned_notary_signing_public_raw=signer_pub,
        expected_issuer_id="notary01", now=1000,
    )


def test_synthetic_ciphertext_s3_to_signed_metadata_only_fifo():
    t, env, pem, pub, ddb, s3, sqs = fixture()
    stored = t.admit_ciphertext(env)
    assert stored["stored"] is True
    result = queue(t, env, pem, pub, stored)
    assert result == {"queued": True, "job_id":"job01",
                      "operation":"preview-only", "submitted":False}
    assert len(sqs.messages) == 1
    msg = json.loads(sqs.messages[0]["MessageBody"])
    assert set(msg) == {"schema","tenant_id","case_id","object_id","job_id","s3_version"}
    assert msg["schema"] == "notarai.customer-job.v1"
    assert sqs.messages[0]["MessageGroupId"] == "pilot01"
    for record in s3.items.values():
        assert b"FAKE-CLIENT-SECRET-CANARY" not in record["bytes"]
    assert ddb.rows["DOC#pilot01#case01#object01"]["state"]["S"] == "queued"
    assert ddb.rows["JOB#pilot01#job01"]["state"]["S"] == "queued"


def test_duplicate_ciphertext_logical_identity_denied_before_second_put():
    t, env, *_ = fixture()
    t.admit_ciphertext(env)
    with pytest.raises(CustomerTransportDenied):
        t.admit_ciphertext(env)


def test_cross_tenant_envelope_refused_before_dynamodb():
    t, env, _, _, ddb, s3, sqs = fixture()
    env["tenant_id"] = "pilot02"
    with pytest.raises(CustomerTransportDenied):
        t.admit_ciphertext(env)
    assert not ddb.rows and not s3.items and not sqs.messages


def test_bad_origin_signature_refused_before_queue_or_dek():
    t, env, pem, pub, ddb, s3, sqs = fixture()
    stored = t.admit_ciphertext(env)
    with pytest.raises(CustomerTransportDenied):
        queue(t, env, pem, pub, stored, signature_override=b"0"*64)
    assert not sqs.messages
    assert not any(x.startswith("JOB#") for x in ddb.rows)


def test_wrong_ciphertext_digest_or_s3_version_denied():
    t, env, pem, pub, ddb, s3, sqs = fixture()
    stored = t.admit_ciphertext(env)
    receipt, sig = sign_customer_origin(
        env, s3_version=stored["s3_version"], issuer_id="notary01",
        expires_at=2000, trusted_client_signing_private_pem=pem)
    for version, digest in (("other-version", stored["ciphertext_sha256"]),
                            (stored["s3_version"], "0"*64)):
        with pytest.raises(CustomerTransportDenied):
            t.enqueue_signed_preview(
                env, s3_version=version, ciphertext_sha256=digest, job_id="job01",
                origin_receipt=receipt, origin_signature=sig,
                pinned_notary_signing_public_raw=pub,
                expected_issuer_id="notary01", now=1000)
    assert not sqs.messages


def test_sqs_ambiguous_failure_is_not_retried():
    t, env, pem, pub, ddb, s3, sqs = fixture()
    stored = t.admit_ciphertext(env)
    sqs.fail = True
    with pytest.raises(CustomerTransportDenied):
        queue(t, env, pem, pub, stored)
    assert ddb.rows["JOB#pilot01#job01"]["state"]["S"] == "queue_uncertain"
    sqs.fail = False
    with pytest.raises(CustomerTransportDenied):
        queue(t, env, pem, pub, stored)
    assert not sqs.messages


def test_untrusted_source_throws_only_generic_error():
    t, env, pem, pub, *_ = fixture()
    with pytest.raises(CustomerTransportDenied, match="confidential transport denied"):
        t.enqueue_signed_preview(
            env, s3_version="missing", ciphertext_sha256="a"*64, job_id="badjob",
            origin_receipt={}, origin_signature=b"secret",
            pinned_notary_signing_public_raw=pub,
            expected_issuer_id="notary01", now=1000)
