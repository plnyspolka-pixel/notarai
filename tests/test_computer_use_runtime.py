"""Tenant worker bootstrap accepts only signed provisioner files and EU runtime."""
import base64
import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest

from computer_use.runtime import prepare_worker


class Table:
    def get_item(self,**kwargs):
        return {"Item":{"disabled":True}}


class BotoFake:
    def resource(self,service,**kwargs):
        assert service=="dynamodb"
        return SimpleNamespace(Table=lambda name:Table())
    def client(self,service,**kwargs):
        assert service in ("sqs","s3")
        return SimpleNamespace()


def env(tmp_path):
    payload={
        "tenant_id":"test_office",
        "revision":1,
        "app":{
            "app_id":"test_app",
            "start_url":"https://example.test/",
            "windows_app":None,
            "fields":{"case":{"kind":"css","selector":"#case"}}
        },
    }
    file=tmp_path/"signed-profile.json"
    raw=json.dumps(payload).encode()
    file.write_bytes(raw)
    key=b"Z"*32
    return {
        "NOTARAI_VE_TENANT":"test_office",
        "NOTARAI_VE_WORKER_ID":"robot_1",
        "NOTARAI_VE_TENANT_QUEUE_URL":"https://sqs.eu-central-1.amazonaws.com/000/test.fifo",
        "NOTARAI_VE_JOBS_TABLE":"jobs",
        "NOTARAI_VE_SETTINGS_TABLE":"settings",
        "NOTARAI_VE_PAYLOAD_BUCKET":"example",
        "NOTARAI_VE_TENANT_KMS_KEY":"arn:aws:kms:eu-central-1:000:key/test",
        "NOTARAI_VE_PROFILE_FILE":str(file),
        "NOTARAI_VE_PROFILE_SIGNATURE":hmac.new(key,raw,hashlib.sha256).hexdigest(),
        "NOTARAI_VE_PROFILE_SIGNING_KEY_B64":base64.b64encode(key).decode(),
        "AWS_REGION":"eu-central-1"
    }


def test_provisioned_worker_has_bound_tenant_and_disabled_vision(tmp_path):
    worker=prepare_worker(config=env(tmp_path),boto3_module=BotoFake())
    assert worker.tenant_id=="test_office"
    assert worker.worker_id=="robot_1"
    assert worker.worker._tenant_id=="test_office"
    assert worker.worker._vision is None


def test_runtime_rejects_us_region(tmp_path):
    config=env(tmp_path)
    config["AWS_REGION"]="us-east-1"
    with pytest.raises(RuntimeError,match="invalid_worker_region"):
        prepare_worker(config=config,boto3_module=BotoFake())


def test_runtime_rejects_tampered_profile(tmp_path):
    config=env(tmp_path)
    with open(config["NOTARAI_VE_PROFILE_FILE"],"ab") as f:
        f.write(b" ")
    with pytest.raises(ValueError,match="signature_mismatch"):
        prepare_worker(config=config,boto3_module=BotoFake())


def test_runtime_cannot_enable_vision_in_linux(tmp_path):
    config=env(tmp_path)
    config["NOTARAI_VE_VISUAL_ENABLED"]="true"
    with pytest.raises(RuntimeError,match="visual_worker_requires_windows"):
        prepare_worker(config=config,boto3_module=BotoFake())
