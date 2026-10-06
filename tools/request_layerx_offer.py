"""Request one live gateway quote and save its validated PAYMENT-REQUIRED header."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from layerx_sdk.x402 import payment_commitment, payment_payer
from layerx_sdk.x402_http import decode_header, validate_required


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, code, msg, headers, newurl
        raise ValueError("gateway-redirect-refused")


def _https_gateway_base(value: str) -> str:
    base = value.rstrip("/")
    parsed = urlsplit(base)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("gateway-url-must-be-https")
    return base


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Request a staging quote and save its validated 402LXP v2 offer."
    )
    parser.add_argument("--gateway-base-url", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--request-file", required=True, type=Path)
    parser.add_argument("--output", default=Path("payment-required.txt"), type=Path)
    args = parser.parse_args()

    try:
        base = _https_gateway_base(args.gateway_base_url)
        configured_gateway = os.environ.get(
            "GATEWAY_PUBLIC_BASE_URL", ""
        ).strip().rstrip("/")
        if configured_gateway != base:
            raise ValueError("buyer_and_gateway_url_mismatch")
        agent_id = str(uuid.UUID(args.agent_id))
        api_key = os.environ.get("PAXRELAY_AGENT_API_KEY", "").strip()
        if len(api_key) != 51 or not api_key.startswith("pk_"):
            raise ValueError("PAXRELAY_AGENT_API_KEY_missing_or_invalid")
        raw = args.request_file.read_text(encoding="utf-8-sig")
        if not raw or len(raw.encode("utf-8")) > 1_048_576:
            raise ValueError("request_body_size_invalid")
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError("request_body_must_be_an_object")

        request = Request(
            base + "/v1/invoke",
            data=json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Agent-Id": agent_id,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        opener = build_opener(_NoRedirect())
        try:
            response = opener.open(request, timeout=30)
        except HTTPError as exc:
            response = exc
            status = exc.code
        else:
            status = response.status
        with response:
            header = response.headers.get("PAYMENT-REQUIRED")
            response_body = response.read(1_048_577)
        if status != 402 or not header or len(response_body) > 1_048_576:
            raise ValueError("gateway_did_not_return_a_valid_402_offer")

        required = validate_required(decode_header(header))
        offers = required["accepts"]
        if len(offers) != 1:
            raise ValueError("expected_one_payment_offer")
        offer = offers[0]
        if (
            offer["scheme"] != "exact"
            or payment_commitment(offer.get("extra")) != "executed"
        ):
            raise ValueError("unsupported_payment_offer")
        resource_url = required["resource"]["url"]
        base_parts = urlsplit(base)
        resource_parts = urlsplit(resource_url)
        expected_path = base_parts.path.rstrip("/") + "/v1/invoke/"
        if (
            resource_parts.scheme != "https"
            or resource_parts.netloc != base_parts.netloc
            or resource_parts.query
            or resource_parts.fragment
            or not resource_parts.path.startswith(expected_path)
        ):
            raise ValueError("payment_resource_does_not_match_gateway")
        challenge_body = json.loads(response_body)
        if not isinstance(challenge_body, dict):
            raise ValueError("invalid_gateway_challenge_body")
        tool_call_id = str(uuid.UUID(challenge_body["tool_call_id"]))
        resource_path = resource_parts.path
        if resource_path.rsplit("/", 1)[-1] != tool_call_id:
            raise ValueError("payment_resource_call_id_mismatch")
        expected_network = os.environ.get("LAYERX_TESTNET_NETWORK_ID", "").strip()
        gateway_network = os.environ.get("LAYERX_NETWORK_ID", "").strip()
        expected_payer = os.environ.get(
            "LAYERX_TESTNET_PAYER_ACCOUNT", ""
        ).strip().lower()
        expected_asset = os.environ.get("LAYERX_USDX_ASSET_ID", "").strip().lower()
        if not all(
            (expected_network, gateway_network, expected_payer, expected_asset)
        ):
            raise ValueError("buyer_environment_incomplete")
        if expected_network != gateway_network:
            raise ValueError("buyer_and_gateway_network_mismatch")
        if offer["network"] != f"layerx:{int(expected_network)}":
            raise ValueError("buyer_and_gateway_network_mismatch")
        if payment_payer(offer.get("extra")) != expected_payer:
            raise ValueError("buyer_and_gateway_payer_mismatch")
        if offer["asset"] != expected_asset:
            raise ValueError("buyer_and_gateway_asset_mismatch")
        gateway_key = os.environ.get("LAYERX_SEQUENCER_PUBLIC_KEY", "").strip().lower()
        buyer_key = os.environ.get(
            "LAYERX_TESTNET_SEQUENCER_PUBLIC_KEY", ""
        ).strip().lower()
        if not gateway_key or gateway_key != buyer_key:
            raise ValueError("buyer_and_gateway_sequencer_mismatch")
        args.output.write_text(header, encoding="ascii")
        print(
            json.dumps(
                {
                    "state": "offer_saved",
                    "resource_url": resource_url,
                    "network": offer["network"],
                    "amount_atomic": offer["amount"],
                    "asset": offer["asset"],
                    "pay_to": offer["payTo"],
                    "payer": payment_payer(offer.get("extra")),
                    "payment_required_file": str(args.output),
                },
                separators=(",", ":"),
            )
        )
        return 0
    except Exception:
        print(
            json.dumps(
                {"state": "error", "error": "layerx_offer_request_failed"}
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
