"""Web pages: a browser window of its own that NotarAI fills.

The browser keeps its own profile next to the vault, so the notary signs in to a portal once
(ePUAP, Elektroniczne Księgi Wieczyste, CRBR…) and stays signed in. On Windows it is Edge,
which every office has; no browser is downloaded. All Playwright calls run on one thread,
because its objects belong to the thread that created them.
"""
import concurrent.futures
import os
import re
import threading
from pathlib import Path

from .autofill import Control, FillError

# Every visible, enabled form field and button, with the label a person would read next to it.
COLLECT = r"""
() => {
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const byIds = ids => clean(ids.split(/\s+/).map(id => (document.getElementById(id) || {}).textContent || '').join(' '));
  const before = el => {
    // Nearest text to the left on the same line, or just above: how forms without <label> look.
    const box = el.getBoundingClientRect(); let best = '', distance = 1e9;
    for (const node of document.querySelectorAll('label, span, div, td, th, p, b, strong, dt, legend')) {
      if (node.contains(el) || !visible(node)) continue;
      const own = clean([...node.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' '));
      if (!own || own.length > 120) continue;
      const r = node.getBoundingClientRect();
      const sameLine = r.bottom > box.top + 2 && r.top < box.bottom - 2 && r.right <= box.left + 4;
      const above = r.bottom <= box.top + 4 && r.left < box.right && r.right > box.left - 40 && box.top - r.bottom < 60;
      if (!sameLine && !above) continue;
      const d = sameLine ? box.left - r.right : 1000 + box.top - r.bottom;
      if (d < distance) { distance = d; best = own; }
    }
    return best;
  };
  const label = el => {
    if (el.getAttribute('aria-labelledby')) { const t = byIds(el.getAttribute('aria-labelledby')); if (t) return t; }
    if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'));
    if (el.id) { const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]'); if (l) return clean(l.textContent); }
    const wrap = el.closest('label'); if (wrap) return clean(wrap.textContent);
    return before(el) || clean(el.getAttribute('placeholder')) || clean(el.getAttribute('title')) || clean(el.name);
  };
  const out = []; let n = 0;
  for (const el of document.querySelectorAll('input, select, textarea, button, [role=button], a[role=button]')) {
    if (!visible(el) || el.disabled || el.readOnly && el.tagName !== 'BUTTON') continue;
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (['hidden', 'password', 'file'].includes(type)) continue;
    const id = 'n' + (n++);
    el.setAttribute('data-notarai', id);
    let kind = 'text', value = el.value || '', options = [];
    if (el.tagName === 'SELECT') { kind = 'select'; options = [...el.options].map(o => clean(o.textContent));
      value = el.selectedIndex >= 0 ? clean(el.options[el.selectedIndex].textContent) : ''; }
    else if (type === 'checkbox' || type === 'radio') { kind = 'check'; value = el.checked ? 'tak' : 'nie'; }
    else if (el.tagName === 'BUTTON' || ['submit', 'button', 'reset'].includes(type) || el.getAttribute('role') === 'button') {
      kind = 'button'; value = ''; }
    const text = kind === 'button' ? clean(el.textContent || el.value || el.getAttribute('aria-label')) : label(el);
    out.push({ id, kind, label: text, value, options });
  }
  return out;
}
"""
MARK = "el => { el.style.outline = '3px solid #0d6b57'; el.style.outlineOffset = '1px'; }"


def _default_executable():
    configured = os.environ.get("NOTARAI_V2_BROWSER")
    if configured:
        return configured, None
    if os.name == "nt":
        return None, "msedge"          # the Edge every Windows office already has
    for candidate in ("/opt/pw-browsers/chromium", "/usr/bin/chromium", "/usr/bin/google-chrome"):
        if Path(candidate).exists():
            return candidate, None
    return None, "chrome"


