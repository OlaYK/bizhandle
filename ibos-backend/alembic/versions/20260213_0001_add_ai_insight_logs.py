"""add ai insight logs table

Revision ID: 20260213_0001
Revises:
Create Date: 2026-02-13 23:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260213_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_insight_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("insight_type", sa.String(length=30), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_insight_logs_business_id"), "ai_insight_logs", ["business_id"], unique=False)
    op.create_index(op.f("ix_ai_insight_logs_created_at"), "ai_insight_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_insight_logs_created_at"), table_name="ai_insight_logs")
    op.drop_index(op.f("ix_ai_insight_logs_business_id"), table_name="ai_insight_logs")
    op.drop_table("ai_insight_logs")
