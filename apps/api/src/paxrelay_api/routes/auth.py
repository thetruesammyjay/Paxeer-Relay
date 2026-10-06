"""OIDC dashboard project discovery and signed-in user context."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from paxrelay_api.config import get_settings
from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import NotFoundError
from paxrelay_api.schemas import DashboardProjectOut
from paxrelay_api.security.dashboard_auth import DashboardIdentity, get_dashboard_identity
from paxrelay_api.security.rate_limit import enforce_dashboard_discovery_limit
from paxrelay_db import Organisation, Project, ProjectMembership

router = APIRouter(prefix="/auth", tags=["dashboard-auth"])


@router.get("/projects", response_model=list[DashboardProjectOut])
async def list_dashboard_projects(
    request: Request,
    response: Response,
    session: SessionDep,
    identity: DashboardIdentity = Depends(get_dashboard_identity),
) -> list[DashboardProjectOut]:
    """List active project memberships available to the signed-in user."""
    settings = getattr(request.app.state, "settings", None) or get_settings()
    await enforce_dashboard_discovery_limit(
        request=request,
        response=response,
        user_id=identity.user_id,
        settings=settings,
    )
    environment = "development" if settings.app_env == "test" else settings.app_env
    rows = (
        await session.execute(
            select(ProjectMembership, Project, Organisation)
            .join(Project, Project.id == ProjectMembership.project_id)
            .join(Organisation, Organisation.id == ProjectMembership.organisation_id)
            .where(
                ProjectMembership.user_id == str(identity.user_id),
                ProjectMembership.environment == environment,
                ProjectMembership.is_active.is_(True),
                Project.organisation_id == ProjectMembership.organisation_id,
                Project.environment == ProjectMembership.environment,
                Project.is_active.is_(True),
                Project.deleted_at.is_(None),
                Organisation.is_active.is_(True),
                Organisation.deleted_at.is_(None),
            )
            .order_by(Organisation.name, Project.name)
        )
    ).all()
    return [
        DashboardProjectOut(
            organisation_id=row[0].organisation_id,
            organisation_name=row[2].name,
            project_id=row[0].project_id,
            project_name=row[1].name,
            environment=row[0].environment,
            role=row[0].role,
        )
        for row in rows
    ]


@router.get("/context", response_model=DashboardProjectOut)
async def get_dashboard_context(
    tenant: TenantDep,
    session: SessionDep,
) -> DashboardProjectOut:
    """Return the selected project context after membership authorization."""
    membership = await session.get(ProjectMembership, str(tenant.membership_id))
    project = await session.get(Project, str(tenant.project_id))
    organisation = await session.get(Organisation, str(tenant.organisation_id))
    if membership is None or project is None or organisation is None:
        raise NotFoundError("Project context not found.")
    return DashboardProjectOut(
        organisation_id=tenant.organisation_id,
        organisation_name=organisation.name,
        project_id=tenant.project_id,
        project_name=project.name,
        environment=tenant.environment,
        role=membership.role,
    )
