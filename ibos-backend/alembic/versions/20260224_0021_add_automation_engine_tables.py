"""add automation engine tables

Revision ID: 20260224_0021
Revises: 20260224_0020
Create Date: 2026-02-24 09:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260224_0021"
down_revision: Union[str, None] = "20260224_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("trigger_source", sa.String(length=30), nullable=False, server_default="outbox_event"),
        sa.Column("trigger_event_type", sa.String(length=120), nullable=False, server_default="*"),
        sa.Column("conditions_json", sa.JSON(), nullable=True),
        sa.Column("actions_json", sa.JSON(), nullable=True),
        sa.Column("template_key", sa.String(length=60), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("run_limit_per_hour", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("reentry_cooldown_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("rollback_on_failure", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "name", name="uq_automation_rules_business_name"),
    )
    op.create_index("ix_automation_rules_business_id", "automation_rules", ["business_id"], unique=False)
    op.create_index("ix_automation_rules_created_by_user_id", "automation_rules", ["created_by_user_id"], unique=False)
    op.create_index("ix_automation_rules_updated_by_user_id", "automation_rules", ["updated_by_user_id"], unique=False)
    op.create_index("ix_automation_rules_template_key", "automation_rules", ["template_key"], unique=False)
    op.create_index("ix_automation_rules_trigger_event_type", "automation_rules", ["trigger_event_type"], unique=False)
    op.create_index(
        "ix_automation_rules_business_status_updated_at",
        "automation_rules",
        ["business_id", "status", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_automation_rules_business_trigger_status",
        "automation_rules",
        ["business_id", "trigger_event_type", "status"],
        unique=False,
    )

    op.create_table(
        "automation_rule_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), nullable=False),
        sa.Column("trigger_event_id", sa.String(length=36), nullable=True),
        sa.Column("trigger_event_type", sa.String(length=120), nullable=False),
        sa.Column("trigger_payload_json", sa.JSON(), nullable=True),
        sa.Column("trigger_fingerprint", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("blocked_reason", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("steps_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("steps_succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("steps_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["integration_outbox_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "trigger_event_id", name="uq_automation_rule_runs_rule_trigger_event"),
    )
    op.create_index("ix_automation_rule_runs_business_id", "automation_rule_runs", ["business_id"], unique=False)
    op.create_index("ix_automation_rule_runs_rule_id", "automation_rule_runs", ["rule_id"], unique=False)
    op.create_index(
        "ix_automation_rule_runs_trigger_event_id",
        "automation_rule_runs",
        ["trigger_event_id"],
        unique=False,
    )
    op.create_index(
        "ix_automation_rule_runs_trigger_fingerprint",
        "automation_rule_runs",
        ["trigger_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_automation_rule_runs_rule_created_at",
        "automation_rule_runs",
        ["rule_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_automation_rule_runs_business_status_created_at",
        "automation_rule_runs",
        ["business_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "automation_rule_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("rule_run_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["rule_run_id"], ["automation_rule_runs.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_rule_steps_business_id", "automation_rule_steps", ["business_id"], unique=False)
    op.create_index("ix_automation_rule_steps_rule_run_id", "automation_rule_steps", ["rule_run_id"], unique=False)
    op.create_index("ix_automation_rule_steps_rule_id", "automation_rule_steps", ["rule_id"], unique=False)
    op.create_index(
        "ix_automation_rule_steps_run_step",
        "automation_rule_steps",
        ["rule_run_id", "step_index"],
        unique=False,
    )
    op.create_index(
        "ix_automation_rule_steps_business_created_at",
        "automation_rule_steps",
        ["business_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "automation_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("rule_run_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("assignee_user_id", sa.String(length=36), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["rule_run_id"], ["automation_rule_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_tasks_business_id", "automation_tasks", ["business_id"], unique=False)
    op.create_index("ix_automation_tasks_rule_run_id", "automation_tasks", ["rule_run_id"], unique=False)
    op.create_index("ix_automation_tasks_assignee_user_id", "automation_tasks", ["assignee_user_id"], unique=False)
    op.create_index(
        "ix_automation_tasks_business_status_created_at",
        "automation_tasks",
        ["business_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "automation_discounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("rule_run_id", sa.String(length=36), nullable=True),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="percentage"),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("target_customer_id", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["rule_run_id"], ["automation_rule_runs.id"]),
        sa.ForeignKeyConstraint(["target_customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "code", name="uq_automation_discounts_business_code"),
    )
    op.create_index("ix_automation_discounts_business_id", "automation_discounts", ["business_id"], unique=False)
    op.create_index("ix_automation_discounts_rule_run_id", "automation_discounts", ["rule_run_id"], unique=False)
    op.create_index(
        "ix_automation_discounts_target_customer_id",
        "automation_discounts",
        ["target_customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_automation_discounts_business_status_created_at",
        "automation_discounts",
        ["business_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_automation_discounts_business_status_created_at", table_name="automation_discounts")
    op.drop_index("ix_automation_discounts_target_customer_id", table_name="automation_discounts")
    op.drop_index("ix_automation_discounts_rule_run_id", table_name="automation_discounts")
    op.drop_index("ix_automation_discounts_business_id", table_name="automation_discounts")
    op.drop_table("automation_discounts")

    op.drop_index("ix_automation_tasks_business_status_created_at", table_name="automation_tasks")
    op.drop_index("ix_automation_tasks_assignee_user_id", table_name="automation_tasks")
    op.drop_index("ix_automation_tasks_rule_run_id", table_name="automation_tasks")
    op.drop_index("ix_automation_tasks_business_id", table_name="automation_tasks")
    op.drop_table("automation_tasks")

    op.drop_index("ix_automation_rule_steps_business_created_at", table_name="automation_rule_steps")
    op.drop_index("ix_automation_rule_steps_run_step", table_name="automation_rule_steps")
    op.drop_index("ix_automation_rule_steps_rule_id", table_name="automation_rule_steps")
    op.drop_index("ix_automation_rule_steps_rule_run_id", table_name="automation_rule_steps")
    op.drop_index("ix_automation_rule_steps_business_id", table_name="automation_rule_steps")
    op.drop_table("automation_rule_steps")

    op.drop_index("ix_automation_rule_runs_business_status_created_at", table_name="automation_rule_runs")
    op.drop_index("ix_automation_rule_runs_rule_created_at", table_name="automation_rule_runs")
    op.drop_index("ix_automation_rule_runs_trigger_fingerprint", table_name="automation_rule_runs")
    op.drop_index("ix_automation_rule_runs_trigger_event_id", table_name="automation_rule_runs")
    op.drop_index("ix_automation_rule_runs_rule_id", table_name="automation_rule_runs")
    op.drop_index("ix_automation_rule_runs_business_id", table_name="automation_rule_runs")
    op.drop_table("automation_rule_runs")

    op.drop_index("ix_automation_rules_business_trigger_status", table_name="automation_rules")
    op.drop_index("ix_automation_rules_business_status_updated_at", table_name="automation_rules")
    op.drop_index("ix_automation_rules_trigger_event_type", table_name="automation_rules")
    op.drop_index("ix_automation_rules_template_key", table_name="automation_rules")
    op.drop_index("ix_automation_rules_updated_by_user_id", table_name="automation_rules")
    op.drop_index("ix_automation_rules_created_by_user_id", table_name="automation_rules")
    op.drop_index("ix_automation_rules_business_id", table_name="automation_rules")
    op.drop_table("automation_rules")
