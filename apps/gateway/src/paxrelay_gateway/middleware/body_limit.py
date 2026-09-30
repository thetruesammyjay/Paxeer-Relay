"""Streaming request-size limit for paid-call gateway routes."""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    """Reject oversized write bodies before route processing."""

    _BODY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
    _DEFAULT_MAX_BYTES = 1_048_576

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        method = scope.get("method", "GET").upper()
        if scope["type"] != "http" or method not in self._BODY_METHODS:
            await self.app(scope, receive, send)
            return

        application = scope.get("app")
        settings = getattr(getattr(application, "state", None), "settings", None)
        max_bytes = getattr(settings, "gateway_max_request_bytes", self._DEFAULT_MAX_BYTES)
        content_lengths = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if len(content_lengths) > 1:
            await self._send_error(
                scope, send, 400, "invalid_content_length", "Invalid request framing."
            )
            return
        has_transfer_encoding = any(
            name.lower() == b"transfer-encoding" for name, _ in scope.get("headers", [])
        )
        if content_lengths and has_transfer_encoding:
            await self._send_error(
                scope, send, 400, "invalid_content_length", "Invalid request framing."
            )
            return
        if content_lengths:
            if not content_lengths[0].isdigit():
                await self._send_error(
                    scope, send, 400, "invalid_content_length", "Invalid request framing."
                )
                return
            try:
                content_length = int(content_lengths[0])
            except ValueError:
                await self._send_error(
                    scope, send, 400, "invalid_content_length", "Invalid request framing."
                )
                return
            if content_length > max_bytes:
                await self._send_error(
                    scope,
                    send,
                    413,
                    "payload_too_large",
                    "Request body exceeds the configured size limit.",
                )
                return

        received_bytes = 0
        response_started = False

        async def receive_with_limit() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > max_bytes:
                    raise _RequestBodyTooLarge
            return message

        async def track_response(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive_with_limit, track_response)
        except _RequestBodyTooLarge:
            if not response_started:
                await self._send_error(
                    scope,
                    send,
                    413,
                    "payload_too_large",
                    "Request body exceeds the configured size limit.",
                )

    @staticmethod
    async def _send_error(
        scope: Scope,
        send: Send,
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        body = json.dumps(
            {"error": {"code": code, "message": message}}
        ).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
        ]
        if scope.get("http_version") in {"1.0", "1.1"}:
            headers.append((b"connection", b"close"))
        await send(
            {"type": "http.response.start", "status": status_code, "headers": headers}
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})
