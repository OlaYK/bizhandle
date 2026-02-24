"""add checkout webhook events

Revision ID: 20260222_0013
Revises: 20260222_0012
Create Date: 2026-02-22 19:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_0013"
down_revision: Union[str, None] = "20260222_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "checkout_webhook_events"):
        op.create_table(
            "checkout_webhook_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("checkout_session_id", sa.String(length=36), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False),
            sa.Column("event_id", sa.String(length=120), nullable=False),
            sa.Column("event_type", sa.String(length=60), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["checkout_session_id"], ["checkout_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_id", name="uq_checkout_webhook_events_event_id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "checkout_webhook_events"):
        if not _index_exists(inspector, "checkout_webhook_events", "ix_checkout_webhook_events_checkout_session_id"):
            op.create_index(
                "ix_checkout_webhook_events_checkout_session_id",
                "checkout_webhook_events",
                ["checkout_session_id"],
                unique=False,
            )
        if not _index_exists(inspector, "checkout_webhook_events", "ix_checkout_webhook_events_provider"):
            op.create_index(
                "ix_checkout_webhook_events_provider",
                "checkout_webhook_events",
                ["provider"],
                unique=False,
            )
        if not _index_exists(inspector, "checkout_webhook_events", "ix_checkout_webhook_events_event_id"):
            op.create_index(
                "ix_checkout_webhook_events_event_id",
                "checkout_webhook_events",
                ["event_id"],
                unique=True,
            )
        if not _index_exists(inspector, "checkout_webhook_events", "ix_checkout_webhook_events_checkout_provider"):
            op.create_index(
                "ix_checkout_webhook_events_checkout_provider",
                "checkout_webhook_events",
                ["checkout_session_id", "provider"],
                unique=False,
            )
        if not _index_exists(inspector, "checkout_webhook_events", "ix_checkout_webhook_events_provider_created_at"):
            op.create_index(
                "ix_checkout_webhook_events_provider_created_at",
                "checkout_webhook_events",
                ["provider", "created_at"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "checkout_webhook_events"):
        if _index_exists(inspector, "checkout_webhook_events", "ix_checkout_webhook_events_provider_created_at"):
            op.drop_index("ix_checkout_webhook_events_provider_created_at", table_name="checkout_webhook_events")
        if _index_exists(inspector, "checkout_webhook_events", "ix_checkout_webhook_events_checkout_provider"):
            op.drop_index("ix_checkout_webhook_events_checkout_provider", table_name="checkout_webhook_events")
        if _index_exists(inspector, "checkout_webhook_events", "ix_checkout_webhook_events_event_id"):
            op.drop_index("ix_checkout_webhook_events_event_id", table_name="checkout_webhook_events")
        if _index_exists(inspector, "checkout_webhook_events", "ix_checkout_webhook_events_provider"):
            op.drop_index("ix_checkout_webhook_events_provider", table_name="checkout_webhook_events")
        if _index_exists(inspector, "checkout_webhook_events", "ix_checkout_webhook_events_checkout_session_id"):
            op.drop_index("ix_checkout_webhook_events_checkout_session_id", table_name="checkout_webhook_events")
        op.drop_table("checkout_webhook_events")
