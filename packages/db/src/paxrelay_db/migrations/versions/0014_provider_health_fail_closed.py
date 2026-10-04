"""Do not route services before a real provider health check.

Revision ID: 0014_provider_health_fail_closed
Revises: 0013_analytics_refresh_state
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014_provider_health_fail_closed"
down_revision = "0013_analytics_refresh_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older service creation marked metrics as healthy before the worker had
    # probed the endpoint. Preserve observed services and fail closed for rows
    # that have no recorded probe timestamp.
    op.execute(
        sa.text(
            """
            UPDATE provider_metrics AS metrics
            SET health_check_passing = FALSE,
                availability_score = 0.0,
                reputation_score = 0.5
            FROM services AS service
            WHERE metrics.service_id = service.id
              AND COALESCE(service.health_json ->> 'last_check_at', '') = ''
            """
        )
    )


def downgrade() -> None:
    # Do not restore synthetic healthy state; the worker will measure services.
    pass