class Browser:
    """One persistent browser window. Thread-confined; every method hops onto that thread."""

    def __init__(self, profile: Path, *, headless: bool = False):
        self._profile, self._headless = Path(profile), headless
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="notarai-web")
        self._context = None
        self._playwright = None
        self._lock = threading.Lock()

    def _run(self, function, *args):
        try:
            return self._pool.submit(function, *args).result(timeout=120)
        except FillError:
            raise
        except Exception:
            raise FillError("Przeglądarka nie odpowiedziała. Sprawdź okno przeglądarki NotarAI i spróbuj ponownie.") from None

    # ---- on the browser thread
    def _page(self):
        if self._context is None or not self._context.pages:
            from playwright.sync_api import sync_playwright

            if self._playwright is None:
                self._playwright = sync_playwright().start()
            executable, channel = _default_executable()
            self._profile.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._context = self._playwright.chromium.launch_persistent_context(
                str(self._profile), headless=self._headless, executable_path=executable, channel=channel,
                viewport=None if not self._headless else {"width": 1280, "height": 900},
                args=["--no-first-run", "--no-default-browser-check"])
            self._context.set_default_timeout(15000)
        pages = [p for p in self._context.pages if not p.is_closed()]
        return pages[-1] if pages else self._context.new_page()

    def _open(self, url):
        page = self._page()
        page.goto(url, wait_until="domcontentloaded")
        page.bring_to_front()
        return page.url

    def _focus(self, address):
        page = self._page()
        if address and not page.url.startswith(("http://", "https://")):
            page.goto(address, wait_until="domcontentloaded")
        page.bring_to_front()

    def _controls(self):
        controls = []
        for frame in self._page().frames:          # official forms often live in frames
            try:
                found = frame.evaluate(COLLECT)
            except Exception:
                continue
            for item in found:
                controls.append(Control((frame, item["id"]), item["kind"], item["label"], item["value"], item["options"]))
        return controls

    @staticmethod
    def _locator(control):
        frame, ident = control.ref
        return frame.locator(f'[data-notarai="{ident}"]')

    def _type(self, control, value):
        locator = self._locator(control)
        locator.fill(value)
        locator.evaluate(MARK)

    def _choose(self, control, option):
        locator = self._locator(control)
        locator.select_option(label=option)
        locator.evaluate(MARK)

    def _check(self, control, on):
        locator = self._locator(control)
        locator.set_checked(on)
        locator.evaluate(MARK)

    def _read(self, control):
        locator = self._locator(control)
        if control.kind == "select":
            return locator.evaluate("el => el.selectedIndex >= 0 ? el.options[el.selectedIndex].textContent.trim() : ''")
        if control.kind == "check":
            return "tak" if locator.is_checked() else "nie"
        return locator.input_value()

    def _click(self, control):
        page = self._page()
        self._locator(control).click()
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass        # pages that keep polling never go idle; what is on screen now is what counts

    def _where(self):
        page = self._page()
        return re.sub(r"#.*$", "", page.url)

    def _snapshot(self):
        return self._page().screenshot(type="jpeg", quality=60, full_page=True)

    def _close(self):
        if self._context is not None:
            self._context.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._context = self._playwright = None

    def on_page(self, function, timeout: float = 240):
        """Run `function(page)` on the browser thread (a longer task such as a KRZ search)."""
        try:
            return self._pool.submit(lambda: function(self._page())).result(timeout=timeout)
        except FillError:
            raise
        except Exception:
            raise FillError("Przeglądarka nie odpowiedziała. Sprawdź okno przeglądarki NotarAI i spróbuj ponownie.") from None

    # ---- the target interface used by autofill.Autofill
    def open(self, url: str) -> str:
        if not re.fullmatch(r"https://[^\s]+|http://127\.0\.0\.1(:\d+)?/[^\s]*", url):
            raise FillError("Otwieram tylko adresy https://.")
        return self._run(self._open, url)

    def focus(self, address):
        return self._run(self._focus, address)

    def controls(self):
        return self._run(self._controls)

    def type(self, control, value):
        return self._run(self._type, control, value)

    def choose(self, control, option):
        return self._run(self._choose, control, option)

    def check(self, control, on):
        return self._run(self._check, control, on)

    def read(self, control):
        return self._run(self._read, control)

    def click(self, control):
        return self._run(self._click, control)

    def where(self):
        return self._run(self._where)

    def snapshot(self):
        return self._run(self._snapshot)

    def close(self):
        try:
            self._run(self._close)
        finally:
            self._pool.shutdown(wait=False)
