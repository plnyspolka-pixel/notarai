"""Small code updates: checked, verified, staged, swapped in at the next start; never half-applied."""
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from worker.updater import Updater, version_tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "installer"))
import apply_update  # noqa: E402

URL = "https://pobieranie.example/aktualizacja.json"


def package(version="2.4.1", extra=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("wersja.json", json.dumps({"version": version, "runtime": "lib-1"}))
        archive.writestr("worker/__init__.py", "")
        archive.writestr("worker/nowy.py", "WERSJA = '%s'\n" % version)
        archive.writestr("launch.py", "# nowy\n")
        for name, body in (extra or {}).items():
            archive.writestr(name, body)
    return out.getvalue()


def server(files):
    asked = []

    def fetch(url, limit):
        asked.append(url)
        body = files[url.rsplit("/", 1)[-1]]
        if len(body) > limit:
            raise AssertionError("limit")
        return body
    fetch.asked = asked
    return fetch


def install(tmp_path, version="2.4.0"):
    app = tmp_path / "app"
    (app / "worker").mkdir(parents=True)
    (app / "worker" / "stary.py").write_text("STARY = True\n")
    (app / "launch.py").write_text("# stary\n")
    (app / "wersja.json").write_text(json.dumps({"version": version, "runtime": "lib-1"}))
    return app


def manifest(data, version="2.4.1", runtime="lib-1", **change):
    return json.dumps({"version": version, "runtime": runtime, "file": f"NotarAI-V2-aktualizacja-{version}.zip",
                       "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), **change}).encode()


def test_versions_compare_as_numbers():
    assert version_tuple("2.10.0") > version_tuple("2.9.9")
    with pytest.raises(ValueError):
        version_tuple("2.4; rm")


def test_a_newer_package_is_verified_and_staged_then_swapped_in(tmp_path):
    app = install(tmp_path)
    data = package()
    fetch = server({"aktualizacja.json": manifest(data), "NotarAI-V2-aktualizacja-2.4.1.zip": data})
    updater = Updater(app, URL, fetch=fetch)
    state = updater.check()
    assert state["available"] == "2.4.1" and state["ready"] == "2.4.1" and state["error"] is None
    assert (app / "launch.py").read_text() == "# stary\n"            # nothing replaced while running
    assert updater.check()["ready"] == "2.4.1" and len(fetch.asked) == 3   # staged once, not downloaded again
    assert apply_update.apply(app, tmp_path / "lock", lambda f: True) == "2.4.1"
    assert (app / "launch.py").read_text() == "# nowy\n" and (app / "worker" / "nowy.py").is_file()
    assert not (app / "worker" / "stary.py").exists() and json.loads((app / "wersja.json").read_text())["version"] == "2.4.1"
    assert Updater(app, URL, fetch=fetch).check()["available"] is None     # now the newest


def test_nothing_is_swapped_while_the_worker_runs(tmp_path):
    app = install(tmp_path)
    data = package()
    Updater(app, URL, fetch=server({"aktualizacja.json": manifest(data), "NotarAI-V2-aktualizacja-2.4.1.zip": data})).check()
    assert apply_update.apply(app, tmp_path / "lock", lambda f: False) is None
    assert (app / "launch.py").read_text() == "# stary\n" and (app / "aktualizacja" / "gotowa.json").is_file()


@pytest.mark.parametrize("problem", ["checksum", "size", "foreign file", "escape", "wrong version", "bad name"])
def test_a_bad_package_is_refused_and_the_old_program_stays(tmp_path, problem):
    app = install(tmp_path)
    data = package(extra={"evil.exe": "x"} if problem == "foreign file" else
                   {"worker/../../evil.py": "x"} if problem == "escape" else None)
    if problem == "wrong version":
        data = package(version="2.4.2")
    change = {"sha256": "0" * 64} if problem == "checksum" else {"size": len(data) + 1} if problem == "size" else \
        {"file": "../x.zip"} if problem == "bad name" else {}
    files = {"aktualizacja.json": manifest(data, **change), "NotarAI-V2-aktualizacja-2.4.1.zip": data, "x.zip": data}
    state = Updater(app, URL, fetch=server(files)).check()
    assert state["ready"] is None and "nie instaluję" in state["error"]
    assert apply_update.apply(app, tmp_path / "lock", lambda f: True) is None
    assert (app / "launch.py").read_text() == "# stary\n"


def test_new_libraries_need_the_full_installer(tmp_path):
    app = install(tmp_path)
    data = package()
    state = Updater(app, URL, fetch=server({"aktualizacja.json": manifest(data, runtime="lib-2")})).check()
    assert state["full_installer"] and state["ready"] is None


def test_offline_is_a_quiet_later(tmp_path):
    def offline(url, limit):
        raise OSError("no network")
    state = Updater(install(tmp_path), URL, fetch=offline).check()
    assert state["error"] == "Nie udało się sprawdzić aktualizacji. Spróbuję później."


def test_a_failed_swap_puts_the_old_program_back(tmp_path, monkeypatch):
    app = install(tmp_path)
    data = package()
    Updater(app, URL, fetch=server({"aktualizacja.json": manifest(data), "NotarAI-V2-aktualizacja-2.4.1.zip": data})).check()
    real = Path.rename

    def flaky(self, target):
        if self.name == "worker" and "nowa" in str(self):
            raise OSError("file in use")
        return real(self, target)
    monkeypatch.setattr(Path, "rename", flaky)
    assert apply_update.apply(app, tmp_path / "lock", lambda f: True) is None
    monkeypatch.undo()
    assert (app / "launch.py").read_text() == "# stary\n" and (app / "worker" / "stary.py").is_file()
    assert not (app / "aktualizacja" / "gotowa.json").exists()        # a broken package cannot block every start


def test_the_panel_offers_the_update_and_restarts_only_after_a_yes(tmp_path):
    from worker.api import create_app
    from worker.init_vault import initialize

    app_dir = install(tmp_path)
    data = package()
    updater = Updater(app_dir, URL, fetch=server({"aktualizacja.json": manifest(data),
                                                  "NotarAI-V2-aktualizacja-2.4.1.zip": data}))
    restarted = []
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home, updater=updater, restarter=lambda: restarted.append(True)))
    blocks = client.post("/v2/chat", headers=admin, json={"text": "aktualizacja"}).json()["blocks"]
    assert "Zainstalowana wersja: 2.4.0. Pobrałem aktualizację 2.4.1" in blocks[0]["text"]
    hello = client.post("/v2/chat", headers=admin, json={"hello": True}).json()["blocks"]
    assert any("Gotowa aktualizacja programu do wersji 2.4.1" in b.get("text", "") for b in hello)
    asked = client.post("/v2/chat", headers=admin, json={"text": "zainstaluj aktualizację"}).json()["blocks"]
    assert asked[0]["type"] == "confirm" and not restarted
    client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"]})
    assert restarted == [True]
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": "write"}).json()["code"]
    phone = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}
    said = client.post("/v2/chat", headers=phone, json={"text": "zainstaluj aktualizację"}).json()["blocks"]
    assert all(b["type"] != "confirm" for b in said)


def test_a_development_copy_does_not_update_itself(tmp_path):
    assert Updater(tmp_path, URL, fetch=lambda u, l: b"").check()["error"].startswith("Ta kopia programu")
