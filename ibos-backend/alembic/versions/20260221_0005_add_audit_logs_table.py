"""add audit logs table

Revision ID: 20260221_0005
Revises: 20260221_0004
Create Date: 2026-02-21 21:25:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260221_0005"
down_revision: Union[str, None] = "20260221_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("actor_user_id", sa.String(length=36), nullable=False),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("target_type", sa.String(length=100), nullable=False),
            sa.Column("target_id", sa.String(length=36), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "audit_logs"):
        return

    if not _index_exists(inspector, "audit_logs", "ix_audit_logs_business_id"):
        op.create_index("ix_audit_logs_business_id", "audit_logs", ["business_id"], unique=False)
    if not _index_exists(inspector, "audit_logs", "ix_audit_logs_actor_user_id"):
        op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"], unique=False)
    if not _index_exists(inspector, "audit_logs", "ix_audit_logs_target_id"):
        op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"], unique=False)
    if not _index_exists(inspector, "audit_logs", "ix_audit_logs_business_created_at"):
        op.create_index(
            "ix_audit_logs_business_created_at",
            "audit_logs",
            ["business_id", "created_at"],
            unique=False,
        )
    if not _index_exists(inspector, "audit_logs", "ix_audit_logs_business_action_created_at"):
        op.create_index(
            "ix_audit_logs_business_action_created_at",
            "audit_logs",
            ["business_id", "action", "created_at"],
            unique=False,
        )
    if not _index_exists(inspector, "audit_logs", "ix_audit_logs_business_actor_created_at"):
        op.create_index(
            "ix_audit_logs_business_actor_created_at",
            "audit_logs",
            ["business_id", "actor_user_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "audit_logs"):
        return

    if _index_exists(inspector, "audit_logs", "ix_audit_logs_business_actor_created_at"):
        op.drop_index("ix_audit_logs_business_actor_created_at", table_name="audit_logs")
    if _index_exists(inspector, "audit_logs", "ix_audit_logs_business_action_created_at"):
        op.drop_index("ix_audit_logs_business_action_created_at", table_name="audit_logs")
    if _index_exists(inspector, "audit_logs", "ix_audit_logs_business_created_at"):
        op.drop_index("ix_audit_logs_business_created_at", table_name="audit_logs")
    if _index_exists(inspector, "audit_logs", "ix_audit_logs_target_id"):
        op.drop_index("ix_audit_logs_target_id", table_name="audit_logs")
    if _index_exists(inspector, "audit_logs", "ix_audit_logs_actor_user_id"):
        op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    if _index_exists(inspector, "audit_logs", "ix_audit_logs_business_id"):
        op.drop_index("ix_audit_logs_business_id", table_name="audit_logs")

    op.drop_table("audit_logs")
