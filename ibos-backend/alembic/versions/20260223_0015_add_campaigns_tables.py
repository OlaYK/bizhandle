"""add campaigns, consents, and retention trigger tables

Revision ID: 20260223_0015
Revises: 20260222_0014
Create Date: 2026-02-23 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260223_0015"
down_revision: Union[str, None] = "20260222_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_segments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("filters_json", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "name", name="uq_customer_segments_business_name"),
    )
    op.create_index("ix_customer_segments_business_id", "customer_segments", ["business_id"], unique=False)
    op.create_index("ix_customer_segments_created_by_user_id", "customer_segments", ["created_by_user_id"], unique=False)
    op.create_index(
        "ix_customer_segments_business_active_created_at",
        "customer_segments",
        ["business_id", "is_active", "created_at"],
        unique=False,
    )

    op.create_table(
        "campaign_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False, server_default="whatsapp"),
        sa.Column("content", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("approved_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "name", name="uq_campaign_templates_business_name"),
    )
    op.create_index("ix_campaign_templates_business_id", "campaign_templates", ["business_id"], unique=False)
    op.create_index("ix_campaign_templates_created_by_user_id", "campaign_templates", ["created_by_user_id"], unique=False)
    op.create_index("ix_campaign_templates_approved_by_user_id", "campaign_templates", ["approved_by_user_id"], unique=False)
    op.create_index(
        "ix_campaign_templates_business_status_created_at",
        "campaign_templates",
        ["business_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("segment_id", sa.String(length=36), nullable=True),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False, server_default="whatsapp"),
        sa.Column("provider", sa.String(length=60), nullable=False, server_default="whatsapp_stub"),
        sa.Column("message_content", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_recipients", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opened_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replied_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["segment_id"], ["customer_segments.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["campaign_templates.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_business_id", "campaigns", ["business_id"], unique=False)
    op.create_index("ix_campaigns_segment_id", "campaigns", ["segment_id"], unique=False)
    op.create_index("ix_campaigns_template_id", "campaigns", ["template_id"], unique=False)
    op.create_index("ix_campaigns_created_by_user_id", "campaigns", ["created_by_user_id"], unique=False)
    op.create_index(
        "ix_campaigns_business_status_created_at",
        "campaigns",
        ["business_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "campaign_recipients",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("recipient", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("outbound_message_id", sa.String(length=36), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["outbound_message_id"], ["outbound_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "customer_id", name="uq_campaign_recipients_campaign_customer"),
    )
    op.create_index("ix_campaign_recipients_campaign_id", "campaign_recipients", ["campaign_id"], unique=False)
    op.create_index("ix_campaign_recipients_business_id", "campaign_recipients", ["business_id"], unique=False)
    op.create_index("ix_campaign_recipients_customer_id", "campaign_recipients", ["customer_id"], unique=False)
    op.create_index("ix_campaign_recipients_outbound_message_id", "campaign_recipients", ["outbound_message_id"], unique=False)
    op.create_index(
        "ix_campaign_recipients_campaign_status",
        "campaign_recipients",
        ["campaign_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_recipients_business_status_created_at",
        "campaign_recipients",
        ["business_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "customer_consents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="subscribed"),
        sa.Column("source", sa.String(length=60), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("opted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id",
            "customer_id",
            "channel",
            name="uq_customer_consents_business_customer_channel",
        ),
    )
    op.create_index("ix_customer_consents_business_id", "customer_consents", ["business_id"], unique=False)
    op.create_index("ix_customer_consents_customer_id", "customer_consents", ["customer_id"], unique=False)
    op.create_index(
        "ix_customer_consents_business_channel_status",
        "customer_consents",
        ["business_id", "channel", "status"],
        unique=False,
    )

    op.create_table(
        "retention_triggers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("segment_id", sa.String(length=36), nullable=True),
        sa.Column("template_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "trigger_type",
            sa.String(length=40),
            nullable=False,
            server_default="repeat_purchase_nudge",
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("channel", sa.String(length=30), nullable=False, server_default="whatsapp"),
        sa.Column("provider", sa.String(length=60), nullable=False, server_default="whatsapp_stub"),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["segment_id"], ["customer_segments.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["campaign_templates.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retention_triggers_business_id", "retention_triggers", ["business_id"], unique=False)
    op.create_index("ix_retention_triggers_segment_id", "retention_triggers", ["segment_id"], unique=False)
    op.create_index("ix_retention_triggers_template_id", "retention_triggers", ["template_id"], unique=False)
    op.create_index("ix_retention_triggers_created_by_user_id", "retention_triggers", ["created_by_user_id"], unique=False)
    op.create_index(
        "ix_retention_triggers_business_status_created_at",
        "retention_triggers",
        ["business_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "retention_trigger_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("retention_trigger_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["retention_trigger_id"], ["retention_triggers.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retention_trigger_runs_business_id", "retention_trigger_runs", ["business_id"], unique=False)
    op.create_index("ix_retention_trigger_runs_retention_trigger_id", "retention_trigger_runs", ["retention_trigger_id"], unique=False)
    op.create_index("ix_retention_trigger_runs_campaign_id", "retention_trigger_runs", ["campaign_id"], unique=False)
    op.create_index(
        "ix_retention_trigger_runs_trigger_created_at",
        "retention_trigger_runs",
        ["retention_trigger_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_retention_trigger_runs_trigger_created_at", table_name="retention_trigger_runs")
    op.drop_index("ix_retention_trigger_runs_campaign_id", table_name="retention_trigger_runs")
    op.drop_index("ix_retention_trigger_runs_retention_trigger_id", table_name="retention_trigger_runs")
    op.drop_index("ix_retention_trigger_runs_business_id", table_name="retention_trigger_runs")
    op.drop_table("retention_trigger_runs")

    op.drop_index("ix_retention_triggers_business_status_created_at", table_name="retention_triggers")
    op.drop_index("ix_retention_triggers_created_by_user_id", table_name="retention_triggers")
    op.drop_index("ix_retention_triggers_template_id", table_name="retention_triggers")
    op.drop_index("ix_retention_triggers_segment_id", table_name="retention_triggers")
    op.drop_index("ix_retention_triggers_business_id", table_name="retention_triggers")
    op.drop_table("retention_triggers")

    op.drop_index("ix_customer_consents_business_channel_status", table_name="customer_consents")
    op.drop_index("ix_customer_consents_customer_id", table_name="customer_consents")
    op.drop_index("ix_customer_consents_business_id", table_name="customer_consents")
    op.drop_table("customer_consents")

    op.drop_index("ix_campaign_recipients_business_status_created_at", table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_campaign_status", table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_outbound_message_id", table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_customer_id", table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_business_id", table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_campaign_id", table_name="campaign_recipients")
    op.drop_table("campaign_recipients")

    op.drop_index("ix_campaigns_business_status_created_at", table_name="campaigns")
    op.drop_index("ix_campaigns_created_by_user_id", table_name="campaigns")
    op.drop_index("ix_campaigns_template_id", table_name="campaigns")
    op.drop_index("ix_campaigns_segment_id", table_name="campaigns")
    op.drop_index("ix_campaigns_business_id", table_name="campaigns")
    op.drop_table("campaigns")

    op.drop_index("ix_campaign_templates_business_status_created_at", table_name="campaign_templates")
    op.drop_index("ix_campaign_templates_approved_by_user_id", table_name="campaign_templates")
    op.drop_index("ix_campaign_templates_created_by_user_id", table_name="campaign_templates")
    op.drop_index("ix_campaign_templates_business_id", table_name="campaign_templates")
    op.drop_table("campaign_templates")

    op.drop_index("ix_customer_segments_business_active_created_at", table_name="customer_segments")
    op.drop_index("ix_customer_segments_created_by_user_id", table_name="customer_segments")
    op.drop_index("ix_customer_segments_business_id", table_name="customer_segments")
    op.drop_table("customer_segments")
