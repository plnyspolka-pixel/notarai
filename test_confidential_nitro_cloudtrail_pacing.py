"""SEC-07 CloudTrail pacing and fail-closed retries (no AWS calls)."""
import pytest

from confidential.cloudtrail_readonly import (
    CloudTrailReadRejected, PacedCloudTrail,
)


class Clock:
    def __init__(self):
        self.now = 10.0
        self.pauses = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        assert seconds >= 0
        self.pauses.append(seconds)
        self.now += seconds


class AwsThrottle(Exception):
    def __init__(self, code):
        super().__init__("raw_sensitive_details_must_not_leak")
        self.response = {"Error": {"Code": code}}


def test_four_calls_are_paced_below_two_per_second():
    clock = Clock()
    calls = []

    class Client:
        def lookup_events(self, **kwargs):
            calls.append(clock.now)
            return {"Events": []}

    wrapper = PacedCloudTrail(
        Client(), monotonic=clock.monotonic, sleep=clock.sleep,
    )
    for _ in range(4):
        assert wrapper.lookup_events(MaxResults=50) == {"Events": []}
    assert len(calls) == 4
    assert all(b - a >= 0.55 - 1e-8
               for a, b in zip(calls, calls[1:]))
    assert all(x > 0 for x in clock.pauses)


@pytest.mark.parametrize("code", [
    "Throttling", "ThrottlingException", "ThrottledException",
    "TooManyRequestsException", "RequestLimitExceeded",
])
def test_transient_throttling_is_retried_at_most_twice(code):
    clock = Clock()

    class Client:
        calls = 0

        def lookup_events(self, **kwargs):
            self.calls += 1
            if self.calls <= 2:
                raise AwsThrottle(code)
            return {"Events": []}

    client = Client()
    wrapper = PacedCloudTrail(
        client, monotonic=clock.monotonic, sleep=clock.sleep,
    )
    assert wrapper.lookup_events(MaxResults=50) == {"Events": []}
    assert client.calls == 3
    assert clock.pauses


def test_persistent_throttling_fails_closed_without_raw_details():
    clock = Clock()

    class Client:
        calls = 0

        def lookup_events(self, **kwargs):
            self.calls += 1
            raise AwsThrottle("ThrottlingException")

    client = Client()
    wrapper = PacedCloudTrail(
        client, monotonic=clock.monotonic, sleep=clock.sleep,
    )
    with pytest.raises(CloudTrailReadRejected) as exc:
        wrapper.lookup_events(MaxResults=50)
    assert client.calls == 3
    assert "raw_sensitive_details" not in str(exc.value)


def test_unauthorized_failures_are_not_retried_and_are_redacted():
    clock = Clock()

    class Client:
        calls = 0

        def lookup_events(self, **kwargs):
            self.calls += 1
            raise AwsThrottle("AccessDeniedException")

    client = Client()
    wrapper = PacedCloudTrail(
        client, monotonic=clock.monotonic, sleep=clock.sleep,
    )
    with pytest.raises(CloudTrailReadRejected) as exc:
        wrapper.lookup_events(MaxResults=50)
    assert client.calls == 1
    assert "raw_sensitive_details" not in str(exc.value)


@pytest.mark.parametrize("response", [
    None, {}, {"Events": "fake"},
    {"Events": [{}] * 51},
    {"Events": [], "NextToken": ""},
    {"Events": [], "NextToken": 4},
])
def test_malformed_cloudtrail_pages_fail_closed(response):
    class Client:
        def lookup_events(self, **kwargs):
            return response

    wrapper = PacedCloudTrail(Client())
    with pytest.raises(CloudTrailReadRejected):
        wrapper.lookup_events(MaxResults=50)


@pytest.mark.parametrize("kwargs", [
    {}, {"MaxResults": 50, "AccessKey": "secret"},
    {"MaxResults": 50, "EventCategory": "Insight"},
])
def test_reject_unapproved_lookup_arguments(kwargs):
    class Client:
        def lookup_events(self, **kwargs):
            raise AssertionError("should not call AWS")

    wrapper = PacedCloudTrail(Client())
    with pytest.raises(CloudTrailReadRejected):
        wrapper.lookup_events(**kwargs)


def test_independent_accounts_use_separate_per_account_rate_limiter():
    clock = Clock()
    calls = []

    class Client:
        def __init__(self, name):
            self.name = name

        def lookup_events(self, **kwargs):
            calls.append((self.name, clock.now))
            return {"Events": []}

    op = PacedCloudTrail(
        Client("workload"), monotonic=clock.monotonic, sleep=clock.sleep,
    )
    custody = PacedCloudTrail(
        Client("custody"), monotonic=clock.monotonic, sleep=clock.sleep,
    )
    op.lookup_events(MaxResults=50)
    custody.lookup_events(MaxResults=50)
    op.lookup_events(MaxResults=50)
    assert calls[0][1] == calls[1][1]
    assert calls[2][1] - calls[0][1] >= 0.55 - 1e-8
