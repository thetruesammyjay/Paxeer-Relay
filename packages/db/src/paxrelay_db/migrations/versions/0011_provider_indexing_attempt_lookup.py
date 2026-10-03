"""Index execution history queries used by provider metric indexing.

Revision ID: 0011_provider_indexing_attempt_lookup
Revises: 0010_tool_call_result_replay
"""

from __future__ import annotations

from alembic import op

revision = "0011_provider_indexing_attempt_lookup"
down_revision = "0010_tool_call_result_replay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_execution_attempts_service_version_created",
        "execution_attempts",
        ["service_version_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_execution_attempts_service_version_created",
        table_name="execution_attempts",
    )
