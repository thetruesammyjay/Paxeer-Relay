"""Invite and manage people with access to the current project."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select

from paxrelay_api.audit import record_change
from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import ConflictError, ForbiddenError, NotFoundError
from paxrelay_api.schemas import ProjectMemberCreate, ProjectMemberOut, ProjectMemberUpdate
from paxrelay_api.security.authorization import require_scope
from paxrelay_api.security.scopes import ALL_SCOPES
from paxrelay_db import Project, ProjectMembership, User
from paxrelay_db.repositories._common import sid

router = APIRouter(prefix="/project-members", tags=["project-members"])


def _require_human_project_admin(tenant: TenantDep) -> None:
    if tenant.user_id is None or tenant.role not in {"owner", "admin"}:
        raise ForbiddenError("A signed-in project owner or administrator must manage membership.")


def _out(membership: ProjectMembership, user: User) -> ProjectMemberOut:
    return ProjectMemberOut(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        is_active=membership.is_active,
        created_at=membership.created_at,
    )


async def _get_membership(
    session: SessionDep,
    tenant: TenantDep,
    membership_id: UUID,
) -> tuple[ProjectMembership, User]:
    row = (
        await session.execute(
            select(ProjectMembership, User)
            .join(User, User.id == ProjectMembership.user_id)
            .where(
                ProjectMembership.id == sid(membership_id),
                ProjectMembership.organisation_id == sid(tenant.organisation_id),
                ProjectMembership.project_id == sid(tenant.project_id),
                ProjectMembership.environment == tenant.environment,
            )
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("Project member not found.")
    return row[0], row[1]


async def _protect_last_owner(
    session: SessionDep,
    tenant: TenantDep,
    membership: ProjectMembership,
    new_role: str | None = None,
    *,
    revoking: bool = False,
) -> None:
    removing_owner = membership.role == "owner" and (
        revoking or new_role not in (None, "owner")
    )
    if not removing_owner:
        return
    active_owners = await session.scalar(
        select(func.count())
        .select_from(ProjectMembership)
        .where(
            ProjectMembership.organisation_id == sid(tenant.organisation_id),
            ProjectMembership.project_id == sid(tenant.project_id),
            ProjectMembership.environment == tenant.environment,
            ProjectMembership.role == "owner",
            ProjectMembership.is_active.is_(True),
            ProjectMembership.id != membership.id,
        )
    )
    if not active_owners:
        raise ConflictError("A project must keep at least one active owner.")


async def _lock_project(session: SessionDep, tenant: TenantDep) -> None:
    """Serialize role changes so concurrent requests cannot remove all owners."""
    project = (
        await session.execute(
            select(Project.id)
            .where(
                Project.id == sid(tenant.project_id),
                Project.organisation_id == sid(tenant.organisation_id),
                Project.environment == tenant.environment,
                Project.is_active.is_(True),
                Project.deleted_at.is_(None),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project not found.")


@router.get(
    "",
    response_model=list[ProjectMemberOut],
    dependencies=[Depends(require_scope("project-members:read"))],
)
async def list_project_members(
    session: SessionDep,
    tenant: TenantDep,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[ProjectMemberOut]:
    rows = (
        await session.execute(
            select(ProjectMembership, User)
            .join(User, User.id == ProjectMembership.user_id)
            .where(
                ProjectMembership.organisation_id == sid(tenant.organisation_id),
                ProjectMembership.project_id == sid(tenant.project_id),
                ProjectMembership.environment == tenant.environment,
            )
            .order_by(User.email)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [_out(row[0], row[1]) for row in rows]


@router.post(
    "",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("project-members:write"))],
)
async def invite_project_member(
    body: ProjectMemberCreate,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> ProjectMemberOut:
    _require_human_project_admin(tenant)
    if body.role == "owner" and not tenant.scopes.issuperset(ALL_SCOPES):
        raise ForbiddenError("Only a project owner can grant the owner role.")

    await _lock_project(session, tenant)

    user = (
        await session.execute(
            select(User).where(func.lower(User.email) == body.email).with_for_update()
        )
    ).scalar_one_or_none()
    if user is None:
        user = User(
            id=sid(uuid4()),
            email=body.email,
            email_verified=False,
            is_active=True,
        )
        session.add(user)
        await session.flush()
    elif not user.is_active or user.deleted_at is not None:
        raise ConflictError("This account is inactive and cannot be invited.")

    existing = (
        await session.execute(
            select(ProjectMembership).where(
                ProjectMembership.user_id == user.id,
                ProjectMembership.project_id == sid(tenant.project_id),
                ProjectMembership.environment == tenant.environment,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.is_active:
            raise ConflictError("This person is already a member of the project.")
        existing.role = body.role
        existing.is_active = True
        membership = existing
        event_type = "project.member.reactivated"
    else:
        membership = ProjectMembership(
            id=sid(uuid4()),
            user_id=user.id,
            organisation_id=sid(tenant.organisation_id),
            project_id=sid(tenant.project_id),
            environment=tenant.environment,
            role=body.role,
            is_active=True,
        )
        session.add(membership)
        event_type = "project.member.invited"
    await session.flush()
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type=event_type,
        resource_type="project_membership",
        resource_id=membership.id,
        details={"email": user.email, "role": membership.role},
    )
    return _out(membership, user)


@router.patch(
    "/{membership_id}",
    response_model=ProjectMemberOut,
    dependencies=[Depends(require_scope("project-members:write"))],
)
async def update_project_member(
    membership_id: UUID,
    body: ProjectMemberUpdate,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> ProjectMemberOut:
    _require_human_project_admin(tenant)
    if body.role == "owner" and not tenant.scopes.issuperset(ALL_SCOPES):
        raise ForbiddenError("Only a project owner can grant the owner role.")
    await _lock_project(session, tenant)
    membership, user = await _get_membership(session, tenant, membership_id)
    await _protect_last_owner(session, tenant, membership, body.role)
    membership.role = body.role
    await session.flush()
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="project.member.role_updated",
        resource_type="project_membership",
        resource_id=membership.id,
        details={"email": user.email, "role": membership.role},
    )
    return _out(membership, user)


@router.delete(
    "/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    dependencies=[Depends(require_scope("project-members:write"))],
)
async def revoke_project_member(
    membership_id: UUID,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> Response:
    _require_human_project_admin(tenant)
    await _lock_project(session, tenant)
    membership, user = await _get_membership(session, tenant, membership_id)
    await _protect_last_owner(session, tenant, membership, revoking=True)
    membership.is_active = False
    await session.flush()
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="project.member.revoked",
        resource_type="project_membership",
        resource_id=membership.id,
        details={"email": user.email, "role": membership.role},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
