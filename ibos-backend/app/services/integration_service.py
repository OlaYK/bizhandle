import base64
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.integration import (
    AppInstallation,
    IntegrationDeliveryAttempt,
    IntegrationOutboxEvent,
)


def _cipher_key() -> bytes:
    return hashlib.sha256(settings.secret_key.encode("utf-8")).digest()


def encrypt_secret(plain_text: str) -> str:
    key = _cipher_key()
    raw = plain_text.encode("utf-8")
    encrypted = bytes(value ^ key[idx % len(key)] for idx, value in enumerate(raw))
    return base64.urlsafe_b64encode(encrypted).decode("ascii")


def decrypt_secret(cipher_text: str) -> str:
    key = _cipher_key()
    encrypted = base64.urlsafe_b64decode(cipher_text.encode("ascii"))
    raw = bytes(value ^ key[idx % len(key)] for idx, value in enumerate(encrypted))
    return raw.decode("utf-8")


def queue_outbox_event(
    db: Session,
    *,
    business_id: str,
    event_type: str,
    target_app_key: str,
    payload_json: dict[str, Any] | None = None,
    max_attempts: int | None = None,
) -> IntegrationOutboxEvent:
    event = IntegrationOutboxEvent(
        id=str(uuid.uuid4()),
        business_id=business_id,
        event_type=event_type,
        target_app_key=target_app_key,
        payload_json=payload_json,
        status="pending",
        attempt_count=0,
        max_attempts=max_attempts or settings.integration_outbox_max_attempts,
        next_attempt_at=datetime.now(timezone.utc),
        last_error=None,
    )
    db.add(event)
    return event


@dataclass(frozen=True)
class DispatchSummary:
    processed: int
    delivered: int
    failed: int
    dead_lettered: int


def _is_installation_connected(
    db: Session,
    *,
    business_id: str,
    app_key: str,
) -> bool:
    installation = db.execute(
        select(AppInstallation).where(
            AppInstallation.business_id == business_id,
            AppInstallation.app_key == app_key,
            AppInstallation.status == "connected",
        )
    ).scalar_one_or_none()
    return installation is not None


def dispatch_due_outbox_events(db: Session, *, business_id: str | None = None, limit: int = 100) -> DispatchSummary:
    now = datetime.now(timezone.utc)
    stmt = select(IntegrationOutboxEvent).where(
        and_(
            IntegrationOutboxEvent.status.in_(["pending", "failed"]),
            IntegrationOutboxEvent.next_attempt_at <= now,
        )
    )
    if business_id:
        stmt = stmt.where(IntegrationOutboxEvent.business_id == business_id)

    events = db.execute(stmt.order_by(IntegrationOutboxEvent.created_at.asc()).limit(limit)).scalars().all()
    processed = 0
    delivered = 0
    failed = 0
    dead_lettered = 0

    for event in events:
        processed += 1
        event.attempt_count += 1

        connected = _is_installation_connected(
            db,
            business_id=event.business_id,
            app_key=event.target_app_key,
        )
        if connected:
            event.status = "delivered"
            event.last_error = None
            delivered += 1
            db.add(
                IntegrationDeliveryAttempt(
                    id=str(uuid.uuid4()),
                    outbox_event_id=event.id,
                    attempt_number=event.attempt_count,
                    status="delivered",
                    response_code=200,
                    response_body="ok",
                )
            )
            continue

        error_message = f"App '{event.target_app_key}' not connected"
        event.last_error = error_message
        if event.attempt_count >= event.max_attempts:
            event.status = "dead_letter"
            dead_lettered += 1
            delivery_status = "dead_letter"
        else:
            event.status = "failed"
            event.next_attempt_at = now + timedelta(seconds=settings.integration_outbox_retry_seconds)
            failed += 1
            delivery_status = "failed"

        db.add(
            IntegrationDeliveryAttempt(
                id=str(uuid.uuid4()),
                outbox_event_id=event.id,
                attempt_number=event.attempt_count,
                status=delivery_status,
                response_code=503,
                response_body=error_message,
            )
        )

    return DispatchSummary(
        processed=processed,
        delivered=delivered,
        failed=failed,
        dead_lettered=dead_lettered,
    )
