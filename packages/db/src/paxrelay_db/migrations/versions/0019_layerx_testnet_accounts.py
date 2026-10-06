"""Store LayerX provider accounts and full payment destinations.

Revision ID: 0019_layerx_testnet_accounts
Revises: 0018_oidc_project_memberships
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0019_layerx_testnet_accounts"
down_revision = "0018_oidc_project_memberships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column("layerx_account_id", sa.String(length=64), nullable=True),
    )
    op.alter_column(
        "quotes",
        "recipient_address",
        existing_type=sa.String(length=42),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "approval_requests",
        "recipient_address",
        existing_type=sa.String(length=42),
        type_=sa.String(length=64),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "approval_requests",
        "recipient_address",
        existing_type=sa.String(length=64),
        type_=sa.String(length=42),
        existing_nullable=True,
    )
    op.alter_column(
        "quotes",
        "recipient_address",
        existing_type=sa.String(length=64),
        type_=sa.String(length=42),
        existing_nullable=False,
    )
    op.drop_column("providers", "layerx_account_id")
