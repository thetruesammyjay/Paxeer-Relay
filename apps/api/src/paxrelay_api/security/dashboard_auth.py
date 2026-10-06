"""Verify short-lived assertions signed by the trusted PaxRelay web server."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import Depends, Request
from redis.exceptions import RedisError
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_api.config import ApiSettings, get_settings
from paxrelay_api.exceptions import (
    AuthenticationUnavailableError,
    ForbiddenError,
    UnauthorizedError,
)
from paxrelay_db import ExternalIdentity, ProjectMembership, User, get_session

_ASSERTION_ISSUER = "paxrelay-web"
_ASSERTION_AUDIENCE = "paxrelay-api"


@dataclass(frozen=True)
class DashboardIdentity:
    user_id: UUID
    issuer: str
    subject: str
    email: str
    display_name: str | None


async def verify_dashboard_assertion(request: Request, token: str) -> dict[str, Any]:
    """Verify a narrowly scoped, short-lived web-server assertion."""
    settings: ApiSettings = getattr(request.app.state, "settings", None) or get_settings()
    if not settings.internal_dashboard_auth_secret or not settings.dashboard_oidc_issuer:
        raise UnauthorizedError("Dashboard sign-in is not configured.")
    try:
        claims = jwt.decode(
            token,
            settings.internal_dashboard_auth_secret,
            algorithms=["HS256"],
            issuer=_ASSERTION_ISSUER,
            audience=_ASSERTION_AUDIENCE,
            options={
                "require_sub": True,
                "require_iat": True,
                "require_exp": True,
                "require_jti": True,
            },
        )
    except JWTError as exc:
        raise UnauthorizedError("The dashboard session is invalid or expired.") from exc

    issuer = claims.get("oidc_issuer")
    subject = claims.get("sub")
    email = claims.get("email")
    issued_at = claims.get("iat")
    expires_at = claims.get("exp")
    token_id = claims.get("jti")
    if (
        issuer != settings.dashboard_oidc_issuer
        or not isinstance(subject, str)
        or not subject
        or not isinstance(email, str)
        or "@" not in email
        or claims.get("email_verified") is not True
        or not isinstance(issued_at, int)
        or not isinstance(expires_at, int)
        or expires_at <= issued_at
        or expires_at - issued_at > 90
        or issued_at > int(datetime.now(UTC).timestamp()) + 10
        or not isinstance(token_id, str)
        or not token_id
    ):
        raise UnauthorizedError("The dashboard session is invalid or expired.")

    if settings.rate_limiting_enabled:
        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            raise AuthenticationUnavailableError()
        try:
            accepted = await redis.set(
                f"{settings.redis_key_prefix}:dashboard:assertion:{token_id}",
                "1",
                ex=90,
                nx=True,
            )
        except (RedisError, OSError, TimeoutError) as exc:
            raise AuthenticationUnavailableError() from exc
        if not accepted:
            raise UnauthorizedError("The dashboard session is invalid or expired.")
    return claims


async def resolve_dashboard_identity(
    *,
    claims: dict[str, Any],
    session: AsyncSession,
) -> DashboardIdentity:
    """Link a verified OIDC subject to an active, pre-provisioned user."""
    issuer = claims["oidc_issuer"]
    subject = claims["sub"]
    email = claims["email"].strip().lower()
    identity = (
        await session.execute(
            select(ExternalIdentity).where(
                ExternalIdentity.issuer == issuer,
                ExternalIdentity.subject == subject,
            )
        )
    ).scalar_one_or_none()

    user: User | None
    identity_added = False
    if identity is not None:
        user = await session.get(User, identity.user_id)
    else:
        user = (
            await session.execute(
                select(User)
                .where(
                    func.lower(User.email) == email,
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if user is None:
            raise ForbiddenError(
                "This verified account has not been invited to an active PaxRelay project."
            )
        # A second first-login request may have linked this identity while
        # waiting for the user-row lock. Recheck before inserting the link.
        identity = (
            await session.execute(
                select(ExternalIdentity).where(
                    ExternalIdentity.issuer == issuer,
                    ExternalIdentity.subject == subject,
                )
            )
        ).scalar_one_or_none()
        if identity is not None:
            if identity.user_id != user.id:
                raise ForbiddenError("This external identity is linked to another PaxRelay account.")
        else:
            has_membership = await session.scalar(
                select(ProjectMembership.id)
                .where(
                    ProjectMembership.user_id == user.id,
                    ProjectMembership.is_active.is_(True),
                )
                .limit(1)
            )
            if has_membership is None:
                raise ForbiddenError(
                    "This verified account has not been invited to an active PaxRelay project."
                )
            session.add(ExternalIdentity(user_id=user.id, issuer=issuer, subject=subject))
            identity_added = True

    if user is None or not user.is_active or user.deleted_at is not None:
        raise ForbiddenError("This PaxRelay account is inactive.")

    now = datetime.now(UTC).replace(tzinfo=None)
    changed = identity_added
    if not user.email_verified:
        user.email_verified = True
        changed = True
    if user.last_login_at is None or user.last_login_at <= now - timedelta(minutes=10):
        user.last_login_at = now
        changed = True
    display_name = claims.get("name")
    if isinstance(display_name, str) and display_name.strip():
        normalized_name = display_name.strip()[:128]
        if user.display_name != normalized_name:
            user.display_name = normalized_name
            changed = True
    if changed:
        await session.flush()
    return DashboardIdentity(
        user_id=UUID(str(user.id)),
        issuer=issuer,
        subject=subject,
        email=email,
        display_name=user.display_name,
    )


async def get_dashboard_identity(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> DashboardIdentity:
    """Verify the web server assertion and resolve its provisioned user."""
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or token.startswith("pk_"):
        raise UnauthorizedError("A signed-in dashboard session is required.")
    claims = await verify_dashboard_assertion(request, token)
    return await resolve_dashboard_identity(claims=claims, session=session)
