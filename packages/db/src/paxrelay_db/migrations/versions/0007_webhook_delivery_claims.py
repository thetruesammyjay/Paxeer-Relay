"""Add leased claims and retry diagnostics to webhook deliveries.

Revision ID: 0007_webhook_delivery_claims
Revises: 0006_outbox_pending_index
"""

from __future__ import annotations

from alembic import op

revision = "0007_webhook_delivery_claims"
down_revision = "0006_outbox_pending_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE webhook_deliveries "
        "ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP, "
        "ADD COLUMN IF NOT EXISTS claim_token VARCHAR(36), "
        "ADD COLUMN IF NOT EXISTS last_error VARCHAR(64)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_webhook_delivery_due "
        "ON webhook_deliveries (next_attempt_at, created_at, id) "
        "WHERE status = 'pending'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_webhook_delivery_stale_claim "
        "ON webhook_deliveries (claimed_at) WHERE status = 'processing'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_webhook_delivery_due")
    op.execute("DROP INDEX IF EXISTS ix_webhook_delivery_stale_claim")
    op.execute(
        "ALTER TABLE webhook_deliveries "
        "DROP COLUMN IF EXISTS claimed_at, "
        "DROP COLUMN IF EXISTS claim_token, "
        "DROP COLUMN IF EXISTS last_error"
    )
