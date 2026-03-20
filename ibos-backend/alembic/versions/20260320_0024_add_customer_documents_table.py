"""add customer documents table

Revision ID: 20260320_0024
Revises: 20260224_0023
Create Date: 2026-03-20 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260320_0024"
down_revision: Union[str, None] = "20260224_0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("invoice_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("document_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending_signature",
        ),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("consent_text", sa.String(length=4000), nullable=True),
        sa.Column("recipient_name", sa.String(length=120), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("recipient_phone", sa.String(length=40), nullable=True),
        sa.Column("sign_token", sa.String(length=80), nullable=False),
        sa.Column("sign_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_by_name", sa.String(length=120), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signer_ip", sa.String(length=64), nullable=True),
        sa.Column("signature_note", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sign_token"),
    )
    op.create_index(
        "ix_customer_documents_business_status_created_at",
        "customer_documents",
        ["business_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_customer_documents_customer_created_at",
        "customer_documents",
        ["customer_id", "created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_customer_documents_business_id"), "customer_documents", ["business_id"], unique=False)
    op.create_index(op.f("ix_customer_documents_created_by_user_id"), "customer_documents", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_customer_documents_customer_id"), "customer_documents", ["customer_id"], unique=False)
    op.create_index(op.f("ix_customer_documents_invoice_id"), "customer_documents", ["invoice_id"], unique=False)
    op.create_index(op.f("ix_customer_documents_order_id"), "customer_documents", ["order_id"], unique=False)
    op.create_index(op.f("ix_customer_documents_sign_token"), "customer_documents", ["sign_token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_customer_documents_sign_token"), table_name="customer_documents")
    op.drop_index(op.f("ix_customer_documents_order_id"), table_name="customer_documents")
    op.drop_index(op.f("ix_customer_documents_invoice_id"), table_name="customer_documents")
    op.drop_index(op.f("ix_customer_documents_customer_id"), table_name="customer_documents")
    op.drop_index(op.f("ix_customer_documents_created_by_user_id"), table_name="customer_documents")
    op.drop_index(op.f("ix_customer_documents_business_id"), table_name="customer_documents")
    op.drop_index("ix_customer_documents_customer_created_at", table_name="customer_documents")
    op.drop_index("ix_customer_documents_business_status_created_at", table_name="customer_documents")
    op.drop_table("customer_documents")
