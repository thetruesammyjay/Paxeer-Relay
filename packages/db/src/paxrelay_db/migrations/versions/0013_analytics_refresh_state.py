"""Record successful analytics rollup refreshes.

Revision ID: 0013_analytics_refresh_state
Revises: 0012_analytics_spend_rollups
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_analytics_refresh_state"
down_revision = "0012_analytics_spend_rollups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_refresh_state",
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(), nullable=False),
        sa.Column("hourly_from", sa.DateTime(), nullable=False),
        sa.Column("daily_from", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("environment"),
    )


def downgrade() -> None:
    op.drop_table("analytics_refresh_state")
