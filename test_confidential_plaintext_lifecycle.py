"""SEC-10 synthetic-only: no AWS, no real PII and no actual Nitro claim."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import sys
import types

import pytest
import yaml

from confidential.plaintext_lifecycle import (
    UnsafeGuestRuntime, assert_tmpfs, audit_no_plaintext_markers,
    ephemeral_browser_home, harden_guest_process,
)
from test_confidential_infra import CloudFormationLoader, ROOT


# These are artificial non-personal markers, never a real DEK/document.
FAKE_DOCUMENT = b"NOTARAI-SYNTHETIC-PLAINTEXT-SEC10-NEVER-REAL"
FAKE_DEK = b"NOTARAI-SYNTHETIC-KEY-SEC10-NEVER-REAL"


def test_tmpfs_is_explicit_and_not_inferred_from_a_path(tmp_path):
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text("28 1 0:42 / /tmp rw,nosuid,nodev - tmpfs tmpfs rw\n")
    assert_tmpfs(path="/tmp", mountinfo=str(mountinfo))
    for fs in ("overlay", "ext4", "nfs"):
        mountinfo.write_text(f"28 1 0:42 / /tmp rw - {fs} source rw\n")
        with pytest.raises(UnsafeGuestRuntime, match="tmpfs required"):
            assert_tmpfs(path="/tmp", mountinfo=str(mountinfo))
    mountinfo.write_text("28 1 0:42 / /var rw - tmpfs tmpfs rw\n")
    with pytest.raises(UnsafeGuestRuntime):
        assert_tmpfs(path="/tmp", mountinfo=str(mountinfo))


def test_browser_home_restored_after_success_and_failure(monkeypatch):
    monkeypatch.setattr("confidential.plaintext_lifecycle.assert_tmpfs", lambda: None)
    old = {key: os.environ.get(key) for key in
           ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "TMPDIR")}
    for failure in (False, True):
        saved = None
        try:
            with ephemeral_browser_home() as folder:
                saved = Path(folder)
                assert all(os.environ[key] == folder for key in old)
                (saved / "chromium-cache").write_bytes(FAKE_DOCUMENT)
                if failure:
                    raise RuntimeError("synthetic browser exception")
        except RuntimeError:
            assert failure
        assert saved is not None and not saved.exists()
        assert {key: os.environ.get(key) for key in old} == old


@pytest.mark.parametrize("scenario", [
    "success", "exception", "retry", "browser_crash", "network_error", "timeout",
])
def test_six_synthetic_lifecycle_failures_never_persist_plaintext(
    scenario, tmp_path, monkeypatch
):
    """Simulates exception paths, NOT a real OS kill/Nitro hardware crash."""
    monkeypatch.setattr("confidential.plaintext_lifecycle.assert_tmpfs", lambda: None)
    persistent = tmp_path / "operator-visible"
    persistent.mkdir()
    logs = persistent / "worker.log"
    messages = []
    home = None
    try:
        with ephemeral_browser_home() as folder:
            home = Path(folder)
            (home / "browser-cache").write_bytes(FAKE_DOCUMENT + FAKE_DEK)
            if scenario == "success":
                messages.append("preview_completed")
            elif scenario == "retry":
                raise ConnectionError("synthetic confidential retry error")
            elif scenario == "browser_crash":
                raise BrokenPipeError("synthetic browser crashed")
            elif scenario == "network_error":
                raise OSError("synthetic network dropped")
            elif scenario == "timeout":
                raise TimeoutError("synthetic operation timed out")
            else:
                raise RuntimeError("synthetic confidential exception")
    except Exception as exc:
        # Same constant-message logging policy as confidential.worker.main.
        messages.append("failed (" + type(exc).__name__ + ")")
    logs.write_text("\n".join(messages))
    assert home is not None and not home.exists()
    assert audit_no_plaintext_markers(persistent, (FAKE_DOCUMENT, FAKE_DEK)) == 1
    assert FAKE_DOCUMENT not in logs.read_bytes()
    assert FAKE_DEK not in logs.read_bytes()


@pytest.mark.parametrize("marker", [FAKE_DOCUMENT, FAKE_DEK])
def test_artifact_scanner_refuses_persistent_plaintext_without_echo(tmp_path, marker):
    (tmp_path / "leaked").write_bytes(marker)
    with pytest.raises(UnsafeGuestRuntime) as error:
        audit_no_plaintext_markers(tmp_path, (FAKE_DOCUMENT, FAKE_DEK))
    assert marker.decode() not in str(error.value)


def test_artifact_scan_rejects_symlink(tmp_path):
    (tmp_path / "target").write_text("metadata-only")
    (tmp_path / "link").symlink_to(tmp_path / "target")
    with pytest.raises(UnsafeGuestRuntime, match="symlink"):
        audit_no_plaintext_markers(tmp_path, (FAKE_DOCUMENT, FAKE_DEK))


def test_worker_exception_never_prints_untrusted_exception_message(monkeypatch):
    import confidential.worker as worker
    monkeypatch.setattr(worker, "harden_guest_process", lambda: None)
    monkeypatch.setattr(worker, "_config", lambda: ("pilot01", "bucket", "queue", "key"))
    monkeypatch.setitem(sys.modules, "boto3",
                        types.SimpleNamespace(Session=lambda **kwargs: object()))
    def poisoned(*args):
        raise RuntimeError(FAKE_DOCUMENT.decode() + FAKE_DEK.decode())
    monkeypatch.setattr(worker, "_process_one", poisoned)
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        assert worker.main() == 1
    output = (stdout.getvalue() + stderr.getvalue()).encode()
    assert FAKE_DOCUMENT not in output and FAKE_DEK not in output
    assert b"RuntimeError" in output


def test_guest_task_is_readonly_tmpfs_no_logs_and_preview_only():
    doc = yaml.load(
        (ROOT / "notarai-confidential-task.yaml").read_text(),
        Loader=CloudFormationLoader,
    )
    task = doc["Resources"]["ConfidentialTaskDefinition"]["Properties"]
    container = task["ContainerDefinitions"][0]
    assert task["TrustedExecutionConfiguration"]["IsolationMode"] == "CONFIDENTIAL_SANDBOX"
    assert container["ReadonlyRootFilesystem"] is True
    assert container.get("LogConfiguration") is None
    assert container.get("MountPoints") in (None, [])
    tmpfs = container["LinuxParameters"]["Tmpfs"]
    assert len(tmpfs) == 1 and tmpfs[0]["ContainerPath"] == "/tmp"
    assert {"nosuid", "nodev"} <= set(tmpfs[0]["MountOptions"])
    assert all(x["Name"] != "AWS_CONTAINER_CREDENTIALS_FULL_URI"
               for x in container["Environment"])


def test_no_recovery_backdoor_or_plaintext_grants_in_guest_role():
    doc = yaml.load(
        (ROOT / "notarai-confidential-task.yaml").read_text(),
        Loader=CloudFormationLoader,
    )
    rules = doc["Resources"]["ConfidentialTaskRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    actions = {action for entry in rules for action in
               ([entry["Action"]] if isinstance(entry["Action"], str) else entry["Action"])}
    assert "kms:CreateGrant" not in actions
    assert "kms:PutKeyPolicy" not in actions
    assert "kms:ScheduleKeyDeletion" not in actions
    assert "s3:ListBucketVersions" not in actions
    assert "s3:DeleteObject" not in actions
    assert "s3:RestoreObject" not in actions
    decrypt = [x for x in rules if x["Action"] == "kms:Decrypt"]
    assert len(decrypt) == 1
    assert "kms:RecipientAttestation:PCR17" in decrypt[0]["Condition"]["StringEqualsIgnoreCase"]


def test_no_unconditional_plaintext_recovery_route():
    from confidential import router
    paths = [getattr(r, "path", "") for r in router.router.routes]
    assert not any("recover" in p or "admin-decrypt" in p for p in paths)
    assert all("plaintext" not in p for p in paths)


def _aws_fixture():
    from scripts.verify_confidential_plaintext_lifecycle import inspect_task_definition
    tenant = "pilot01"
    account = "111122223333"
    task_arn = (f"arn:aws:ecs:eu-central-1:{account}:task-definition/"
                f"notarai-confidential-{tenant}:7")
    task = {
        "taskDefinitionArn": task_arn,
        "trustedExecutionConfiguration": {"isolationMode": "CONFIDENTIAL_SANDBOX"},
        "containerDefinitions": [{
            "image": "example@sha256:" + "a" * 64,
            "readonlyRootFilesystem": True,
            "linuxParameters": {"tmpfs": [{"containerPath": "/tmp",
                                           "mountOptions": ["rw", "nosuid", "nodev"]}]},
        }],
    }
    return account, tenant, task_arn, task


def test_read_only_auditor_defaults_to_zero_aws_access(capsys):
    from scripts.verify_confidential_plaintext_lifecycle import main
    assert main([]) == 0
    assert "AWS calls DISABLED" in capsys.readouterr().out
    assert main(["--check"]) == 2


def test_read_only_auditor_rejects_wrong_scope():
    from scripts.verify_confidential_plaintext_lifecycle import (
        validate_scope, UnsafeAudit,
    )
    account, tenant, task_arn, _ = _aws_fixture()
    good = dict(
        account=account, tenant=tenant,
        bucket=f"ntr-cf-{tenant}-{account}-eu-central-1",
        queue_url=(f"https://sqs.eu-central-1.amazonaws.com/{account}/"
                   f"notarai-confidential-{tenant}.fifo"),
        task_arn=task_arn,
    )
    validate_scope(**good)
    for changes in (
        {"tenant": "production"},
        {"bucket": "my-real-client-bucket"},
        {"queue_url": good["queue_url"].replace("pilot01", "pilot02")},
        {"task_arn": good["task_arn"].replace("pilot01", "pilot02")},
        {"account": "000000000000"},
    ):
        with pytest.raises(UnsafeAudit):
            validate_scope(**{**good, **changes})


def test_metadata_only_audit_uses_allowlisted_aws_read_calls():
    from scripts.verify_confidential_plaintext_lifecycle import read_only_audit
    account, tenant, task_arn, task = _aws_fixture()
    calls = []

    class FakeClient:
        def __init__(self, service):
            self.service = service

        def __getattr__(self, name):
            allow = {
                "sts": {"get_caller_identity"},
                "ecs": {"describe_task_definition"},
                "s3": {"get_bucket_versioning",
                       "get_bucket_lifecycle_configuration", "list_object_versions"},
                "sqs": {"get_queue_attributes"},
                "dynamodb": {"describe_continuous_backups"},
                "cloudtrail": {"describe_trails"},
                "logs": {"describe_log_groups"},
            }
            assert name in allow[self.service], "unexpected AWS operation"
            def call(**kwargs):
                calls.append((self.service, name))
                if name == "get_caller_identity":
                    return {"Account": account}
                if name == "describe_task_definition":
                    return {"taskDefinition": task}
                if name == "get_bucket_versioning":
                    return {"Status": "Enabled"}
                if name == "get_bucket_lifecycle_configuration":
                    return {"Rules": []}
                if name == "list_object_versions":
                    return {"Versions": [{}], "IsTruncated": False}
                if name == "get_queue_attributes":
                    if kwargs["QueueUrl"].endswith("-dead.fifo"):
                        return {"Attributes": {"MessageRetentionPeriod": "1209600"}}
                    redrive = {"deadLetterTargetArn": (
                        f"arn:aws:sqs:eu-central-1:{account}:"
                        "notarai-confidential-pilot01-dead.fifo"
                    )}
                    return {"Attributes": {
                        "MessageRetentionPeriod": "86400",
                        "RedrivePolicy": json.dumps(redrive),
                    }}
                if name == "describe_continuous_backups":
                    return {"ContinuousBackupsDescription": {
                        "PointInTimeRecoveryDescription": {
                            "PointInTimeRecoveryStatus": "ENABLED",
                            "RecoveryPeriodInDays": 35,
                        }
                    }}
                if name == "describe_trails":
                    return {"trailList": []}
                if name == "describe_log_groups":
                    return {"logGroups": [{"retentionInDays": 7}]}
                raise AssertionError(name)
            return call

    class Session:
        region_name = "eu-central-1"
        def client(self, service):
            return FakeClient(service)

    report = read_only_audit(
        Session(), account=account, tenant=tenant, task_arn=task_arn,
        bucket=f"ntr-cf-{tenant}-{account}-eu-central-1",
        queue_url=(f"https://sqs.eu-central-1.amazonaws.com/{account}/"
                   f"notarai-confidential-{tenant}.fifo"),
    )
    assert all(report["task_controls"].values())
    assert report["s3_versioning_enabled"] and report["ddb_pitr_days"] == 35
    assert report["sqs_retention_seconds"] == 86400
    assert report["sqs_dlq_retention_seconds"] == 1209600
    assert report["cloudwatch_named_group_retention_days"] == [7]
    assert len(calls) == 10
    assert {name for _, name in calls} == {
        "get_caller_identity", "describe_task_definition",
        "get_bucket_versioning", "get_bucket_lifecycle_configuration",
        "list_object_versions", "get_queue_attributes",
        "describe_continuous_backups", "describe_trails",
        "describe_log_groups",
    }


def test_auditor_refuses_wrong_account_before_storage_calls():
    from scripts.verify_confidential_plaintext_lifecycle import (
        read_only_audit, UnsafeAudit,
    )
    account, tenant, task_arn, _ = _aws_fixture()
    class Session:
        region_name = "eu-central-1"
        def client(self, service):
            assert service == "sts"
            return types.SimpleNamespace(
                get_caller_identity=lambda: {"Account": "999988887777"}
            )
    with pytest.raises(UnsafeAudit, match="account mismatch"):
        read_only_audit(
            Session(), account=account, tenant=tenant, task_arn=task_arn,
            bucket=f"ntr-cf-{tenant}-{account}-eu-central-1",
            queue_url=(f"https://sqs.eu-central-1.amazonaws.com/{account}/"
                       f"notarai-confidential-{tenant}.fifo"),
        )


def test_guest_process_hardening_calls_kernel_controls(monkeypatch):
    import confidential.plaintext_lifecycle as lifecycle
    invoked = []
    class FakeLibc:
        def __init__(self):
            def prctl(*args):
                invoked.append(("prctl", args))
                return 0
            self.prctl = prctl
    monkeypatch.setattr(lifecycle.resource, "setrlimit",
                        lambda limit, value: invoked.append(("setrlimit", limit, value)))
    monkeypatch.setattr(lifecycle.resource, "getrlimit", lambda limit: (0, 0))
    monkeypatch.setattr(lifecycle.ctypes, "CDLL", lambda *a, **k: FakeLibc())
    monkeypatch.setattr(lifecycle.faulthandler, "disable",
                        lambda: invoked.append(("disable",)))
    monkeypatch.setattr(lifecycle.os, "umask",
                        lambda mask: invoked.append(("umask", mask)))
    monkeypatch.setattr(lifecycle, "assert_tmpfs",
                        lambda: invoked.append(("tmpfs",)))
    lifecycle.harden_guest_process()
    assert ("setrlimit", lifecycle.resource.RLIMIT_CORE, (0, 0)) in invoked
    assert ("prctl", (4, 0, 0, 0, 0)) in invoked
    assert ("disable",) in invoked
    assert ("umask", 0o077) in invoked
    assert ("tmpfs",) in invoked


def test_guest_process_fails_closed_if_dumpability_cannot_be_disabled(monkeypatch):
    import confidential.plaintext_lifecycle as lifecycle
    class FakeLibc:
        def __init__(self):
            def prctl(*args):
                return -1
            self.prctl = prctl
    monkeypatch.setattr(lifecycle.resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(lifecycle.resource, "getrlimit", lambda *args: (0, 0))
    monkeypatch.setattr(lifecycle.ctypes, "CDLL", lambda *a, **k: FakeLibc())
    monkeypatch.setattr(lifecycle, "assert_tmpfs", lambda: None)
    with pytest.raises(UnsafeGuestRuntime, match="dumpable"):
        lifecycle.harden_guest_process()


def test_stdio_redirection_targets_only_devnull_before_plaintext(monkeypatch):
    import confidential.plaintext_lifecycle as lifecycle
    calls = []
    monkeypatch.setattr(lifecycle.os, "open",
                        lambda path, flags: (calls.append(("open", path)), 93)[1])
    monkeypatch.setattr(lifecycle.os, "dup2",
                        lambda source, dest: calls.append(("dup2", source, dest)))
    monkeypatch.setattr(lifecycle.os, "close",
                        lambda fd: calls.append(("close", fd)))
    lifecycle.silence_guest_stdio()
    assert calls == [
        ("open", "/dev/null"), ("dup2", 93, 1), ("dup2", 93, 2), ("close", 93)
    ]


def test_stdio_redirection_fails_closed_before_decrypt(monkeypatch):
    import confidential.plaintext_lifecycle as lifecycle
    calls = []
    monkeypatch.setattr(lifecycle.os, "open", lambda path, flags: 93)
    def deny(source, dest):
        calls.append(dest)
        raise OSError("synthetic forbidden stdio")
    monkeypatch.setattr(lifecycle.os, "dup2", deny)
    monkeypatch.setattr(lifecycle.os, "close", lambda fd: calls.append("closed"))
    with pytest.raises(UnsafeGuestRuntime) as err:
        lifecycle.silence_guest_stdio()
    assert str(err.value) == "guest output suppression failed"
    assert calls == [1, "closed"]


def test_worker_redirection_precedes_decryption_in_source():
    import inspect
    import confidential.worker as worker
    source = inspect.getsource(worker._process_one)
    assert source.index("silence_guest_stdio()") < source.index("_load_decrypted_form(")
