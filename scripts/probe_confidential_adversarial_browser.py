"""SEC-08 local hostile HTML / JavaScript smoke; never connects to Internet.

Proof scope: only Playwright interception against a fictional loopback collector.
Independent Nitro ENI/DNS/host/KMS evidence remains BLOCKED.
"""
from __future__ import annotations

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from confidential.form_engine import TrustedForm, fill_form

MARKER = "SYNTHETIC-CANARY-NOT-A-PERSON"
HTML = b'''<!DOCTYPE html><html><body>
<form id="frm" action="/leak" method="POST">
<input id="name" name="name">
<button id="send" type="submit">send</button>
</form>
<script>
document.querySelector('#name').addEventListener('input', function() {
  const v = encodeURIComponent(this.value);
  fetch('/leak?data=' + v).catch(()=>{});
  fetch('/leak', {method:'POST', body:v}).catch(()=>{});
  const image = new Image(); image.src = '/leak.gif?d=' + v;
  try { navigator.sendBeacon('/leak', v); } catch (_) {}
  try { document.querySelector('#frm').requestSubmit(); } catch (_) {}
});
</script></body></html>'''


class Collector(BaseHTTPRequestHandler):
    attempted = 0

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(HTML)))
            self.end_headers()
            self.wfile.write(HTML)
            return
        type(self).attempted += 1
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        type(self).attempted += 1
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt, *args):
        pass  # no URLs or synthetic marker in test logs


async def probe():
    from playwright.async_api import async_playwright

    Collector.attempted = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), Collector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = "http://127.0.0.1:" + str(server.server_port)
        form = TrustedForm("hostile-local", url + "/", (url,),
                           {"name": "#name"}, "#send")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                accept_downloads=False, service_workers="block", permissions=[])
            try:
                page = await context.new_page()
                answer = await fill_form(
                    page, form, {"name": MARKER}, job_id="synthetic",
                    execution_mode="auto", loopback_for_tests=True)
                await page.wait_for_timeout(250)
                assert answer.submitted is False
                assert await page.locator("#name").input_value() == MARKER
                assert Collector.attempted == 0, "hostile page reached collector"
                print("PASS: hostile page GET/POST/beacon/image/form writes blocked")
            finally:
                await context.close()
                await browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    asyncio.run(probe())
