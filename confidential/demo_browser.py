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
</form></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(HTML)))
        self.end_headers()
        self.wfile.write(HTML)

    def do_POST(self):
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
            async def approved(job, form, digest):
                return job == "demo-1" and form == "local-demo"
            result = await fill_form(
                page, template,
                {"name": "Fictional Person", "reference": "DEMO-123"},
                job_id="demo-1", submit=True, approve=approved,
                loopback_for_tests=True,
            )
            assert result.submitted
            await context.close()
            await browser.close()
        print("Local browser form demo passed (no customer data)")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    asyncio.run(main())
