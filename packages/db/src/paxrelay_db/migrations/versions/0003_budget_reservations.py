"""Reserve per-agent policy budget for outstanding payment quotes.

Revision ID: 0003_budget_reservations
Revises: 0002_webhook_secret_encryption
"""

from __future__ import annotations

from alembic import op

revision = "0003_budget_reservations"
down_revision = "0002_webhook_secret_encryption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The initial migration creates from current metadata on fresh installs.
    # IF NOT EXISTS also upgrades databases that already applied revision 0001.
    op.execute(
        "CREATE TABLE IF NOT EXISTS budget_reservations ("
        "id UUID PRIMARY KEY, "
        "organisation_id UUID NOT NULL, "
        "project_id UUID NOT NULL, "
        "environment VARCHAR(32) NOT NULL, "
        "agent_id UUID NOT NULL, "
        "quote_id UUID NOT NULL, "
        "amount_atomic NUMERIC(78, 0) NOT NULL, "
        "currency VARCHAR(16) NOT NULL, "
        "status VARCHAR(16) NOT NULL DEFAULT 'active', "
        "expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, "
        "consumed_at TIMESTAMP WITHOUT TIME ZONE NULL, "
        "created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "CONSTRAINT uq_budget_reservation_quote UNIQUE (quote_id)"
        ")"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_budget_reservation_agent_status_expiry "
        "ON budget_reservations (agent_id, status, expires_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS budget_reservations")
