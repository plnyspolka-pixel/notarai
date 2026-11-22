"""Local-only form automation exercise; no official portals or real client data.

Install Chromium with: python -m playwright install chromium
Run: python -m confidential.demo_browser
"""
from __future__ import annotations

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from confidential.form_engine import TrustedForm, fill_form


HTML = b"""<!doctype html><html><body>
<form action="/done" method="POST">
<label for="name">Name</label><input id="name" name="name">
<label for="ref">Reference</label><input id="ref" name="ref">
<button id="submit" type="submit">Send fictional form</button>
</form>
<script>
// An explicitly malicious fictional form: input listeners attempt to export
// values using a same-origin GET (no HTTP POST). AUTO must block this too.
document.querySelector("#name").addEventListener("input", event => {
  fetch("/leak?value=" + encodeURIComponent(event.target.value))
    .catch(() => {});
});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    post_count = 0
    leak_count = 0

    def do_GET(self):
        if self.path.startswith("/leak?"):
            Handler.leak_count += 1
            self.send_response(204)
            self.end_headers()
            return
        if self.path != "/":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(HTML)))
        self.end_headers()
        self.wfile.write(HTML)

    def do_POST(self):
        Handler.post_count += 1
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Fictional test submitted")

    def log_message(self, fmt, *args):
        pass  # never print form values to logs


async def main():
    from playwright.async_api import async_playwright
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        Handler.post_count = 0
        Handler.leak_count = 0
        url = "http://127.0.0.1:" + str(server.server_port)
        template = TrustedForm(
            "local-demo", url + "/", (url,), {"name": "#name", "reference": "#ref"}, "#submit"
        )
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=False, service_workers="block")
            page = await context.new_page()
            result = await fill_form(
                page, template,
                {"name": "Fictional Person", "reference": "DEMO-123"},
                job_id="demo-1", loopback_for_tests=True,
            )
            assert not result.submitted
            assert await page.locator("#name").input_value() == "Fictional Person"
            # The hostile input listener MUST be denied by the context route
            # before any typed field value can reach the fixture server.
            await page.wait_for_timeout(100)
            assert Handler.leak_count == 0, "GET exfiltration reached the server"
            # AUTO is the default. Even a physical click and a scripted
            # POST must not reach the local test server.
            Handler.post_count = 0
            await page.locator("#submit").click(timeout=10000)
            blocked = await page.evaluate("""async () => {
                try {
                    await fetch("/done", {method: "POST", body: "SYNTHETIC"});
                    return false;
                } catch (_) { return true; }
            }""")
            assert blocked and Handler.post_count == 0
            get_blocked = await page.evaluate("""async () => {
                try {
                    await fetch("/leak?value=FICTIONAL-SECRET", {method: "GET"});
                    return false;
                } catch (_) { return true; }
            }""")
            assert get_blocked and Handler.leak_count == 0
            await context.close()
            await browser.close()
        print("Local AUTO preview passed: form filled; GET exfiltration and POST blocked")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    asyncio.run(main())
