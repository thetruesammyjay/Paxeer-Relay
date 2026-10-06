"""Prepare one testnet PAYMENT-SIGNATURE with the official LayerX buyer SDK.

The input activity must already be signed by the funded test payer authority.
This command submits that activity through LayerX RPC and prints only the
resulting payment header; it never reads or prints an account private key.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from layerx_sdk.x402 import payment_commitment, payment_payer
from layerx_sdk.x402_http import decode_header, validate_required
from layerx_sdk.x402_rpc import PaymentRpc

from paxrelay_paxeer.layerx_receipts import LayerXReceiptVerifier


_HEX_32 = re.compile(r"^[0-9a-f]{64}$")


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submit a payer-signed LayerX testnet activity and prepare its 402LXP proof."
    )
    parser.add_argument(
        "--payment-required-file",
        required=True,
        type=Path,
        help="File containing the Base64 PAYMENT-REQUIRED response header.",
    )
    parser.add_argument(
        "--signed-activity-file",
        required=True,
        type=Path,
        help="File containing the already-signed canonical activity as lowercase hex.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Explicitly submit the signed activity to LayerX; omit for a preflight summary.",
    )
    args = parser.parse_args()

    try:
        rpc_url = _required_env("LAYERX_TESTNET_RPC_URL")
        key_id = _required_env("LAYERX_TESTNET_API_KEY_ID")
        api_key = _required_env("LAYERX_TESTNET_API_KEY_SECRET")
        payer = _required_env("LAYERX_TESTNET_PAYER_ACCOUNT").lower()
        network_id = int(_required_env("LAYERX_TESTNET_NETWORK_ID"))
        sequencer_key = _required_env("LAYERX_TESTNET_SEQUENCER_PUBLIC_KEY").lower()
        if not _HEX_32.fullmatch(payer) or payer == "0" * 64:
            raise ValueError(
                "LAYERX_TESTNET_PAYER_ACCOUNT must be a nonzero 32-byte hex account"
            )
        if not _HEX_32.fullmatch(sequencer_key):
            raise ValueError("LAYERX_TESTNET_SEQUENCER_PUBLIC_KEY must be 32-byte hex")
        if not 1 <= network_id <= 0xFFFF_FFFF:
            raise ValueError("LAYERX_TESTNET_NETWORK_ID is out of range")
        gateway_network_id = _required_env("LAYERX_NETWORK_ID")
        gateway_sequencer_key = _required_env(
            "LAYERX_SEQUENCER_PUBLIC_KEY"
        ).lower()
        gateway_asset_id = _required_env("LAYERX_USDX_ASSET_ID").lower()
        public_gateway = _required_env("GATEWAY_PUBLIC_BASE_URL").rstrip("/")
        expected_payer = _required_env("LAYERX_TESTNET_PAYER_ACCOUNT").lower()
        if int(gateway_network_id) != network_id:
            raise ValueError("buyer_and_gateway_network_mismatch")
        if gateway_sequencer_key != sequencer_key:
            raise ValueError("buyer_and_gateway_sequencer_mismatch")
        if expected_payer != payer:
            raise ValueError("buyer_and_gateway_payer_mismatch")
        if not re.fullmatch(r"[A-Za-z0-9._~-]{1,128}", key_id):
            raise ValueError("LAYERX_TESTNET_API_KEY_ID has an invalid format")

        required_header = args.payment_required_file.read_text(encoding="utf-8").strip()
        required = validate_required(decode_header(required_header))
        offers = [
            offer
            for offer in required["accepts"]
            if offer["scheme"] == "exact"
            and offer["network"] == f"layerx:{network_id}"
            and payment_commitment(offer.get("extra")) == "executed"
            and payment_payer(offer.get("extra")) == payer
        ]
        if len(offers) != 1:
            raise ValueError("challenge does not contain one exact offer bound to this testnet payer")
        offer = offers[0]
        if offer["asset"] != gateway_asset_id:
            raise ValueError("buyer_and_gateway_asset_mismatch")
        resource_url = required["resource"]["url"]
        parsed_resource = urlsplit(resource_url)
        parsed_gateway = urlsplit(public_gateway)
        expected_path = parsed_gateway.path.rstrip("/") + "/v1/invoke/"
        if (
            parsed_resource.scheme != "https"
            or parsed_resource.netloc != parsed_gateway.netloc
            or parsed_resource.query
            or parsed_resource.fragment
            or not parsed_resource.path.startswith(expected_path)
        ):
            raise ValueError("payment_resource_gateway_mismatch")
        resource_call_id = parsed_resource.path.rsplit("/", 1)[-1]
        if not re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            resource_call_id,
        ):
            raise ValueError("payment_resource_call_id_invalid")

        canonical_hex = args.signed_activity_file.read_text(encoding="utf-8").strip()
        if (
            not canonical_hex
            or len(canonical_hex) > 1_048_576
            or re.fullmatch(r"(?:[0-9a-fA-F]{2})+", canonical_hex) is None
        ):
            raise ValueError(
                "signed activity file must contain canonical activity hex"
            )
        canonical = bytes.fromhex(canonical_hex)
        activity_id = hashlib.sha256(b"LXP/v1/activity-id\0" + canonical).hexdigest()

        if not args.submit:
            print(
                json.dumps(
                    {
                        "state": "preflight_only",
                        "activity_id": activity_id,
                        "resource_url": resource_url,
                        "network": offer["network"],
                        "amount_atomic": offer["amount"],
                        "asset": offer["asset"],
                        "pay_to": offer["payTo"],
                        "payer": payer,
                        "submission_requires": "--submit",
                    },
                    separators=(",", ":"),
                )
            )
            return 0

        rpc = PaymentRpc(
            rpc_url,
            {"Authorization": f"LayerX-Key {key_id}:{api_key}"},
        )
        verifier = LayerXReceiptVerifier(
            network_id=network_id,
            sequencer_public_key=sequencer_key,
        )
        proof = verifier.buyer_middleware(rpc).prepare(
            required_header,
            canonical_hex.lower(),
            activity_id,
            payer,
        )
        if proof is None:
            print(json.dumps({"state": "pending", "activity_id": activity_id}))
            return 2
        print(
            json.dumps(
                {
                    "state": "verified",
                    "activity_id": activity_id,
                    "payment_signature": proof,
                },
                separators=(",", ":"),
            )
        )
        return 0
    except Exception:
        # Keep credentials, response bodies, and arbitrary RPC data out of CLI output.
        print(
            json.dumps({"state": "error", "error": "layerx_buyer_failed"}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
