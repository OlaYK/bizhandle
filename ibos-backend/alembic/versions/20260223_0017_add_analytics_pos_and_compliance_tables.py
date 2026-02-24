"""add analytics, pos, and compliance hardening tables

Revision ID: 20260223_0017
Revises: 20260223_0016
Create Date: 2026-02-23 20:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260223_0017"
down_revision: Union[str, None] = "20260223_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_daily_metrics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("revenue", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cogs", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("expenses", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("gross_profit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_profit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("orders_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repeat_orders_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stockout_events_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id",
            "metric_date",
            "channel",
            name="uq_analytics_daily_metrics_business_date_channel",
        ),
    )
    op.create_index("ix_analytics_daily_metrics_business_id", "analytics_daily_metrics", ["business_id"], unique=False)
    op.create_index("ix_analytics_daily_metrics_metric_date", "analytics_daily_metrics", ["metric_date"], unique=False)
    op.create_index("ix_analytics_daily_metrics_channel", "analytics_daily_metrics", ["channel"], unique=False)
    op.create_index(
        "ix_analytics_daily_metrics_business_channel_metric_date",
        "analytics_daily_metrics",
        ["business_id", "channel", "metric_date"],
        unique=False,
    )

    op.create_table(
        "marketing_attribution_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("medium", sa.String(length=80), nullable=True),
        sa.Column("campaign_name", sa.String(length=120), nullable=True),
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("revenue_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_marketing_attribution_events_business_id",
        "marketing_attribution_events",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_marketing_attribution_events_channel",
        "marketing_attribution_events",
        ["channel"],
        unique=False,
    )
    op.create_index(
        "ix_marketing_attribution_events_order_id",
        "marketing_attribution_events",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        "ix_marketing_attribution_events_business_channel_event_time",
        "marketing_attribution_events",
        ["business_id", "channel", "event_time"],
        unique=False,
    )
    op.create_index(
        "ix_marketing_attribution_events_business_event_type_event_time",
        "marketing_attribution_events",
        ["business_id", "event_type", "event_time"],
        unique=False,
    )

    op.create_table(
        "analytics_report_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False, server_default="weekly"),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analytics_report_schedules_business_id",
        "analytics_report_schedules",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_report_schedules_business_status_next_run_at",
        "analytics_report_schedules",
        ["business_id", "status", "next_run_at"],
        unique=False,
    )

    op.create_table(
        "pos_shift_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("opened_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("closed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("opening_cash", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("closing_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_difference", sa.Numeric(12, 2), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["opened_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pos_shift_sessions_business_id", "pos_shift_sessions", ["business_id"], unique=False)
    op.create_index("ix_pos_shift_sessions_opened_by_user_id", "pos_shift_sessions", ["opened_by_user_id"], unique=False)
    op.create_index("ix_pos_shift_sessions_closed_by_user_id", "pos_shift_sessions", ["closed_by_user_id"], unique=False)
    op.create_index(
        "ix_pos_shift_sessions_business_status_opened_at",
        "pos_shift_sessions",
        ["business_id", "status", "opened_at"],
        unique=False,
    )
    op.create_index(
        "ix_pos_shift_sessions_business_opened_by_status",
        "pos_shift_sessions",
        ["business_id", "opened_by_user_id", "status"],
        unique=False,
    )

    op.create_table(
        "offline_order_sync_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("client_event_id", sa.String(length=120), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("conflict_code", sa.String(length=40), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id",
            "client_event_id",
            name="uq_offline_order_sync_events_business_client_event",
        ),
    )
    op.create_index("ix_offline_order_sync_events_business_id", "offline_order_sync_events", ["business_id"], unique=False)
    op.create_index("ix_offline_order_sync_events_order_id", "offline_order_sync_events", ["order_id"], unique=False)
    op.create_index(
        "ix_offline_order_sync_events_business_status_created_at",
        "offline_order_sync_events",
        ["business_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "audit_log_archives",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("archived_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("cutoff_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("records_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["archived_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_archives_business_id", "audit_log_archives", ["business_id"], unique=False)
    op.create_index(
        "ix_audit_log_archives_archived_by_user_id",
        "audit_log_archives",
        ["archived_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_log_archives_business_created_at",
        "audit_log_archives",
        ["business_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_log_archives_business_cutoff_date",
        "audit_log_archives",
        ["business_id", "cutoff_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_archives_business_cutoff_date", table_name="audit_log_archives")
    op.drop_index("ix_audit_log_archives_business_created_at", table_name="audit_log_archives")
    op.drop_index("ix_audit_log_archives_archived_by_user_id", table_name="audit_log_archives")
    op.drop_index("ix_audit_log_archives_business_id", table_name="audit_log_archives")
    op.drop_table("audit_log_archives")

    op.drop_index("ix_offline_order_sync_events_business_status_created_at", table_name="offline_order_sync_events")
    op.drop_index("ix_offline_order_sync_events_order_id", table_name="offline_order_sync_events")
    op.drop_index("ix_offline_order_sync_events_business_id", table_name="offline_order_sync_events")
    op.drop_table("offline_order_sync_events")

    op.drop_index("ix_pos_shift_sessions_business_opened_by_status", table_name="pos_shift_sessions")
    op.drop_index("ix_pos_shift_sessions_business_status_opened_at", table_name="pos_shift_sessions")
    op.drop_index("ix_pos_shift_sessions_closed_by_user_id", table_name="pos_shift_sessions")
    op.drop_index("ix_pos_shift_sessions_opened_by_user_id", table_name="pos_shift_sessions")
    op.drop_index("ix_pos_shift_sessions_business_id", table_name="pos_shift_sessions")
    op.drop_table("pos_shift_sessions")

    op.drop_index("ix_analytics_report_schedules_business_status_next_run_at", table_name="analytics_report_schedules")
    op.drop_index("ix_analytics_report_schedules_business_id", table_name="analytics_report_schedules")
    op.drop_table("analytics_report_schedules")

    op.drop_index("ix_marketing_attribution_events_business_event_type_event_time", table_name="marketing_attribution_events")
    op.drop_index("ix_marketing_attribution_events_business_channel_event_time", table_name="marketing_attribution_events")
    op.drop_index("ix_marketing_attribution_events_order_id", table_name="marketing_attribution_events")
    op.drop_index("ix_marketing_attribution_events_channel", table_name="marketing_attribution_events")
    op.drop_index("ix_marketing_attribution_events_business_id", table_name="marketing_attribution_events")
    op.drop_table("marketing_attribution_events")

    op.drop_index("ix_analytics_daily_metrics_business_channel_metric_date", table_name="analytics_daily_metrics")
    op.drop_index("ix_analytics_daily_metrics_channel", table_name="analytics_daily_metrics")
    op.drop_index("ix_analytics_daily_metrics_metric_date", table_name="analytics_daily_metrics")
    op.drop_index("ix_analytics_daily_metrics_business_id", table_name="analytics_daily_metrics")
    op.drop_table("analytics_daily_metrics")
