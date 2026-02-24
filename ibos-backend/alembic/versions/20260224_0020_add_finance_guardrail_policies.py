"""add finance guardrail policies

Revision ID: 20260224_0020
Revises: 20260224_0019
Create Date: 2026-02-24 08:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260224_0020"
down_revision: Union[str, None] = "20260224_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "finance_guardrail_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("margin_floor_ratio", sa.Float(), nullable=False, server_default="0.15"),
        sa.Column("margin_drop_threshold", sa.Float(), nullable=False, server_default="0.08"),
        sa.Column("expense_growth_threshold", sa.Float(), nullable=False, server_default="0.25"),
        sa.Column("minimum_cash_buffer", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", name="uq_finance_guardrail_policies_business"),
    )
    op.create_index(
        "ix_finance_guardrail_policies_business_id",
        "finance_guardrail_policies",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_finance_guardrail_policies_updated_by_user_id",
        "finance_guardrail_policies",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_finance_guardrail_policies_business_updated_at",
        "finance_guardrail_policies",
        ["business_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_finance_guardrail_policies_business_updated_at", table_name="finance_guardrail_policies")
    op.drop_index("ix_finance_guardrail_policies_updated_by_user_id", table_name="finance_guardrail_policies")
    op.drop_index("ix_finance_guardrail_policies_business_id", table_name="finance_guardrail_policies")
    op.drop_table("finance_guardrail_policies")
