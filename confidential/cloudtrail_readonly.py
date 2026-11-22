"""SEC-07: paced, read-only CloudTrail LookupEvents calls.

AWS CloudTrail LookupEvents allows 2 requests/second per account/region.
Pacing prevents an evidence audit from failing simply because it looked up
several denied KMS events too quickly. Retrying ONLY recognized throttling
responses does not create resources, modify policies or decrypt anything.

Never return raw botocore exception strings (might contain sensitive IDs).
"""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping


class CloudTrailReadRejected(ValueError):
    """Fail closed on malformed events and non-throttling AWS errors."""


_THROTTLES = frozenset({
    "Throttling", "ThrottlingException", "ThrottledException",
    "TooManyRequestsException", "RequestLimitExceeded",
})


class PacedCloudTrail:
    """Per-account/region wrapper over the read-only LookupEvents API.

    Every account must have its own wrapper. Use the same instance throughout
    a given sequence of EventId and paginated lookup calls.
    """

    def __init__(self, client, *, min_interval: float = 0.55,
                 monotonic: Callable[[], float] | None = None,
                 sleep: Callable[[float], None] | None = None,
                 max_throttle_retries: int = 2):
        if not isinstance(min_interval, (float, int)) or not (
            0.5 <= min_interval <= 5.0
        ):
            raise CloudTrailReadRejected("invalid CloudTrail call rate")
        if type(max_throttle_retries) is not int or not (
            0 <= max_throttle_retries <= 4
        ):
            raise CloudTrailReadRejected("invalid throttle retry limit")
        self._client = client
        self._interval = min_interval
        self._clock = monotonic or time.monotonic
        self._sleep = sleep or time.sleep
        self._next_at = None
        self._retries = max_throttle_retries

    def lookup_events(self, **kwargs) -> dict:
        # Only allow the approved AWS read-only API argument names.
        if (not kwargs or
                not set(kwargs).issubset({
                    "LookupAttributes", "StartTime", "EndTime",
                    "MaxResults", "NextToken",
                })):
            raise CloudTrailReadRejected("unapproved CloudTrail read arguments")
        for attempt in range(self._retries + 1):
            current = self._clock()
            if self._next_at is not None and current < self._next_at:
                self._sleep(self._next_at - current)
            # Schedule a minimum gap even if the call raises or is throttled.
            self._next_at = self._clock() + self._interval
            try:
                response = self._client.lookup_events(**kwargs)
                if not isinstance(response, Mapping):
                    raise CloudTrailReadRejected("CloudTrail response invalid")
                events = response.get("Events")
                if not isinstance(events, list) or len(events) > 50:
                    raise CloudTrailReadRejected("CloudTrail events malformed")
                token = response.get("NextToken")
                if token is not None and (
                    not isinstance(token, str) or not token
                ):
                    raise CloudTrailReadRejected("CloudTrail paging token invalid")
                return dict(response)
            except CloudTrailReadRejected:
                raise
            except Exception as exc:
                error = getattr(exc, "response", None)
                code = ((error.get("Error") or {}).get("Code")
                        if isinstance(error, Mapping) else None)
                if code not in _THROTTLES or attempt == self._retries:
                    raise CloudTrailReadRejected(
                        "CloudTrail lookup failed or throttle retry exhausted"
                    ) from None
                # Next attempt is paced and bounded. boto3's own retry policy
                # may also apply; no unbounded exponential recursion.
                self._next_at = max(
                    self._next_at or self._clock(),
                    self._clock() + self._interval * (2 ** (attempt + 1)),
                )
        raise CloudTrailReadRejected("CloudTrail lookup unavailable")
