"""SEC-08 application-level AUTO preview egress gate (not a network firewall).

Independent VPC/host DNS, AWS API and Nitro controls still required.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


class EgressDenied(ValueError):
    """No attacker-controlled values in error messages."""


def _canonical(url: str, loopback: bool = False) -> str:
    if not isinstance(url, str) or len(url) > 2048:
        raise EgressDenied("preview egress rejected")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise EgressDenied("preview egress rejected") from None
    if not host or parts.username or parts.password or parts.query or parts.fragment:
        raise EgressDenied("preview egress rejected")
    if parts.scheme != "https":
        if not (loopback and parts.scheme == "http" and
                host in ("127.0.0.1", "localhost")):
            raise EgressDenied("preview egress rejected")
    if parts.scheme == "https" and port not in (None, 443):
        raise EgressDenied("preview egress rejected")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not host.isascii() or not all(
            c.isalnum() or c in ".-" for c in host
        ) or host.startswith("-") or ".." in host:
            raise EgressDenied("preview egress rejected")
    else:
        if not (loopback and host == "127.0.0.1"):
            raise EgressDenied("preview egress rejected")
    return parts.geturl()


class PreviewEgressGuard:
    """Only pinned initial GET before values are entered; then network lock.

    Browser routing is defense-in-depth only. Separate Nitro guest and parent
    network enforcement is mandatory. No external official portals enabled.
    """

    def __init__(self, trusted_url: str, *, loopback_for_tests: bool = False):
        self._url = _canonical(trusted_url, loopback_for_tests)
        self._loopback = loopback_for_tests
        self._locked = False

    def lock(self) -> None:
        self._locked = True

    def allows(self, url: str, method: str, post_data: object = None) -> bool:
        if self._locked or method != "GET" or post_data not in (None, b"", ""):
            return False
        try:
            return _canonical(url, self._loopback) == self._url
        except EgressDenied:
            return False

    def observed_page_is_trusted(self, url: str) -> bool:
        try:
            return _canonical(url, self._loopback) == self._url
        except EgressDenied:
            return False

    async def intercept(self, route) -> None:
        try:
            request = route.request
            ok = self.allows(request.url, request.method,
                             getattr(request, "post_data", None))
        except (AttributeError, ValueError, TypeError):
            ok = False
        if not ok:
            await route.abort()
            return
        # Browser may restore cookies, so ALL traffic must be locked BEFORE
        # filling confidential values. No dynamic URLs or custom headers.
        await route.continue_(headers={"accept": "text/html"})
