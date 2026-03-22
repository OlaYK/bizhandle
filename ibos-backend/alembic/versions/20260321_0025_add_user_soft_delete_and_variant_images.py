"""add user soft delete fields and variant images

Revision ID: 20260321_0025
Revises: 20260320_0024
Create Date: 2026-03-21 09:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260321_0025"
down_revision: Union[str, None] = "20260320_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "product_variants",
        sa.Column("image_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product_variants", "image_url")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "is_deleted")
