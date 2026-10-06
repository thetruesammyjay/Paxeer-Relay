"""Read-only validation for the published 402LXP HTTP v2 offer contract.

This module validates the PAYMENT-REQUIRED envelope before any wallet or
receipt code sees it. It does not create payment evidence and must not be used
as a substitute for LayerX SDK receipt verification.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


MAX_ENVELOPE_BYTES = 65_536
MAX_AMOUNT = (1 << 128) - 1
MAX_TIMEOUT_SECONDS = (1 << 32) - 1
_HEX_32 = re.compile(r"^[0-9a-f]{64}$")
_DECIMAL = re.compile(r"^(0|[1-9][0-9]*)$")
_NETWORK = re.compile(r"^layerx:([1-9][0-9]*)$")
_COMMITMENTS = {"executed", "batched", "finalised"}
_SCHEMES = {"exact", "metered", "subscription"}


class X402ContractError(ValueError):
    """A stable, safe-to-display reason why an offer violates the contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExactPaymentOffer:
    """Validated fields PaxRelay needs to display an exact per-call offer."""

    network: str
    asset: str
    amount: str
    pay_to: str
    max_timeout_seconds: int
    commitment: str


def decode_payment_required(value: str) -> dict[str, Any]:
    """Decode and validate a base64-encoded PAYMENT-REQUIRED header.

    The returned mapping is the original v2 envelope. Unknown top-level and
    resource extension fields are retained for forward compatibility, while
    the exact payment alternative used by this demo path is strict.
    """
    if not isinstance(value, str) or not value or len(value) > MAX_ENVELOPE_BYTES * 2:
        raise X402ContractError("invalid_header_size")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise X402ContractError("invalid_header_base64") from exc
    if not raw or len(raw) > MAX_ENVELOPE_BYTES:
        raise X402ContractError("invalid_envelope_size")
    try:
        decoded = raw.decode("utf-8", errors="strict")
        envelope = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except X402ContractError:
        raise
    except ValueError as exc:
        raise X402ContractError("invalid_envelope_json") from exc
    validate_payment_required(envelope)
    return envelope


def validate_payment_required(envelope: Any) -> tuple[ExactPaymentOffer, ...]:
    """Validate a v2 envelope and return its exact offers.

    The published contract permits 1–32 alternatives. This parser validates
    their common fields and returns `exact` alternatives; other valid schemes
    are ignored by the exact-payment demo path.
    """
    if not isinstance(envelope, dict):
        raise X402ContractError("envelope_must_be_object")
    if type(envelope.get("x402Version")) is not int or envelope["x402Version"] != 2:
        raise X402ContractError("unsupported_protocol_version")

    resource = envelope.get("resource")
    if not isinstance(resource, dict) or not _valid_resource_url(resource.get("url")):
        raise X402ContractError("invalid_resource_url")

    alternatives = envelope.get("accepts")
    if not isinstance(alternatives, list) or not 1 <= len(alternatives) <= 32:
        raise X402ContractError("invalid_alternatives_count")

    exact: list[ExactPaymentOffer] = []
    for alternative in alternatives:
        if not isinstance(alternative, dict):
            raise X402ContractError("alternative_must_be_object")
        scheme = alternative.get("scheme")
        if not isinstance(scheme, str) or scheme not in _SCHEMES:
            raise X402ContractError("unsupported_scheme")
        network = alternative.get("network")
        match = _NETWORK.fullmatch(network) if isinstance(network, str) else None
        if match is None:
            raise X402ContractError("invalid_network")
        asset = alternative.get("asset")
        pay_to = alternative.get("payTo")
        if not isinstance(asset, str) or _HEX_32.fullmatch(asset) is None:
            raise X402ContractError("invalid_asset")
        if not isinstance(pay_to, str) or _HEX_32.fullmatch(pay_to) is None:
            raise X402ContractError("invalid_pay_to")
        amount = alternative.get("amount")
        if not isinstance(amount, str) or _DECIMAL.fullmatch(amount) is None:
            raise X402ContractError("invalid_amount")
        amount_value = int(amount)
        if amount_value < 1 or amount_value > MAX_AMOUNT:
            raise X402ContractError("amount_out_of_range")
        timeout = alternative.get("maxTimeoutSeconds")
        if type(timeout) is not int or timeout < 1 or timeout > MAX_TIMEOUT_SECONDS:
            raise X402ContractError("invalid_timeout")

        commitment = _read_commitment(alternative)
        if scheme == "exact":
            exact.append(
                ExactPaymentOffer(
                    network=network,
                    asset=asset,
                    amount=amount,
                    pay_to=pay_to,
                    max_timeout_seconds=timeout,
                    commitment=commitment,
                )
            )
    return tuple(exact)


def _read_commitment(alternative: dict[str, Any]) -> str:
    extra = alternative.get("extra")
    if extra is None:
        return "executed"
    if not isinstance(extra, dict):
        raise X402ContractError("invalid_extra")
    layerx = extra.get("layerx")
    if layerx is None:
        return "executed"
    if not isinstance(layerx, dict):
        raise X402ContractError("invalid_layerx_extra")
    commitment = layerx.get("commitment")
    if commitment not in _COMMITMENTS:
        raise X402ContractError("invalid_commitment")
    return commitment


def _valid_resource_url(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 2048:
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
        )
    except ValueError:
        return False


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise X402ContractError("duplicate_json_key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise X402ContractError("invalid_json_constant")
