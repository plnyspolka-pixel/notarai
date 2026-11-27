"""Off-site encrypted copies and unattended daily backups. S3 and Cognito are faked."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from worker import recovery
from worker.api import create_app
from worker.init_vault import initialize
from worker.replica import KEEP, Replica, ReplicaError


class S3:
    def __init__(self):
        self.objects, self.fail = {}, False

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        if self.fail:
            raise RuntimeError("network")
        assert ExtraArgs == {"ServerSideEncryption": "AES256"}
        self.objects[(bucket, key)] = open(path, "rb").read()

    def list_objects_v2(self, Bucket, Prefix):
        return {"Contents": [{"Key": k, "Size": len(v)} for (b, k), v in self.objects.items()
                             if b == Bucket and k.startswith(Prefix)]}

    def delete_object(self, Bucket, Key):
        del self.objects[(Bucket, Key)]

    def download_file(self, bucket, key, path):
        open(path, "wb").write(self.objects[(bucket, key)])


class Account:
    signed_in = True

    def __init__(self, s3, identity="eu-central-1:office-a"):
        self.s3, self.identity, self.regions = s3, identity, []

    def identity_id(self):
        return self.identity

    def client_factory(self, region=None):
        self.regions.append(region)
        return lambda service: self.s3


@pytest.fixture
def office(tmp_path):
    home = tmp_path / "home"
    token = initialize(home)
    return home, {"Authorization": "Bearer " + token}, S3()


def test_copy_goes_off_site_as_ciphertext_and_restores_elsewhere(office, tmp_path):
    home, admin, s3 = office
    code = recovery.enroll(home)
    (home / "settings.json").write_text(json.dumps(
        {"replica": {"enabled": True, "bucket": "notarai-v2-kopie", "region": "eu-central-1"}}))
    account = Account(s3)
    client = TestClient(create_app(home, account=account))
    client.post("/v2/documents", headers=admin, json={
        "name": "TAJNY-AKT.txt", "expected_version": 0, "content_b64": "VEFKTkEgVFJFU0M="})
    sent = client.post("/v2/backup/offsite", headers=admin)
    assert sent.status_code == 200 and sent.json()["documents"] == 1
    (bucket, key), blob = next(iter(s3.objects.items()))
    assert bucket == "notarai-v2-kopie" and key.startswith("eu-central-1:office-a/notarai-")
    assert b"TAJNA TRESC" not in blob and b"TAJNY-AKT" not in blob
    assert account.regions[-1] == "eu-central-1"
    status = client.get("/v2/status", headers=admin).json()["recovery"]
    assert status["offsite_enabled"] and status["last_offsite"]
    listed = client.get("/v2/backup/offsite", headers=admin).json()
    assert [item["name"] for item in listed] == [key.split("/")[1]]

    # New computer: sign in, download, restore with the printed code.
    replica = Replica(tmp_path, account, "notarai-v2-kopie", "eu-central-1")
    local = tmp_path / "pobrana.notarai-backup"
    replica.download(listed[0]["name"], local)
    assert recovery.restore(local, tmp_path / "nowy", code)["documents"] == 1
    for bad in ("../x.notarai-backup", "a/b.notarai-backup", "x.txt", listed[0]["name"]):
        with pytest.raises(ReplicaError):
            replica.download(bad, local)

    # Another office's copies are invisible: a different identity means a different prefix.
    assert Replica(tmp_path, Account(s3, "eu-central-1:office-b"), "notarai-v2-kopie", "eu-central-1").list() == []


def test_old_copies_are_pruned_and_failures_are_plain(office, tmp_path):
    home, _, s3 = office
    recovery.enroll(home)
    replica = Replica(home, Account(s3), "notarai-v2-kopie", "eu-central-1")
    for index in range(KEEP + 2):
        s3.objects[("notarai-v2-kopie", f"eu-central-1:office-a/notarai-20200101-0000{index:02d}.notarai-backup")] = b"x"
    replica.upload()
    names = [item["name"] for item in replica.list()]
    assert len(names) == KEEP and "notarai-20200101-000000.notarai-backup" not in names
    s3.fail = True
    with pytest.raises(ReplicaError) as error:
        replica.upload()
    assert "network" not in str(error.value)
    assert not [p for p in home.iterdir() if p.name.startswith("tmp")]
    with pytest.raises(ValueError):
        Replica(home, Account(s3), "notarai-v2-kopie", "us-east-1")


def test_daily_copies_happen_without_being_asked(office, tmp_path, monkeypatch):
    home, admin, s3 = office
    usb = tmp_path / "usb"
    usb.mkdir()
    (home / "settings.json").write_text(json.dumps({
        "backup_dir": str(usb), "replica": {"enabled": True, "bucket": "notarai-v2-kopie", "region": "eu-central-1"}}))
    app = create_app(home, account=Account(s3))
    assert app.state.maintain() == {}                      # no recovery code yet: a copy would be useless
    recovery.enroll(home)
    first = app.state.maintain()
    assert set(first) == {"local", "offsite"} and len(list(usb.iterdir())) == 1 and len(s3.objects) == 1
    assert app.state.maintain() == {}                      # not due again today
    for old in usb.iterdir():
        old.unlink()
    monkeypatch.setattr(time, "time_ns", lambda real=time.time_ns: real() + 2 * 86400 * 10**9)   # two days pass
    s3.fail = True
    assert set(app.state.maintain()) == {"local"}           # off-site fails quietly, local still runs
    assert len(list(usb.iterdir())) == 1


def test_replica_settings_must_stay_in_the_eu(office):
    home, _, _ = office
    for bad in ({"enabled": True, "bucket": "ok-bucket", "region": "us-east-1"},
                {"enabled": True, "bucket": "", "region": "eu-central-1"},
                {"enabled": True, "bucket": "Bad_Bucket", "region": "eu-central-1"}):
        (home / "settings.json").write_text(json.dumps({"replica": bad}))
        with pytest.raises(ValueError):
            create_app(home)
