"""add orders tables

Revision ID: 20260221_0006
Revises: 20260221_0005
Create Date: 2026-02-21 22:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260221_0006"
down_revision: Union[str, None] = "20260221_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "orders"):
        op.create_table(
            "orders",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("customer_id", sa.String(length=36), nullable=True),
            sa.Column("payment_method", sa.String(length=30), nullable=False),
            sa.Column(
                "channel",
                sa.String(length=30),
                nullable=False,
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("sale_id", sa.String(length=36), nullable=True),
            sa.Column("note", sa.String(length=255), nullable=True),
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
            sa.ForeignKeyConstraint(["sale_id"], ["sales.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "orders"):
        if not _index_exists(inspector, "orders", "ix_orders_business_id"):
            op.create_index("ix_orders_business_id", "orders", ["business_id"], unique=False)
        if not _index_exists(inspector, "orders", "ix_orders_customer_id"):
            op.create_index("ix_orders_customer_id", "orders", ["customer_id"], unique=False)
        if not _index_exists(inspector, "orders", "ix_orders_sale_id"):
            op.create_index("ix_orders_sale_id", "orders", ["sale_id"], unique=False)
        if not _index_exists(inspector, "orders", "ix_orders_business_created_at"):
            op.create_index(
                "ix_orders_business_created_at",
                "orders",
                ["business_id", "created_at"],
                unique=False,
            )
        if not _index_exists(inspector, "orders", "ix_orders_business_status_created_at"):
            op.create_index(
                "ix_orders_business_status_created_at",
                "orders",
                ["business_id", "status", "created_at"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "order_items"):
        op.create_table(
            "order_items",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("order_id", sa.String(length=36), nullable=False),
            sa.Column("variant_id", sa.String(length=36), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
            sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "order_items"):
        if not _index_exists(inspector, "order_items", "ix_order_items_order_id"):
            op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)
        if not _index_exists(inspector, "order_items", "ix_order_items_variant_id"):
            op.create_index("ix_order_items_variant_id", "order_items", ["variant_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "order_items"):
        if _index_exists(inspector, "order_items", "ix_order_items_variant_id"):
            op.drop_index("ix_order_items_variant_id", table_name="order_items")
        if _index_exists(inspector, "order_items", "ix_order_items_order_id"):
            op.drop_index("ix_order_items_order_id", table_name="order_items")
        op.drop_table("order_items")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "orders"):
        if _index_exists(inspector, "orders", "ix_orders_business_status_created_at"):
            op.drop_index("ix_orders_business_status_created_at", table_name="orders")
        if _index_exists(inspector, "orders", "ix_orders_business_created_at"):
            op.drop_index("ix_orders_business_created_at", table_name="orders")
        if _index_exists(inspector, "orders", "ix_orders_sale_id"):
            op.drop_index("ix_orders_sale_id", table_name="orders")
        if _index_exists(inspector, "orders", "ix_orders_customer_id"):
            op.drop_index("ix_orders_customer_id", table_name="orders")
        if _index_exists(inspector, "orders", "ix_orders_business_id"):
            op.drop_index("ix_orders_business_id", table_name="orders")
        op.drop_table("orders")
