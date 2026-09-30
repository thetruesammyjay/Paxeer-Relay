"""Add internal reconciliation timestamps and a one-record-per-payment review queue.

Revision ID: 0008_settlement_review_queue
Revises: 0007_webhook_delivery_claims
"""

from __future__ import annotations

from alembic import op

revision = "0008_settlement_review_queue"
down_revision = "0007_webhook_delivery_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE settlement_records "
        "ADD COLUMN IF NOT EXISTS internal_checked_at TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "ADD COLUMN IF NOT EXISTS claim_token VARCHAR(36)"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "ADD COLUMN IF NOT EXISTS last_error VARCHAR(64)"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "ADD COLUMN IF NOT EXISTS l1_settlement_id VARCHAR(66)"
    )
    op.execute(
        "UPDATE settlement_records "
        "SET reconciliation_status = 'awaiting_external' "
        "WHERE reconciliation_status = 'pending'"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conname = 'uq_settlement_record_payment' "
        "AND conrelid = 'settlement_records'::regclass) THEN "
        "IF EXISTS (SELECT payment_id FROM settlement_records "
        "GROUP BY payment_id HAVING COUNT(*) > 1) THEN "
        "RAISE EXCEPTION 'duplicate settlement_records.payment_id values must be reviewed before migration'; "
        "END IF; "
        "ALTER TABLE settlement_records ADD CONSTRAINT "
        "uq_settlement_record_payment UNIQUE (payment_id); "
        "END IF; END $$"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_settlement_reconciliation_review "
        "ON settlement_records (reconciliation_status, created_at, id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_settlement_reconciliation_due "
        "ON settlement_records (next_attempt_at, created_at, id) "
        "WHERE reconciliation_status IN ('awaiting_external', 'layerx_confirmed')"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_settlement_reconciliation_claim "
        "ON settlement_records (claimed_at) WHERE claim_token IS NOT NULL"
    )
    op.execute("DROP INDEX IF EXISTS ix_settlement_records_payment_id")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_settlement_reconciliation_claim")
    op.execute("DROP INDEX IF EXISTS ix_settlement_reconciliation_due")
    op.execute("DROP INDEX IF EXISTS ix_settlement_reconciliation_review")
    op.execute(
        "ALTER TABLE settlement_records "
        "DROP CONSTRAINT IF EXISTS uq_settlement_record_payment"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "DROP COLUMN IF EXISTS internal_checked_at"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "DROP COLUMN IF EXISTS last_error"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "DROP COLUMN IF EXISTS claim_token"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "DROP COLUMN IF EXISTS claimed_at"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "DROP COLUMN IF EXISTS last_checked_at"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "DROP COLUMN IF EXISTS next_attempt_at"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "DROP COLUMN IF EXISTS attempt_count"
    )
    op.execute(
        "ALTER TABLE settlement_records "
        "DROP COLUMN IF EXISTS l1_settlement_id"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_settlement_records_payment_id "
        "ON settlement_records (payment_id)"
    )
