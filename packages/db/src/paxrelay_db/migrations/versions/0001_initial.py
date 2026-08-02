"""initial schema — all PaxRelay tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-02

This initial migration creates the entire schema directly from the SQLAlchemy
metadata (``Base.metadata``). Driving it from the ORM guarantees the migrated
schema always matches the model definitions exactly. Subsequent migrations
should use explicit ``op.*`` operations generated via ``alembic revision
--autogenerate``.
"""

from __future__ import annotations

from alembic import op

# Importing the db package registers every model on Base.metadata.
import paxrelay_db  # noqa: F401
from paxrelay_db.base import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
