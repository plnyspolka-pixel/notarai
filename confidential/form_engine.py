"""Deterministic, site-scoped browser form filling with explicit approval.

No arbitrary scripts from an LLM, selectors chosen only by trusted adapters.
No automatic submission. This code is intended to execute in Nitro guest.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Awaitable, Callable, Mapping
from urllib.parse import urlsplit


class BlockedAction(ValueError):
    pass


def _origin(url: str, loopback_for_tests: bool = False) -> str:
    parts = urlsplit(url)
    if parts.username or parts.password or parts.fragment or not parts.hostname:
        raise BlockedAction("invalid browser destination")
    if parts.scheme != "https":
        if not (loopback_for_tests and parts.scheme == "http" and
                parts.hostname in ("127.0.0.1", "localhost")):
            raise BlockedAction("HTTPS required")
    return parts.scheme + "://" + parts.netloc.lower()


@dataclass(frozen=True)
class TrustedForm:
    form_id: str
    url: str
    allowed_origins: tuple[str, ...]
    selectors: Mapping[str, str]
    submit_selector: str | None = None

    def validate(self, loopback_for_tests: bool = False) -> None:
        if not self.form_id or not self.selectors:
            raise BlockedAction("incomplete trusted form")
        canonical_origins = {_origin(x, loopback_for_tests) for x in self.allowed_origins}
        if _origin(self.url, loopback_for_tests) not in canonical_origins:
            raise BlockedAction("form destination outside allowlist")
        if len(self.selectors) > 40 or not all(
            isinstance(k, str) and isinstance(v, str) and k and v and len(v) <= 500
            for k, v in self.selectors.items()
        ):
            raise BlockedAction("invalid trusted selectors")


@dataclass(frozen=True)
class FormResult:
    form_id: str
    filled_fields: int
    digest: str
    submitted: bool
    origin: str


Approval = Callable[[str, str, str], Awaitable[bool]]


async def fill_form(
    page,
    form: TrustedForm,
    values: Mapping[str, str],
    *,
    job_id: str,
    submit: bool = False,
    approve: Approval | None = None,
    loopback_for_tests: bool = False,
) -> FormResult:
    """External approve callback must validate a fresh user-signed approval.

    This function never issues an approval itself. The callback must verify
    the exact job_id + form_id + digest and reject replay; a Boolean supplied
    by an untrusted API request is NOT an authorization.
    """
    form.validate(loopback_for_tests)
    if not isinstance(job_id, str) or not job_id or len(job_id) > 100:
        raise BlockedAction("missing job identity")
    if set(values) != set(form.selectors) or any(
        not isinstance(v, str) or len(v) > 20000 for v in values.values()
    ):
        raise BlockedAction("untrusted or incomplete form values")
    allowed = {_origin(u, loopback_for_tests) for u in form.allowed_origins}

    async def restrict(route):
        try:
            requested_origin = _origin(route.request.url, loopback_for_tests)
        except BlockedAction:
            await route.abort()
            return
        if requested_origin in allowed:
            await route.continue_()
        else:
            await route.abort()

    await page.route("**/*", restrict)
    await page.goto(form.url, wait_until="domcontentloaded", timeout=30000)
    if _origin(page.url, loopback_for_tests) not in allowed:
        raise BlockedAction("destination redirected outside allowlist")
    for key, selector in form.selectors.items():
        await page.locator(selector).fill(values[key], timeout=10000)

    canonical = json.dumps(
        {"job_id": job_id, "form_id": form.form_id, "fields": dict(values)},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    did_submit = False
    if submit:
        if not form.submit_selector or approve is None:
            raise BlockedAction("submission requires signed user approval")
        if not await approve(job_id, form.form_id, digest):
            raise BlockedAction("user approval rejected")
        await page.locator(form.submit_selector).click(timeout=10000)
        did_submit = True
    return FormResult(form.form_id, len(values), digest, did_submit, _origin(page.url, loopback_for_tests))
