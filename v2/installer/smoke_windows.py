"""Exercise the shipped installer using a disposable Windows test profile."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from playwright.sync_api import expect, sync_playwright

DOCUMENT = "synthetic-preview.txt"
CONTENT = "Fikcyjny dokument testowy V2."
QUIET_SETUP = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]


@contextmanager
def running_preview(app_dir: Path, log: Path):
    command = [
        str(app_dir / "runtime" / "python.exe"), "-X", "utf8",
        str(app_dir / "launch.py"), "--no-browser",
    ]
    with log.open("wb") as output, subprocess.Popen(
        command, cwd=app_dir, stdout=output, stderr=subprocess.STDOUT,
    ) as worker:
        try:
            deadline = monotonic() + 20
            while monotonic() < deadline and worker.poll() is None:
                lines = log.read_text(encoding="utf-8").splitlines()
                url = next((line.removeprefix("Pocket: ") for line in lines if line.startswith("Pocket: ")), "")
                code = next((line.removeprefix("Kod parowania: ") for line in lines
                             if line.startswith("Kod parowania: ")), "")
                if re.fullmatch(r"http://127\.0\.0\.1:[0-9]+/v2/pocket", url) and code:
                    yield url, code
                    return
                sleep(0.1)
            raise RuntimeError(f"Preview failed to start, exit code {worker.poll()}.")
        finally:
            if worker.poll() is None:
                worker.terminate()
                worker.wait(timeout=10)


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
    if app_dir.exists() or vault.exists():
        raise RuntimeError("Installer smoke test needs a fresh Windows test profile.")

    try:
        subprocess.run([str(installer), *QUIET_SETUP], check=True, timeout=120)
        assert (app_dir / "runtime" / "python.exe").is_file()
        print("EXE installed in the current Windows profile.", flush=True)
        with TemporaryDirectory() as work, sync_playwright() as playwright:
            log = Path(work) / "preview.log"
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            try:
                with running_preview(app_dir, log) as (url, code):
                    page = paired_pocket(browser, url, code)
                    page.get_by_role("button", name="Nowy dokument tekstowy").click()
                    page.get_by_label("Nazwa dokumentu tekstowego").fill(DOCUMENT)
                    page.get_by_label("Treść", exact=True).fill(CONTENT)
                    page.get_by_role("button", name="Zapisz nową wersję").click()
                    expect(page.get_by_role("status")).to_have_text("Zapisano wersję 1.")
                    page.close()

                with running_preview(app_dir, log) as (url, code):
                    page = paired_pocket(browser, url, code)
                    page.get_by_role("button", name=f"{DOCUMENT} · wersja 1").click()
                    expect(page.get_by_label("Treść", exact=True)).to_have_value(CONTENT)
                    page.close()
            finally:
                browser.close()
        assert (vault / "vault.key.dpapi").is_file()
        assert (vault / "api.token.dpapi").is_file()
        assert CONTENT.encode("utf-8") not in (vault / "vault.sqlite3").read_bytes()
        print("Edge paired, saved a synthetic document, and read it after restart.", flush=True)
    finally:
        uninstall = app_dir / "unins000.exe"
        if uninstall.is_file():
            subprocess.run([str(uninstall), *QUIET_SETUP], check=True, timeout=120)

    assert not (app_dir / "runtime" / "python.exe").exists()
    assert (vault / "vault.sqlite3").is_file()
    print("Uninstall removed program files and preserved the local test vault.", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(strict=True))
