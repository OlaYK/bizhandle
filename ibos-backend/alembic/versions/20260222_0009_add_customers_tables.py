"""add customers tables

Revision ID: 20260222_0009
Revises: 20260221_0008
Create Date: 2026-02-22 02:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_0009"
down_revision: Union[str, None] = "20260221_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_constraint_exists(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    return constraint_name in {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "customers"):
        op.create_table(
            "customers",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("phone", sa.String(length=40), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
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
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "customers"):
        if not _index_exists(inspector, "customers", "ix_customers_business_id"):
            op.create_index("ix_customers_business_id", "customers", ["business_id"], unique=False)
        if not _index_exists(inspector, "customers", "ix_customers_phone"):
            op.create_index("ix_customers_phone", "customers", ["phone"], unique=False)
        if not _index_exists(inspector, "customers", "ix_customers_email"):
            op.create_index("ix_customers_email", "customers", ["email"], unique=False)
        if not _index_exists(inspector, "customers", "ix_customers_business_name_created_at"):
            op.create_index(
                "ix_customers_business_name_created_at",
                "customers",
                ["business_id", "name", "created_at"],
                unique=False,
            )
        if not _index_exists(inspector, "customers", "ix_customers_business_email"):
            op.create_index("ix_customers_business_email", "customers", ["business_id", "email"], unique=False)
        if not _index_exists(inspector, "customers", "ix_customers_business_phone"):
            op.create_index("ix_customers_business_phone", "customers", ["business_id", "phone"], unique=False)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "customer_tags"):
        op.create_table(
            "customer_tags",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=60), nullable=False),
            sa.Column("color", sa.String(length=20), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "customer_tags"):
        if not _index_exists(inspector, "customer_tags", "ix_customer_tags_business_id"):
            op.create_index("ix_customer_tags_business_id", "customer_tags", ["business_id"], unique=False)
        if not _index_exists(inspector, "customer_tags", "ix_customer_tags_business_name"):
            op.create_index(
                "ix_customer_tags_business_name",
                "customer_tags",
                ["business_id", "name"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "customer_tag_links"):
        op.create_table(
            "customer_tag_links",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("customer_id", sa.String(length=36), nullable=False),
            sa.Column("tag_id", sa.String(length=36), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
            sa.ForeignKeyConstraint(["tag_id"], ["customer_tags.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "business_id",
                "customer_id",
                "tag_id",
                name="uq_customer_tag_links_triplet",
            ),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "customer_tag_links"):
        if not _index_exists(inspector, "customer_tag_links", "ix_customer_tag_links_business_id"):
            op.create_index(
                "ix_customer_tag_links_business_id",
                "customer_tag_links",
                ["business_id"],
                unique=False,
            )
        if not _index_exists(inspector, "customer_tag_links", "ix_customer_tag_links_customer_id"):
            op.create_index(
                "ix_customer_tag_links_customer_id",
                "customer_tag_links",
                ["customer_id"],
                unique=False,
            )
        if not _index_exists(inspector, "customer_tag_links", "ix_customer_tag_links_tag_id"):
            op.create_index(
                "ix_customer_tag_links_tag_id",
                "customer_tag_links",
                ["tag_id"],
                unique=False,
            )
        if not _index_exists(inspector, "customer_tag_links", "ix_customer_tag_links_business_customer"):
            op.create_index(
                "ix_customer_tag_links_business_customer",
                "customer_tag_links",
                ["business_id", "customer_id"],
                unique=False,
            )
        if not _index_exists(inspector, "customer_tag_links", "ix_customer_tag_links_business_tag"):
            op.create_index(
                "ix_customer_tag_links_business_tag",
                "customer_tag_links",
                ["business_id", "tag_id"],
                unique=False,
            )

        if not _unique_constraint_exists(
            inspector, "customer_tag_links", "uq_customer_tag_links_triplet"
        ):
            op.create_unique_constraint(
                "uq_customer_tag_links_triplet",
                "customer_tag_links",
                ["business_id", "customer_id", "tag_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "customer_tag_links"):
        if _index_exists(inspector, "customer_tag_links", "ix_customer_tag_links_business_tag"):
            op.drop_index("ix_customer_tag_links_business_tag", table_name="customer_tag_links")
        if _index_exists(inspector, "customer_tag_links", "ix_customer_tag_links_business_customer"):
            op.drop_index("ix_customer_tag_links_business_customer", table_name="customer_tag_links")
        if _index_exists(inspector, "customer_tag_links", "ix_customer_tag_links_tag_id"):
            op.drop_index("ix_customer_tag_links_tag_id", table_name="customer_tag_links")
        if _index_exists(inspector, "customer_tag_links", "ix_customer_tag_links_customer_id"):
            op.drop_index("ix_customer_tag_links_customer_id", table_name="customer_tag_links")
        if _index_exists(inspector, "customer_tag_links", "ix_customer_tag_links_business_id"):
            op.drop_index("ix_customer_tag_links_business_id", table_name="customer_tag_links")
        if _unique_constraint_exists(inspector, "customer_tag_links", "uq_customer_tag_links_triplet"):
            op.drop_constraint("uq_customer_tag_links_triplet", "customer_tag_links", type_="unique")
        op.drop_table("customer_tag_links")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "customer_tags"):
        if _index_exists(inspector, "customer_tags", "ix_customer_tags_business_name"):
            op.drop_index("ix_customer_tags_business_name", table_name="customer_tags")
        if _index_exists(inspector, "customer_tags", "ix_customer_tags_business_id"):
            op.drop_index("ix_customer_tags_business_id", table_name="customer_tags")
        op.drop_table("customer_tags")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "customers"):
        if _index_exists(inspector, "customers", "ix_customers_business_phone"):
            op.drop_index("ix_customers_business_phone", table_name="customers")
        if _index_exists(inspector, "customers", "ix_customers_business_email"):
            op.drop_index("ix_customers_business_email", table_name="customers")
        if _index_exists(inspector, "customers", "ix_customers_business_name_created_at"):
            op.drop_index("ix_customers_business_name_created_at", table_name="customers")
        if _index_exists(inspector, "customers", "ix_customers_email"):
            op.drop_index("ix_customers_email", table_name="customers")
        if _index_exists(inspector, "customers", "ix_customers_phone"):
            op.drop_index("ix_customers_phone", table_name="customers")
        if _index_exists(inspector, "customers", "ix_customers_business_id"):
            op.drop_index("ix_customers_business_id", table_name="customers")
        op.drop_table("customers")
