"""Vault key hierarchy, access log, recovery code, backup and restore drills."""
import json
import sqlite3
import zipfile

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from worker import recovery
from worker.init_vault import initialize
from worker.local_secrets import read_secret
from worker.vault import Vault


def new_home(tmp_path, name="home"):
    home = tmp_path / name
    initialize(home)
    return home, Vault(home, read_secret(home, "vault.key"))


def test_legacy_single_key_vault_is_migrated(tmp_path):
    key = b"K" * 32
    cipher = AESGCM(key)
    doc = "11111111-1111-4111-8111-111111111111"
    with sqlite3.connect(tmp_path / "vault.sqlite3") as db:
        db.execute("CREATE TABLE revisions (id TEXT, version INTEGER, payload BLOB NOT NULL, PRIMARY KEY(id, version))")
        for version, body in ((1, b"first"), (2, b"second")):
            meta = json.dumps({"name": f"akt-{version}.txt"}).encode()
            plain = len(meta).to_bytes(4, "big") + meta + body
            nonce = bytes([version]) * 12
            db.execute("INSERT INTO revisions VALUES (?,?,?)",
                       (doc, version, nonce + cipher.encrypt(nonce, plain, f"notarai-v2:{doc}:{version}".encode())))
    vault = Vault(tmp_path, key)
    assert vault.get(doc, 1) == (1, "akt-1.txt", b"first")
    assert vault.get(doc) == (2, "akt-2.txt", b"second")
    assert vault.verify()["revisions"] == 2
    assert Vault(tmp_path, key).versions(doc) == [2, 1]  # reopening does not migrate twice


def test_listing_does_not_decrypt_bodies_and_wrong_key_fails(tmp_path):
    home, vault = new_home(tmp_path)
    doc, _ = vault.put(None, 0, "akt.txt", b"body", case="sprawa-1")
    with sqlite3.connect(home / "vault.sqlite3") as db:
        db.execute("UPDATE revisions SET payload = x'00'")
    assert vault.summaries()[0]["name"] == "akt.txt"
    assert vault.summaries(cases={"inna"}) == []
    assert vault.list(cases={"sprawa-1"}) == [{"id": doc, "version": 1}]
    with pytest.raises(InvalidTag):
        Vault(home, b"X" * 32).summaries()


def test_case_is_fixed_and_validated(tmp_path):
    _, vault = new_home(tmp_path)
    doc, _ = vault.put(None, 0, "a.txt", b"a", case="sprawa-1")
    vault.put(doc, 1, "a.txt", b"b")
    with pytest.raises(ValueError):
        vault.put(doc, 2, "a.txt", b"c", case="sprawa-2")
    with pytest.raises(ValueError):
        vault.put(None, 0, "a.txt", b"a", case="../x")
    assert vault.case_of(doc) == "sprawa-1"
    assert vault.cases() == ["sprawa-1"]


def test_access_log_records_reads_and_detects_tampering(tmp_path):
    home, vault = new_home(tmp_path)
    doc, _ = vault.put(None, 0, "TAJNA-NAZWA.txt", b"TAJNA-TRESC", actor="device-1")
    vault.get(doc, actor="device-2")
    entries = vault.audit()
    assert [(e["actor"], e["action"], e["version"]) for e in entries] == [
        ("device-2", "read", 1), ("device-1", "write", 1)]
    raw = (home / "vault.sqlite3").read_bytes()
    assert b"TAJNA-NAZWA" not in raw and b"TAJNA-TRESC" not in raw
    assert vault.verify()["audit_entries"] == 2
    with sqlite3.connect(home / "vault.sqlite3") as db:
        db.execute("UPDATE audit SET actor='nobody' WHERE seq=2")
    with pytest.raises(ValueError):
        vault.verify()
    with sqlite3.connect(home / "vault.sqlite3") as db:
        db.execute("UPDATE audit SET actor='device-2' WHERE seq=2")
        db.execute("DELETE FROM audit WHERE seq=1")
    with pytest.raises(ValueError):
        vault.verify()


def test_recovery_code_roundtrip_and_typos():
    code, secret = recovery.new_code()
    assert recovery.parse_code(code) == secret
    assert recovery.parse_code(code.lower().replace("-", " ")) == secret
    assert recovery.parse_code(code.replace("O", "0").replace("I", "1").replace("B", "8")) == secret
    broken = ("A" if code[0] != "A" else "B") + code[1:]
    with pytest.raises(recovery.RecoveryError):
        recovery.parse_code(broken)
    with pytest.raises(recovery.RecoveryError):
        recovery.parse_code("not a code")


