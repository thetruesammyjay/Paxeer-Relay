"""Index pending outbox events for ordered worker batches.

Revision ID: 0006_outbox_pending_index
Revises: 0005_approval_expiration_index
"""

from __future__ import annotations

from alembic import op

revision = "0006_outbox_pending_index"
down_revision = "0005_approval_expiration_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_outbox_pending_created "
        "ON outbox_events (created_at, id) WHERE status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_outbox_pending_created")
