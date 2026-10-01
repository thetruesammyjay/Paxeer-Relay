"""Persist bounded provider results for completed idempotent calls.

Revision ID: 0010_tool_call_result_replay
Revises: 0009_reconciliation_source_fingerprint
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_tool_call_result_replay"
down_revision = "0009_reconciliation_source_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tool_calls", sa.Column("result_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tool_calls", "result_json")
