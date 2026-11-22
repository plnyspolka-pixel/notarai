"""SEC-05 synthetic negative tests. NEVER performs real AWS operations."""
import base64
import copy
import io
import json
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.dispatch import DispatcherConfig, UnsafeDispatch, dispatch_once
from confidential.release_enforcement import LiveReleaseGate, verify_kms_signed_release
from confidential.operator_boundary import BoundaryDenied
from test_confidential_dispatch import SQSFake, DynamoFake
from test_confidential_operator_boundary import (
    fixture, OPERATOR, CUSTODY, TENANT, PCR, DIGEST, TASK, KEY,
)
from test_confidential_release_approval import NOW, signed_case

SIGNING = f"arn:aws:kms:eu-central-1:{CUSTODY}:key/99999999-9999-9999-9999-999999999999"
ROLE = f"arn:aws:iam::{CUSTODY}:role/custody-release-auditor"
CLUSTER = "notarai-confidential-shared"


def config():
    return DispatcherConfig(
        account=OPERATOR, tenant=TENANT, cluster=CLUSTER,
        capacity_provider=CLUSTER, task_definition_arn=TASK,
        queue_url=f"https://sqs.eu-central-1.amazonaws.com/{OPERATOR}/notarai-confidential-{TENANT}.fifo",
        subnet="subnet-0123456789abcdef0",
        security_group="sg-0123456789abcdef0",
        lease_table=f"notarai-confidential-dispatch-{TENANT}",
        shared_pool=True, external_custody_key_arn=KEY,
    )


class FakeSTS:
    def __init__(self, account):
        self.account = account

    def get_caller_identity(self):
        return {"Account": self.account}


class FakeECS:
    def __init__(self, source):
        self.source = source
        self.launches = []

    def describe_task_definition(self, **kw):
        assert kw["taskDefinition"] == TASK
        return {"taskDefinition": copy.deepcopy(self.source["task_definition"])}

    def describe_capacity_providers(self, **kw):
        assert kw == {"capacityProviders": [CLUSTER]}
        return {"capacityProviders": [{
            "name": CLUSTER, "status": "ACTIVE",
            "managedInstancesProvider": {"instanceLaunchTemplate": {
                "nitroEnclavesEnabled": True,
                "networkConfiguration": {
                    "securityGroups": [config().security_group],
                    "subnets": [config().subnet],
                },
            }},
        }]}

    def list_tasks(self, **kw):
        return {"taskArns": []}

    def run_task(self, **kw):
        self.launches.append(kw)
        return {"tasks": [{
            "taskArn": f"arn:aws:ecs:eu-central-1:{OPERATOR}:task/{CLUSTER}/synthetic",
            "trustedExecutionSummary": {
                "isolationMode": "CONFIDENTIAL_SANDBOX",
                "attestationPolicyStatus": "CONFIGURED",
            },
        }], "failures": []}


class FakeKMS:
    def __init__(self, source, signer_pub):
        self.source = source
        self.public_pem = signer_pub
        self.calls = []

    def describe_key(self, **kw):
        if kw["KeyId"] == KEY:
            return {"KeyMetadata": copy.deepcopy(self.source["key_metadata"])}
        assert kw["KeyId"] == SIGNING
        return {"KeyMetadata": {
            "Arn": SIGNING, "AWSAccountId": CUSTODY,
            "KeyManager": "CUSTOMER", "KeyUsage": "SIGN_VERIFY",
            "KeySpec": "ECC_NIST_P256", "KeyState": "Enabled",
        }}

    def get_key_policy(self, **kw):
        return {"Policy": json.dumps(self.source["key_policy"])}

    def list_grants(self, **kw):
        return {"Grants": self.source["key_grants"]}

    def get_public_key(self, **kw):
        assert kw["KeyId"] == SIGNING
        public = serialization.load_pem_public_key(self.public_pem)
        return {"PublicKey": public.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ), "SigningAlgorithms": ["ECDSA_SHA_256"]}

    def verify(self, **kw):
        self.calls.append(kw)
        assert kw["MessageType"] == "RAW" and kw["KeyId"] == SIGNING
        public = serialization.load_pem_public_key(self.public_pem)
        try:
            public.verify(kw["Signature"], kw["Message"], ec.ECDSA(hashes.SHA256()))
        except Exception:
            return {"SignatureValid": False, "KeyId": SIGNING,
                    "SigningAlgorithm": "ECDSA_SHA_256"}
        return {"SignatureValid": True, "KeyId": SIGNING,
                "SigningAlgorithm": "ECDSA_SHA_256"}


class FakeS3:
    def __init__(self, receipt):
        self.receipt = receipt

    def get_object(self, **kw):
        assert kw == {
            "Bucket": "custody-releases", "Key": "pilot01/release.json",
            "VersionId": "version-a", "ExpectedBucketOwner": CUSTODY,
        }
        return {"Body": io.BytesIO(json.dumps(self.receipt).encode())}


class FakeCustody:
    def __init__(self, kms, s3):
        self.kms, self.s3 = kms, s3

    def client(self, name):
        return {"sts": FakeSTS(CUSTODY), "kms": self.kms, "s3": self.s3}[name]


