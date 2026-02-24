"""add developer platform tables

Revision ID: 20260224_0022
Revises: 20260224_0021
Create Date: 2026-02-24 13:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260224_0022"
down_revision: Union[str, None] = "20260224_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "public_api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("scopes_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("rotated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["rotated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "name", name="uq_public_api_keys_business_name"),
        sa.UniqueConstraint("key_hash", name="uq_public_api_keys_key_hash"),
    )
    op.create_index("ix_public_api_keys_business_id", "public_api_keys", ["business_id"], unique=False)
    op.create_index("ix_public_api_keys_key_prefix", "public_api_keys", ["key_prefix"], unique=False)
    op.create_index("ix_public_api_keys_created_by_user_id", "public_api_keys", ["created_by_user_id"], unique=False)
    op.create_index("ix_public_api_keys_rotated_by_user_id", "public_api_keys", ["rotated_by_user_id"], unique=False)
    op.create_index(
        "ix_public_api_keys_business_status_created_at",
        "public_api_keys",
        ["business_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_public_api_keys_business_key_prefix",
        "public_api_keys",
        ["business_id", "key_prefix"],
        unique=False,
    )

    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("endpoint_url", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("events_json", sa.JSON(), nullable=True),
        sa.Column("secret_encrypted", sa.String(length=2048), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("retry_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "name", name="uq_webhook_subscriptions_business_name"),
    )
    op.create_index("ix_webhook_subscriptions_business_id", "webhook_subscriptions", ["business_id"], unique=False)
    op.create_index(
        "ix_webhook_subscriptions_created_by_user_id",
        "webhook_subscriptions",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_webhook_subscriptions_updated_by_user_id",
        "webhook_subscriptions",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_webhook_subscriptions_business_status_updated_at",
        "webhook_subscriptions",
        ["business_id", "status", "updated_at"],
        unique=False,
    )

    op.create_table(
        "webhook_event_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("outbox_event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("last_response_code", sa.Integer(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["outbox_event_id"], ["integration_outbox_events.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["webhook_subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_id", "outbox_event_id", name="uq_webhook_event_delivery_subscription_event"),
    )
    op.create_index("ix_webhook_event_deliveries_business_id", "webhook_event_deliveries", ["business_id"], unique=False)
    op.create_index(
        "ix_webhook_event_deliveries_subscription_id",
        "webhook_event_deliveries",
        ["subscription_id"],
        unique=False,
    )
    op.create_index(
        "ix_webhook_event_deliveries_outbox_event_id",
        "webhook_event_deliveries",
        ["outbox_event_id"],
        unique=False,
    )
    op.create_index("ix_webhook_event_deliveries_event_type", "webhook_event_deliveries", ["event_type"], unique=False)
    op.create_index(
        "ix_webhook_event_deliveries_business_status_next_attempt",
        "webhook_event_deliveries",
        ["business_id", "status", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_webhook_event_deliveries_subscription_created_at",
        "webhook_event_deliveries",
        ["subscription_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "webhook_delivery_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("webhook_delivery_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.String(length=500), nullable=True),
        sa.Column("signature", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["webhook_delivery_id"], ["webhook_event_deliveries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_webhook_delivery_attempts_webhook_delivery_id",
        "webhook_delivery_attempts",
        ["webhook_delivery_id"],
        unique=False,
    )

    op.create_table(
        "marketplace_app_listings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("app_key", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False, server_default="operations"),
        sa.Column("requested_scopes_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("review_notes", sa.String(length=500), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "app_key", name="uq_marketplace_app_listing_business_app_key"),
    )
    op.create_index("ix_marketplace_app_listings_business_id", "marketplace_app_listings", ["business_id"], unique=False)
    op.create_index(
        "ix_marketplace_app_listings_reviewed_by_user_id",
        "marketplace_app_listings",
        ["reviewed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_marketplace_app_listings_created_by_user_id",
        "marketplace_app_listings",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_marketplace_app_listings_updated_by_user_id",
        "marketplace_app_listings",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_marketplace_app_listings_business_status_updated_at",
        "marketplace_app_listings",
        ["business_id", "status", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_marketplace_app_listings_status_published_at",
        "marketplace_app_listings",
        ["status", "published_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_marketplace_app_listings_status_published_at", table_name="marketplace_app_listings")
    op.drop_index("ix_marketplace_app_listings_business_status_updated_at", table_name="marketplace_app_listings")
    op.drop_index("ix_marketplace_app_listings_updated_by_user_id", table_name="marketplace_app_listings")
    op.drop_index("ix_marketplace_app_listings_created_by_user_id", table_name="marketplace_app_listings")
    op.drop_index("ix_marketplace_app_listings_reviewed_by_user_id", table_name="marketplace_app_listings")
    op.drop_index("ix_marketplace_app_listings_business_id", table_name="marketplace_app_listings")
    op.drop_table("marketplace_app_listings")

    op.drop_index("ix_webhook_delivery_attempts_webhook_delivery_id", table_name="webhook_delivery_attempts")
    op.drop_table("webhook_delivery_attempts")

    op.drop_index(
        "ix_webhook_event_deliveries_subscription_created_at",
        table_name="webhook_event_deliveries",
    )
    op.drop_index(
        "ix_webhook_event_deliveries_business_status_next_attempt",
        table_name="webhook_event_deliveries",
    )
    op.drop_index("ix_webhook_event_deliveries_event_type", table_name="webhook_event_deliveries")
    op.drop_index("ix_webhook_event_deliveries_outbox_event_id", table_name="webhook_event_deliveries")
    op.drop_index("ix_webhook_event_deliveries_subscription_id", table_name="webhook_event_deliveries")
    op.drop_index("ix_webhook_event_deliveries_business_id", table_name="webhook_event_deliveries")
    op.drop_table("webhook_event_deliveries")

    op.drop_index(
        "ix_webhook_subscriptions_business_status_updated_at",
        table_name="webhook_subscriptions",
    )
    op.drop_index("ix_webhook_subscriptions_updated_by_user_id", table_name="webhook_subscriptions")
    op.drop_index("ix_webhook_subscriptions_created_by_user_id", table_name="webhook_subscriptions")
    op.drop_index("ix_webhook_subscriptions_business_id", table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")

    op.drop_index("ix_public_api_keys_business_key_prefix", table_name="public_api_keys")
    op.drop_index("ix_public_api_keys_business_status_created_at", table_name="public_api_keys")
    op.drop_index("ix_public_api_keys_rotated_by_user_id", table_name="public_api_keys")
    op.drop_index("ix_public_api_keys_created_by_user_id", table_name="public_api_keys")
    op.drop_index("ix_public_api_keys_key_prefix", table_name="public_api_keys")
    op.drop_index("ix_public_api_keys_business_id", table_name="public_api_keys")
    op.drop_table("public_api_keys")
