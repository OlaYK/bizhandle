"""add storefront domain and seo controls

Revision ID: 20260222_0011
Revises: 20260222_0010
Create Date: 2026-02-22 16:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_0011"
down_revision: Union[str, None] = "20260222_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "storefront_configs"):
        return

    if not _column_exists(inspector, "storefront_configs", "seo_title"):
        op.add_column("storefront_configs", sa.Column("seo_title", sa.String(length=160), nullable=True))
    if not _column_exists(inspector, "storefront_configs", "seo_description"):
        op.add_column(
            "storefront_configs",
            sa.Column("seo_description", sa.String(length=320), nullable=True),
        )
    if not _column_exists(inspector, "storefront_configs", "seo_og_image_url"):
        op.add_column(
            "storefront_configs",
            sa.Column("seo_og_image_url", sa.String(length=500), nullable=True),
        )
    if not _column_exists(inspector, "storefront_configs", "domain_verification_status"):
        op.add_column(
            "storefront_configs",
            sa.Column(
                "domain_verification_status",
                sa.String(length=20),
                nullable=False,
                server_default="not_configured",
            ),
        )
    if not _column_exists(inspector, "storefront_configs", "domain_verification_token"):
        op.add_column(
            "storefront_configs",
            sa.Column("domain_verification_token", sa.String(length=80), nullable=True),
        )
    if not _column_exists(inspector, "storefront_configs", "domain_last_checked_at"):
        op.add_column(
            "storefront_configs",
            sa.Column("domain_last_checked_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "storefront_configs"):
        return

    if _column_exists(inspector, "storefront_configs", "domain_last_checked_at"):
        with op.batch_alter_table("storefront_configs") as batch_op:
            batch_op.drop_column("domain_last_checked_at")
    if _column_exists(inspector, "storefront_configs", "domain_verification_token"):
        with op.batch_alter_table("storefront_configs") as batch_op:
            batch_op.drop_column("domain_verification_token")
    if _column_exists(inspector, "storefront_configs", "domain_verification_status"):
        with op.batch_alter_table("storefront_configs") as batch_op:
            batch_op.drop_column("domain_verification_status")
    if _column_exists(inspector, "storefront_configs", "seo_og_image_url"):
        with op.batch_alter_table("storefront_configs") as batch_op:
            batch_op.drop_column("seo_og_image_url")
    if _column_exists(inspector, "storefront_configs", "seo_description"):
        with op.batch_alter_table("storefront_configs") as batch_op:
            batch_op.drop_column("seo_description")
    if _column_exists(inspector, "storefront_configs", "seo_title"):
        with op.batch_alter_table("storefront_configs") as batch_op:
            batch_op.drop_column("seo_title")
