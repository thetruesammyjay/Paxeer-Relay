"""Provider endpoint validation and DNS-pinned connection support."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpcore


class UnsafeProviderEndpoint(ValueError):
    """The configured provider endpoint is malformed or resolves unsafely."""


class ProviderEndpointResolutionTimeout(TimeoutError):
    """DNS resolution for a provider endpoint exceeded its time budget."""


@dataclass(frozen=True)
class ResolvedProviderEndpoint:
    """Validated endpoint data used for a single provider request."""

    hostname: str
    port: int
    addresses: tuple[str, ...]


def _normalise_host(host: str) -> str:
    """Return a lowercase ASCII hostname suitable for DNS and HTTP routing."""
    host = host.rstrip(".")
    try:
        return host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UnsafeProviderEndpoint("invalid provider hostname") from exc


def _normalise_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Parse an address and collapse IPv4-mapped IPv6 into IPv4."""
    if "%" in value:
        raise UnsafeProviderEndpoint("scoped provider IP addresses are not allowed")
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise UnsafeProviderEndpoint(
            "provider DNS returned an invalid address"
        ) from exc
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def _address_is_allowed(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    allow_private: bool,
) -> bool:
    if (
        address.is_multicast
        or address.is_unspecified
        or address.is_reserved
        or address.is_link_local
    ):
        return False
    if allow_private:
        return address.is_global or address.is_private or address.is_loopback
    return address.is_global


async def resolve_provider_endpoint(
    endpoint_url: str,
    *,
    allow_private: bool,
    timeout_seconds: float = 5,
    allowed_hosts: frozenset[str] | None = None,
) -> ResolvedProviderEndpoint:
    """Validate an endpoint and capture safe addresses for a pinned request.

    Each request resolves the hostname once. ``PinnedAddressBackend`` uses only
    these captured addresses for TCP connections, while HTTPX/httpcore retain
    the original hostname for the Host header and TLS certificate validation.
    """
    try:
        parsed = urlsplit(endpoint_url)
        hostname = parsed.hostname
        parsed_port = parsed.port
        port = parsed_port if parsed_port is not None else (
            443 if parsed.scheme == "https" else 80
        )
    except ValueError as exc:
        raise UnsafeProviderEndpoint("invalid provider URL") from exc

    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or not 1 <= port <= 65535
    ):
        raise UnsafeProviderEndpoint("invalid provider URL")
    if not allow_private and parsed.scheme != "https":
        raise UnsafeProviderEndpoint("provider endpoint must use HTTPS")

    hostname = _normalise_host(hostname)
    if allowed_hosts is not None:
        normalized_allowlist = {_normalise_host(value) for value in allowed_hosts}
        if hostname not in normalized_allowlist:
            raise UnsafeProviderEndpoint("provider hostname is not allowlisted")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None

    if literal is not None:
        candidates = [literal]
    else:
        try:
            results = await asyncio.wait_for(
                asyncio.get_running_loop().getaddrinfo(
                    hostname,
                    port,
                    family=socket.AF_UNSPEC,
                    type=socket.SOCK_STREAM,
                    proto=socket.IPPROTO_TCP,
                ),
                timeout=timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProviderEndpointResolutionTimeout(
                "provider hostname resolution timed out"
            ) from exc
        except (OSError, UnicodeError) as exc:
            raise UnsafeProviderEndpoint(
                "provider hostname could not be resolved"
            ) from exc
        candidates = [_normalise_ip(result[4][0]) for result in results]

    unique_addresses = tuple(dict.fromkeys(str(address) for address in candidates))
    if not unique_addresses:
        raise UnsafeProviderEndpoint("provider hostname has no usable addresses")
    if len(unique_addresses) > 16:
        raise UnsafeProviderEndpoint("provider hostname returned too many addresses")
    if any(
        not _address_is_allowed(_normalise_ip(address), allow_private=allow_private)
        for address in unique_addresses
    ):
        raise UnsafeProviderEndpoint(
            "provider hostname resolves to a restricted address"
        )

    return ResolvedProviderEndpoint(
        hostname=hostname,
        port=port,
        addresses=unique_addresses,
    )


class PinnedAddressBackend(httpcore.AsyncNetworkBackend):
    """Connect only to the addresses captured by ``resolve_provider_endpoint``."""

    def __init__(self, endpoint: ResolvedProviderEndpoint) -> None:
        self._endpoint = endpoint
        self._backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if (
            _normalise_host(host) != self._endpoint.hostname
            or port != self._endpoint.port
        ):
            raise httpcore.ConnectError("provider destination changed after validation")

        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout if timeout is not None else None
        for address in self._endpoint.addresses:
            attempt_timeout = timeout
            if deadline is not None:
                attempt_timeout = deadline - loop.time()
                if attempt_timeout <= 0:
                    if last_error is not None:
                        raise last_error
                    raise httpcore.ConnectTimeout("provider connection timed out")
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=attempt_timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                if isinstance(exc, httpcore.ConnectTimeout):
                    raise
                last_error = exc
        if last_error is not None:
            raise last_error
        raise httpcore.ConnectError("provider endpoint has no validated address")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise httpcore.ConnectError("Unix socket provider endpoints are not supported")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)