def signed_launch():
    signature = signed_case()
    data = fixture()
    ecs = FakeECS(data)
    kms = FakeKMS(data, signature["trusted_public_key_pem"])
    s3 = FakeS3(signature["envelope"])
    pem = serialization.load_pem_public_key(signature["trusted_public_key_pem"])
    der = pem.public_bytes(serialization.Encoding.DER,
                           serialization.PublicFormat.SubjectPublicKeyInfo)
    import hashlib
    fingerprint = hashlib.sha256(der).hexdigest()
    gate = LiveReleaseGate(
        config=config(), workload_sts=FakeSTS(OPERATOR), ecs=ecs,
        assume_custody=lambda role: FakeCustody(kms, s3) if role == ROLE
        else (_ for _ in ()).throw(AssertionError("untrusted role")),
        custody_account=CUSTODY, custody_audit_role_arn=ROLE,
        kms_key_arn=KEY, signing_key_arn=SIGNING,
        approved_pcr17=PCR, approved_image_sha256=DIGEST,
        pinned_signer_sha256=fingerprint,
        release_bucket="custody-releases", release_key="pilot01/release.json",
        release_version="version-a", clock=lambda: NOW + timedelta(seconds=2),
    )
    return gate, ecs, kms, s3, data


def test_authorized_signed_release_has_two_live_checks_before_launch():
    gate, ecs, kms, _, _ = signed_launch()
    state = dispatch_once(
        config(), sqs=SQSFake(), ecs=ecs, dynamodb=DynamoFake(),
        release_gate=gate, clock=lambda: 1000, token_factory=lambda: "a" * 32,
    )
    assert state == "launched"
    assert len(ecs.launches) == 1 and len(kms.calls) == 2
    assert not ecs.launches[0].get("overrides")
    assert ecs.launches[0]["enableExecuteCommand"] is False


@pytest.mark.parametrize("reason", [
    "missing_signature", "bad_signature", "expired", "wrong_tenant",
    "wrong_pcr17", "wrong_image_digest", "wrong_kms_policy_hash",
])
def test_seven_denials_never_reach_run_task_or_lease(reason):
    gate, ecs, kms, s3, data = signed_launch()
    if reason == "missing_signature":
        s3.receipt.pop("signature_b64")
    elif reason == "bad_signature":
        s3.receipt["signature_b64"] = base64.b64encode(b"wrong").decode()
    elif reason == "expired":
        gate.clock = lambda: NOW + timedelta(hours=25)
    elif reason == "wrong_tenant":
        s3.receipt["payload"]["tenant"] = "pilot02"
    elif reason == "wrong_pcr17":
        gate.approved_pcr17 = "c" * 96
    elif reason == "wrong_image_digest":
        gate.approved_image_sha256 = "c" * 64
    elif reason == "wrong_kms_policy_hash":
        data["key_policy"]["Statement"][0]["Action"].append("kms:Decrypt")
    ddb = DynamoFake()
    with pytest.raises(UnsafeDispatch, match="release authorization"):
        dispatch_once(
            config(), sqs=SQSFake(), ecs=ecs, dynamodb=ddb, release_gate=gate,
        )
    assert not ecs.launches and ddb.put_calls == 0


def test_missing_gate_is_denied_even_with_empty_queue():
    ecs = FakeECS(fixture())
    with pytest.raises(UnsafeDispatch, match="mandatory"):
        dispatch_once(config(), sqs=SQSFake(0), ecs=ecs, dynamodb=DynamoFake())
    assert not ecs.launches


def test_policy_mutation_after_first_check_blocks_second_gate():
    gate, ecs, kms, _, data = signed_launch()
    original = kms.get_key_policy
    count = [0]

    def drift(**kwargs):
        count[0] += 1
        if count[0] == 2:
            data["key_policy"]["Statement"][2]["Condition"][
                "StringEqualsIgnoreCase"]["kms:RecipientAttestation:PCR17"] = "b" * 96
        return original(**kwargs)

    kms.get_key_policy = drift
    ddb = DynamoFake()
    result = dispatch_once(
        config(), sqs=SQSFake(), ecs=ecs, dynamodb=ddb,
        release_gate=gate, clock=lambda: 1000,
        token_factory=lambda: "a" * 32,
    )
    assert result == "launch_uncertain"
    assert not ecs.launches and ddb.put_calls == 1


def test_wrong_fingerprint_and_same_account_do_not_verify():
    gate, ecs, kms, _, _ = signed_launch()
    gate.pinned_signer_sha256 = "0" * 64
    with pytest.raises(BoundaryDenied):
        gate()
    gate, ecs, kms, _, _ = signed_launch()
    gate.custody_account = OPERATOR
    with pytest.raises(BoundaryDenied):
        gate()


def test_legacy_demo_key_is_not_accepted_by_server_gate():
    gate, ecs, _, _, _ = signed_launch()
    gate.config = DispatcherConfig(**{
        **config().__dict__, "external_custody_key_arn": "",
    })
    with pytest.raises(BoundaryDenied):
        gate()


def test_invalid_external_custody_account_rejected_at_config_boundary():
    invalid = DispatcherConfig(**{
        **config().__dict__,
        "external_custody_key_arn":
        f"arn:aws:kms:eu-central-1:{OPERATOR}:key/test",
    })
    with pytest.raises(UnsafeDispatch):
        invalid.validate()
