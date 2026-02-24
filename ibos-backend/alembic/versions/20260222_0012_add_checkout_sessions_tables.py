"""add checkout sessions tables

Revision ID: 20260222_0012
Revises: 20260222_0011
Create Date: 2026-02-22 18:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_0012"
down_revision: Union[str, None] = "20260222_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "checkout_sessions"):
        op.create_table(
            "checkout_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("session_token", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("customer_id", sa.String(length=36), nullable=True),
            sa.Column("payment_method", sa.String(length=30), nullable=False, server_default="transfer"),
            sa.Column("channel", sa.String(length=30), nullable=False, server_default="instagram"),
            sa.Column("note", sa.String(length=255), nullable=True),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("success_redirect_url", sa.String(length=500), nullable=True),
            sa.Column("cancel_redirect_url", sa.String(length=500), nullable=True),
            sa.Column("payment_provider", sa.String(length=40), nullable=False, server_default="stub"),
            sa.Column("payment_reference", sa.String(length=120), nullable=True),
            sa.Column("payment_checkout_url", sa.String(length=500), nullable=True),
            sa.Column("order_id", sa.String(length=36), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_token", name="uq_checkout_sessions_session_token"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "checkout_sessions"):
        if not _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_business_id"):
            op.create_index("ix_checkout_sessions_business_id", "checkout_sessions", ["business_id"], unique=False)
        if not _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_session_token"):
            op.create_index("ix_checkout_sessions_session_token", "checkout_sessions", ["session_token"], unique=True)
        if not _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_customer_id"):
            op.create_index("ix_checkout_sessions_customer_id", "checkout_sessions", ["customer_id"], unique=False)
        if not _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_order_id"):
            op.create_index("ix_checkout_sessions_order_id", "checkout_sessions", ["order_id"], unique=False)
        if not _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_business_status_created_at"):
            op.create_index(
                "ix_checkout_sessions_business_status_created_at",
                "checkout_sessions",
                ["business_id", "status", "created_at"],
                unique=False,
            )
        if not _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_business_expires_at"):
            op.create_index(
                "ix_checkout_sessions_business_expires_at",
                "checkout_sessions",
                ["business_id", "expires_at"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "checkout_session_items"):
        op.create_table(
            "checkout_session_items",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("checkout_session_id", sa.String(length=36), nullable=False),
            sa.Column("variant_id", sa.String(length=36), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
            sa.ForeignKeyConstraint(["checkout_session_id"], ["checkout_sessions.id"]),
            sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "checkout_session_items"):
        if not _index_exists(inspector, "checkout_session_items", "ix_checkout_session_items_checkout_session_id"):
            op.create_index(
                "ix_checkout_session_items_checkout_session_id",
                "checkout_session_items",
                ["checkout_session_id"],
                unique=False,
            )
        if not _index_exists(inspector, "checkout_session_items", "ix_checkout_session_items_variant_id"):
            op.create_index(
                "ix_checkout_session_items_variant_id",
                "checkout_session_items",
                ["variant_id"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "checkout_session_items"):
        if _index_exists(inspector, "checkout_session_items", "ix_checkout_session_items_variant_id"):
            op.drop_index("ix_checkout_session_items_variant_id", table_name="checkout_session_items")
        if _index_exists(inspector, "checkout_session_items", "ix_checkout_session_items_checkout_session_id"):
            op.drop_index("ix_checkout_session_items_checkout_session_id", table_name="checkout_session_items")
        op.drop_table("checkout_session_items")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "checkout_sessions"):
        if _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_business_expires_at"):
            op.drop_index("ix_checkout_sessions_business_expires_at", table_name="checkout_sessions")
        if _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_business_status_created_at"):
            op.drop_index("ix_checkout_sessions_business_status_created_at", table_name="checkout_sessions")
        if _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_order_id"):
            op.drop_index("ix_checkout_sessions_order_id", table_name="checkout_sessions")
        if _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_customer_id"):
            op.drop_index("ix_checkout_sessions_customer_id", table_name="checkout_sessions")
        if _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_session_token"):
            op.drop_index("ix_checkout_sessions_session_token", table_name="checkout_sessions")
        if _index_exists(inspector, "checkout_sessions", "ix_checkout_sessions_business_id"):
            op.drop_index("ix_checkout_sessions_business_id", table_name="checkout_sessions")
        op.drop_table("checkout_sessions")
