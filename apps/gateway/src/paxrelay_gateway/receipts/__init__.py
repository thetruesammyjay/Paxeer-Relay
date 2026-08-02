"""Receipt issuance sub-package."""

from paxrelay_gateway.receipts.issuer import build_and_sign_receipt

__all__ = ["build_and_sign_receipt"]
