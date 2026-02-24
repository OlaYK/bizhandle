"""add advanced receivables tables and invoice extensions

Revision ID: 20260223_0016
Revises: 20260223_0015
Create Date: 2026-02-23 14:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260223_0016"
down_revision: Union[str, None] = "20260223_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("base_currency", sa.String(length=3), nullable=False, server_default="USD"),
    )

    op.create_table(
        "invoice_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("brand_name", sa.String(length=120), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("primary_color", sa.String(length=20), nullable=True),
        sa.Column("footer_text", sa.String(length=255), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_templates_business_id", "invoice_templates", ["business_id"], unique=False)
    op.create_index(
        "ix_invoice_templates_business_status_created_at",
        "invoice_templates",
        ["business_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_invoice_templates_business_default_updated_at",
        "invoice_templates",
        ["business_id", "is_default", "updated_at"],
        unique=False,
    )

    op.add_column(
        "invoices",
        sa.Column("base_currency", sa.String(length=3), nullable=False, server_default="USD"),
    )
    op.add_column(
        "invoices",
        sa.Column("fx_rate_to_base", sa.Numeric(12, 6), nullable=False, server_default="1"),
    )
    op.add_column(
        "invoices",
        sa.Column("total_amount_base", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "invoices",
        sa.Column("amount_paid_base", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column("invoices", sa.Column("template_id", sa.String(length=36), nullable=True))
    op.add_column("invoices", sa.Column("reminder_policy_json", sa.JSON(), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("reminder_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("invoices", sa.Column("next_reminder_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key("fk_invoices_template_id", "invoices", "invoice_templates", ["template_id"], ["id"])
    op.create_index("ix_invoices_template_id", "invoices", ["template_id"], unique=False)
    op.create_index("ix_invoices_next_reminder_at", "invoices", ["next_reminder_at"], unique=False)
    op.create_index(
        "ix_invoices_business_next_reminder",
        "invoices",
        ["business_id", "next_reminder_at"],
        unique=False,
    )

    op.create_table(
        "invoice_payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_base", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("fx_rate_to_base", sa.Numeric(12, 6), nullable=False),
        sa.Column("payment_method", sa.String(length=30), nullable=True),
        sa.Column("payment_reference", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_payments_invoice_id", "invoice_payments", ["invoice_id"], unique=False)
    op.create_index("ix_invoice_payments_business_id", "invoice_payments", ["business_id"], unique=False)
    op.create_index(
        "ix_invoice_payments_business_paid_at",
        "invoice_payments",
        ["business_id", "paid_at"],
        unique=False,
    )
    op.create_index(
        "ix_invoice_payments_invoice_created_at",
        "invoice_payments",
        ["invoice_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "invoice_installments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_installments_invoice_id", "invoice_installments", ["invoice_id"], unique=False)
    op.create_index("ix_invoice_installments_business_id", "invoice_installments", ["business_id"], unique=False)
    op.create_index("ix_invoice_installments_due_date", "invoice_installments", ["due_date"], unique=False)
    op.create_index(
        "ix_invoice_installments_invoice_due_date",
        "invoice_installments",
        ["invoice_id", "due_date"],
        unique=False,
    )
    op.create_index(
        "ix_invoice_installments_business_status_due_date",
        "invoice_installments",
        ["business_id", "status", "due_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_invoice_installments_business_status_due_date", table_name="invoice_installments")
    op.drop_index("ix_invoice_installments_invoice_due_date", table_name="invoice_installments")
    op.drop_index("ix_invoice_installments_due_date", table_name="invoice_installments")
    op.drop_index("ix_invoice_installments_business_id", table_name="invoice_installments")
    op.drop_index("ix_invoice_installments_invoice_id", table_name="invoice_installments")
    op.drop_table("invoice_installments")

    op.drop_index("ix_invoice_payments_invoice_created_at", table_name="invoice_payments")
    op.drop_index("ix_invoice_payments_business_paid_at", table_name="invoice_payments")
    op.drop_index("ix_invoice_payments_business_id", table_name="invoice_payments")
    op.drop_index("ix_invoice_payments_invoice_id", table_name="invoice_payments")
    op.drop_table("invoice_payments")

    op.drop_index("ix_invoices_business_next_reminder", table_name="invoices")
    op.drop_index("ix_invoices_next_reminder_at", table_name="invoices")
    op.drop_index("ix_invoices_template_id", table_name="invoices")
    op.drop_constraint("fk_invoices_template_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "escalation_level")
    op.drop_column("invoices", "next_reminder_at")
    op.drop_column("invoices", "reminder_count")
    op.drop_column("invoices", "reminder_policy_json")
    op.drop_column("invoices", "template_id")
    op.drop_column("invoices", "amount_paid_base")
    op.drop_column("invoices", "total_amount_base")
    op.drop_column("invoices", "fx_rate_to_base")
    op.drop_column("invoices", "base_currency")

    op.drop_index("ix_invoice_templates_business_default_updated_at", table_name="invoice_templates")
    op.drop_index("ix_invoice_templates_business_status_created_at", table_name="invoice_templates")
    op.drop_index("ix_invoice_templates_business_id", table_name="invoice_templates")
    op.drop_table("invoice_templates")

    op.drop_column("businesses", "base_currency")
