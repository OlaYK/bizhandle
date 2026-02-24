"""add business memberships table

Revision ID: 20260221_0004
Revises: 4d4298a09d7e
Create Date: 2026-02-21 20:10:00.000000
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260221_0004"
down_revision: Union[str, None] = "4d4298a09d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "business_memberships"):
        op.create_table(
            "business_memberships",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="owner"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "business_memberships"):
        if not _index_exists(inspector, "business_memberships", "ix_business_memberships_business_id"):
            op.create_index(
                "ix_business_memberships_business_id",
                "business_memberships",
                ["business_id"],
                unique=False,
            )
        if not _index_exists(inspector, "business_memberships", "ix_business_memberships_user_id"):
            op.create_index(
                "ix_business_memberships_user_id",
                "business_memberships",
                ["user_id"],
                unique=False,
            )
        if not _index_exists(inspector, "business_memberships", "ux_business_memberships_business_user"):
            op.create_index(
                "ux_business_memberships_business_user",
                "business_memberships",
                ["business_id", "user_id"],
                unique=True,
            )
        if not _index_exists(
            inspector,
            "business_memberships",
            "ix_business_memberships_user_active_created_at",
        ):
            op.create_index(
                "ix_business_memberships_user_active_created_at",
                "business_memberships",
                ["user_id", "is_active", "created_at"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "businesses") or not _table_exists(
        inspector, "business_memberships"
    ):
        return

    existing_pairs = {
        (business_id, user_id)
        for business_id, user_id in bind.execute(
            sa.text("SELECT business_id, user_id FROM business_memberships")
        ).all()
    }
    businesses = bind.execute(sa.text("SELECT id, owner_user_id FROM businesses")).all()
    for business_id, owner_user_id in businesses:
        pair = (business_id, owner_user_id)
        if pair in existing_pairs:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO business_memberships (id, business_id, user_id, role, is_active)
                VALUES (:id, :business_id, :user_id, 'owner', :is_active)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "business_id": business_id,
                "user_id": owner_user_id,
                "is_active": True,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "business_memberships"):
        return

    if _index_exists(inspector, "business_memberships", "ix_business_memberships_user_active_created_at"):
        op.drop_index("ix_business_memberships_user_active_created_at", table_name="business_memberships")
    if _index_exists(inspector, "business_memberships", "ux_business_memberships_business_user"):
        op.drop_index("ux_business_memberships_business_user", table_name="business_memberships")
    if _index_exists(inspector, "business_memberships", "ix_business_memberships_user_id"):
        op.drop_index("ix_business_memberships_user_id", table_name="business_memberships")
    if _index_exists(inspector, "business_memberships", "ix_business_memberships_business_id"):
        op.drop_index("ix_business_memberships_business_id", table_name="business_memberships")

    op.drop_table("business_memberships")
