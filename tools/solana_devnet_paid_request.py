"""Run one bounded x402 V2 payment against PaxRelay using Solana Devnet."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from x402 import x402Client
from x402.http import (
    decode_payment_required_header,
    encode_payment_signature_header,
)
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.exact import ExactSvmScheme

SOLANA_DEVNET_NETWORK = "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"
SOLANA_DEVNET_USDC_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Set {name} in .solana-buyer.env")
    return value


def _same_origin(left: str, right: str) -> bool:
    a = urlsplit(left)
    b = urlsplit(right)
    return (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submit one policy-controlled paid request using Devnet USDC."
    )
    parser.add_argument("--capability", required=True)
    parser.add_argument("--arguments-json", default="{}")
    parser.add_argument("--idempotency-key")
    args = parser.parse_args()

    try:
        gateway_url = _required_env("PAXRELAY_GATEWAY_URL").rstrip("/")
        agent_id = _required_env("PAXRELAY_AGENT_ID")
        agent_api_key = _required_env("PAXRELAY_AGENT_API_KEY")
        private_key = _required_env("SOLANA_DEVNET_PRIVATE_KEY")
        rpc_url = os.environ.get(
            "SOLANA_DEVNET_RPC_URL", "https://api.devnet.solana.com"
        ).strip()
        max_amount = int(os.environ.get("SOLANA_X402_MAX_AMOUNT_ATOMIC", "10000"))
        if max_amount < 1 or max_amount > 10_000:
            raise ValueError(
                "SOLANA_X402_MAX_AMOUNT_ATOMIC must be between 1 and 10000 "
                "(0.01 Devnet USDC)."
            )
        arguments = json.loads(args.arguments_json)
        if not isinstance(arguments, dict):
            raise ValueError("--arguments-json must be a JSON object.")
        if private_key.startswith("["):
            secret_bytes = bytes(json.loads(private_key))
            keypair = Keypair.from_bytes(secret_bytes)
        else:
            keypair = Keypair.from_base58_string(private_key)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    auth_headers = {
        "Authorization": f"Bearer {agent_api_key}",
        "X-Agent-Id": agent_id,
    }
    idempotency_key = args.idempotency_key or str(uuid4())
    if not 1 <= len(idempotency_key) <= 128:
        print(
            "Configuration error: idempotency key must be 1-128 characters.",
            file=sys.stderr,
        )
        return 2
    print(f"idempotency_key={idempotency_key}", file=sys.stderr)
    request_body = {
        "capability": args.capability,
        "idempotency_key": idempotency_key,
        "arguments": arguments,
        "payment_rail": "solana-devnet",
    }

    try:
        with httpx.Client(timeout=30, follow_redirects=False) as http:
            challenge_response = http.post(
                f"{gateway_url}/v1/invoke",
                headers=auth_headers,
                json=request_body,
            )
            if challenge_response.status_code != 402:
                print(
                    json.dumps(
                        {
                            "phase": "challenge",
                            "status": challenge_response.status_code,
                            "response": _json_or_text(challenge_response),
                        },
                        indent=2,
                    ),
                    file=sys.stderr,
                )
                return 1

            encoded_requirement = challenge_response.headers.get("PAYMENT-REQUIRED")
            if not encoded_requirement:
                raise ValueError("The gateway did not return PAYMENT-REQUIRED.")
            required = decode_payment_required_header(encoded_requirement)
            if required.x402_version != 2 or not required.resource:
                raise ValueError("The gateway returned an unsupported x402 offer.")
            if len(required.accepts) != 1:
                raise ValueError("Expected exactly one payment option in the offer.")
            requirement = required.accepts[0]
            if (
                requirement.scheme != "exact"
                or requirement.network != SOLANA_DEVNET_NETWORK
                or requirement.asset != SOLANA_DEVNET_USDC_MINT
            ):
                raise ValueError(
                    "Offer is not the configured Solana Devnet exact-USDC payment."
                )
            amount = int(requirement.amount)
            if amount < 1 or amount > max_amount:
                raise ValueError(
                    f"Offered amount {amount} atomic units exceeds the local cap "
                    f"of {max_amount}. No payment was created."
                )
            Pubkey.from_string(requirement.pay_to)
            expected_tool_call_id = challenge_response.json().get("tool_call_id")
            expected_resource_url = (
                f"{gateway_url}/v1/invoke/{expected_tool_call_id}"
            )
            if (
                not expected_tool_call_id
                or required.resource.url != expected_resource_url
                or not _same_origin(required.resource.url, gateway_url)
            ):
                raise ValueError(
                    "The offered resource URL does not match this gateway request."
                )

            buyer = x402Client()
            buyer.register(
                SOLANA_DEVNET_NETWORK,
                ExactSvmScheme(
                    signer=KeypairSigner(keypair),
                    rpc_url=rpc_url,
                ),
            )
            payload = buyer.create_payment_payload(
                required,
                resource=required.resource,
            )
            payment_signature = encode_payment_signature_header(payload)

            paid_response = http.post(
                required.resource.url,
                headers={**auth_headers, "PAYMENT-SIGNATURE": payment_signature},
                json={},
            )
            response_body = _json_or_text(paid_response)
            if paid_response.is_error:
                print(
                    json.dumps(
                        {
                            "phase": "settlement_or_delivery",
                            "status": paid_response.status_code,
                            "response": response_body,
                            "payment_response": paid_response.headers.get(
                                "PAYMENT-RESPONSE"
                            ),
                        },
                        indent=2,
                    ),
                    file=sys.stderr,
                )
                return 1

            print(
                json.dumps(
                    {
                        "status": paid_response.status_code,
                        "network": requirement.network,
                        "asset": requirement.asset,
                        "amount_atomic": requirement.amount,
                        "recipient": requirement.pay_to,
                        "payment_response": paid_response.headers.get(
                            "PAYMENT-RESPONSE"
                        ),
                        "result": response_body,
                    },
                    indent=2,
                )
            )
            return 0
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        print(f"Paid request failed: {exc}", file=sys.stderr)
        return 1


def _json_or_text(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError:
        return response.text[:2_000]


if __name__ == "__main__":
    raise SystemExit(main())
