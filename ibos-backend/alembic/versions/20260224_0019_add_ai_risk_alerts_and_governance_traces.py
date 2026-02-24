"""add ai risk alerts and governance traces

Revision ID: 20260224_0019
Revises: 20260223_0018
Create Date: 2026-02-24 00:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260224_0019"
down_revision: Union[str, None] = "20260223_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_risk_alert_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("refund_rate_threshold", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("stockout_threshold", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("cashflow_margin_threshold", sa.Float(), nullable=False, server_default="0.15"),
        sa.Column("channels_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", name="uq_ai_risk_alert_configs_business"),
    )
    op.create_index("ix_ai_risk_alert_configs_business_id", "ai_risk_alert_configs", ["business_id"], unique=False)
    op.create_index(
        "ix_ai_risk_alert_configs_updated_by_user_id",
        "ai_risk_alert_configs",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_risk_alert_configs_business_updated_at",
        "ai_risk_alert_configs",
        ["business_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "ai_risk_alert_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("config_id", sa.String(length=36), nullable=True),
        sa.Column("alert_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="triggered"),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("triggered_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("threshold_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("channels_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("acknowledged_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["config_id"], ["ai_risk_alert_configs.id"]),
        sa.ForeignKeyConstraint(["acknowledged_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_risk_alert_events_business_id", "ai_risk_alert_events", ["business_id"], unique=False)
    op.create_index("ix_ai_risk_alert_events_config_id", "ai_risk_alert_events", ["config_id"], unique=False)
    op.create_index(
        "ix_ai_risk_alert_events_acknowledged_by_user_id",
        "ai_risk_alert_events",
        ["acknowledged_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_risk_alert_events_business_status_created_at",
        "ai_risk_alert_events",
        ["business_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_risk_alert_events_business_type_created_at",
        "ai_risk_alert_events",
        ["business_id", "alert_type", "created_at"],
        unique=False,
    )

    op.create_table(
        "ai_governance_traces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("trace_type", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("feature_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("prompt", sa.String(length=3000), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["feature_snapshot_id"], ["ai_feature_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_governance_traces_business_id", "ai_governance_traces", ["business_id"], unique=False)
    op.create_index(
        "ix_ai_governance_traces_actor_user_id",
        "ai_governance_traces",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_governance_traces_feature_snapshot_id",
        "ai_governance_traces",
        ["feature_snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_governance_traces_business_created_at",
        "ai_governance_traces",
        ["business_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_governance_traces_business_type_created_at",
        "ai_governance_traces",
        ["business_id", "trace_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_governance_traces_business_type_created_at", table_name="ai_governance_traces")
    op.drop_index("ix_ai_governance_traces_business_created_at", table_name="ai_governance_traces")
    op.drop_index("ix_ai_governance_traces_feature_snapshot_id", table_name="ai_governance_traces")
    op.drop_index("ix_ai_governance_traces_actor_user_id", table_name="ai_governance_traces")
    op.drop_index("ix_ai_governance_traces_business_id", table_name="ai_governance_traces")
    op.drop_table("ai_governance_traces")

    op.drop_index("ix_ai_risk_alert_events_business_type_created_at", table_name="ai_risk_alert_events")
    op.drop_index("ix_ai_risk_alert_events_business_status_created_at", table_name="ai_risk_alert_events")
    op.drop_index("ix_ai_risk_alert_events_acknowledged_by_user_id", table_name="ai_risk_alert_events")
    op.drop_index("ix_ai_risk_alert_events_config_id", table_name="ai_risk_alert_events")
    op.drop_index("ix_ai_risk_alert_events_business_id", table_name="ai_risk_alert_events")
    op.drop_table("ai_risk_alert_events")

    op.drop_index("ix_ai_risk_alert_configs_business_updated_at", table_name="ai_risk_alert_configs")
    op.drop_index("ix_ai_risk_alert_configs_updated_by_user_id", table_name="ai_risk_alert_configs")
    op.drop_index("ix_ai_risk_alert_configs_business_id", table_name="ai_risk_alert_configs")
    op.drop_table("ai_risk_alert_configs")
