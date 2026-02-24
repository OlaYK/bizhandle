"""add business pending order timeout

Revision ID: 20260221_0007
Revises: 20260221_0006
Create Date: 2026-02-21 23:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260221_0007"
down_revision: Union[str, None] = "20260221_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "businesses", "pending_order_timeout_minutes"):
        op.add_column(
            "businesses",
            sa.Column(
                "pending_order_timeout_minutes",
                sa.Integer(),
                nullable=False,
                server_default="60",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "businesses", "pending_order_timeout_minutes"):
        op.drop_column("businesses", "pending_order_timeout_minutes")
