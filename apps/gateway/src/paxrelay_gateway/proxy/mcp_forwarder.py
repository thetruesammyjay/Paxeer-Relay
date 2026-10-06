"""DNS-pinned Streamable HTTP forwarding for versioned provider MCP tools."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterable, Iterator
from datetime import datetime
from typing import Any

import httpcore2
import httpx2
from jsonschema import Draft202012Validator, FormatChecker, SchemaError, ValidationError
from mcp import Client, MCPError, types
from mcp.client.streamable_http import streamable_http_client

from paxrelay_domain import ExecutionState
from paxrelay_gateway.proxy.endpoint_security import (
    ProviderEndpointResolutionTimeout,
    ResolvedProviderEndpoint,
    UnsafeProviderEndpoint,
    _normalise_host,
    resolve_provider_endpoint,
)
from paxrelay_gateway.proxy.forwarder import ForwardResult


class McpToolContractError(ValueError):
    """The published MCP tool contract is invalid or changed upstream."""


class ProviderResponseTooLarge(ValueError):
    """An upstream MCP HTTP response exceeded the configured byte limit."""


def validate_mcp_arguments(
    schema: dict[str, Any] | None,
    arguments: dict[str, Any],
) -> None:
    """Validate JSON arguments against the immutable service-version schema."""
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise McpToolContractError("MCP input schema is missing or invalid")
    try:
        json.dumps(arguments, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise McpToolContractError("MCP arguments are not valid JSON values") from exc
    for node in _walk_schema(schema):
        for reference_key in ("$ref", "$dynamicRef", "$recursiveRef"):
            reference = node.get(reference_key)
            if reference is not None and not str(reference).startswith("#"):
                raise McpToolContractError("remote JSON Schema references are not allowed")
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(arguments)
    except (SchemaError, ValidationError, RecursionError) as exc:
        raise McpToolContractError("arguments do not match the MCP tool schema") from exc


async def forward_mcp_tool(
    *,
    endpoint_url: str,
    tool_name: str,
    input_schema: dict[str, Any],
    arguments: dict[str, Any],
    timeout_seconds: int = 30,
    connect_timeout_seconds: int = 5,
    max_response_bytes: int = 10_485_760,
    allow_private_endpoints: bool = False,
    allowed_provider_hosts: frozenset[str] | None = None,
) -> ForwardResult:
    """Connect to one MCP endpoint and call the pinned, versioned tool.

    The SDK handles Streamable HTTP sessions, protocol negotiation, pagination,
    and JSON-RPC. This wrapper keeps its transport on the same resolved IPs as
    the HTTP provider forwarder and bounds individual HTTP/SSE responses.
    """
    started = datetime.utcnow()
    tool_call_started = False
    client: httpx2.AsyncClient | None = None

    try:
        validate_mcp_arguments(input_schema, arguments)
        endpoint = await resolve_provider_endpoint(
            endpoint_url,
            allow_private=allow_private_endpoints,
            timeout_seconds=min(connect_timeout_seconds, timeout_seconds),
            allowed_hosts=allowed_provider_hosts,
        )
        transport = _pinned_bounded_transport(endpoint, max_response_bytes)
        client = httpx2.AsyncClient(
            transport=transport,
            timeout=httpx2.Timeout(
                timeout_seconds,
                connect=min(connect_timeout_seconds, timeout_seconds),
            ),
            headers={"Accept-Encoding": "identity"},
            follow_redirects=False,
            trust_env=False,
        )

        async with asyncio.timeout(timeout_seconds):
            transport = streamable_http_client(
                endpoint_url,
                http_client=client,
                terminate_on_close=True,
                max_sse_event_size=max_response_bytes,
            )
            async with Client(
                transport,
                read_timeout_seconds=timeout_seconds,
                client_info=types.Implementation(
                    name="paxrelay-gateway",
                    version="0.1.0",
                ),
                cache=None,
            ) as session:
                matching_tool = await _find_tool(session, tool_name)
                if matching_tool is None:
                    raise McpToolContractError("published MCP tool is unavailable")
                if not _same_json(matching_tool.input_schema, input_schema):
                    raise McpToolContractError("published MCP tool schema changed")

                tool_call_started = True
                # Use the negotiated low-level call directly. The high-level
                # Client.call_tool may refresh and retry on a header mismatch;
                # retries could silently switch away from the paid version's
                # immutable schema contract.
                result = await session.session.call_tool(
                    tool_name,
                    arguments,
                    read_timeout_seconds=timeout_seconds,
                )
                body = result.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude_none=True,
                )
                response_bytes = json.dumps(
                    body,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
                if len(response_bytes) > max_response_bytes:
                    raise ProviderResponseTooLarge

                completed = datetime.utcnow()
                is_error = bool(
                    getattr(result, "is_error", body.get("isError", False))
                )
                return ForwardResult(
                    execution_state=(
                        ExecutionState.PROVIDER_ERROR
                        if is_error
                        else ExecutionState.SUCCEEDED
                    ),
                    http_status_code=200,
                    response_body=body,
                    response_bytes=response_bytes,
                    started_at=started,
                    completed_at=completed,
                    latency_ms=int((completed - started).total_seconds() * 1000),
                    error_code="mcp_tool_error" if is_error else None,
                )
    except ProviderEndpointResolutionTimeout:
        return _forward_failure(started, ExecutionState.TIMEOUT, "dns_timeout")
    except UnsafeProviderEndpoint:
        return _forward_failure(
            started,
            ExecutionState.PROVIDER_ERROR,
            "unsafe_provider_endpoint",
        )
    except TimeoutError:
        return _forward_failure(started, ExecutionState.TIMEOUT, "timeout")
    except httpx2.TimeoutException:
        return _forward_failure(started, ExecutionState.TIMEOUT, "timeout")
    except ProviderResponseTooLarge:
        state = (
            ExecutionState.UNKNOWN
            if tool_call_started
            else ExecutionState.PROVIDER_ERROR
        )
        return _forward_failure(started, state, "response_too_large")
    except McpToolContractError:
        return _forward_failure(
            started,
            ExecutionState.PROVIDER_ERROR,
            "mcp_tool_contract_mismatch",
        )
    except MCPError as exc:
        if _is_mcp_timeout(exc):
            return _forward_failure(started, ExecutionState.TIMEOUT, "timeout")
        state = (
            ExecutionState.UNKNOWN
            if tool_call_started
            else ExecutionState.PROVIDER_ERROR
        )
        return _forward_failure(started, state, "mcp_protocol_error")
    except httpx2.HTTPError:
        state = (
            ExecutionState.UNKNOWN
            if tool_call_started
            else ExecutionState.PROVIDER_ERROR
        )
        return _forward_failure(started, state, "connection_error")
    except Exception as exc:
        if _contains_response_limit_error(exc):
            state = (
                ExecutionState.UNKNOWN
                if tool_call_started
                else ExecutionState.PROVIDER_ERROR
            )
            return _forward_failure(started, state, "response_too_large")
        state = (
            ExecutionState.UNKNOWN
            if tool_call_started
            else ExecutionState.PROVIDER_ERROR
        )
        return _forward_failure(started, state, "mcp_transport_error")
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                # A close failure must not discard the provider outcome after
                # payment has already been verified and the call may have run.
                pass


async def _find_tool(
    session: Client,
    tool_name: str,
) -> Any | None:
    """Find a tool through bounded MCP pagination, rejecting ambiguous names."""
    cursor: str | None = None
    found: Any | None = None
    seen_cursors: set[str] = set()
    for _ in range(20):
        result = await session.list_tools(cursor=cursor, cache_mode="refresh")
        for tool in result.tools:
            if tool.name == tool_name:
                if found is not None:
                    raise McpToolContractError("MCP endpoint returned duplicate tool names")
                found = tool
        cursor = result.next_cursor
        if cursor is None:
            return found
        if not cursor or len(cursor) > 2048 or cursor in seen_cursors:
            raise McpToolContractError("MCP endpoint returned invalid pagination")
        seen_cursors.add(cursor)
    raise McpToolContractError("MCP tool listing exceeded the pagination limit")


def _same_json(left: Any, right: Any) -> bool:
    try:
        return json.dumps(
            left,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ) == json.dumps(
            right,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return False


def _is_mcp_timeout(error: MCPError) -> bool:
    error_data = getattr(error, "error", None)
    code = (
        error_data.get("code")
        if isinstance(error_data, dict)
        else getattr(error_data, "code", None)
    )
    return code == -32001


def _contains_response_limit_error(error: BaseException) -> bool:
    if isinstance(error, ProviderResponseTooLarge):
        return True
    if isinstance(error, BaseExceptionGroup):
        return any(_contains_response_limit_error(item) for item in error.exceptions)
    return False


def _walk_schema(root: dict[str, Any]) -> Iterator[dict[str, Any]]:
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        for key in (
            "properties",
            "$defs",
            "definitions",
            "patternProperties",
            "dependentSchemas",
            "propertyNames",
        ):
            children = node.get(key)
            if isinstance(children, dict):
                stack.extend(
                    value for value in children.values() if isinstance(value, dict)
                )
        for key in (
            "items",
            "contains",
            "additionalProperties",
            "unevaluatedProperties",
            "unevaluatedItems",
            "contentSchema",
            "not",
            "if",
            "then",
            "else",
        ):
            child = node.get(key)
            if isinstance(child, dict):
                stack.append(child)
        for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
            children = node.get(key)
            if isinstance(children, list):
                stack.extend(value for value in children if isinstance(value, dict))


def _forward_failure(
    started: datetime,
    state: ExecutionState,
    error_code: str,
) -> ForwardResult:
    completed = datetime.utcnow()
    return ForwardResult(
        execution_state=state,
        http_status_code=None,
        response_body=None,
        response_bytes=b"",
        started_at=started,
        completed_at=completed,
        latency_ms=int((completed - started).total_seconds() * 1000),
        error_code=error_code,
    )


def _pinned_bounded_transport(
    endpoint: ResolvedProviderEndpoint,
    max_response_bytes: int,
) -> httpx2.AsyncBaseTransport:
    transport = httpx2.AsyncHTTPTransport(
        trust_env=False,
        retries=0,
        limits=httpx2.Limits(max_connections=4, max_keepalive_connections=2),
    )
    pool = getattr(transport, "_pool", None)
    backend = getattr(pool, "_network_backend", None)
    if pool is None or backend is None:
        raise RuntimeError("HTTPX2 transport cannot enforce pinned provider addresses")
    pool._network_backend = _PinnedHttpcore2Backend(endpoint, backend)
    return _ResponseLimitTransport(transport, max_response_bytes)


class _PinnedHttpcore2Backend:
    """Duck-typed httpcore2 backend that only connects to validated addresses."""

    def __init__(self, endpoint: ResolvedProviderEndpoint, backend: Any) -> None:
        self._endpoint = endpoint
        self._backend = backend

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> Any:
        if (
            _normalise_host(host) != self._endpoint.hostname
            or port != self._endpoint.port
        ):
            raise httpcore2.ConnectError("provider destination changed after validation")

        last_error: httpcore2.ConnectError | None = None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout if timeout is not None else None
        for address in self._endpoint.addresses:
            attempt_timeout = timeout
            if deadline is not None:
                attempt_timeout = deadline - loop.time()
                if attempt_timeout <= 0:
                    raise httpcore2.ConnectTimeout("provider connection timed out")
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=attempt_timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except httpcore2.ConnectTimeout:
                raise
            except httpcore2.ConnectError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise httpcore2.ConnectError("provider endpoint has no validated address")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> Any:
        raise httpcore2.ConnectError("Unix socket provider endpoints are not supported")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class _ResponseLimitTransport(httpx2.AsyncBaseTransport):
    """Limit streamed and declared provider response bodies for MCP HTTP calls."""

    def __init__(self, transport: httpx2.AsyncBaseTransport, maximum_bytes: int) -> None:
        self._transport = transport
        self._maximum_bytes = maximum_bytes

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        response = await self._transport.handle_async_request(request)
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = -1
            if declared_size > self._maximum_bytes:
                await response.aclose()
                raise ProviderResponseTooLarge
        content_encoding = response.headers.get("content-encoding", "identity").lower()
        if content_encoding not in {"", "identity"}:
            await response.aclose()
            raise ValueError("compressed MCP responses are not accepted")
        response.stream = _LimitedByteStream(response.stream, self._maximum_bytes)
        return response

    async def aclose(self) -> None:
        await self._transport.aclose()


class _LimitedByteStream(httpx2.AsyncByteStream):
    """Abort a body as soon as its decoded byte count exceeds the limit."""

    def __init__(self, stream: httpx2.AsyncByteStream, maximum_bytes: int) -> None:
        self._stream = stream
        self._maximum_bytes = maximum_bytes

    async def __aiter__(self) -> AsyncIterator[bytes]:
        size = 0
        async for chunk in self._stream:
            size += len(chunk)
            if size > self._maximum_bytes:
                raise ProviderResponseTooLarge
            yield chunk

    async def aclose(self) -> None:
        await self._stream.aclose()
