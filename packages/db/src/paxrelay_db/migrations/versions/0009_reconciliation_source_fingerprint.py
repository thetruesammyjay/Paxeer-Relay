"""Track reconciliation-relevant facts without treating every row update as a change.

Revision ID: 0009_reconciliation_source_fingerprint
Revises: 0008_settlement_review_queue
"""

from __future__ import annotations

from alembic import op

revision = "0009_reconciliation_source_fingerprint"
down_revision = "0008_settlement_review_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE settlement_records "
        "ADD COLUMN IF NOT EXISTS internal_fingerprint VARCHAR(64)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE settlement_records "
        "DROP COLUMN IF EXISTS internal_fingerprint"
    )
