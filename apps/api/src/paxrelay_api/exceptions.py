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
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(error=ErrorBody(code=exc.code, message=exc.message)).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error=ErrorBody(code="validation_error", message=str(exc.errors()))
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
