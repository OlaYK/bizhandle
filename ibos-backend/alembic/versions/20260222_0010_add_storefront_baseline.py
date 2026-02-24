"""add storefront baseline schema

Revision ID: 20260222_0010
Revises: 20260222_0009
Create Date: 2026-02-22 12:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_0010"
down_revision: Union[str, None] = "20260222_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "storefront_configs"):
        op.create_table(
            "storefront_configs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("tagline", sa.String(length=255), nullable=True),
            sa.Column("description", sa.String(length=1000), nullable=True),
            sa.Column("logo_url", sa.String(length=500), nullable=True),
            sa.Column("accent_color", sa.String(length=20), nullable=True),
            sa.Column("hero_image_url", sa.String(length=500), nullable=True),
            sa.Column("support_email", sa.String(length=255), nullable=True),
            sa.Column("support_phone", sa.String(length=40), nullable=True),
            sa.Column("policy_shipping", sa.String(length=2000), nullable=True),
            sa.Column("policy_returns", sa.String(length=2000), nullable=True),
            sa.Column("policy_privacy", sa.String(length=2000), nullable=True),
            sa.Column("custom_domain", sa.String(length=255), nullable=True),
            sa.Column("domain_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "is_published",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
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
            sa.UniqueConstraint("business_id", name="uq_storefront_configs_business_id"),
            sa.UniqueConstraint("slug", name="uq_storefront_configs_slug"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "storefront_configs"):
        if not _index_exists(inspector, "storefront_configs", "ix_storefront_configs_business_id"):
            op.create_index(
                "ix_storefront_configs_business_id",
                "storefront_configs",
                ["business_id"],
                unique=False,
            )
        if not _index_exists(inspector, "storefront_configs", "ix_storefront_configs_slug"):
            op.create_index("ix_storefront_configs_slug", "storefront_configs", ["slug"], unique=False)
        if not _index_exists(inspector, "storefront_configs", "ix_storefront_configs_business_slug"):
            op.create_index(
                "ix_storefront_configs_business_slug",
                "storefront_configs",
                ["business_id", "slug"],
                unique=False,
            )
        if not _index_exists(inspector, "storefront_configs", "ix_storefront_configs_custom_domain"):
            op.create_index(
                "ix_storefront_configs_custom_domain",
                "storefront_configs",
                ["custom_domain"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "products") and not _column_exists(inspector, "products", "is_published"):
        op.add_column(
            "products",
            sa.Column(
                "is_published",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "product_variants") and not _column_exists(
        inspector, "product_variants", "is_published"
    ):
        op.add_column(
            "product_variants",
            sa.Column(
                "is_published",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "products") and not _index_exists(
        inspector, "products", "ix_products_business_published_active"
    ):
        op.create_index(
            "ix_products_business_published_active",
            "products",
            ["business_id", "is_published", "active"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "product_variants") and not _index_exists(
        inspector, "product_variants", "ix_product_variants_business_product_published"
    ):
        op.create_index(
            "ix_product_variants_business_product_published",
            "product_variants",
            ["business_id", "product_id", "is_published"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "product_variants") and _index_exists(
        inspector, "product_variants", "ix_product_variants_business_product_published"
    ):
        op.drop_index(
            "ix_product_variants_business_product_published",
            table_name="product_variants",
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "products") and _index_exists(
        inspector, "products", "ix_products_business_published_active"
    ):
        op.drop_index("ix_products_business_published_active", table_name="products")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "product_variants") and _column_exists(
        inspector, "product_variants", "is_published"
    ):
        with op.batch_alter_table("product_variants") as batch_op:
            batch_op.drop_column("is_published")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "products") and _column_exists(inspector, "products", "is_published"):
        with op.batch_alter_table("products") as batch_op:
            batch_op.drop_column("is_published")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "storefront_configs"):
        if _index_exists(inspector, "storefront_configs", "ix_storefront_configs_custom_domain"):
            op.drop_index("ix_storefront_configs_custom_domain", table_name="storefront_configs")
        if _index_exists(inspector, "storefront_configs", "ix_storefront_configs_business_slug"):
            op.drop_index("ix_storefront_configs_business_slug", table_name="storefront_configs")
        if _index_exists(inspector, "storefront_configs", "ix_storefront_configs_slug"):
            op.drop_index("ix_storefront_configs_slug", table_name="storefront_configs")
        if _index_exists(inspector, "storefront_configs", "ix_storefront_configs_business_id"):
            op.drop_index("ix_storefront_configs_business_id", table_name="storefront_configs")
        op.drop_table("storefront_configs")
