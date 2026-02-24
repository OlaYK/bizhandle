"""add ai copilot feature store, insights, and prescriptive actions

Revision ID: 20260223_0018
Revises: 20260223_0017
Create Date: 2026-02-23 23:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260223_0018"
down_revision: Union[str, None] = "20260223_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_feature_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("window_start_date", sa.Date(), nullable=False),
        sa.Column("window_end_date", sa.Date(), nullable=False),
        sa.Column("orders_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paid_orders_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gross_revenue", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("refunds_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refunds_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_revenue", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("expenses_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("refund_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stockout_events_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("campaigns_sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("campaigns_failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repeat_customers_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id",
            "window_start_date",
            "window_end_date",
            name="uq_ai_feature_snapshots_business_window",
        ),
    )
    op.create_index("ix_ai_feature_snapshots_business_id", "ai_feature_snapshots", ["business_id"], unique=False)
    op.create_index(
        "ix_ai_feature_snapshots_created_by_user_id",
        "ai_feature_snapshots",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_feature_snapshots_business_window_end_created_at",
        "ai_feature_snapshots",
        ["business_id", "window_end_date", "created_at"],
        unique=False,
    )

    op.create_table(
        "ai_generated_insights",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("feature_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("insight_type", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=2000), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["feature_snapshot_id"], ["ai_feature_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_generated_insights_business_id", "ai_generated_insights", ["business_id"], unique=False)
    op.create_index(
        "ix_ai_generated_insights_feature_snapshot_id",
        "ai_generated_insights",
        ["feature_snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_generated_insights_business_status_created_at",
        "ai_generated_insights",
        ["business_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_generated_insights_business_type_created_at",
        "ai_generated_insights",
        ["business_id", "insight_type", "created_at"],
        unique=False,
    )

    op.create_table(
        "ai_prescriptive_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("insight_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="proposed"),
        sa.Column("decision_note", sa.String(length=255), nullable=True),
        sa.Column("decided_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["insight_id"], ["ai_generated_insights.id"]),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_prescriptive_actions_business_id",
        "ai_prescriptive_actions",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_prescriptive_actions_insight_id",
        "ai_prescriptive_actions",
        ["insight_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_prescriptive_actions_decided_by_user_id",
        "ai_prescriptive_actions",
        ["decided_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_prescriptive_actions_business_status_created_at",
        "ai_prescriptive_actions",
        ["business_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_prescriptive_actions_insight_status",
        "ai_prescriptive_actions",
        ["insight_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_prescriptive_actions_insight_status", table_name="ai_prescriptive_actions")
    op.drop_index("ix_ai_prescriptive_actions_business_status_created_at", table_name="ai_prescriptive_actions")
    op.drop_index("ix_ai_prescriptive_actions_decided_by_user_id", table_name="ai_prescriptive_actions")
    op.drop_index("ix_ai_prescriptive_actions_insight_id", table_name="ai_prescriptive_actions")
    op.drop_index("ix_ai_prescriptive_actions_business_id", table_name="ai_prescriptive_actions")
    op.drop_table("ai_prescriptive_actions")

    op.drop_index("ix_ai_generated_insights_business_type_created_at", table_name="ai_generated_insights")
    op.drop_index("ix_ai_generated_insights_business_status_created_at", table_name="ai_generated_insights")
    op.drop_index("ix_ai_generated_insights_feature_snapshot_id", table_name="ai_generated_insights")
    op.drop_index("ix_ai_generated_insights_business_id", table_name="ai_generated_insights")
    op.drop_table("ai_generated_insights")

    op.drop_index("ix_ai_feature_snapshots_business_window_end_created_at", table_name="ai_feature_snapshots")
    op.drop_index("ix_ai_feature_snapshots_created_by_user_id", table_name="ai_feature_snapshots")
    op.drop_index("ix_ai_feature_snapshots_business_id", table_name="ai_feature_snapshots")
    op.drop_table("ai_feature_snapshots")
