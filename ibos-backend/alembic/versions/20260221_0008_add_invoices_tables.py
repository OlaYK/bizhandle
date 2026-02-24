"""add invoices tables

Revision ID: 20260221_0008
Revises: 20260221_0007
Create Date: 2026-02-22 00:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260221_0008"
down_revision: Union[str, None] = "20260221_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "invoices"):
        op.create_table(
            "invoices",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("customer_id", sa.String(length=36), nullable=True),
            sa.Column("order_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("payment_reference", sa.String(length=120), nullable=True),
            sa.Column("payment_method", sa.String(length=30), nullable=True),
            sa.Column("issue_date", sa.Date(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("note", sa.String(length=255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "invoices"):
        if not _index_exists(inspector, "invoices", "ix_invoices_business_id"):
            op.create_index("ix_invoices_business_id", "invoices", ["business_id"], unique=False)
        if not _index_exists(inspector, "invoices", "ix_invoices_customer_id"):
            op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"], unique=False)
        if not _index_exists(inspector, "invoices", "ix_invoices_order_id"):
            op.create_index("ix_invoices_order_id", "invoices", ["order_id"], unique=False)
        if not _index_exists(inspector, "invoices", "ix_invoices_due_date"):
            op.create_index("ix_invoices_due_date", "invoices", ["due_date"], unique=False)
        if not _index_exists(inspector, "invoices", "ix_invoices_business_status_created_at"):
            op.create_index(
                "ix_invoices_business_status_created_at",
                "invoices",
                ["business_id", "status", "created_at"],
                unique=False,
            )
        if not _index_exists(inspector, "invoices", "ix_invoices_business_due_date"):
            op.create_index(
                "ix_invoices_business_due_date",
                "invoices",
                ["business_id", "due_date"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "invoice_events"):
        op.create_table(
            "invoice_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("invoice_id", sa.String(length=36), nullable=False),
            sa.Column("business_id", sa.String(length=36), nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("idempotency_key", sa.String(length=120), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
            sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "invoice_events"):
        if not _index_exists(inspector, "invoice_events", "ix_invoice_events_invoice_id"):
            op.create_index("ix_invoice_events_invoice_id", "invoice_events", ["invoice_id"], unique=False)
        if not _index_exists(inspector, "invoice_events", "ix_invoice_events_business_id"):
            op.create_index("ix_invoice_events_business_id", "invoice_events", ["business_id"], unique=False)
        if not _index_exists(inspector, "invoice_events", "ix_invoice_events_idempotency_key"):
            op.create_index(
                "ix_invoice_events_idempotency_key",
                "invoice_events",
                ["idempotency_key"],
                unique=False,
            )
        if not _index_exists(inspector, "invoice_events", "ix_invoice_events_business_created_at"):
            op.create_index(
                "ix_invoice_events_business_created_at",
                "invoice_events",
                ["business_id", "created_at"],
                unique=False,
            )
        if not _index_exists(inspector, "invoice_events", "ix_invoice_events_invoice_event_type_created_at"):
            op.create_index(
                "ix_invoice_events_invoice_event_type_created_at",
                "invoice_events",
                ["invoice_id", "event_type", "created_at"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "invoice_events"):
        if _index_exists(inspector, "invoice_events", "ix_invoice_events_invoice_event_type_created_at"):
            op.drop_index("ix_invoice_events_invoice_event_type_created_at", table_name="invoice_events")
        if _index_exists(inspector, "invoice_events", "ix_invoice_events_business_created_at"):
            op.drop_index("ix_invoice_events_business_created_at", table_name="invoice_events")
        if _index_exists(inspector, "invoice_events", "ix_invoice_events_idempotency_key"):
            op.drop_index("ix_invoice_events_idempotency_key", table_name="invoice_events")
        if _index_exists(inspector, "invoice_events", "ix_invoice_events_business_id"):
            op.drop_index("ix_invoice_events_business_id", table_name="invoice_events")
        if _index_exists(inspector, "invoice_events", "ix_invoice_events_invoice_id"):
            op.drop_index("ix_invoice_events_invoice_id", table_name="invoice_events")
        op.drop_table("invoice_events")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "invoices"):
        if _index_exists(inspector, "invoices", "ix_invoices_business_due_date"):
            op.drop_index("ix_invoices_business_due_date", table_name="invoices")
        if _index_exists(inspector, "invoices", "ix_invoices_business_status_created_at"):
            op.drop_index("ix_invoices_business_status_created_at", table_name="invoices")
        if _index_exists(inspector, "invoices", "ix_invoices_due_date"):
            op.drop_index("ix_invoices_due_date", table_name="invoices")
        if _index_exists(inspector, "invoices", "ix_invoices_order_id"):
            op.drop_index("ix_invoices_order_id", table_name="invoices")
        if _index_exists(inspector, "invoices", "ix_invoices_customer_id"):
            op.drop_index("ix_invoices_customer_id", table_name="invoices")
        if _index_exists(inspector, "invoices", "ix_invoices_business_id"):
            op.drop_index("ix_invoices_business_id", table_name="invoices")
        op.drop_table("invoices")
