"""Exercise the real CLI against a disposable window on a Windows desktop."""
import os
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from worker.connect import Router, State
from worker.winapp_adapter import WinApp


@pytest.mark.skipif(
    sys.platform != "win32" or not os.environ.get("NOTARAI_V2_TEST_WINAPP"),
    reason="requires an interactive Windows runner and an independently verified WinApp CLI",
)
def test_winapp_discovers_and_inspects_synthetic_window():
    title = f"NotarAI V2 synthetic test {uuid4()}"
    router = Router([WinApp(os.environ["NOTARAI_V2_TEST_WINAPP"])])
    program = (
        "import sys, tkinter as tk;"
        "root = tk.Tk(); root.title(sys.argv[1]); root.geometry('320x120');"
        "tk.Label(root, text='Synthetic V2 label').pack(); root.mainloop()"
    )
    with subprocess.Popen([sys.executable, "-c", program, title]) as fixture:
        try:
            deadline = time.monotonic() + 25
            while fixture.poll() is None and time.monotonic() < deadline:
                result = router.run("list_windows", {})
                assert result.state is State.VERIFIED
                windows = result.data
                assert isinstance(windows, list), "WinApp v0.8.0 emits a window array"
                for window in windows:
                    if window.get("processId") == fixture.pid and window.get("title") == title:
                        hwnd = window["hwnd"]
                        result = router.run("inspect_window", {"hwnd": hwnd})
                        assert result.state is State.VERIFIED
                        assert result.data["windows"][0]["title"] == title
                        return
                time.sleep(0.25)
            pytest.fail("WinApp did not find the disposable window on the runner desktop")
        finally:
            fixture.terminate()
