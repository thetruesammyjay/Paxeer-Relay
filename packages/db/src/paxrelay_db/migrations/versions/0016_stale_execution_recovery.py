"""Index active execution reservations for stale recovery.

Revision ID: 0016_stale_execution_recovery
Revises: 0015_agent_failure_policy_lookup
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0016_stale_execution_recovery"
down_revision = "0015_agent_failure_policy_lookup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_execution_attempts_active_stale",
        "execution_attempts",
        ["execution_state", "created_at", "id"],
        postgresql_where=sa.text("execution_state IN ('reserved', 'running')"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_execution_attempts_active_stale",
        table_name="execution_attempts",
    )
