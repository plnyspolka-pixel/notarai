"""A small window on top of everything when the agent needs the notary (owner's decision 27.11.2026).

The agent works in the background; when it has a question, needs a login or something to approve, the notary
should not have to look for the NotarAI window. A small window appears in the top right corner, above all other
windows, with the exact question and its answers. What the notary picks there is handed to the chat as if it
had been picked in the main window, so the conversation stays the one record of what was asked and answered.

The window is a page served by this worker to this computer only, under a one-time address. It shows the same
text the chat shows; nothing is written to disk or to any log.
"""
import os
import secrets
import subprocess
import threading
import time
from pathlib import Path

TITLE = "NotarAI pyta"
TTL = 3600
WIDTH, HEIGHT = 470, 330

PAGE = Path(__file__).with_name("attention.html")       # its script and style are files of their own: the pages allow no inline code



class Attention:
    """Questions waiting for the notary, each under a one-time token, and the answers on their way to the chat."""

    def __init__(self, *, opener=None, enabled=lambda: True, clock=time.monotonic):
        self._opener, self._enabled, self._clock = opener, enabled, clock
        self._lock = threading.Lock()
        self._asked: dict[str, dict] = {}        # token -> {"owner", "text", "actions": [(label, turn)], "free", "expires"}
        self._inbox: dict[str, list] = {}        # owner -> turns for the chat, in order

    def ask(self, owner: str, text: str, actions: list, *, free: str | None = None, url=lambda token: "") -> str | None:
        """`actions`: (label, turn) where turn is what the chat gets: {"text": …} or {"confirm": …}.
        `free`: a prefix for the notary's own words (None: no text field). Returns the token, or None when off."""
        if not self._enabled() or not text.strip() or not (actions or free is not None):
            return None
        token = secrets.token_urlsafe(24)
        with self._lock:
            now = self._clock()
            self._asked = {k: v for k, v in self._asked.items() if v["expires"] > now and v["owner"] != owner}
            self._asked[token] = {"owner": owner, "text": text.strip()[:1500], "actions": list(actions)[:6], "free": free,
                                  "expires": now + TTL}
        if self._opener is not None:
            try:
                self._opener(url(token))
            except Exception:
                pass                              # the question is in the chat anyway
        return token

    def shown(self, token: str) -> dict | None:
        with self._lock:
            asked = self._asked.get(token)
            if asked is None or asked["expires"] <= self._clock():
                return None
            return {"text": asked["text"], "actions": [label for label, _ in asked["actions"]], "free": asked["free"] is not None}

    def answer(self, token: str, *, choice: int | None = None, words: str | None = None) -> bool:
        with self._lock:
            asked = self._asked.get(token)
            if asked is None or asked["expires"] <= self._clock():
                return False
            if choice is not None and 0 <= choice < len(asked["actions"]):
                turn = dict(asked["actions"][choice][1])
            elif words and words.strip() and asked["free"] is not None:
                turn = {"text": asked["free"] + " ".join(words.split())[:1000]}
            else:
                return False
            del self._asked[token]                # one answer for one question
            self._inbox.setdefault(asked["owner"], []).append(turn)
            return True

    def withdraw(self, owner: str) -> None:
        """The question was answered in the chat itself, or the work was stopped."""
        with self._lock:
            self._asked = {k: v for k, v in self._asked.items() if v["owner"] != owner}

    def collect(self, owner: str) -> list:
        with self._lock:
            return self._inbox.pop(owner, [])


def _find_edge() -> Path | None:
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            candidate = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if candidate.is_file():
                return candidate
    return None


def _keep_on_top(seconds: float = 12.0) -> None:
    """Find the little window by its title and put it above everything, without taking the keyboard away."""
    try:
        import win32con
        import win32gui
    except Exception:
        return
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = []
        try:
            win32gui.EnumWindows(lambda handle, _: found.append(handle)
                                 if win32gui.IsWindowVisible(handle) and win32gui.GetWindowText(handle).startswith(TITLE) else None, None)
            for handle in found:
                win32gui.SetWindowPos(handle, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
        except Exception:
            pass
        if found:
            return
        time.sleep(0.4)


def windows_popup(profile: Path):
    """The opener for an installed station: a small Edge app window in the top right corner, kept on top."""
    def open_(url: str) -> None:
        edge = _find_edge()
        if edge is None or not url:
            return
        try:
            import ctypes
            right = int(ctypes.windll.user32.GetSystemMetrics(0)) - WIDTH - 24
        except Exception:
            right = 800
        subprocess.Popen([str(edge), f"--app={url}", f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
                          f"--window-size={WIDTH},{HEIGHT}", f"--window-position={max(0, right)},24"], close_fds=True)
        threading.Thread(target=_keep_on_top, daemon=True).start()
    return open_
