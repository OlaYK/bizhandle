"""add google_sub column to users

Revision ID: 20260213_0002
Revises: 20260213_0001
Create Date: 2026-02-13 23:59:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260213_0002"
down_revision: Union[str, None] = "20260213_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "users" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    if "google_sub" not in existing_columns:
        op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))

    existing_indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_google_sub" not in existing_indexes:
        op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "users" not in inspector.get_table_names():
        return

    existing_indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_google_sub" in existing_indexes:
        op.drop_index("ix_users_google_sub", table_name="users")

    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    if "google_sub" in existing_columns:
        op.drop_column("users", "google_sub")
