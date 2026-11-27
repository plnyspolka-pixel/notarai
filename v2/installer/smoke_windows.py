"""Exercise the shipped installer using a disposable Windows test profile."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from playwright.sync_api import expect, sync_playwright

from preview_instance import discover

DOCUMENT = "synthetic-preview.txt"
CONTENT = "Fikcyjny dokument testowy V2."
QUIET_SETUP = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
CODE_LABEL = "Kod parowania: "


def launch_command(app_dir, *options):
    return [
        str(app_dir / "runtime" / "python.exe"), "-X", "utf8",
        str(app_dir / "launch.py"), "--no-browser", *options,
    ]


def displayed_code(output):
    return next((line.removeprefix(CODE_LABEL) for line in output.splitlines()
                 if line.startswith(CODE_LABEL)), "")


@contextmanager
def running_preview(app_dir: Path, state: Path, log: Path):
    with log.open("wb") as output, subprocess.Popen(
        launch_command(app_dir), cwd=app_dir, stdout=output, stderr=subprocess.STDOUT,
    ) as worker:
        try:
            deadline = monotonic() + 20
            while monotonic() < deadline and worker.poll() is None:
                url = discover(state)
                code = displayed_code(log.read_text(encoding="utf-8", errors="replace"))
                if url and code:
                    yield url, code
                    return
                sleep(0.1)
            raise RuntimeError(f"Preview failed to start, exit code {worker.poll()}.")
        finally:
            if worker.poll() is None:
                worker.terminate()
                worker.wait(timeout=10)
            if sys.exc_info()[0] is not None:
                for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                    if not line.startswith(CODE_LABEL):
                        print(line, file=sys.stderr)


def paired_pocket(browser, url, code):
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="NotarAI Pocket")).to_be_visible()
    page.get_by_label("Kod parowania").fill(code)
    page.get_by_role("button", name="Połącz").click()
    expect(page.get_by_role("status")).to_have_text("Połączono z prawem zapisu.")
    return page


def main(installer: Path) -> None:
    local = Path(os.environ["LOCALAPPDATA"])
    app_dir = local / "Programs" / "NotarAI V2 Preview"
    vault = local / "NotarAI" / "V2-preview"
    state = local / "NotarAI" / "V2-preview-runtime" / "instance.json"
    shortcuts = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "NotarAI V2 Preview"
    if app_dir.exists() or vault.exists() or state.exists():
        raise RuntimeError("Installer smoke test needs a fresh Windows test profile.")

    try:
        subprocess.run([str(installer), *QUIET_SETUP], check=True, timeout=120)
        assert (app_dir / "runtime" / "python.exe").is_file()
        assert (shortcuts / "NotarAI.lnk").is_file()
        startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        assert (startup / "NotarAI w tle.lnk").is_file()
        assert (app_dir / "runtime" / "pythonw.exe").is_file()
        print("EXE installed in the current Windows profile with the NotarAI and background shortcuts.", flush=True)
        with TemporaryDirectory() as work, sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            log = Path(work) / "preview.log"
            try:
                with running_preview(app_dir, state, log) as (url, old_code):
                    initial = json.loads(state.read_text(encoding="ascii"))
                    repeated = subprocess.run(
                        launch_command(app_dir), cwd=app_dir, capture_output=True,
                        text=True, check=True, timeout=10,
                    )
                    assert repeated.stdout.strip() == f"Pocket: {url}"

                    rotation = subprocess.run(
                        launch_command(app_dir, "--new-code"), cwd=app_dir, capture_output=True,
                        text=True, check=True, timeout=10,
                    )
                    code = displayed_code(rotation.stdout)
                    assert code and code != old_code
                    assert json.loads(state.read_text(encoding="ascii")) == initial
                    session = browser.new_context()
                    try:
                        redeem = url.removesuffix("/pocket") + "/devices/redeem"
                        assert session.request.post(redeem, data={"code": old_code}).status == 403
                    finally:
                        session.close()
                    print("Duplicate launch and code replacement reused the running worker; the old code was rejected.", flush=True)

                    page = paired_pocket(browser, url, code)
                    page.get_by_role("button", name="Nowy dokument tekstowy").click()
                    page.get_by_label("Nazwa dokumentu tekstowego").fill(DOCUMENT)
                    page.get_by_label("Treść", exact=True).fill(CONTENT)
                    page.get_by_role("button", name="Zapisz nową wersję").click()
                    expect(page.get_by_role("status")).to_have_text("Zapisano wersję 1.")
                    page.close()

                assert state.is_file(), "a forced exit should leave the stale instance file"
                with running_preview(app_dir, state, log) as (url, code):
                    assert json.loads(state.read_text(encoding="ascii"))["nonce"] != initial["nonce"]
                    page = paired_pocket(browser, url, code)
                    page.get_by_role("button", name=f"{DOCUMENT} · wersja 1").click()
                    expect(page.get_by_label("Treść", exact=True)).to_have_value(CONTENT)
                    page.close()
            finally:
                browser.close()
        assert (vault / "vault.key.dpapi").is_file()
        assert (vault / "api.token.dpapi").is_file()
        assert CONTENT.encode("utf-8") not in (vault / "vault.sqlite3").read_bytes()
        print("Edge reopened the synthetic document after a forced exit and worker restart.", flush=True)
    finally:
        uninstall = app_dir / "unins000.exe"
        if uninstall.is_file():
            subprocess.run([str(uninstall), *QUIET_SETUP], check=True, timeout=120)

    assert not (app_dir / "runtime" / "python.exe").exists()
    assert not (shortcuts / "NotarAI.lnk").exists()
    assert (vault / "vault.sqlite3").is_file()
    print("Uninstall removed program files and shortcuts and preserved the local test vault.", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(strict=True))
