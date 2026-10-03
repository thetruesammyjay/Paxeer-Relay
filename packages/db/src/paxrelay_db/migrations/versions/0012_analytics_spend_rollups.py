"""Add hourly and daily tenant spend rollups.

Revision ID: 0012_analytics_spend_rollups
Revises: 0011_provider_indexing_attempt_lookup
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_analytics_spend_rollups"
down_revision = "0011_provider_indexing_attempt_lookup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_spend_rollups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("period", sa.String(length=8), nullable=False),
        sa.Column("bucket_start", sa.DateTime(), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("capability", sa.String(length=256), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("currency_decimals", sa.Integer(), nullable=False),
        sa.Column("total_amount_atomic", sa.Numeric(precision=78, scale=0), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_analytics_spend_rollup_dimensions",
        "analytics_spend_rollups",
        [
            "organisation_id",
            "project_id",
            "environment",
            "period",
            "bucket_start",
            "agent_id",
            "capability",
            "currency",
            "currency_decimals",
        ],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_analytics_spend_rollup_dimensions",
        table_name="analytics_spend_rollups",
    )
    op.drop_table("analytics_spend_rollups")
