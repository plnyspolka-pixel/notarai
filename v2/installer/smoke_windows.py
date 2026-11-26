"""Exercise the shipped installer using a disposable Windows test profile."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryFile
from time import monotonic, sleep

from playwright.sync_api import expect, sync_playwright
import win32con
import win32gui
import win32process

from preview_instance import discover
from preview_window import CODE, NEW_CODE, TITLE

DOCUMENT = "synthetic-preview.txt"
CONTENT = "Fikcyjny dokument testowy V2."
QUIET_SETUP = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]


def launch_command(app_dir, executable):
    return [
        str(app_dir / "runtime" / executable), "-X", "utf8",
        str(app_dir / "launch.py"), "--no-browser",
    ]


@contextmanager
def running_preview(app_dir: Path, state: Path, *, simulate_crash=False):
    with TemporaryFile() as output, subprocess.Popen(
        launch_command(app_dir, "pythonw.exe"), cwd=app_dir, stdout=output, stderr=output,
    ) as worker:
        window = 0
        try:
            deadline = monotonic() + 20
            while monotonic() < deadline and worker.poll() is None:
                found = win32gui.FindWindow("#32770", TITLE)
                if found and win32process.GetWindowThreadProcessId(found)[1] == worker.pid:
                    window = found
                    url = discover(state)
                    if url and win32gui.GetDlgItemText(window, CODE):
                        yield url, window
                        return
                sleep(0.1)
            raise RuntimeError(f"Preview window or server failed to start, exit code {worker.poll()}.")
        finally:
            if worker.poll() is None:
                if simulate_crash or not window:
                    worker.terminate()
                    worker.wait(timeout=10)
                else:
                    win32gui.PostMessage(window, win32con.WM_CLOSE, 0, 0)
                    try:
                        assert worker.wait(timeout=10) == 0
                    except subprocess.TimeoutExpired:
                        worker.terminate()
                        worker.wait(timeout=5)
                        raise
            if sys.exc_info()[0] is not None:
                output.seek(0)
                print(output.read().decode("utf-8", errors="replace"), file=sys.stderr)


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
    if app_dir.exists() or vault.exists() or state.exists():
        raise RuntimeError("Installer smoke test needs a fresh Windows test profile.")

    try:
        subprocess.run([str(installer), *QUIET_SETUP], check=True, timeout=120)
        assert (app_dir / "runtime" / "python.exe").is_file()
        print("EXE installed in the current Windows profile.", flush=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            try:
                with running_preview(app_dir, state, simulate_crash=True) as (url, window):
                    initial_state = json.loads(state.read_text(encoding="ascii"))
                    old_code = win32gui.GetDlgItemText(window, CODE)
                    repeated = subprocess.run(
                        launch_command(app_dir, "python.exe"), cwd=app_dir, capture_output=True,
                        text=True, check=True, timeout=10,
                    )
                    assert repeated.stdout.strip() == f"Pocket: {url}"
                    assert json.loads(state.read_text(encoding="ascii")) == initial_state
                    assert win32gui.GetDlgItemText(window, CODE) == old_code
                    print("The second launcher reused the running worker and pairing code.", flush=True)

                    button = win32gui.GetDlgItem(window, NEW_CODE)
                    assert win32gui.GetWindowText(button) == "Nowy kod parowania"
                    win32gui.SendMessageTimeout(button, win32con.BM_CLICK, 0, 0, win32con.SMTO_ABORTIFHUNG, 5000)
                    deadline = monotonic() + 5
                    while (code := win32gui.GetDlgItemText(window, CODE)) == old_code and monotonic() < deadline:
                        sleep(0.05)
                    assert code and code != old_code, "the native button did not replace the displayed code"
                    session = browser.new_context()
                    try:
                        redeem = url.removesuffix("/pocket") + "/devices/redeem"
                        assert session.request.post(redeem, data={"code": old_code}).status == 403
                    finally:
                        session.close()
                    print("The native pairing button invalidated the previous code.", flush=True)

                    page = paired_pocket(browser, url, code)
                    page.get_by_role("button", name="Nowy dokument tekstowy").click()
                    page.get_by_label("Nazwa dokumentu tekstowego").fill(DOCUMENT)
                    page.get_by_label("Treść", exact=True).fill(CONTENT)
                    page.get_by_role("button", name="Zapisz nową wersję").click()
                    expect(page.get_by_role("status")).to_have_text("Zapisano wersję 1.")
                    page.close()

                assert state.is_file(), "a forced exit should leave the stale instance file"
                with running_preview(app_dir, state) as (url, window):
                    assert json.loads(state.read_text(encoding="ascii"))["nonce"] != initial_state["nonce"]
                    page = paired_pocket(browser, url, win32gui.GetDlgItemText(window, CODE))
                    page.get_by_role("button", name=f"{DOCUMENT} · wersja 1").click()
                    expect(page.get_by_label("Treść", exact=True)).to_have_value(CONTENT)
                    page.close()
                assert not state.exists(), "closing the window must remove the live instance file"
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
    assert (vault / "vault.sqlite3").is_file()
    print("Uninstall removed program files and preserved the local test vault.", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(strict=True))
