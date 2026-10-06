from __future__ import annotations

import base64
import json

import pytest

from paxrelay_paxeer.x402_http import (
    X402ContractError,
    decode_payment_required,
    validate_payment_required,
)


def _envelope(**alternative_updates):
    alternative = {
        "scheme": "exact",
        "network": "layerx:1",
        "asset": "a" * 64,
        "amount": "1000000",
        "payTo": "b" * 64,
        "maxTimeoutSeconds": 300,
    }
    alternative.update(alternative_updates)
    return {
        "x402Version": 2,
        "resource": {"url": "https://provider.example/v1/search"},
        "accepts": [alternative],
    }


def _encoded(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def test_decodes_documented_exact_offer_and_defaults_to_executed():
    header = _encoded(json.dumps(_envelope(), separators=(",", ":")).encode())

    decoded = decode_payment_required(header)
    offers = validate_payment_required(decoded)

    assert decoded["x402Version"] == 2
    assert len(offers) == 1
    assert offers[0].network == "layerx:1"
    assert offers[0].amount == "1000000"
    assert offers[0].commitment == "executed"


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"network": "paxeer:125"}, "invalid_network"),
        ({"asset": "0x" + "a" * 64}, "invalid_asset"),
        ({"payTo": "0x" + "b" * 64}, "invalid_pay_to"),
        ({"amount": "01"}, "invalid_amount"),
        ({"amount": str(1 << 128)}, "amount_out_of_range"),
        ({"maxTimeoutSeconds": True}, "invalid_timeout"),
        ({"extra": {"layerx": {"commitment": "finalized"}}}, "invalid_commitment"),
    ],
)
def test_rejects_invalid_offer_fields(updates, code):
    with pytest.raises(X402ContractError) as error:
        validate_payment_required(_envelope(**updates))

    assert error.value.code == code


def test_rejects_wrong_protocol_version_and_non_https_resource():
    wrong_version = _envelope()
    wrong_version["x402Version"] = 1
    with pytest.raises(X402ContractError, match="unsupported_protocol_version"):
        validate_payment_required(wrong_version)

    insecure = _envelope()
    insecure["resource"]["url"] = "http://provider.example/v1/search"
    with pytest.raises(X402ContractError, match="invalid_resource_url"):
        validate_payment_required(insecure)


def test_rejects_duplicate_json_keys_and_oversized_envelope():
    with pytest.raises(X402ContractError, match="duplicate_json_key"):
        decode_payment_required(_encoded(b'{"x402Version":2,"x402Version":2}'))

    with pytest.raises(X402ContractError, match="invalid_envelope_size"):
        decode_payment_required(_encoded(b" " * 65_537))


def test_validates_commitment_and_limits_alternatives():
    batched = _envelope(extra={"layerx": {"commitment": "batched"}})
    assert validate_payment_required(batched)[0].commitment == "batched"

    too_many = _envelope()
    too_many["accepts"] = [too_many["accepts"][0]] * 33
    with pytest.raises(X402ContractError, match="invalid_alternatives_count"):
        validate_payment_required(too_many)


@pytest.mark.asyncio
async def test_official_payment_verification_fails_closed_until_sdk_is_integrated():
    from paxrelay_paxeer import OfficialPaxeerAdapter
    from paxrelay_paxeer.errors import AdapterConfigurationError

    adapter = OfficialPaxeerAdapter(
        rpc_url="https://rpc.example",
        layerx_api_url="https://layerx.example",
    )

    with pytest.raises(
        AdapterConfigurationError,
        match="layerx_402lxp_v2_verifier_not_integrated",
    ):
        await adapter.verify_payment("{}", {})
