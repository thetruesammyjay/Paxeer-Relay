"""Store recoverable, authenticated-encrypted webhook signing secrets.

Revision ID: 0002_webhook_secret_encryption
Revises: 0001_initial
"""

from __future__ import annotations

from alembic import op

revision = "0002_webhook_secret_encryption"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 creates from current metadata on a fresh database, while databases
    # already at 0001 need this additive column. IF NOT EXISTS supports both.
    op.execute(
        "ALTER TABLE webhook_endpoints "
        "ADD COLUMN IF NOT EXISTS secret_ciphertext TEXT"
    )
    # Older rows contain only a one-way digest. Disable them because the
    # original secret cannot be reconstructed for signed webhook delivery.
    op.execute(
        "UPDATE webhook_endpoints "
        "SET is_active = FALSE "
        "WHERE secret_ciphertext IS NULL AND is_active IS TRUE"
    )


def downgrade() -> None:
    # The legacy secret_hash column remains available to the prior application.
    op.execute(
        "ALTER TABLE webhook_endpoints "
        "DROP COLUMN IF EXISTS secret_ciphertext"
    )
