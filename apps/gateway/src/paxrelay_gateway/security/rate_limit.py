"""Redis-backed fixed-window limits for authenticated gateway keys."""

from __future__ import annotations

import logging
import time
from uuid import UUID

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
