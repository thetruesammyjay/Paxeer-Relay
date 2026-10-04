"""Redis-backed fixed-window limits for authenticated gateway keys."""

from __future__ import annotations

import logging
import time
from uuid import UUID, uuid4

from fastapi import Request, Response
from redis.exceptions import RedisError

from paxrelay_gateway.config import GatewaySettings

logger = logging.getLogger("paxrelay.gateway.rate_limit")

_INCREMENT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""

_ACQUIRE_CONCURRENCY_SCRIPT = """
local now = redis.call('TIME')
local now_ms = now[1] * 1000 + math.floor(now[2] / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms)
local in_flight = redis.call('ZCARD', KEYS[1])
local limit = tonumber(ARGV[1])
if in_flight >= limit then
  return {0, in_flight}
end
local lease_ms = tonumber(ARGV[3])
redis.call('ZADD', KEYS[1], now_ms + lease_ms, ARGV[2])
redis.call('PEXPIRE', KEYS[1], lease_ms)
return {1, in_flight + 1}
"""

_RELEASE_CONCURRENCY_SCRIPT = """
local now = redis.call('TIME')
local now_ms = now[1] * 1000 + math.floor(now[2] / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms)
redis.call('ZREM', KEYS[1], ARGV[1])
if redis.call('ZCARD', KEYS[1]) == 0 then
  return redis.call('DEL', KEYS[1])
end
return 1
"""


class GatewayRateLimitExceeded(Exception):
    """Raised when a valid gateway key exceeds its shared request quota."""

    def __init__(self, *, retry_after_seconds: int, limit: int, reset_at: int) -> None:
        super().__init__("The gateway request limit has been reached.")
        self.retry_after_seconds = retry_after_seconds
        self.limit = limit
        self.reset_at = reset_at


class GatewayRateLimitUnavailable(Exception):
    """Raised when Redis cannot enforce an enabled gateway limit."""

    def __init__(self) -> None:
        super().__init__("The gateway cannot verify its request limit right now.")


class GatewayConcurrencyLimitExceeded(Exception):
    """Raised when a key has reached its in-flight gateway request cap."""

    def __init__(self, *, limit: int, in_flight: int) -> None:
        super().__init__("The gateway concurrent request limit has been reached.")
        self.limit = limit
        self.in_flight = in_flight


class GatewayConcurrencyLimitUnavailable(Exception):
    """Raised when Redis cannot enforce the gateway concurrency cap."""

    def __init__(self) -> None:
        super().__init__("The gateway cannot verify its concurrency limit right now.")


async def enforce_gateway_key_limit(
    *,
    request: Request,
    response: Response,
    key_id: UUID,
    project_id: UUID,
    environment: str,
    settings: GatewaySettings,
) -> None:
    """Count a request in a Redis window; fail closed when limits are enabled."""
    if not settings.rate_limiting_enabled:
        return

    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise GatewayRateLimitUnavailable()

    now = int(time.time())
    window = settings.gateway_rate_limit_window_seconds
    bucket = now // window
    reset_after = window - now % window
    counter_key = (
        f"{settings.redis_key_prefix}:gateway:limit:{environment}:"
        f"{project_id}:{key_id}:{bucket}"
    )
    try:
        count = int(await redis.eval(_INCREMENT_SCRIPT, 1, counter_key, window * 2))
    except (RedisError, OSError, TimeoutError) as exc:
        logger.error("Gateway rate limiter unavailable error_type=%s", type(exc).__name__)
        raise GatewayRateLimitUnavailable() from exc

    limit = settings.gateway_rate_limit_max_requests
    reset_at = now + reset_after
    rate_headers = {
        "RateLimit-Limit": str(limit),
        "RateLimit-Remaining": str(max(limit - count, 0)),
        "RateLimit-Reset": str(reset_after),
        "X-RateLimit-Reset": str(reset_at),
    }
    request.state.gateway_rate_limit_headers = rate_headers
    response.headers.update(rate_headers)

    if count > limit:
        raise GatewayRateLimitExceeded(
            retry_after_seconds=reset_after,
            limit=limit,
            reset_at=reset_at,
        )


async def acquire_gateway_key_slot(
    *,
    request: Request,
    key_id: UUID,
    project_id: UUID,
    environment: str,
    settings: GatewaySettings,
) -> str | None:
    """Acquire a shared in-flight slot for an authenticated gateway key."""
    if not settings.rate_limiting_enabled:
        return None

    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise GatewayConcurrencyLimitUnavailable()

    token = uuid4().hex
    concurrency_key = (
        f"{settings.redis_key_prefix}:gateway:concurrency:{environment}:"
        f"{project_id}:{key_id}"
    )
    limit = settings.gateway_max_concurrent_requests_per_key
    lease_ms = settings.gateway_concurrency_lease_seconds * 1000
    try:
        result = await redis.eval(
            _ACQUIRE_CONCURRENCY_SCRIPT,
            1,
            concurrency_key,
            limit,
            token,
            lease_ms,
        )
    except (RedisError, OSError, TimeoutError) as exc:
        logger.error(
            "Gateway concurrency limiter unavailable error_type=%s",
            type(exc).__name__,
        )
        raise GatewayConcurrencyLimitUnavailable() from exc

    try:
        acquired, in_flight = int(result[0]), int(result[1])
    except (IndexError, TypeError, ValueError) as exc:
        logger.error("Gateway concurrency limiter returned an invalid response")
        raise GatewayConcurrencyLimitUnavailable() from exc

    request.state.gateway_concurrency_headers = {
        "X-Gateway-Concurrency-Limit": str(limit),
        "X-Gateway-Concurrency-In-Flight": str(in_flight),
    }
    if acquired != 1:
        raise GatewayConcurrencyLimitExceeded(limit=limit, in_flight=in_flight)
    return token


async def release_gateway_key_slot(
    *,
    request: Request,
    key_id: UUID,
    project_id: UUID,
    environment: str,
    token: str | None,
    settings: GatewaySettings,
) -> None:
    """Release a request slot; its lease also recovers after process failure."""
    if token is None:
        return
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        logger.warning(
            "Gateway concurrency slot will expire after Redis became unavailable"
        )
        return

    concurrency_key = (
        f"{settings.redis_key_prefix}:gateway:concurrency:{environment}:"
        f"{project_id}:{key_id}"
    )
    try:
        await redis.eval(_RELEASE_CONCURRENCY_SCRIPT, 1, concurrency_key, token)
    except (RedisError, OSError, TimeoutError) as exc:
        # Do not replace a completed paid-call response with a Redis cleanup
        # error. The bounded lease removes the slot if this release is lost.
        logger.warning(
            "Gateway concurrency slot release failed error_type=%s",
            type(exc).__name__,
        )
