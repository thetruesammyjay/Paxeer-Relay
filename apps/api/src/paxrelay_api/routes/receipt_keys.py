"""Public distribution endpoint for receipt verification keys."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from paxrelay_api.config import get_settings
from paxrelay_api.schemas import ReceiptKeyringOut
from paxrelay_receipts import ReceiptKeyring

logger = logging.getLogger("paxrelay.api.receipt_keys")

router = APIRouter(prefix="/receipt-keys", tags=["receipts"])


@router.get(
    "",
    response_model=ReceiptKeyringOut,
    response_class=JSONResponse,
    responses={503: {"description": "Receipt verification keys are unavailable."}},
)
def get_receipt_keyring(
    request: Request,
    response: Response,
) -> dict[str, object] | JSONResponse:
    """Return the configured public keyring without requiring authentication.

    The manifest contains public keys only. It is re-read and validated on
    every request so key rotation and revocation take effect without an API
    restart. Responses are not cacheable because stale revocation data would
    allow verifiers to trust a compromised key.
    """
    settings = getattr(request.app.state, "settings", None) or get_settings()
    manifest_path = settings.receipt_public_keyring_file
    if manifest_path is None:
        return _unavailable("Receipt verification keys are not configured.")

    try:
        keyring = ReceiptKeyring.from_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        logger.warning(
            "Receipt verification keyring unavailable error_type=%s",
            type(exc).__name__,
        )
        return _unavailable("Receipt verification keys are unavailable.")

    response.headers["Cache-Control"] = "no-store"
    return json.loads(keyring.to_json())


def _unavailable(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": detail},
        headers={"Cache-Control": "no-store"},
    )
