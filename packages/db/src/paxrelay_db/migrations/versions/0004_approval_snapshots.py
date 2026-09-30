"""Bind approvals to the exact route, recipient, and policy version.

Revision ID: 0004_approval_snapshots
Revises: 0003_budget_reservations
"""

from __future__ import annotations

from alembic import op

revision = "0004_approval_snapshots"
down_revision = "0003_budget_reservations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh databases already have these columns from current metadata. Existing
    # installations need them added before the gateway can resume approvals.
    op.execute(
        "ALTER TABLE approval_requests "
        "ADD COLUMN IF NOT EXISTS provider_id UUID, "
        "ADD COLUMN IF NOT EXISTS service_version_id UUID, "
        "ADD COLUMN IF NOT EXISTS recipient_address VARCHAR(42), "
        "ADD COLUMN IF NOT EXISTS request_hash VARCHAR(66), "
        "ADD COLUMN IF NOT EXISTS policy_id UUID, "
        "ADD COLUMN IF NOT EXISTS policy_version INTEGER, "
        "ADD COLUMN IF NOT EXISTS decision_reason VARCHAR(512)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_approval_request_tool_call "
        "ON approval_requests (tool_call_id)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE approval_requests "
        "DROP CONSTRAINT IF EXISTS uq_approval_request_tool_call"
    )
    op.execute(
        "DROP INDEX IF EXISTS uq_approval_request_tool_call"
    )
    op.execute(
        "ALTER TABLE approval_requests "
        "DROP COLUMN IF EXISTS provider_id, "
        "DROP COLUMN IF EXISTS service_version_id, "
        "DROP COLUMN IF EXISTS recipient_address, "
        "DROP COLUMN IF EXISTS request_hash, "
        "DROP COLUMN IF EXISTS policy_id, "
        "DROP COLUMN IF EXISTS policy_version, "
        "DROP COLUMN IF EXISTS decision_reason"
    )
