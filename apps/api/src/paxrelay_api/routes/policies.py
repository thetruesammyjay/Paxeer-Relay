"""Policy creation, listing, and assignment routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from paxrelay_domain import Policy, PolicyAssignment, PolicyMode, PolicyRules
from paxrelay_db.repositories import SqlAlchemyAgentRepository, SqlAlchemyPolicyRepository

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.audit import record_change
from paxrelay_api.exceptions import NotFoundError
from paxrelay_api.schemas import (
    PolicyAssignIn,
    PolicyAssignmentOut,
    PolicyCreate,
    PolicyDetailOut,
    PolicyOut,
    PolicyRulesOut,
)
from paxrelay_api.security.authorization import require_scope
from paxrelay_api.tenant import tenant_owns

router = APIRouter(prefix="/policies", tags=["policies"])


def _money_to_atomic(value) -> dict | None:
    """Map a MoneyIn schema to the atomic dict the domain PolicyRules expects."""
    if value is None:
        return None
    return {
        "amount_atomic": value.amount_atomic,
        "currency": value.currency,
        "decimals": value.decimals,
    }


@router.post(
    "",
    response_model=PolicyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("policies:write"))],
)
async def create_policy(
    body: PolicyCreate,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> PolicyOut:
    repo = SqlAlchemyPolicyRepository(session)
    rules = PolicyRules(
        maximum_per_call=_money_to_atomic(body.maximum_per_call),
        daily_budget=_money_to_atomic(body.daily_budget),
        monthly_budget=_money_to_atomic(body.monthly_budget),
        allowed_capabilities=body.allowed_capabilities,
        allowed_providers=body.allowed_providers,
        blocked_providers=body.blocked_providers,
        minimum_provider_reputation=body.minimum_provider_reputation,
        minimum_provider_success_rate=body.minimum_provider_success_rate,
        maximum_accepted_latency_ms=body.maximum_accepted_latency_ms,
        maximum_consecutive_failures=body.maximum_consecutive_failures,
        approval_threshold=_money_to_atomic(body.approval_threshold),
    )
    policy = Policy(
        organisation_id=tenant.organisation_id,
        project_id=tenant.project_id,
        environment=tenant.environment,
        name=body.name,
        description=body.description,
        mode=PolicyMode(body.mode),
        rules=rules,
    )
    saved = await repo.save(policy)
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="policy.created",
        resource_type="policy",
        resource_id=saved.id,
        details={"name": saved.name, "mode": saved.mode.value},
    )
    return PolicyOut(
        id=saved.id,
        name=saved.name,
        description=saved.description,
        mode=saved.mode.value,
        version=saved.version,
        is_active=saved.is_active,
    )


@router.get(
    "",
    response_model=list[PolicyOut],
    dependencies=[Depends(require_scope("policies:read"))],
)
async def list_policies(
    session: SessionDep,
    tenant: TenantDep,
    mode: str | None = Query(None, description="Filter by policy mode"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    search: str | None = Query(None, description="Case-insensitive match on name"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[PolicyOut]:
    repo = SqlAlchemyPolicyRepository(session)
    policies = await repo.list(
        tenant.organisation_id,
        tenant.project_id,
        limit=limit,
        offset=offset,
        mode=mode,
        is_active=is_active,
        search=search,
        environment=tenant.environment,
    )
    return [
        PolicyOut(
            id=p.id,
            name=p.name,
            description=p.description,
            mode=p.mode.value,
            version=p.version,
            is_active=p.is_active,
        )
        for p in policies
    ]


@router.get(
    "/{policy_id}",
    response_model=PolicyDetailOut,
    dependencies=[Depends(require_scope("policies:read"))],
)
async def get_policy(
    policy_id: UUID, session: SessionDep, tenant: TenantDep
) -> PolicyDetailOut:
    repo = SqlAlchemyPolicyRepository(session)
    policy = await repo.get(policy_id)
    # Treat a cross-tenant resource as not-found to avoid information leakage.
    if policy is None or not tenant_owns(tenant, policy):
        raise NotFoundError(f"Policy {policy_id} not found.")
    assignments = await repo.list_assignments(policy_id)
    return PolicyDetailOut(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        mode=policy.mode.value,
        version=policy.version,
        is_active=policy.is_active,
        rules=PolicyRulesOut.model_validate(policy.rules.model_dump(mode="json")),
        assignments=[
            PolicyAssignmentOut(
                id=assignment.id,
                agent_id=assignment.agent_id,
                policy_id=assignment.policy_id,
                assigned_at=assignment.assigned_at,
            )
            for assignment in assignments
        ],
    )


@router.post(
    "/{policy_id}/assign",
    response_model=PolicyAssignmentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("policies:write"))],
)
async def assign_policy(
    policy_id: UUID,
    body: PolicyAssignIn,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> PolicyAssignmentOut:
    repo = SqlAlchemyPolicyRepository(session)
    policy = await repo.get(policy_id)
    # Verify ownership so callers cannot assign policies from other tenants.
    if policy is None or not tenant_owns(tenant, policy):
        raise NotFoundError(f"Policy {policy_id} not found.")

    agent = await SqlAlchemyAgentRepository(session).get(body.agent_id)
    if agent is None or not tenant_owns(tenant, agent):
        raise NotFoundError(f"Agent {body.agent_id} not found.")
    assignment = await repo.assign(PolicyAssignment(agent_id=body.agent_id, policy_id=policy_id))
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="policy.assigned",
        resource_type="policy_assignment",
        resource_id=assignment.id,
        details={"policy_id": str(policy_id), "agent_id": str(body.agent_id)},
    )
    return PolicyAssignmentOut(
        id=assignment.id,
        agent_id=assignment.agent_id,
        policy_id=assignment.policy_id,
        assigned_at=assignment.assigned_at,
    )