def test_lost_profile_drill(tmp_path):
    """The computer is gone: only the backup file and the printed code remain."""
    home, vault = new_home(tmp_path)
    with pytest.raises(recovery.RecoveryError):
        recovery.backup(home, tmp_path / "early.notarai-backup")
    code = recovery.enroll(home)
    with pytest.raises(recovery.RecoveryError):
        recovery.enroll(home)
    doc, _ = vault.put(None, 0, "akt.txt", b"pierwsza")
    vault.put(doc, 1, "akt.txt", b"druga")
    backup = tmp_path / "kopia.notarai-backup"
    manifest = recovery.backup(home, backup)
    assert manifest["documents"] == 1 and manifest["revisions"] == 2
    assert recovery.inspect(backup)["vault_sha256"] == manifest["vault_sha256"]
    with pytest.raises(recovery.RecoveryError):
        recovery.backup(home, backup)
    data = backup.read_bytes()
    assert b"pierwsza" not in data and b"akt.txt" not in data
    assert read_secret(home, "vault.key") not in data

    fresh = tmp_path / "new-computer"
    other_code, _ = recovery.new_code()
    with pytest.raises(recovery.RecoveryError):
        recovery.restore(backup, fresh, other_code)
    assert list(fresh.iterdir()) == []
    result = recovery.restore(backup, fresh, code)
    assert result["revisions"] == 2 and len(result["token"]) >= 40
    restored = Vault(fresh, read_secret(fresh, "vault.key"))
    assert restored.get(doc, 1)[2] == b"pierwsza" and restored.get(doc)[2] == b"druga"
    assert read_secret(fresh, "api.token") != read_secret(home, "api.token")
    assert not (fresh / "devices.sqlite3").exists()
    with pytest.raises(recovery.RecoveryError):
        recovery.restore(backup, fresh, code)  # never overwrites
    # A second backup from the restored vault works with the same code.
    recovery.backup(fresh, tmp_path / "second.notarai-backup")


