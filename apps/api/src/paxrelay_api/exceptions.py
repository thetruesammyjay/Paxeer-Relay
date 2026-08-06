"""Structured exceptions and FastAPI error handlers.

Every error returned by the API uses the shape ``{"error": {"code", "message"}}``
so the dashboard and SDKs can branch on stable machine-readable codes.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from paxrelay_api.schemas import ErrorBody, ErrorResponse


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


def register_error_handlers(app: FastAPI) -> None:
    """Attach handlers that translate exceptions into the error envelope."""

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        headers: dict[str, str] | None = None
        if isinstance(exc, UnauthorizedError):
            # RFC 7235 §3.1 — a 401 response MUST include WWW-Authenticate.
            headers = {"WWW-Authenticate": "Bearer"}
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(error=ErrorBody(code=exc.code, message=exc.message)).model_dump(),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Only expose field location and message — not input values or internal
        # Pydantic type names that would help callers probe the schema.
        safe_details = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error=ErrorBody(code="validation_error", message=safe_details)
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorBody(code="internal_error", message="An unexpected error occurred.")
            ).model_dump(),
        )
