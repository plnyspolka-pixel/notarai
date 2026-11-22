"""S3 envelope boundary tests; never calls AWS."""
from io import BytesIO
from types import SimpleNamespace
import pytest

from computer_use.payloads import EncryptedPayloadStore


class S3:
    def __init__(self):
        self.saved={}
    def put_object(self,**kw):
        self.saved[(kw["Bucket"],kw["Key"])]=dict(kw)
    def get_object(self,**kw):
        data=self.saved[(kw["Bucket"],kw["Key"])]
        return {"Body":BytesIO(data["Body"]), "ServerSideEncryption":data["ServerSideEncryption"],
                "SSEKMSKeyId":data["SSEKMSKeyId"]}


def setup():
    s3=S3()
    store=EncryptedPayloadStore(s3=s3,bucket="test-bucket",
                                tenant_id="t1",kms_key_id="arn:aws:kms:eu-central-1:123:key/test")
    return s3,store


def test_s3_private_kms_object_with_integrity():
    s3,store=setup()
    digest=store.write("t1","jobA","input",{"field":"case","value":"FIKCYJNE"})
    assert store.read("t1","jobA","input",digest)=={"field":"case","value":"FIKCYJNE"}
    args=next(iter(s3.saved.values()))
    assert args["ServerSideEncryption"]=="aws:kms"
    assert args["IfNoneMatch"]=="*"
    assert "virtual-employee/tenants/t1/jobs/jobA/input.json" in args["Key"]
    assert "FIKCYJNE" not in args["Key"]


def test_s3_no_cross_tenant_path():
    _,store=setup()
    with pytest.raises(PermissionError):
        store.write("other_tenant","jobA","input",{"x":1})


def test_s3_detects_modification():
    s3,store=setup()
    digest=store.write("t1","jobA","result",{"x":1})
    data=next(iter(s3.saved.values()))
    data["Body"]=b'{"x":2}'
    with pytest.raises(PermissionError,match="integrity"):
        store.read("t1","jobA","result",digest)


def test_s3_refuses_wrong_kms_key():
    s3,store=setup()
    digest=store.write("t1","jobA","input",{"x":1})
    data=next(iter(s3.saved.values()))
    data["SSEKMSKeyId"]="different-key"
    with pytest.raises(PermissionError,match="kms"):
        store.read("t1","jobA","input",digest)


def test_s3_rejects_unsafe_digest():
    _,store=setup()
    with pytest.raises(ValueError):
        store.read("t1","jobA","input","../payload")
