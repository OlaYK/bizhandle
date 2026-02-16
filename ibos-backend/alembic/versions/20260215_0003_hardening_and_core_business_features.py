"""hardening and core business features

Revision ID: 20260215_0003
Revises: 6703cb55cc18
Create Date: 2026-02-15 22:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260215_0003"
down_revision: Union[str, None] = "6703cb55cc18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {ix["name"] for ix in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "users"):
        duplicate_email = bind.execute(
            sa.text(
                """
                SELECT lower(email), COUNT(*) FROM users
                GROUP BY lower(email)
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        ).first()
        if duplicate_email:
            raise RuntimeError("Cannot apply migration: duplicate user emails (case-insensitive)")

        duplicate_username = bind.execute(
            sa.text(
                """
                SELECT lower(username), COUNT(*) FROM users
                GROUP BY lower(username)
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        ).first()
        if duplicate_username:
            raise RuntimeError("Cannot apply migration: duplicate usernames (case-insensitive)")

    if _table_exists(inspector, "businesses"):
        duplicate_owners = bind.execute(
            sa.text(
                """
                SELECT owner_user_id, COUNT(*) FROM businesses
                GROUP BY owner_user_id
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        ).first()
        if duplicate_owners:
            raise RuntimeError("Cannot apply migration: duplicate businesses for a single owner")

    if _table_exists(inspector, "product_variants") and _column_exists(inspector, "product_variants", "sku"):
        duplicate_sku = bind.execute(
            sa.text(
                """
                SELECT p.business_id, lower(pv.sku), COUNT(*)
                FROM product_variants pv
                JOIN products p ON p.id = pv.product_id
                WHERE pv.sku IS NOT NULL
                GROUP BY p.business_id, lower(pv.sku)
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        ).first()
        if duplicate_sku:
            raise RuntimeError(
                "Cannot apply migration: duplicate SKU values (case-insensitive) within business"
            )

    if not _table_exists(inspector, "refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("token_jti", sa.String(length=36), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("replaced_by_jti", sa.String(length=36), nullable=True),
            sa.Column("created_by_ip", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)
        op.create_index("ix_refresh_tokens_token_jti", "refresh_tokens", ["token_jti"], unique=True)
        op.create_index(
            "ix_refresh_tokens_user_revoked_expires",
            "refresh_tokens",
            ["user_id", "revoked_at", "expires_at"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "product_variants"):
        if not _column_exists(inspector, "product_variants", "business_id"):
            op.add_column("product_variants", sa.Column("business_id", sa.String(length=36), nullable=True))
        if not _column_exists(inspector, "product_variants", "reorder_level"):
            op.add_column(
                "product_variants",
                sa.Column("reorder_level", sa.Integer(), nullable=False, server_default="0"),
            )

        op.execute(
            sa.text(
                """
                UPDATE product_variants pv
                SET business_id = p.business_id
                FROM products p
                WHERE p.id = pv.product_id
                  AND pv.business_id IS NULL
                """
            )
        )
        op.alter_column("product_variants", "business_id", nullable=False)

        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("product_variants")}
        if "fk_product_variants_business_id_businesses" not in existing_fks:
            op.create_foreign_key(
                "fk_product_variants_business_id_businesses",
                "product_variants",
                "businesses",
                ["business_id"],
                ["id"],
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "inventory_ledger") and not _column_exists(inspector, "inventory_ledger", "note"):
        op.add_column("inventory_ledger", sa.Column("note", sa.String(length=255), nullable=True))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "sales"):
        if not _column_exists(inspector, "sales", "kind"):
            op.add_column(
                "sales",
                sa.Column("kind", sa.String(length=20), nullable=False, server_default="sale"),
            )
        if not _column_exists(inspector, "sales", "parent_sale_id"):
            op.add_column("sales", sa.Column("parent_sale_id", sa.String(length=36), nullable=True))
        if not _column_exists(inspector, "sales", "note"):
            op.add_column("sales", sa.Column("note", sa.String(length=255), nullable=True))

        op.execute(sa.text("UPDATE sales SET kind = 'sale' WHERE kind IS NULL"))
        op.alter_column("sales", "kind", nullable=False, server_default="sale")

        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("sales")}
        if "fk_sales_parent_sale_id_sales" not in existing_fks:
            op.create_foreign_key(
                "fk_sales_parent_sale_id_sales",
                "sales",
                "sales",
                ["parent_sale_id"],
                ["id"],
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "businesses") and not _index_exists(
        inspector, "businesses", "ux_businesses_owner_user_id"
    ):
        op.create_index("ux_businesses_owner_user_id", "businesses", ["owner_user_id"], unique=True)

    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_lower ON users (lower(email))")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username_lower ON users (lower(username))")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_product_variants_business_sku_lower
        ON product_variants (business_id, lower(sku))
        WHERE sku IS NOT NULL
        """
    )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "products") and not _index_exists(
        inspector, "products", "ix_products_business_created_at"
    ):
        op.create_index(
            "ix_products_business_created_at",
            "products",
            ["business_id", "created_at"],
            unique=False,
        )

    if _table_exists(inspector, "product_variants"):
        if not _index_exists(inspector, "product_variants", "ix_product_variants_business_created_at"):
            op.create_index(
                "ix_product_variants_business_created_at",
                "product_variants",
                ["business_id", "created_at"],
                unique=False,
            )
        if not _index_exists(inspector, "product_variants", "ix_product_variants_business_reorder_level"):
            op.create_index(
                "ix_product_variants_business_reorder_level",
                "product_variants",
                ["business_id", "reorder_level"],
                unique=False,
            )

    if _table_exists(inspector, "inventory_ledger"):
        if not _index_exists(inspector, "inventory_ledger", "ix_inventory_ledger_business_created_at"):
            op.create_index(
                "ix_inventory_ledger_business_created_at",
                "inventory_ledger",
                ["business_id", "created_at"],
                unique=False,
            )
        if not _index_exists(inspector, "inventory_ledger", "ix_inventory_ledger_business_variant_created_at"):
            op.create_index(
                "ix_inventory_ledger_business_variant_created_at",
                "inventory_ledger",
                ["business_id", "variant_id", "created_at"],
                unique=False,
            )

    if _table_exists(inspector, "sales"):
        if not _index_exists(inspector, "sales", "ix_sales_business_created_at"):
            op.create_index(
                "ix_sales_business_created_at",
                "sales",
                ["business_id", "created_at"],
                unique=False,
            )
        if not _index_exists(inspector, "sales", "ix_sales_business_kind_created_at"):
            op.create_index(
                "ix_sales_business_kind_created_at",
                "sales",
                ["business_id", "kind", "created_at"],
                unique=False,
            )

    if _table_exists(inspector, "expenses") and not _index_exists(
        inspector, "expenses", "ix_expenses_business_created_at"
    ):
        op.create_index(
            "ix_expenses_business_created_at",
            "expenses",
            ["business_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    op.execute("DROP INDEX IF EXISTS ux_product_variants_business_sku_lower")
    op.execute("DROP INDEX IF EXISTS ux_users_username_lower")
    op.execute("DROP INDEX IF EXISTS ux_users_email_lower")

    if _table_exists(inspector, "expenses") and _index_exists(
        inspector, "expenses", "ix_expenses_business_created_at"
    ):
        op.drop_index("ix_expenses_business_created_at", table_name="expenses")

    if _table_exists(inspector, "sales"):
        if _index_exists(inspector, "sales", "ix_sales_business_kind_created_at"):
            op.drop_index("ix_sales_business_kind_created_at", table_name="sales")
        if _index_exists(inspector, "sales", "ix_sales_business_created_at"):
            op.drop_index("ix_sales_business_created_at", table_name="sales")

    if _table_exists(inspector, "inventory_ledger"):
        if _index_exists(inspector, "inventory_ledger", "ix_inventory_ledger_business_variant_created_at"):
            op.drop_index("ix_inventory_ledger_business_variant_created_at", table_name="inventory_ledger")
        if _index_exists(inspector, "inventory_ledger", "ix_inventory_ledger_business_created_at"):
            op.drop_index("ix_inventory_ledger_business_created_at", table_name="inventory_ledger")

    if _table_exists(inspector, "product_variants"):
        if _index_exists(inspector, "product_variants", "ix_product_variants_business_reorder_level"):
            op.drop_index("ix_product_variants_business_reorder_level", table_name="product_variants")
        if _index_exists(inspector, "product_variants", "ix_product_variants_business_created_at"):
            op.drop_index("ix_product_variants_business_created_at", table_name="product_variants")

    if _table_exists(inspector, "products") and _index_exists(
        inspector, "products", "ix_products_business_created_at"
    ):
        op.drop_index("ix_products_business_created_at", table_name="products")

    if _table_exists(inspector, "businesses") and _index_exists(
        inspector, "businesses", "ux_businesses_owner_user_id"
    ):
        op.drop_index("ux_businesses_owner_user_id", table_name="businesses")

    if _table_exists(inspector, "sales"):
        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("sales")}
        if "fk_sales_parent_sale_id_sales" in existing_fks:
            op.drop_constraint("fk_sales_parent_sale_id_sales", "sales", type_="foreignkey")
        if _column_exists(inspector, "sales", "note"):
            op.drop_column("sales", "note")
        if _column_exists(inspector, "sales", "parent_sale_id"):
            op.drop_column("sales", "parent_sale_id")
        if _column_exists(inspector, "sales", "kind"):
            op.drop_column("sales", "kind")

    if _table_exists(inspector, "inventory_ledger") and _column_exists(inspector, "inventory_ledger", "note"):
        op.drop_column("inventory_ledger", "note")

    if _table_exists(inspector, "product_variants"):
        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("product_variants")}
        if "fk_product_variants_business_id_businesses" in existing_fks:
            op.drop_constraint(
                "fk_product_variants_business_id_businesses",
                "product_variants",
                type_="foreignkey",
            )
        if _column_exists(inspector, "product_variants", "reorder_level"):
            op.drop_column("product_variants", "reorder_level")
        if _column_exists(inspector, "product_variants", "business_id"):
            op.drop_column("product_variants", "business_id")

    if _table_exists(inspector, "refresh_tokens"):
        if _index_exists(inspector, "refresh_tokens", "ix_refresh_tokens_user_revoked_expires"):
            op.drop_index("ix_refresh_tokens_user_revoked_expires", table_name="refresh_tokens")
        if _index_exists(inspector, "refresh_tokens", "ix_refresh_tokens_token_jti"):
            op.drop_index("ix_refresh_tokens_token_jti", table_name="refresh_tokens")
        if _index_exists(inspector, "refresh_tokens", "ix_refresh_tokens_user_id"):
            op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
        op.drop_table("refresh_tokens")
