"""Wrapper around the Clash of Clans API. Every CoC API call goes through here."""
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx

BASE_URL = "https://api.clashofclans.com/v1"


# ---------------------------------------------------------------- errors

class CocApiError(Exception):
    """Base error for any non-200 response from the CoC API."""

    def __init__(self, status_code: int, reason: str | None, message: str | None) -> None:
        self.status_code = status_code
        self.reason = reason      # stable code, e.g. "accessDenied.invalidIp"
        self.message = message    # human-readable text from the API
        super().__init__(f"{status_code} {reason}: {message}")


class AccessDeniedError(CocApiError):
    """403: bad key, or the resource is private (e.g. war log not public)."""


class InvalidIpError(AccessDeniedError):
    """403 with reason accessDenied.invalidIp: your IP isn't on the key."""


class NotFoundError(CocApiError):
    """404: wrong tag, or the tag wasn't URL-encoded."""


class RateLimitedError(CocApiError):
    """429: too many requests, slow down."""


class MaintenanceError(CocApiError):
    """503: game servers are under maintenance."""


_ERRORS_BY_STATUS: dict[int, type[CocApiError]] = {
    403: AccessDeniedError,
    404: NotFoundError,
    429: RateLimitedError,
    503: MaintenanceError,
}


def _error_from_response(response: httpx.Response) -> CocApiError:
    """Build the most specific error for a failed response."""
    try:
        body = response.json()
    except ValueError:            # e.g. an HTML error page from a proxy
        body = {}
    reason = body.get("reason")
    message = body.get("message")

    if reason == "accessDenied.invalidIp":
        return InvalidIpError(response.status_code, reason, message)
    error_cls = _ERRORS_BY_STATUS.get(response.status_code, CocApiError)
    return error_cls(response.status_code, reason, message)


# Errors worth retrying: they're temporary. 403/404 never fix themselves.
RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    RateLimitedError,
    MaintenanceError,
    httpx.TransportError,
)


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Read the Retry-After header (seconds) if the server sent one."""
    value = response.headers.get("Retry-After")
    try:
        return float(value) if value is not None else None
    except ValueError:            # could be an HTTP date; ignore it
        return None


# ---------------------------------------------------------------- client

def encode_tag(tag: str) -> str:
    """URL-encode a CoC tag: '#ABC' -> '%23ABC'."""
    return quote(tag, safe="")


class CocClient:
    """Small synchronous client for the CoC API.

    Use as a context manager so the connection is closed:
        with CocClient(api_key) as coc:
            clan = coc.get_clan("#YQPUY28V")
    """

    def __init__(
        self,
        api_key: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        max_backoff: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Create the client.

        max_retries:  extra attempts after the first one, for 429/503/network errors
        backoff_base: first wait in seconds; doubles each retry (1, 2, 4, ...)
        max_backoff:  upper limit for any single wait
        transport, sleep: injectable so tests can fake the network and skip real waiting
        """
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._max_backoff = max_backoff
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> "CocClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection."""
        self._http.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET a path, return parsed JSON, or raise a CocApiError subclass.

        429, 503 and network errors are retried with exponential backoff.
        Everything else (403, 404, ...) fails immediately: retrying won't fix it.
        """
        attempt = 0
        while True:
            try:
                response = self._http.get(path, params=params)
                if response.status_code == 200:
                    return response.json()
                error: Exception = _error_from_response(response)
                retry_after = _parse_retry_after(response)
            except httpx.TransportError as exc:   # timeouts, connection failures
                error, retry_after = exc, None

            if not isinstance(error, RETRYABLE_ERRORS) or attempt >= self._max_retries:
                raise error

            self._sleep(self._backoff_delay(attempt, retry_after))
            attempt += 1

    def _backoff_delay(self, attempt: int, retry_after: float | None) -> float:
        """Wait before the next retry: base * 2^attempt, or Retry-After if longer, capped."""
        delay = self._backoff_base * (2 ** attempt)
        if retry_after is not None:
            delay = max(delay, retry_after)
        return min(delay, self._max_backoff)

    # --- endpoints -------------------------------------------------------

    def get_clan(self, clan_tag: str) -> dict[str, Any]:
        """Clan info and member list."""
        return self._get(f"/clans/{encode_tag(clan_tag)}")

    def get_current_war(self, clan_tag: str) -> dict[str, Any]:
        """Current war. Check 'state': notInWar, preparation, inWar, warEnded."""
        return self._get(f"/clans/{encode_tag(clan_tag)}/currentwar")

    def get_war_log(self, clan_tag: str, limit: int | None = None) -> dict[str, Any]:
        """Past war summaries ({'items': [...], 'paging': ...}). Needs a public war log."""
        params = {"limit": limit} if limit else None
        return self._get(f"/clans/{encode_tag(clan_tag)}/warlog", params=params)

    def get_player(self, player_tag: str) -> dict[str, Any]:
        """Player profile: heroes, troops, achievements."""
        return self._get(f"/players/{encode_tag(player_tag)}")
