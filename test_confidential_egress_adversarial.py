"""SEC-08 adversarial fixture tests; NOT a real Nitro network audit.

Canary below is synthetic, never customer data. A passing offline test does
not satisfy K6 hardware/host/DNS/KMS/egress evidence.
"""
import asyncio
from types import SimpleNamespace

import pytest

from confidential.egress_guard import EgressDenied, PreviewEgressGuard
from confidential.form_engine import fill_form
from test_confidential import Page, Route, form
from test_confidential_egress import check, synthetic

MARKER = "SYNTHETIC-CANARY-NOT-CUSTOMER-DATA"
URL = "https://forms.example.test/app"


class Probe:
    def __init__(self, url=URL, method="GET", headers=None, post_data=None):
        self.request = SimpleNamespace(
            url=url, method=method, headers=headers or {}, post_data=post_data)
        self.action = None
        self.sent_headers = None

    async def abort(self):
        self.action = "abort"

    async def continue_(self, **kwargs):
        self.action = "continue"
        self.sent_headers = kwargs.get("headers")


def call(guard, request):
    asyncio.run(guard.intercept(request))
    return request


def test_one_fictional_get_passes_only_before_secret_is_filled():
    guard = PreviewEgressGuard(URL)
    r = call(guard, Probe(headers={"X-Leak": MARKER, "Referer": MARKER}))
    assert r.action == "continue"
    assert r.sent_headers == {"accept": "text/html"}
    assert MARKER not in str(r.sent_headers)
    guard.lock()
    assert call(guard, Probe()).action == "abort"


@pytest.mark.parametrize("url,method,body", [
    (URL + "?value=" + MARKER, "GET", None),                # GET query
    (URL, "POST", MARKER),                                 # HTTP POST
    ("https://forms.example.test/redirect/" + MARKER, "GET", None),
    ("https://" + MARKER.lower() + ".leak.test/path", "GET", None), # DNS
    ("https://[2001:db8::1]/path", "GET", None),             # IPv6
    ("https://bucket.s3.eu-central-1.amazonaws.com/" + MARKER, "GET", None),
    ("https://llm.example.test/result/" + MARKER, "GET", None), # model output
    ("http://169.254.169.254/latest/meta-data", "GET", None),
    ("https://forms.example.test/" + MARKER, "GET", None), # URL path channel
    (URL, "PUT", None),
    (URL, "HEAD", None),
    (URL, "GET", MARKER),                                  # unexpected GET body
])
def test_unapproved_network_request_never_sent(url, method, body):
    r = call(PreviewEgressGuard(URL), Probe(url, method, post_data=body))
    assert r.action == "abort"
    assert r.sent_headers is None


def test_header_leakage_stripped_on_initial_navigation():
    r = call(PreviewEgressGuard(URL),
             Probe(headers={"Authorization": MARKER, "Cookie": MARKER,
                            "X-Exfil": MARKER}))
    assert r.action == "continue"
    assert r.sent_headers == {"accept": "text/html"}


@pytest.mark.parametrize("url", [
    "https://forms.example.test/app?query=1",
    "https://forms.example.test/app#fragment",
    "http://forms.example.test/app",
    "https://u:p@forms.example.test/app",
    "https://[::1]/app",
    "https://forms.example.test:8443/app",
])
def test_trusted_adapter_cannot_define_uncontrolled_destination(url):
    with pytest.raises(EgressDenied) as exc:
        PreviewEgressGuard(url)
    assert str(exc.value) == "preview egress rejected"


def test_auto_page_network_is_locked_before_confidential_values():
    async def scenario():
        page = Page()
        result = await fill_form(page, form(), {"name": MARKER}, job_id="synthetic")
        assert result.submitted is False
        for request in (
            Route(URL), Route(URL + "?q=" + MARKER),
            Route("https://forms.example.test/assets.js"),
            Route(URL, "POST"),
        ):
            await page.filter(request)
            assert request.action == "abort"
    asyncio.run(scenario())


def test_private_network_static_fixture_not_live_hardware_proof():
    check(synthetic())


def test_errors_do_not_echo_sensitive_marker():
    r = call(PreviewEgressGuard(URL), Probe(URL + "?q=" + MARKER))
    assert r.action == "abort"
    with pytest.raises(EgressDenied) as exc:
        PreviewEgressGuard("https://" + MARKER + "@not-allowed.test/x")
    assert MARKER not in str(exc.value)


def test_worker_exception_logging_never_prints_untrusted_marker(monkeypatch, capsys):
    import confidential.worker as worker

    def raise_unsafe():
        raise RuntimeError(MARKER)

    monkeypatch.setattr(worker, "_config", raise_unsafe)
    assert worker.main() == 1
    logs = capsys.readouterr()
    assert MARKER not in logs.out + logs.err
    assert "RuntimeError" in logs.err


def test_live_check_fails_closed_without_authenticated_nitro_probe():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/verify_confidential_egress_live.py", "--check"],
        check=False, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 2
    assert "BLOCKED" in result.stdout
    assert MARKER not in result.stdout + result.stderr
