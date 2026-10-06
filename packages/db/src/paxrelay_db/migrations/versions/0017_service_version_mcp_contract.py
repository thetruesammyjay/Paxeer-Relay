"""Store the protocol and MCP tool contract in immutable service versions.

Revision ID: 0017_service_version_mcp_contract
Revises: 0016_stale_execution_recovery
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0017_service_version_mcp_contract"
down_revision = "0016_stale_execution_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_versions",
        sa.Column(
            "protocol",
            sa.String(length=16),
            server_default="http",
            nullable=False,
        ),
    )
    op.alter_column("service_versions", "protocol", server_default=None)
    op.add_column(
        "service_versions",
        sa.Column("mcp_tool_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "service_versions",
        sa.Column("mcp_input_schema", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("service_versions", "mcp_input_schema")
    op.drop_column("service_versions", "mcp_tool_name")
    op.drop_column("service_versions", "protocol")
