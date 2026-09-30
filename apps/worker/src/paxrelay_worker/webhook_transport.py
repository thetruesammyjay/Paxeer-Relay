"""DNS validation and pinned HTTPX transport for webhook destinations."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpcore
import httpx


class UnsafeWebhookDestination(ValueError):
    """The endpoint is malformed or resolves to a restricted address."""


class WebhookDnsTimeout(TimeoutError):
    """Destination DNS resolution exceeded its time budget."""


class WebhookDnsFailure(OSError):
    """Destination DNS could not produce usable addresses."""


@dataclass(frozen=True)
class ResolvedWebhookDestination:
    hostname: str
    port: int
    addresses: tuple[str, ...]


def _normalise_hostname(hostname: str) -> str:
    try:
        return hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UnsafeWebhookDestination("invalid destination hostname") from exc


def _normalise_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    if "%" in value:
        raise UnsafeWebhookDestination("scoped IP addresses are not allowed")
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise UnsafeWebhookDestination("DNS returned an invalid IP address") from exc
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def _address_allowed(
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


async def resolve_webhook_destination(
    url: str,
    *,
    allow_private: bool,
    timeout_seconds: float,
) -> ResolvedWebhookDestination:
    """Resolve once, reject unsafe results, and return the addresses to pin."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed_port = parsed.port
    except ValueError as exc:
        raise UnsafeWebhookDestination("invalid destination URL") from exc

    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise UnsafeWebhookDestination("invalid destination URL")
    if not allow_private and parsed.scheme != "https":
        raise UnsafeWebhookDestination("destination must use HTTPS")

    hostname = _normalise_hostname(hostname)
    port = (
        parsed_port
        if parsed_port is not None
        else (443 if parsed.scheme == "https" else 80)
    )
    if not 1 <= port <= 65535:
        raise UnsafeWebhookDestination("invalid destination port")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None

    if literal is not None:
        candidates = [_normalise_ip(str(literal))]
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
            raise WebhookDnsTimeout("destination DNS resolution timed out") from exc
        except (OSError, UnicodeError) as exc:
            raise WebhookDnsFailure("destination DNS resolution failed") from exc
        candidates = [_normalise_ip(result[4][0]) for result in results]

    addresses = tuple(dict.fromkeys(str(address) for address in candidates))
    if not addresses:
        raise WebhookDnsFailure("destination hostname has no addresses")
    if len(addresses) > 16:
        raise UnsafeWebhookDestination("destination returned too many IP addresses")
    if any(
        not _address_allowed(_normalise_ip(address), allow_private=allow_private)
        for address in addresses
    ):
        raise UnsafeWebhookDestination(
            "destination resolves to a restricted IP address"
        )

    return ResolvedWebhookDestination(hostname, port, addresses)


class PinnedWebhookBackend(httpcore.AsyncNetworkBackend):
    """Preserve HTTP Host/TLS identity while connecting only to checked IPs."""

    def __init__(self, destination: ResolvedWebhookDestination) -> None:
        self._destination = destination
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
            _normalise_hostname(host) != self._destination.hostname
            or port != self._destination.port
        ):
            raise httpcore.ConnectError("webhook destination changed after validation")

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout if timeout is not None else None
        last_error: httpcore.ConnectError | None = None
        for address in self._destination.addresses:
            attempt_timeout = timeout
            if deadline is not None:
                attempt_timeout = deadline - loop.time()
                if attempt_timeout <= 0:
                    raise httpcore.ConnectTimeout("webhook connection timed out")
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=attempt_timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except httpcore.ConnectTimeout:
                raise
            except httpcore.ConnectError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise httpcore.ConnectError("webhook destination has no checked IP addresses")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise httpcore.ConnectError(
            "Unix socket webhook destinations are not supported"
        )

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


def pinned_webhook_transport(
    destination: ResolvedWebhookDestination,
) -> httpx.AsyncHTTPTransport:
    """Build a fail-closed HTTPX transport using prevalidated DNS answers."""
    transport = httpx.AsyncHTTPTransport(trust_env=False, retries=0)
    pool = getattr(transport, "_pool", None)
    if pool is None or not hasattr(pool, "_network_backend"):
        raise RuntimeError("HTTPX transport cannot enforce pinned webhook addresses")
    pool._network_backend = PinnedWebhookBackend(destination)
    return transport
