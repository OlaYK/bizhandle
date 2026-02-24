"""add team invitations table

Revision ID: 20260224_0023
Revises: 20260224_0022
Create Date: 2026-02-24 18:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260224_0023"
down_revision: Union[str, None] = "20260224_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("invited_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("accepted_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="staff"),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_team_invitations_token_hash"),
    )
    op.create_index("ix_team_invitations_business_id", "team_invitations", ["business_id"], unique=False)
    op.create_index(
        "ix_team_invitations_invited_by_user_id",
        "team_invitations",
        ["invited_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_team_invitations_accepted_by_user_id",
        "team_invitations",
        ["accepted_by_user_id"],
        unique=False,
    )
    op.create_index("ix_team_invitations_token_hash", "team_invitations", ["token_hash"], unique=True)
    op.create_index(
        "ix_team_invites_biz_status_expires",
        "team_invitations",
        ["business_id", "status", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_team_invites_biz_email_status",
        "team_invitations",
        ["business_id", "email", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_team_invites_biz_email_status", table_name="team_invitations")
    op.drop_index("ix_team_invites_biz_status_expires", table_name="team_invitations")
    op.drop_index("ix_team_invitations_token_hash", table_name="team_invitations")
    op.drop_index("ix_team_invitations_accepted_by_user_id", table_name="team_invitations")
    op.drop_index("ix_team_invitations_invited_by_user_id", table_name="team_invitations")
    op.drop_index("ix_team_invitations_business_id", table_name="team_invitations")
    op.drop_table("team_invitations")
