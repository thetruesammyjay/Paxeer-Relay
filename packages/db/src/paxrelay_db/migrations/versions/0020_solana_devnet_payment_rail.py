"""Add Solana Devnet provider destinations and payment evidence.

Revision ID: 0020_solana_devnet_payment_rail
Revises: 0019_layerx_testnet_accounts
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0020_solana_devnet_payment_rail"
down_revision = "0019_layerx_testnet_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column("solana_devnet_address", sa.String(length=44), nullable=True),
    )
    op.add_column(
        "quotes",
        sa.Column("network", sa.String(length=64), nullable=True),
    )
    # Preserve each existing LayerX quote's actual chain identifier. A fixed
    # migration default would incorrectly relabel historical non-125 quotes.
    op.execute(
        sa.text(
            "UPDATE quotes SET network = 'layerx:' || CAST(chain_id AS VARCHAR) "
            "WHERE network IS NULL"
        )
    )
    op.alter_column(
        "quotes",
        "network",
        existing_type=sa.String(length=64),
        server_default="layerx:125",
        nullable=False,
    )
    op.alter_column(
        "quotes",
        "chain_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "payments",
        sa.Column("solana_transaction_signature", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "solana_transaction_signature")
    # The previous schema requires a chain ID. Solana rows have none, so map
    # them to the legacy LayerX default when reverting this experimental rail.
    op.execute(sa.text("UPDATE quotes SET chain_id = 125 WHERE chain_id IS NULL"))
    op.alter_column(
        "quotes",
        "chain_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_column("quotes", "network")
    op.drop_column("providers", "solana_devnet_address")
