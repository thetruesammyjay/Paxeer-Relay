"""Add OIDC identity links and project-scoped dashboard roles.

Revision ID: 0018_oidc_project_memberships
Revises: 0017_service_version_mcp_contract
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_oidc_project_memberships"
down_revision = "0017_service_version_mcp_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "subject", name="uq_external_identity_issuer_subject"),
    )
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"])

    op.create_table(
        "project_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "project_id", "environment",
            name="uq_project_membership_user_project_env",
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'operator', 'analyst', 'viewer')",
            name="ck_project_membership_role",
        ),
    )
    op.create_index("ix_project_memberships_user_id", "project_memberships", ["user_id"])
    op.create_index(
        "ix_project_memberships_organisation_id",
        "project_memberships",
        ["organisation_id"],
    )
    op.create_index("ix_project_memberships_project_id", "project_memberships", ["project_id"])
    op.create_index(
        "ix_project_memberships_lookup",
        "project_memberships",
        ["user_id", "environment", "is_active"],
    )

    # Keep existing organization members' access explicit after the new
    # project-level boundary is introduced. Unknown legacy roles become read-only.
    op.execute(
        sa.text(
            """
            INSERT INTO project_memberships
                (id, user_id, organisation_id, project_id, environment, role,
                 is_active, created_at, updated_at)
            SELECT
                (md5(m.user_id::text || ':' || p.id::text || ':' || p.environment))::uuid,
                m.user_id,
                p.organisation_id,
                p.id,
                p.environment,
                CASE lower(m.role)
                    WHEN 'owner' THEN 'owner'
                    WHEN 'admin' THEN 'admin'
                    WHEN 'operator' THEN 'operator'
                    WHEN 'analyst' THEN 'analyst'
                    ELSE 'viewer'
                END,
                true,
                now(),
                now()
            FROM memberships AS m
            JOIN users AS u ON u.id = m.user_id AND u.is_active = true AND u.deleted_at IS NULL
            JOIN organisations AS o ON o.id = m.organisation_id
                AND o.is_active = true AND o.deleted_at IS NULL
            JOIN projects AS p ON p.organisation_id = m.organisation_id
                AND p.deleted_at IS NULL
            ON CONFLICT (user_id, project_id, environment) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_project_memberships_lookup", table_name="project_memberships")
    op.drop_index("ix_project_memberships_project_id", table_name="project_memberships")
    op.drop_index("ix_project_memberships_organisation_id", table_name="project_memberships")
    op.drop_index("ix_project_memberships_user_id", table_name="project_memberships")
    op.drop_table("project_memberships")
    op.drop_index("ix_external_identities_user_id", table_name="external_identities")
    op.drop_table("external_identities")
