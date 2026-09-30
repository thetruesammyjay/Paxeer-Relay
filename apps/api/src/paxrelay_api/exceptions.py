"""Structured exceptions and FastAPI error handlers.

Every error returned by the API uses the shape ``{"error": {"code", "message"}}``
so the dashboard and SDKs can branch on stable machine-readable codes.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from paxrelay_api.schemas import ErrorBody, ErrorResponse

logger = logging.getLogger("paxrelay.api")


def _response_headers(
    request: Request,
    headers: dict[str, str] | None = None,
) -> dict[str, str]:
    response_headers = dict(headers or {})
    request_id = getattr(request.state, "request_id", None)
    if request_id is not None:
        response_headers["X-Request-ID"] = request_id
    return response_headers


class ApiError(Exception):
    """Base class for all control-plane API errors."""

    code = "api_error"
    http_status = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ApiError):
    code = "not_found"
    http_status = status.HTTP_404_NOT_FOUND


class ConflictError(ApiError):
    code = "conflict"
    http_status = status.HTTP_409_CONFLICT


class InvalidRequestError(ApiError):
    code = "invalid_request"
    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY


class UnauthorizedError(ApiError):
    code = "unauthorized"
    http_status = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(ApiError):
    code = "forbidden"
    http_status = status.HTTP_403_FORBIDDEN


class RateLimitExceededError(ApiError):
    code = "rate_limited"
    http_status = status.HTTP_429_TOO_MANY_REQUESTS

    def __init__(self, retry_after_seconds: int, limit: int, reset_at: int) -> None:
        super().__init__("The API request limit has been reached.")
        self.retry_after_seconds = retry_after_seconds
        self.limit = limit
        self.reset_at = reset_at


class RateLimitUnavailableError(ApiError):
    code = "rate_limiter_unavailable"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    def __init__(self) -> None:
        super().__init__("The API cannot verify its request limit right now.")


def register_error_handlers(app: FastAPI) -> None:
    """Attach handlers that translate exceptions into the error envelope."""

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        headers: dict[str, str] | None = None
        if isinstance(exc, UnauthorizedError):
            # RFC 7235 §3.1 — a 401 response MUST include WWW-Authenticate.
            headers = {"WWW-Authenticate": "Bearer"}
        elif isinstance(exc, RateLimitExceededError):
            headers = {
                "Retry-After": str(exc.retry_after_seconds),
                "RateLimit-Limit": str(exc.limit),
                "RateLimit-Remaining": "0",
                "RateLimit-Reset": str(exc.retry_after_seconds),
                "X-RateLimit-Reset": str(exc.reset_at),
            }
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(error=ErrorBody(code=exc.code, message=exc.message)).model_dump(),
            headers=_response_headers(request, headers),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Only expose field location and message — not input values or internal
        # Pydantic type names that would help callers probe the schema.
        safe_details = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )[:1024]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error=ErrorBody(code="validation_error", message=safe_details)
            ).model_dump(),
            headers=_response_headers(request),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = {
            status.HTTP_401_UNAUTHORIZED: ("unauthorized", "Authentication is required."),
            status.HTTP_403_FORBIDDEN: ("forbidden", "This action is not permitted."),
            status.HTTP_404_NOT_FOUND: ("not_found", "The requested resource was not found."),
            status.HTTP_405_METHOD_NOT_ALLOWED: ("method_not_allowed", "This method is not allowed."),
        }.get(exc.status_code, ("http_error", "The request could not be completed."))
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=ErrorBody(code=code, message=message)).model_dump(),
            headers=_response_headers(request, exc.headers),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, _: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=ErrorResponse(
                error=ErrorBody(
                    code="conflict",
                    message="The request conflicts with an existing record.",
                )
            ).model_dump(),
            headers=_response_headers(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled API exception request_id=%s method=%s path=%s",
            getattr(request.state, "request_id", "-"),
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorBody(code="internal_error", message="An unexpected error occurred.")
            ).model_dump(),
            headers=_response_headers(request),
        )
