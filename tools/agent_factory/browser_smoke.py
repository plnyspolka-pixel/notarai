"""Synthetic-data-only Playwright smoke test. Not a general browser agent.

No persistent profile, cookies, logins, uploads, downloads, or external origins.
Requires playwright and Chromium installed locally.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit


class BrowserPolicyError(ValueError):
    pass


def local_origin(url: str) -> str:
    p = urlsplit(url)
    if (
        p.scheme != "http"
        or p.hostname not in {"localhost", "127.0.0.1", "::1"}
        or p.port is None
        or p.username is not None
        or p.password is not None
        or p.fragment
    ):
        raise BrowserPolicyError("Only local http://127.0.0.1:PORT test servers are allowed")
    return f"{p.scheme}://{p.netloc}"


def run(url: str, expected: str) -> int:
    allowed = local_origin(url)
    from playwright.sync_api import sync_playwright  # optional project dependency

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=False,
            service_workers="block",
            permissions=[],
        )

        def route_guard(route):
            request_url = route.request.url
            try:
                ok = local_origin(request_url) == allowed
            except BrowserPolicyError:
                ok = False
            if ok:
                route.continue_()
            else:
                route.abort()

        context.route("**/*", route_guard)
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            # Re-check final page URL in case of redirect.
            if local_origin(page.url) != allowed:
                raise BrowserPolicyError("Navigation changed origin")
            if expected not in page.locator("body").inner_text(timeout=5000):
                raise AssertionError(f"Expected text absent: {expected!r}")
            print("PASS: local browser smoke test")
            return 0
        finally:
            context.close()
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected", required=True)
    args = parser.parse_args()
    try:
        return run(args.url, args.expected)
    except (BrowserPolicyError, AssertionError, ImportError) as exc:
        print(f"BLOCKED/FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
