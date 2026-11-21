"""No AWS access, no client data, no real browser session."""
import json

import pytest

from confidential.worker import _parse_message


def test_sqs_message_scoped_to_its_tenant():
    good = {"tenant_id": "demo_tenant", "case_id": "case1", "object_id": "scan1", "job_id": "job1", "s3_version": "v000001"}
    assert _parse_message(json.dumps(good), "demo_tenant") == ("case1", "scan1", "job1", "v000001")
    with pytest.raises(ValueError):
        _parse_message(json.dumps(good), "other_tenant")
    with pytest.raises(ValueError):
        _parse_message(json.dumps({**good, "case_id": "../secret"}), "demo_tenant")
    with pytest.raises(ValueError):
        _parse_message(json.dumps({**good, "submit": True}), "demo_tenant")
    with pytest.raises(ValueError):
        _parse_message(json.dumps({**good, "s3_version": "null"}), "demo_tenant")
    with pytest.raises(ValueError):
        _parse_message(json.dumps({k: v for k, v in good.items()
                                  if k != "s3_version"}), "demo_tenant")


def test_no_hardware_means_no_work(monkeypatch):
    from confidential.worker import _config
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_REQUIRED", "1")
    monkeypatch.setattr("confidential.worker.os.path.exists", lambda path: False)
    with pytest.raises(RuntimeError, match="hardware attestation required"):
        _config()
