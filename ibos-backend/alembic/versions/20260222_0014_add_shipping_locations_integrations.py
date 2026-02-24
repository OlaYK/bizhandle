"""add shipping, locations, and integrations modules

Revision ID: 20260222_0014
Revises: 20260222_0013
Create Date: 2026-02-22 23:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260222_0014"
down_revision: Union[str, None] = "20260222_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shipping_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("default_origin_country", sa.String(length=60), nullable=False, server_default="NG"),
        sa.Column("default_origin_state", sa.String(length=120), nullable=True),
        sa.Column("default_origin_city", sa.String(length=120), nullable=True),
        sa.Column("default_origin_postal_code", sa.String(length=20), nullable=True),
        sa.Column("handling_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", name="uq_shipping_profiles_business_id"),
    )
    op.create_index("ix_shipping_profiles_business_id", "shipping_profiles", ["business_id"], unique=True)

    op.create_table(
        "shipping_zones",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("zone_name", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=60), nullable=False),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("postal_code_prefix", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["profile_id"], ["shipping_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shipping_zones_profile_id", "shipping_zones", ["profile_id"], unique=False)
    op.create_index(
        "ix_shipping_zones_profile_country_active",
        "shipping_zones",
        ["profile_id", "country", "is_active"],
        unique=False,
    )

    op.create_table(
        "shipping_service_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("zone_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="stub_carrier"),
        sa.Column("service_code", sa.String(length=40), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("base_rate", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("per_kg_rate", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("min_eta_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_eta_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["profile_id"], ["shipping_profiles.id"]),
        sa.ForeignKeyConstraint(["zone_id"], ["shipping_zones.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shipping_service_rules_profile_id", "shipping_service_rules", ["profile_id"], unique=False)
    op.create_index("ix_shipping_service_rules_zone_id", "shipping_service_rules", ["zone_id"], unique=False)
    op.create_index(
        "ix_shipping_service_rules_profile_zone_provider",
        "shipping_service_rules",
        ["profile_id", "zone_id", "provider"],
        unique=False,
    )

    op.create_table(
        "checkout_shipping_selections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("checkout_session_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("service_code", sa.String(length=40), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("zone_name", sa.String(length=120), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("eta_min_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("eta_max_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["checkout_session_id"], ["checkout_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checkout_session_id", name="uq_checkout_shipping_selections_checkout_session_id"),
    )
    op.create_index(
        "ix_checkout_shipping_selections_checkout_session_id",
        "checkout_shipping_selections",
        ["checkout_session_id"],
        unique=True,
    )

    op.create_table(
        "shipments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("checkout_session_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("service_code", sa.String(length=40), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="label_purchased"),
        sa.Column("shipping_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("tracking_number", sa.String(length=120), nullable=True),
        sa.Column("label_url", sa.String(length=500), nullable=True),
        sa.Column("recipient_name", sa.String(length=120), nullable=False),
        sa.Column("recipient_phone", sa.String(length=40), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=60), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["checkout_session_id"], ["checkout_sessions.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shipments_business_id", "shipments", ["business_id"], unique=False)
    op.create_index("ix_shipments_order_id", "shipments", ["order_id"], unique=False)
    op.create_index("ix_shipments_checkout_session_id", "shipments", ["checkout_session_id"], unique=False)
    op.create_index("ix_shipments_tracking_number", "shipments", ["tracking_number"], unique=False)
    op.create_index(
        "ix_shipments_business_status_created_at",
        "shipments",
        ["business_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "shipment_tracking_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("shipment_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shipment_tracking_events_shipment_id", "shipment_tracking_events", ["shipment_id"], unique=False)
    op.create_index(
        "ix_shipment_tracking_events_shipment_event_time",
        "shipment_tracking_events",
        ["shipment_id", "event_time"],
        unique=False,
    )

    op.create_table(
        "locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "code", name="uq_locations_business_code"),
    )
    op.create_index("ix_locations_business_id", "locations", ["business_id"], unique=False)
    op.create_index(
        "ix_locations_business_active_created_at",
        "locations",
        ["business_id", "is_active", "created_at"],
        unique=False,
    )

    op.create_table(
        "location_membership_scopes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("membership_id", sa.String(length=36), nullable=False),
        sa.Column("can_manage_inventory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["membership_id"], ["business_memberships.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_id", "membership_id", name="uq_location_membership_scope"),
    )
    op.create_index("ix_location_membership_scopes_business_id", "location_membership_scopes", ["business_id"], unique=False)
    op.create_index("ix_location_membership_scopes_location_id", "location_membership_scopes", ["location_id"], unique=False)
    op.create_index("ix_location_membership_scopes_membership_id", "location_membership_scopes", ["membership_id"], unique=False)

    op.create_table(
        "location_inventory_ledger",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("variant_id", sa.String(length=36), nullable=False),
        sa.Column("qty_delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("reference_id", sa.String(length=36), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_location_inventory_ledger_business_id", "location_inventory_ledger", ["business_id"], unique=False)
    op.create_index("ix_location_inventory_ledger_location_id", "location_inventory_ledger", ["location_id"], unique=False)
    op.create_index("ix_location_inventory_ledger_variant_id", "location_inventory_ledger", ["variant_id"], unique=False)
    op.create_index(
        "ix_loc_inv_ledger_biz_loc_var_created_at",
        "location_inventory_ledger",
        ["business_id", "location_id", "variant_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "stock_transfers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("from_location_id", sa.String(length=36), nullable=False),
        sa.Column("to_location_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["from_location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["to_location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_transfers_business_id", "stock_transfers", ["business_id"], unique=False)
    op.create_index("ix_stock_transfers_from_location_id", "stock_transfers", ["from_location_id"], unique=False)
    op.create_index("ix_stock_transfers_to_location_id", "stock_transfers", ["to_location_id"], unique=False)
    op.create_index("ix_stock_transfers_created_by_user_id", "stock_transfers", ["created_by_user_id"], unique=False)
    op.create_index("ix_stock_transfers_business_created_at", "stock_transfers", ["business_id", "created_at"], unique=False)

    op.create_table(
        "stock_transfer_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stock_transfer_id", sa.String(length=36), nullable=False),
        sa.Column("variant_id", sa.String(length=36), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["stock_transfer_id"], ["stock_transfers.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_transfer_items_stock_transfer_id", "stock_transfer_items", ["stock_transfer_id"], unique=False)
    op.create_index("ix_stock_transfer_items_variant_id", "stock_transfer_items", ["variant_id"], unique=False)

    op.create_table(
        "order_location_allocations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("allocated_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("allocated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["allocated_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_order_location_allocations_order_id"),
    )
    op.create_index("ix_order_location_allocations_business_id", "order_location_allocations", ["business_id"], unique=False)
    op.create_index("ix_order_location_allocations_order_id", "order_location_allocations", ["order_id"], unique=True)
    op.create_index("ix_order_location_allocations_location_id", "order_location_allocations", ["location_id"], unique=False)
    op.create_index(
        "ix_order_location_allocations_business_allocated_at",
        "order_location_allocations",
        ["business_id", "allocated_at"],
        unique=False,
    )

    op.create_table(
        "integration_secrets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("key_name", sa.String(length=80), nullable=False),
        sa.Column("secret_encrypted", sa.String(length=2048), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "provider", "key_name", name="uq_integration_secret_business_provider_key"),
    )
    op.create_index("ix_integration_secrets_business_id", "integration_secrets", ["business_id"], unique=False)

    op.create_table(
        "app_installations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("app_key", sa.String(length=60), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="connected"),
        sa.Column("permissions_json", sa.JSON(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "app_key", name="uq_app_installation_business_app_key"),
    )
    op.create_index("ix_app_installations_business_id", "app_installations", ["business_id"], unique=False)

    op.create_table(
        "integration_outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("target_app_key", sa.String(length=60), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_outbox_events_business_id", "integration_outbox_events", ["business_id"], unique=False)
    op.create_index("ix_integration_outbox_events_event_type", "integration_outbox_events", ["event_type"], unique=False)
    op.create_index("ix_integration_outbox_events_target_app_key", "integration_outbox_events", ["target_app_key"], unique=False)
    op.create_index(
        "ix_integration_outbox_events_business_status_next_attempt",
        "integration_outbox_events",
        ["business_id", "status", "next_attempt_at"],
        unique=False,
    )

    op.create_table(
        "integration_delivery_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("outbox_event_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["outbox_event_id"], ["integration_outbox_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_delivery_attempts_outbox_event_id", "integration_delivery_attempts", ["outbox_event_id"], unique=False)

    op.create_table(
        "outbound_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("recipient", sa.String(length=120), nullable=False),
        sa.Column("content", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("external_message_id", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbound_messages_business_id", "outbound_messages", ["business_id"], unique=False)
    op.create_index("ix_outbound_messages_provider", "outbound_messages", ["provider"], unique=False)
    op.create_index(
        "ix_outbound_messages_business_provider_created_at",
        "outbound_messages",
        ["business_id", "provider", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_outbound_messages_business_provider_created_at", table_name="outbound_messages")
    op.drop_index("ix_outbound_messages_provider", table_name="outbound_messages")
    op.drop_index("ix_outbound_messages_business_id", table_name="outbound_messages")
    op.drop_table("outbound_messages")

    op.drop_index("ix_integration_delivery_attempts_outbox_event_id", table_name="integration_delivery_attempts")
    op.drop_table("integration_delivery_attempts")

    op.drop_index("ix_integration_outbox_events_business_status_next_attempt", table_name="integration_outbox_events")
    op.drop_index("ix_integration_outbox_events_target_app_key", table_name="integration_outbox_events")
    op.drop_index("ix_integration_outbox_events_event_type", table_name="integration_outbox_events")
    op.drop_index("ix_integration_outbox_events_business_id", table_name="integration_outbox_events")
    op.drop_table("integration_outbox_events")

    op.drop_index("ix_app_installations_business_id", table_name="app_installations")
    op.drop_table("app_installations")

    op.drop_index("ix_integration_secrets_business_id", table_name="integration_secrets")
    op.drop_table("integration_secrets")

    op.drop_index("ix_order_location_allocations_business_allocated_at", table_name="order_location_allocations")
    op.drop_index("ix_order_location_allocations_location_id", table_name="order_location_allocations")
    op.drop_index("ix_order_location_allocations_order_id", table_name="order_location_allocations")
    op.drop_index("ix_order_location_allocations_business_id", table_name="order_location_allocations")
    op.drop_table("order_location_allocations")

    op.drop_index("ix_stock_transfer_items_variant_id", table_name="stock_transfer_items")
    op.drop_index("ix_stock_transfer_items_stock_transfer_id", table_name="stock_transfer_items")
    op.drop_table("stock_transfer_items")

    op.drop_index("ix_stock_transfers_business_created_at", table_name="stock_transfers")
    op.drop_index("ix_stock_transfers_created_by_user_id", table_name="stock_transfers")
    op.drop_index("ix_stock_transfers_to_location_id", table_name="stock_transfers")
    op.drop_index("ix_stock_transfers_from_location_id", table_name="stock_transfers")
    op.drop_index("ix_stock_transfers_business_id", table_name="stock_transfers")
    op.drop_table("stock_transfers")

    op.drop_index("ix_loc_inv_ledger_biz_loc_var_created_at", table_name="location_inventory_ledger")
    op.drop_index("ix_location_inventory_ledger_variant_id", table_name="location_inventory_ledger")
    op.drop_index("ix_location_inventory_ledger_location_id", table_name="location_inventory_ledger")
    op.drop_index("ix_location_inventory_ledger_business_id", table_name="location_inventory_ledger")
    op.drop_table("location_inventory_ledger")

    op.drop_index("ix_location_membership_scopes_membership_id", table_name="location_membership_scopes")
    op.drop_index("ix_location_membership_scopes_location_id", table_name="location_membership_scopes")
    op.drop_index("ix_location_membership_scopes_business_id", table_name="location_membership_scopes")
    op.drop_table("location_membership_scopes")

    op.drop_index("ix_locations_business_active_created_at", table_name="locations")
    op.drop_index("ix_locations_business_id", table_name="locations")
    op.drop_table("locations")

    op.drop_index("ix_shipment_tracking_events_shipment_event_time", table_name="shipment_tracking_events")
    op.drop_index("ix_shipment_tracking_events_shipment_id", table_name="shipment_tracking_events")
    op.drop_table("shipment_tracking_events")

    op.drop_index("ix_shipments_business_status_created_at", table_name="shipments")
    op.drop_index("ix_shipments_tracking_number", table_name="shipments")
    op.drop_index("ix_shipments_checkout_session_id", table_name="shipments")
    op.drop_index("ix_shipments_order_id", table_name="shipments")
    op.drop_index("ix_shipments_business_id", table_name="shipments")
    op.drop_table("shipments")

    op.drop_index("ix_checkout_shipping_selections_checkout_session_id", table_name="checkout_shipping_selections")
    op.drop_table("checkout_shipping_selections")

    op.drop_index("ix_shipping_service_rules_profile_zone_provider", table_name="shipping_service_rules")
    op.drop_index("ix_shipping_service_rules_zone_id", table_name="shipping_service_rules")
    op.drop_index("ix_shipping_service_rules_profile_id", table_name="shipping_service_rules")
    op.drop_table("shipping_service_rules")

    op.drop_index("ix_shipping_zones_profile_country_active", table_name="shipping_zones")
    op.drop_index("ix_shipping_zones_profile_id", table_name="shipping_zones")
    op.drop_table("shipping_zones")

    op.drop_index("ix_shipping_profiles_business_id", table_name="shipping_profiles")
    op.drop_table("shipping_profiles")
