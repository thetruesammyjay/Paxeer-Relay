"""Index completed provider attempts for agent failure policies.

Revision ID: 0015_agent_failure_policy_lookup
Revises: 0014_provider_health_fail_closed
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015_agent_failure_policy_lookup"
down_revision = "0014_provider_health_fail_closed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_execution_attempts_terminal_completion",
        "execution_attempts",
        [
            "response_received_at",
            "created_at",
            "attempt_number",
            "id",
        ],
        postgresql_where=sa.text(
            "response_received_at IS NOT NULL AND execution_state IN "
            "('succeeded', 'provider_error', 'timeout', 'unknown')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_execution_attempts_terminal_completion",
        table_name="execution_attempts",
    )
