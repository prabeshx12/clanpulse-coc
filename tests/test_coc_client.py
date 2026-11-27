"""Tests for app/coc_client.py. No real network: httpx.MockTransport fakes the API."""
from collections.abc import Callable

import httpx
import pytest

from app.coc_client import (
    AccessDeniedError,
    CocApiError,
    CocClient,
    InvalidIpError,
    MaintenanceError,
    NotFoundError,
    RateLimitedError,
    encode_tag,
)

Handler = Callable[[httpx.Request], httpx.Response]


class FakeSleep:
    """Records requested waits instead of actually sleeping."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def make_client(handler: Handler, sleep: FakeSleep | None = None, **kwargs) -> CocClient:
    """Build a CocClient whose requests go to `handler` instead of the internet."""
    return CocClient(
        "test-key",
        transport=httpx.MockTransport(handler),
        sleep=sleep or FakeSleep(),
        **kwargs,
    )


def sequence(*responses: httpx.Response) -> tuple[Handler, list[httpx.Request]]:
    """Handler that returns the given responses in order, and records each request."""
    seen: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return queue.pop(0)

    return handler, seen


# ---------------------------------------------------------------- basics

def test_encode_tag_encodes_hash_and_slash() -> None:
    assert encode_tag("#YQPUY28V") == "%23YQPUY28V"
    assert encode_tag("#A/B") == "%23A%2FB"


def test_get_clan_sends_encoded_path_and_auth_header() -> None:
    handler, seen = sequence(httpx.Response(200, json={"name": "Nepali Solo"}))

    with make_client(handler) as coc:
        clan = coc.get_clan("#YQPUY28V")

    assert clan == {"name": "Nepali Solo"}
    assert seen[0].url.raw_path == b"/v1/clans/%23YQPUY28V"
    assert seen[0].headers["Authorization"] == "Bearer test-key"


def test_get_war_log_passes_limit_param() -> None:
    handler, seen = sequence(httpx.Response(200, json={"items": []}))

    with make_client(handler) as coc:
        coc.get_war_log("#ABC", limit=5)

    assert seen[0].url.params["limit"] == "5"


# ---------------------------------------------------------------- error mapping

@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (403, {"reason": "accessDenied.invalidIp"}, InvalidIpError),
        (403, {"reason": "accessDenied"}, AccessDeniedError),
        (404, {"reason": "notFound"}, NotFoundError),
        (500, {"reason": "unknownException"}, CocApiError),
    ],
)
def test_error_status_maps_to_typed_exception(
    status: int, body: dict, expected: type[CocApiError]
) -> None:
    handler, _ = sequence(httpx.Response(status, json=body))

    with make_client(handler) as coc, pytest.raises(expected) as exc_info:
        coc.get_clan("#ABC")

    assert exc_info.type is expected          # exact class, not just a parent
    assert exc_info.value.reason == body["reason"]


def test_non_json_error_body_still_raises_coc_error() -> None:
    handler, _ = sequence(httpx.Response(502, text="<html>Bad Gateway</html>"))

    with make_client(handler) as coc, pytest.raises(CocApiError) as exc_info:
        coc.get_clan("#ABC")

    assert exc_info.value.status_code == 502
    assert exc_info.value.reason is None


# ---------------------------------------------------------------- retries

def test_retries_503_then_succeeds() -> None:
    handler, seen = sequence(
        httpx.Response(503, json={"reason": "inMaintenance"}),
        httpx.Response(200, json={"name": "ok"}),
    )
    sleep = FakeSleep()

    with make_client(handler, sleep) as coc:
        assert coc.get_clan("#ABC") == {"name": "ok"}

    assert len(seen) == 2
    assert sleep.calls == [1.0]


def test_gives_up_after_max_retries_with_exponential_backoff() -> None:
    throttled = httpx.Response(429, json={"reason": "requestThrottled"})
    handler, seen = sequence(*[throttled] * 4)
    sleep = FakeSleep()

    with make_client(handler, sleep, max_retries=3) as coc, pytest.raises(RateLimitedError):
        coc.get_clan("#ABC")

    assert len(seen) == 4                     # 1 attempt + 3 retries
    assert sleep.calls == [1.0, 2.0, 4.0]


def test_backoff_is_capped_at_max_backoff() -> None:
    down = httpx.Response(503, json={"reason": "inMaintenance"})
    handler, _ = sequence(*[down] * 4)
    sleep = FakeSleep()

    with make_client(handler, sleep, max_retries=3, max_backoff=3.0) as coc:
        with pytest.raises(MaintenanceError):
            coc.get_clan("#ABC")

    assert sleep.calls == [1.0, 2.0, 3.0]


def test_retry_after_header_is_respected() -> None:
    handler, _ = sequence(
        httpx.Response(429, json={"reason": "requestThrottled"}, headers={"Retry-After": "7"}),
        httpx.Response(200, json={}),
    )
    sleep = FakeSleep()

    with make_client(handler, sleep) as coc:
        coc.get_clan("#ABC")

    assert sleep.calls == [7.0]


@pytest.mark.parametrize("status", [403, 404])
def test_permanent_errors_are_not_retried(status: int) -> None:
    handler, seen = sequence(httpx.Response(status, json={"reason": "x"}))
    sleep = FakeSleep()

    with make_client(handler, sleep) as coc, pytest.raises(CocApiError):
        coc.get_clan("#ABC")

    assert len(seen) == 1
    assert sleep.calls == []


def test_network_error_is_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectTimeout("timed out", request=request)
        return httpx.Response(200, json={"name": "ok"})

    with make_client(handler) as coc:
        assert coc.get_clan("#ABC") == {"name": "ok"}

    assert calls == 2
