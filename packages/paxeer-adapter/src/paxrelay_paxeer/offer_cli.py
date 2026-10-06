"""Probe a provider's 402 response without submitting payment evidence."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.parse import urlsplit

import httpx

from paxrelay_paxeer.x402_http import (
    X402ContractError,
    decode_payment_required,
    validate_payment_required,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Send one request without payment, then validate the provider's "
            "402LXP HTTP v2 PAYMENT-REQUIRED offer. This command never pays."
        )
    )
    parser.add_argument("url", help="HTTPS provider resource URL")
    parser.add_argument("--method", choices=("GET", "POST"), default="GET")
    parser.add_argument(
        "--json-body",
        help="JSON request body for a POST probe (do not put credentials here)",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    if args.timeout <= 0 or args.timeout > 120:
        parser.error("--timeout must be greater than 0 and at most 120 seconds")
    try:
        parsed_url = urlsplit(args.url)
        if (
            parsed_url.scheme != "https"
            or not parsed_url.hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
        ):
            raise ValueError("url_must_be_https_without_userinfo")
        body: Any = None
        if args.json_body is not None:
            if args.method != "POST":
                raise ValueError("json_body_requires_post")
            body = json.loads(args.json_body)
        with httpx.Client(timeout=args.timeout, follow_redirects=False) as client:
            with client.stream(args.method, args.url, json=body) as response:
                status_code = response.status_code
                header = response.headers.get("PAYMENT-REQUIRED")
        if status_code != 402:
            raise ValueError(f"expected_http_402_received_{status_code}")
        if not header:
            raise ValueError("missing_PAYMENT-REQUIRED_header")
        envelope = decode_payment_required(header)
        offers = validate_payment_required(envelope)
        if not offers:
            raise ValueError("no_exact_offer_supported_by_this_demo_path")
        output_offers = [
            {
                "network": item.network,
                "asset": item.asset,
                "amount": item.amount,
                "pay_to": item.pay_to,
                "max_timeout_seconds": item.max_timeout_seconds,
                "commitment": item.commitment,
            }
            for item in offers
        ]
        print(
            json.dumps(
                {
                    "valid": True,
                    "http_status": status_code,
                    "protocol_version": envelope["x402Version"],
                    "exact_offers": output_offers,
                    "payment_submitted": False,
                },
                indent=2,
            )
        )
        return 0
    except (httpx.HTTPError, ValueError) as exc:
        if isinstance(exc, X402ContractError):
            code = exc.code
        elif isinstance(exc, httpx.HTTPError):
            code = "provider_request_failed"
        else:
            code = str(exc)
        print(json.dumps({"valid": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
