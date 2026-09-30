"""Index active approvals for scheduled expiration scans.

Revision ID: 0005_approval_expiration_index
Revises: 0004_approval_snapshots
"""

from __future__ import annotations

from alembic import op

revision = "0005_approval_expiration_index"
down_revision = "0004_approval_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_approval_expiration_pending "
        "ON approval_requests (expires_at, id) "
        "WHERE status IN ('pending', 'approved')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_approval_expiration_pending")
