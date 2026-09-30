"""Deliver queued webhooks with bounded requests and lease-based recovery."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from paxrelay_db import get_engine
from paxrelay_db.models.executions import WebhookDeliveryModel, WebhookEndpointModel
from paxrelay_receipts.webhook_secrets import decrypt_webhook_secret
from paxrelay_worker.config import WorkerSettings
from paxrelay_worker.jobs import BaseJob
from paxrelay_worker.webhook_transport import (
    UnsafeWebhookDestination,
    WebhookDnsFailure,
    WebhookDnsTimeout,
    pinned_webhook_transport,
    resolve_webhook_destination,
)

logger = logging.getLogger("paxrelay.worker.webhooks")


@dataclass(frozen=True)
class DeliveryClaim:
    delivery_id: str
    endpoint_id: str
    event_type: str
    payload: dict[str, Any]
    attempt_count: int
    claim_token: str
    endpoint_url: str | None
    secret_ciphertext: str | None
    endpoint_active: bool


@dataclass(frozen=True)
class DeliveryResult:
    error: str | None = None
    status_code: int | None = None
    retryable: bool = False
    retry_after_seconds: int | None = None

    @property
    def succeeded(self) -> bool:
        return (
            self.error is None
            and self.status_code is not None
            and 200 <= self.status_code < 300
        )


class WebhookDeliveryJob(BaseJob):
    """Claim due rows, sign requests, and persist success or bounded retries."""

    interval_seconds = 2

    def __init__(self, settings: WorkerSettings) -> None:
        super().__init__(settings)
        self._sessions = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )

    async def tick(self) -> None:
        claims = await self._claim_due_deliveries()
        if not claims:
            return
        await asyncio.gather(*(self._deliver_and_record(claim) for claim in claims))

    async def _claim_due_deliveries(self) -> list[DeliveryClaim]:
        now = datetime.now(UTC).replace(tzinfo=None)
        stale_before = now - timedelta(
            seconds=self.settings.webhook_delivery_lease_seconds
        )
        limit = min(
            self.settings.webhook_delivery_batch_size,
            self.settings.webhook_delivery_concurrency,
        )
        due = or_(
            and_(
                WebhookDeliveryModel.status == "pending",
                or_(
                    WebhookDeliveryModel.next_attempt_at.is_(None),
                    WebhookDeliveryModel.next_attempt_at <= now,
                ),
            ),
            and_(
                WebhookDeliveryModel.status == "processing",
                WebhookDeliveryModel.claimed_at.is_not(None),
                WebhookDeliveryModel.claimed_at <= stale_before,
            ),
        )
        async with self._sessions() as session:
            stmt = (
                select(WebhookDeliveryModel, WebhookEndpointModel)
                .outerjoin(
                    WebhookEndpointModel,
                    WebhookEndpointModel.id == WebhookDeliveryModel.endpoint_id,
                )
                .where(due)
                .order_by(
                    WebhookDeliveryModel.created_at.asc(),
                    WebhookDeliveryModel.id.asc(),
                )
                .limit(limit)
                .with_for_update(of=WebhookDeliveryModel, skip_locked=True)
            )
            rows = (await session.execute(stmt)).all()
            claims: list[DeliveryClaim] = []
            for delivery, endpoint in rows:
                token = str(uuid4())
                delivery.status = "processing"
                delivery.claim_token = token
                delivery.claimed_at = now
                delivery.attempt_count = int(delivery.attempt_count or 0) + 1
                claims.append(
                    DeliveryClaim(
                        delivery_id=delivery.id,
                        endpoint_id=delivery.endpoint_id,
                        event_type=delivery.event_type,
                        payload=dict(delivery.payload_json or {}),
                        attempt_count=delivery.attempt_count,
                        claim_token=token,
                        endpoint_url=endpoint.url if endpoint is not None else None,
                        secret_ciphertext=(
                            endpoint.secret_ciphertext if endpoint is not None else None
                        ),
                        endpoint_active=(
                            bool(endpoint.is_active) if endpoint is not None else False
                        ),
                    )
                )
            if claims:
                await session.commit()
            return claims

    async def _deliver_and_record(self, claim: DeliveryClaim) -> None:
        try:
            result = await self._send(claim)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "Webhook delivery failed internally delivery_id=%s error_type=%s",
                claim.delivery_id,
                type(exc).__name__,
            )
            result = DeliveryResult(error="internal_delivery_error", retryable=True)
        now = datetime.now(UTC).replace(tzinfo=None)
        if result.succeeded:
            status = "delivered"
            next_attempt_at = None
            delivered_at = now
        elif (
            result.retryable
            and claim.attempt_count < self.settings.webhook_max_attempts
        ):
            status = "pending"
            retry_seconds = result.retry_after_seconds or min(
                self.settings.webhook_initial_retry_seconds
                * (2 ** (claim.attempt_count - 1)),
                3600,
            )
            next_attempt_at = now + timedelta(seconds=retry_seconds)
            delivered_at = None
        else:
            status = "cancelled" if result.error == "endpoint_inactive" else "failed"
            next_attempt_at = None
            delivered_at = None

        async with self._sessions() as session:
            update_result = await session.execute(
                update(WebhookDeliveryModel)
                .where(
                    WebhookDeliveryModel.id == claim.delivery_id,
                    WebhookDeliveryModel.status == "processing",
                    WebhookDeliveryModel.claim_token == claim.claim_token,
                )
                .values(
                    status=status,
                    http_status_code=result.status_code,
                    next_attempt_at=next_attempt_at,
                    delivered_at=delivered_at,
                    last_error=result.error,
                    claimed_at=None,
                    claim_token=None,
                    updated_at=now,
                )
            )
            await session.commit()

        if update_result.rowcount == 0:
            logger.warning(
                "Discarded stale webhook claim result delivery_id=%s",
                claim.delivery_id,
            )
            return

        if result.error:
            logger.warning(
                "Webhook delivery did not succeed delivery_id=%s event_type=%s "
                "attempt=%d status=%s error=%s http_status=%s",
                claim.delivery_id,
                claim.event_type,
                claim.attempt_count,
                status,
                result.error,
                result.status_code,
            )
        else:
            logger.info(
                "Webhook delivered delivery_id=%s event_type=%s attempt=%d",
                claim.delivery_id,
                claim.event_type,
                claim.attempt_count,
            )

    async def _send(self, claim: DeliveryClaim) -> DeliveryResult:
        if not claim.endpoint_active or not claim.endpoint_url:
            return DeliveryResult(error="endpoint_inactive")
        if not claim.secret_ciphertext:
            return DeliveryResult(error="secret_unavailable")
        master_key = self.settings.webhook_encryption_key or self.settings.auth_secret
        if not master_key:
            return DeliveryResult(error="encryption_key_unavailable")
        try:
            secret = decrypt_webhook_secret(
                claim.secret_ciphertext,
                master_key,
                claim.endpoint_id,
            )
        except ValueError:
            return DeliveryResult(error="secret_decryption_failed")

        if claim.payload.get("event_type") != claim.event_type:
            return DeliveryResult(error="invalid_event_payload")
        event_id = claim.payload.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            return DeliveryResult(error="invalid_event_payload")

        try:
            body = json.dumps(
                claim.payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError):
            return DeliveryResult(error="invalid_event_payload")
        if len(body) > self.settings.webhook_max_request_bytes:
            return DeliveryResult(error="request_too_large")

        allow_private = self.settings.app_env in {"development", "test"}
        try:
            async with asyncio.timeout(self.settings.webhook_request_timeout_seconds):
                destination = await resolve_webhook_destination(
                    claim.endpoint_url,
                    allow_private=allow_private,
                    timeout_seconds=min(
                        5.0,
                        self.settings.webhook_request_timeout_seconds,
                    ),
                )
                timestamp = str(int(time.time()))
                signature = hmac.new(
                    secret.encode("utf-8"),
                    timestamp.encode("ascii")
                    + b"."
                    + claim.delivery_id.encode("ascii")
                    + b"."
                    + claim.event_type.encode("ascii")
                    + b"."
                    + body,
                    hashlib.sha256,
                ).hexdigest()
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "PaxRelay-Webhooks/1.0",
                    "X-PaxRelay-Event": claim.event_type,
                    "X-PaxRelay-Delivery-Id": claim.delivery_id,
                    "X-PaxRelay-Timestamp": timestamp,
                    "X-PaxRelay-Signature": f"sha256={signature}",
                }
                if isinstance(event_id, str):
                    headers["X-PaxRelay-Event-Id"] = event_id

                transport = pinned_webhook_transport(destination)
                async with httpx.AsyncClient(
                    transport=transport,
                    timeout=httpx.Timeout(
                        self.settings.webhook_request_timeout_seconds,
                        connect=min(5.0, self.settings.webhook_request_timeout_seconds),
                    ),
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    async with client.stream(
                        "POST",
                        claim.endpoint_url,
                        content=body,
                        headers=headers,
                        follow_redirects=False,
                    ) as response:
                        response_bytes = 0
                        async for chunk in response.aiter_bytes():
                            response_bytes += len(chunk)
                            if (
                                response_bytes
                                > self.settings.webhook_max_response_bytes
                            ):
                                return DeliveryResult(
                                    error="response_too_large",
                                    status_code=response.status_code,
                                )
                        code = response.status_code
                        if 200 <= code < 300:
                            return DeliveryResult(status_code=code)
                        retry_after = _retry_after_seconds(
                            response.headers.get("Retry-After")
                        )
                        retryable = code in {408, 425, 429} or code >= 500
                        return DeliveryResult(
                            error=f"http_{code}",
                            status_code=code,
                            retryable=retryable,
                            retry_after_seconds=retry_after if code == 429 else None,
                        )
        except UnsafeWebhookDestination:
            return DeliveryResult(error="unsafe_destination")
        except WebhookDnsTimeout:
            return DeliveryResult(error="dns_timeout", retryable=True)
        except WebhookDnsFailure:
            return DeliveryResult(error="dns_failure", retryable=True)
        except (TimeoutError, httpx.TimeoutException):
            return DeliveryResult(error="timeout", retryable=True)
        except httpx.InvalidURL:
            return DeliveryResult(error="invalid_destination")
        except httpx.HTTPError:
            return DeliveryResult(error="connection_error", retryable=True)
        except RuntimeError:
            return DeliveryResult(error="pinned_transport_unavailable")
        except asyncio.CancelledError:
            raise


def _retry_after_seconds(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return min(max(int(value), 1), 3600)
    except ValueError:
        return None
