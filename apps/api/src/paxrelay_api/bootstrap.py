"""Provision an organisation, project, and initial scoped API key.

Run this administrative command once after database migrations. It prints the
new secret a single time and never writes it to the database or application
logs.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import secrets
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from paxrelay_api.config import get_settings
from paxrelay_api.security.scopes import ALL_SCOPES, encode_scopes
from paxrelay_db import (
    ApiKey,
    AuditLogModel,
    Organisation,
    Project,
    ProjectMembership,
    User,
    close_database,
    configure_database,
    get_engine,
)
from paxrelay_db.repositories._common import sid

_KEY_PREFIX = "pk_"


def _slug(value: str) -> str:
    slug = "-".join(value.lower().strip().split())
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", slug):
        raise ValueError(
            "Slugs must start with a lowercase letter or number and use only letters, numbers, and hyphens."
        )
    return slug


async def _provision(
    *,
    organisation_name: str,
    organisation_slug: str,
    project_name: str,
    project_slug: str,
    environment: str,
    owner_email: str | None,
) -> str:
    settings = get_settings()
    if environment != settings.app_env:
        raise ValueError(
            f"Bootstrap environment {environment!r} must match APP_ENV {settings.app_env!r}."
        )
    configure_database(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )

    raw_key = _KEY_PREFIX + secrets.token_hex(24)
    organisation_id = sid(uuid4())
    project_id = sid(uuid4())
    scopes = encode_scopes(ALL_SCOPES)
    now = datetime.now(UTC).replace(tzinfo=None)

    try:
        session_factory = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
        async with session_factory() as session:
            async with session.begin():
                organisation = (
                    await session.execute(
                        select(Organisation).where(
                            Organisation.slug == organisation_slug,
                            Organisation.deleted_at.is_(None),
                        )
                    )
                ).scalar_one_or_none()

                if organisation is None:
                    organisation = Organisation(
                        id=organisation_id,
                        name=organisation_name,
                        slug=organisation_slug,
                        plan="free",
                        is_active=True,
                    )
                    session.add(organisation)
                    await session.flush()
                    session.add(
                        AuditLogModel(
                            id=sid(uuid4()),
                            organisation_id=organisation.id,
                            project_id=project_id,
                            environment=environment,
                            event_type="organisation.provisioned",
                            actor_id="system:bootstrap",
                            resource_type="organisation",
                            resource_id=organisation.id,
                            details={"slug": organisation.slug},
                        )
                    )
                elif not organisation.is_active:
                    raise ValueError("The requested organisation is inactive.")

                project = (
                    await session.execute(
                        select(Project).where(
                            Project.organisation_id == organisation.id,
                            Project.slug == project_slug,
                            Project.environment == environment,
                            Project.deleted_at.is_(None),
                        )
                    )
                ).scalar_one_or_none()

                if project is None:
                    project = Project(
                        id=project_id,
                        organisation_id=organisation.id,
                        project_id=project_id,
                        environment=environment,
                        name=project_name,
                        slug=project_slug,
                        description="Provisioned by the PaxRelay API bootstrap command.",
                        is_active=True,
                    )
                    session.add(project)
                    await session.flush()
                    session.add(
                        AuditLogModel(
                            id=sid(uuid4()),
                            organisation_id=organisation.id,
                            project_id=project.project_id,
                            environment=environment,
                            event_type="project.provisioned",
                            actor_id="system:bootstrap",
                            resource_type="project",
                            resource_id=project.id,
                            details={"slug": project.slug},
                        )
                    )
                elif not project.is_active:
                    raise ValueError("The requested project is inactive.")

                if owner_email is not None:
                    owner = (
                        await session.execute(
                            select(User)
                            .where(func.lower(User.email) == owner_email)
                            .with_for_update()
                        )
                    ).scalar_one_or_none()
                    if owner is None:
                        owner = User(
                            id=sid(uuid4()),
                            email=owner_email,
                            email_verified=False,
                            is_active=True,
                        )
                        session.add(owner)
                        await session.flush()
                    elif not owner.is_active or owner.deleted_at is not None:
                        raise ValueError("The requested initial owner account is inactive.")

                    membership = (
                        await session.execute(
                            select(ProjectMembership).where(
                                ProjectMembership.user_id == owner.id,
                                ProjectMembership.project_id == project.project_id,
                                ProjectMembership.environment == environment,
                            )
                        )
                    ).scalar_one_or_none()
                    if membership is None:
                        membership = ProjectMembership(
                            id=sid(uuid4()),
                            user_id=owner.id,
                            organisation_id=organisation.id,
                            project_id=project.project_id,
                            environment=environment,
                            role="owner",
                            is_active=True,
                        )
                        session.add(membership)
                    else:
                        membership.organisation_id = organisation.id
                        membership.role = "owner"
                        membership.is_active = True
                    await session.flush()
                    session.add(
                        AuditLogModel(
                            id=sid(uuid4()),
                            organisation_id=organisation.id,
                            project_id=project.project_id,
                            environment=environment,
                            event_type="project.owner.provisioned",
                            actor_id="system:bootstrap",
                            resource_type="project_membership",
                            resource_id=membership.id if membership is not None else owner.id,
                            details={"email": owner.email, "role": "owner"},
                        )
                    )

                key = ApiKey(
                    id=sid(uuid4()),
                    name="Initial administrator key",
                    key_prefix=raw_key[: len(_KEY_PREFIX) + 8],
                    key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
                    key_type="live" if environment == "production" else "test",
                    scopes=scopes,
                    organisation_id=organisation.id,
                    project_id=project.project_id,
                    environment=environment,
                    expires_at=now + timedelta(days=90),
                )
                session.add(key)
                await session.flush()
                session.add(
                    AuditLogModel(
                        id=sid(uuid4()),
                        organisation_id=organisation.id,
                        project_id=project.project_id,
                        environment=environment,
                        event_type="api_key.created",
                        actor_id="system:bootstrap",
                        resource_type="api_key",
                        resource_id=key.id,
                        details={
                            "key_prefix": key.key_prefix,
                            "scope_count": len(ALL_SCOPES),
                        },
                    )
                )
    finally:
        await close_database()

    return raw_key


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an organisation/project and print one initial API key."
    )
    parser.add_argument("--organisation-name", required=True)
    parser.add_argument("--organisation-slug", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--project-slug", required=True)
    parser.add_argument(
        "--owner-email",
        help="Verified work email for the first project owner; required for staging and production.",
    )
    parser.add_argument(
        "--environment",
        choices=("development", "staging", "production"),
        default="development",
    )
    args = parser.parse_args()

    try:
        owner_email = args.owner_email.strip().lower() if args.owner_email else None
        if args.environment in {"staging", "production"} and not owner_email:
            raise ValueError("--owner-email is required for staging and production bootstrap.")
        if owner_email is not None and (
            len(owner_email) > 320
            or "@" not in owner_email
            or owner_email.startswith("@")
            or owner_email.endswith("@")
        ):
            raise ValueError("--owner-email must be a valid email address.")
        if not 1 <= len(args.organisation_name.strip()) <= 128:
            raise ValueError("Organisation names must contain 1 to 128 characters.")
        if not 1 <= len(args.project_name.strip()) <= 128:
            raise ValueError("Project names must contain 1 to 128 characters.")
        key = asyncio.run(
            _provision(
                organisation_name=args.organisation_name.strip(),
                organisation_slug=_slug(args.organisation_slug),
                project_name=args.project_name.strip(),
                project_slug=_slug(args.project_slug),
                environment=args.environment,
                owner_email=owner_email,
            )
        )
    except ValueError as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001 - avoid printing connection details/secrets.
        print(
            f"Bootstrap failed ({type(exc).__name__}). Check the database configuration and migrations.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    if args.owner_email:
        print(f"Initial project owner provisioned: {args.owner_email.strip().lower()}")
    print("PaxRelay API key (shown once; store it in your secret manager):")
    print(key)
    print("Scopes: all currently defined API scopes")
    print("Expiry: 90 days")


if __name__ == "__main__":
    main()
