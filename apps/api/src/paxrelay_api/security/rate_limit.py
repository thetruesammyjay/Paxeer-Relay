"""Redis-backed fixed-window API-key request limiting."""

from __future__ import annotations

import logging
import time
from uuid import UUID

from fastapi import Request, Response
from redis.exceptions import RedisError

from paxrelay_api.config import ApiSettings
from paxrelay_api.exceptions import RateLimitExceededError, RateLimitUnavailableError
from paxrelay_api.tenant import TenantContext

logger = logging.getLogger("paxrelay.api.rate_limit")

_INCREMENT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


async def enforce_api_key_limit(
    *,
    request: Request,
    response: Response,
    tenant: TenantContext,
    settings: ApiSettings,
) -> None:
    """Count one request in a shared Redis bucket; fail closed when enabled."""
    if not settings.rate_limiting_enabled:
        return

    redis = getattr(request.app.state, "redis", None)
    principal_id = tenant.api_key_id or tenant.user_id
    if redis is None or principal_id is None:
        raise RateLimitUnavailableError()

    now = int(time.time())
    window = settings.api_rate_limit_window_seconds
    bucket = now // window
    reset_after = window - now % window
    counter_key = (
        f"{settings.redis_key_prefix}:api:limit:{tenant.environment}:"
        f"{tenant.project_id}:{principal_id}:{bucket}"
    )

    try:
        count = int(await redis.eval(_INCREMENT_SCRIPT, 1, counter_key, window * 2))
    except (RedisError, OSError, TimeoutError) as exc:
        logger.error(
            "API rate limiter unavailable request_id=%s error_type=%s",
            getattr(request.state, "request_id", "-"),
            type(exc).__name__,
        )
        raise RateLimitUnavailableError() from exc

    limit = settings.api_rate_limit_max_requests
    reset_at = now + reset_after
    response.headers["RateLimit-Limit"] = str(limit)
    response.headers["RateLimit-Remaining"] = str(max(limit - count, 0))
    response.headers["RateLimit-Reset"] = str(reset_after)
    response.headers["X-RateLimit-Reset"] = str(reset_at)

    if count > limit:
        raise RateLimitExceededError(
            retry_after_seconds=reset_after,
            limit=limit,
            reset_at=reset_at,
        )


async def enforce_dashboard_discovery_limit(
    *,
    request: Request,
    response: Response,
    user_id: UUID,
    settings: ApiSettings,
) -> None:
    """Limit project discovery, which runs before a project tenant is selected."""
    if not settings.rate_limiting_enabled:
        return
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise RateLimitUnavailableError()

    now = int(time.time())
    window = settings.api_rate_limit_window_seconds
    bucket = now // window
    reset_after = window - now % window
    counter_key = f"{settings.redis_key_prefix}:api:dashboard-discovery:{user_id}:{bucket}"
    try:
        count = int(await redis.eval(_INCREMENT_SCRIPT, 1, counter_key, window * 2))
    except (RedisError, OSError, TimeoutError) as exc:
        logger.error(
            "API rate limiter unavailable request_id=%s error_type=%s",
            getattr(request.state, "request_id", "-"),
            type(exc).__name__,
        )
        raise RateLimitUnavailableError() from exc

    limit = settings.api_rate_limit_max_requests
    reset_at = now + reset_after
    response.headers["RateLimit-Limit"] = str(limit)
    response.headers["RateLimit-Remaining"] = str(max(limit - count, 0))
    response.headers["RateLimit-Reset"] = str(reset_after)
    response.headers["X-RateLimit-Reset"] = str(reset_at)
    if count > limit:
        raise RateLimitExceededError(
            retry_after_seconds=reset_after,
            limit=limit,
            reset_at=reset_at,
        )