def test_damaged_or_foreign_backups_are_rejected(tmp_path):
    home, vault = new_home(tmp_path)
    code = recovery.enroll(home)
    vault.put(None, 0, "akt.txt", b"x" * 4096)
    backup = tmp_path / "kopia.notarai-backup"
    recovery.backup(home, backup)

    damaged = tmp_path / "damaged"
    raw = bytearray(backup.read_bytes())
    raw[len(raw) // 2] ^= 1
    damaged.write_bytes(raw)
    with pytest.raises(recovery.RecoveryError):
        recovery.restore(damaged, tmp_path / "a", code)
    assert list((tmp_path / "a").iterdir()) == []

    extra = tmp_path / "extra"
    extra.write_bytes(backup.read_bytes())
    with zipfile.ZipFile(extra, "a") as archive:
        archive.writestr("evil.txt", "x")
    with pytest.raises(recovery.RecoveryError):
        recovery.restore(extra, tmp_path / "b", code)

    swapped = tmp_path / "swapped"
    with zipfile.ZipFile(backup) as src, zipfile.ZipFile(swapped, "w") as dst:
        manifest = json.loads(src.read("manifest.json"))
        manifest["documents"] = 99
        dst.writestr("manifest.json", json.dumps(manifest))
        dst.writestr(recovery.RECOVERY_FILE, src.read(recovery.RECOVERY_FILE))
        dst.writestr("vault.sqlite3", src.read("vault.sqlite3"))
    with pytest.raises(recovery.RecoveryError):
        recovery.restore(swapped, tmp_path / "c", code)
    (tmp_path / "junk").write_bytes(b"junk")
    with pytest.raises(recovery.RecoveryError):
        recovery.restore(tmp_path / "junk", tmp_path / "d", code)


def test_key_rotation_invalidates_old_key_and_code(tmp_path):
    home, vault = new_home(tmp_path)
    old_code = recovery.enroll(home)
    old_key = read_secret(home, "vault.key")
    doc, _ = vault.put(None, 0, "akt.txt", b"tresc")
    before = (home / "vault.sqlite3").read_bytes()
    new_code = recovery.rotate_master(home)
    new_key = read_secret(home, "vault.key")
    assert new_key != old_key and new_code != old_code
    assert Vault(home, new_key).get(doc)[2] == b"tresc"
    assert Vault(home, new_key).verify()["documents"] == 1
    with pytest.raises(InvalidTag):
        Vault(home, old_key).get(doc)
    payload = sqlite3.connect(home / "vault.sqlite3").execute("SELECT payload FROM revisions").fetchone()[0]
    assert payload in before  # document ciphertext was not rewritten
    backup = tmp_path / "after.notarai-backup"
    recovery.backup(home, backup)
    with pytest.raises(recovery.RecoveryError):
        recovery.restore(backup, tmp_path / "x", old_code)
    assert recovery.restore(backup, tmp_path / "y", new_code)["documents"] == 1
    assert not (home / "vault.key.rotating").exists()


def test_interrupted_rotation_is_completed(tmp_path, monkeypatch):
    home, vault = new_home(tmp_path)
    recovery.enroll(home)
    doc, _ = vault.put(None, 0, "akt.txt", b"tresc")
    # Crash after the database was rewrapped, before the OS secret was replaced.
    monkeypatch.setattr(recovery, "replace_secret", lambda *a: (_ for _ in ()).throw(OSError("power loss")))
    with pytest.raises(OSError):
        recovery.rotate_master(home)
    monkeypatch.undo()
    with pytest.raises(InvalidTag):
        Vault(home, read_secret(home, "vault.key")).get(doc)
    assert recovery.finish_interrupted_rotation(home)
    assert Vault(home, read_secret(home, "vault.key")).get(doc)[2] == b"tresc"
    assert not recovery.enrolled(home)  # stale code removed; operator issues a new one
    assert not recovery.finish_interrupted_rotation(home)

    # Crash before the rewrap: nothing changes.
    code = recovery.enroll(home)
    monkeypatch.setattr(Vault, "rotate", lambda *a: (_ for _ in ()).throw(OSError("power loss")))
    with pytest.raises(OSError):
        recovery.rotate_master(home)
    monkeypatch.undo()
    assert recovery.finish_interrupted_rotation(home)
    assert Vault(home, read_secret(home, "vault.key")).get(doc)[2] == b"tresc"
    backup = tmp_path / "k.notarai-backup"
    recovery.backup(home, backup)
    assert recovery.restore(backup, tmp_path / "z", code)["documents"] == 1


def test_cli_backup_and_restore(tmp_path, monkeypatch, capsys):
    home, vault = new_home(tmp_path)
    vault.put(None, 0, "akt.txt", b"tresc")
    monkeypatch.setenv("NOTARAI_V2_HOME", str(home))
    assert recovery.main(["enroll"]) == 0
    code = capsys.readouterr().out.strip().splitlines()[-1]
    assert recovery.main(["verify"]) == 0
    backup = tmp_path / "cli.notarai-backup"
    assert recovery.main(["backup", str(backup)]) == 0
    assert recovery.main(["backup", str(backup)]) == 1
    monkeypatch.setenv("NOTARAI_V2_HOME", str(tmp_path / "restored"))
    monkeypatch.setenv("NOTARAI_V2_RECOVERY_CODE", code)
    capsys.readouterr()
    assert recovery.main(["restore", str(backup)]) == 0
    assert code not in capsys.readouterr().out


def test_key_rotation_is_refused_while_the_worker_serves(tmp_path):
    from fastapi.testclient import TestClient

    from worker.api import create_app

    home, vault = new_home(tmp_path)
    recovery.enroll(home)
    with TestClient(create_app(home)):                 # lifespan running = worker serving
        with pytest.raises(recovery.RecoveryError) as error:
            recovery.rotate_master(home)
        assert "Zamknij NotarAI" in str(error.value)
    recovery.rotate_master(home)                       # allowed once it has stopped


def test_moving_a_document_between_cases_in_the_database_breaks_its_key(tmp_path):
    home, vault = new_home(tmp_path)
    doc, _ = vault.put(None, 0, "akt.txt", b"tresc", case="sprawa-1")
    with sqlite3.connect(home / "vault.sqlite3") as db:
        db.execute("UPDATE documents SET case_id='sprawa-2'")
    with pytest.raises(InvalidTag):
        vault.get(doc)
    with pytest.raises(InvalidTag):
        vault.summaries(cases={"sprawa-2"})


def test_failed_restore_leaves_no_key_behind(tmp_path, monkeypatch):
    home, vault = new_home(tmp_path)
    code = recovery.enroll(home)
    vault.put(None, 0, "akt.txt", b"x")
    backup = tmp_path / "k.notarai-backup"
    recovery.backup(home, backup)
    real = recovery.write_new_secret

    def failing(target, name, data):
        if name == "api.token":
            raise OSError("disk full")
        real(target, name, data)
    monkeypatch.setattr(recovery, "write_new_secret", failing)
    with pytest.raises(OSError):
        recovery.restore(backup, tmp_path / "new", code)
    assert list((tmp_path / "new").iterdir()) == []


def test_case_parties_are_encrypted_and_survive_rotation_and_restore(tmp_path):
    home, vault = new_home(tmp_path)
    code = recovery.enroll(home)
    vault.put(None, 0, "akt.txt", b"x", case="sprawa-1")
    assert vault.set_parties("sprawa-1", ["Jan  Kowalski", "Jan Kowalski", "", "Anna Nowak"]) == ["Jan Kowalski", "Anna Nowak"]
    assert b"Kowalski" not in (home / "vault.sqlite3").read_bytes()
    assert vault.parties("inna") == [] and vault.parties(None) == []
    with pytest.raises(ValueError):
        vault.set_parties("../x", ["a"])
    code = recovery.rotate_master(home)
    assert Vault(home, read_secret(home, "vault.key")).parties("sprawa-1") == ["Jan Kowalski", "Anna Nowak"]
    backup = tmp_path / "k.notarai-backup"
    recovery.backup(home, backup)
    recovery.restore(backup, tmp_path / "new", code)
    assert Vault(tmp_path / "new", read_secret(tmp_path / "new", "vault.key")).parties("sprawa-1") == ["Jan Kowalski", "Anna Nowak"]
