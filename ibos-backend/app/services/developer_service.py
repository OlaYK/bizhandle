import fnmatch
import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.developer import (
    PublicApiKey,
    WebhookDeliveryAttempt,
    WebhookEventDelivery,
    WebhookSubscription,
)
from app.models.integration import IntegrationOutboxEvent
from app.services.integration_service import decrypt_secret, encrypt_secret

PUBLIC_API_SCOPE_CATALOG: dict[str, str] = {
    "business:read": "Read business profile metadata.",
    "products:read": "Read product catalog records.",
    "orders:read": "Read order records.",
    "customers:read": "Read customer records.",
    "webhooks:manage": "Create and manage outbound webhook subscriptions.",
    "marketplace:manage": "Create and manage marketplace listing submissions.",
}

DEFAULT_PUBLIC_API_SCOPES: list[str] = [
    "business:read",
    "products:read",
    "orders:read",
    "customers:read",
]


@dataclass(frozen=True)
class PublicApiPrincipal:
    key_id: str
    business_id: str
    key_name: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class WebhookDispatchSummary:
    enqueued: int
    processed: int
    delivered: int
    failed: int
    dead_lettered: int


def normalize_scopes(scopes: list[str] | None) -> list[str]:
    values = {item.strip().lower() for item in (scopes or []) if item.strip()}
    if not values:
        return list(DEFAULT_PUBLIC_API_SCOPES)
    return sorted(values)


def validate_scope_keys(scopes: list[str]) -> None:
    unknown = [scope for scope in scopes if scope not in PUBLIC_API_SCOPE_CATALOG and scope != "*"]
    if unknown:
        raise ValueError(f"Unknown scope(s): {', '.join(sorted(unknown))}")


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key_material() -> tuple[str, str, str]:
    token = secrets.token_urlsafe(32).replace("-", "x").replace("_", "y")
    api_key = f"mdk_live_{token}"
    key_prefix = api_key[:20]
    key_hash = hash_api_key(api_key)
    return api_key, key_prefix, key_hash


def has_scope(scopes: list[str] | tuple[str, ...], required_scope: str) -> bool:
    if "*" in scopes:
        return True
    if required_scope in scopes:
        return True
    for scope in scopes:
        if scope.endswith(":*"):
            prefix = scope[:-1]
            if required_scope.startswith(prefix):
                return True
    return False


def resolve_public_api_principal(db: Session, *, api_key: str) -> PublicApiPrincipal | None:
    key_hash = hash_api_key(api_key)
    row = db.execute(
        select(PublicApiKey).where(
            PublicApiKey.key_hash == key_hash,
            PublicApiKey.status == "active",
        )
    ).scalar_one_or_none()
    if not row:
        return None

    now = datetime.now(timezone.utc)
    if row.expires_at and row.expires_at < now:
        return None

    row.last_used_at = now
    scopes = tuple(normalize_scopes(row.scopes_json or []))
    return PublicApiPrincipal(
        key_id=row.id,
        business_id=row.business_id,
        key_name=row.name,
        scopes=scopes,
    )


def generate_webhook_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(32)}"


def encrypt_webhook_secret(secret_value: str) -> str:
    return encrypt_secret(secret_value)


def decrypt_webhook_secret(secret_value_encrypted: str) -> str:
    return decrypt_secret(secret_value_encrypted)


def _matches_event_pattern(event_type: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    for pattern in patterns:
        candidate = (pattern or "").strip()
        if not candidate:
            continue
        if candidate == "*":
            return True
        if fnmatch.fnmatch(event_type, candidate):
            return True
    return False


def _simulate_webhook_post(
    *,
    endpoint_url: str,
    payload_bytes: bytes,
    signature: str,
) -> tuple[int, str]:
    normalized = endpoint_url.strip().lower()
    if not (normalized.startswith("https://") or normalized.startswith("http://")):
        return 400, "Endpoint URL must start with http:// or https://"
    if "reject" in normalized or "fail" in normalized:
        return 503, "Simulated upstream rejection"
    if not payload_bytes:
        return 400, "Empty payload"
    if not signature.startswith("sha256="):
        return 400, "Invalid signature header"
    return 202, "Accepted (simulated)"


def build_webhook_signature(*, signing_secret: str, payload_bytes: bytes) -> str:
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def enqueue_webhook_deliveries(
    db: Session,
    *,
    business_id: str,
    subscription_id: str | None = None,
    event_limit: int = 400,
) -> int:
    sub_stmt = select(WebhookSubscription).where(
        WebhookSubscription.business_id == business_id,
        WebhookSubscription.status == "active",
    )
    if subscription_id:
        sub_stmt = sub_stmt.where(WebhookSubscription.id == subscription_id)
    subscriptions = db.execute(sub_stmt).scalars().all()
    if not subscriptions:
        return 0

    outbox_rows = db.execute(
        select(IntegrationOutboxEvent)
        .where(IntegrationOutboxEvent.business_id == business_id)
        .order_by(IntegrationOutboxEvent.created_at.desc())
        .limit(event_limit)
    ).scalars().all()
    if not outbox_rows:
        return 0

    subscription_ids = [item.id for item in subscriptions]
    outbox_ids = [item.id for item in outbox_rows]
    existing_pairs = db.execute(
        select(WebhookEventDelivery.subscription_id, WebhookEventDelivery.outbox_event_id).where(
            WebhookEventDelivery.subscription_id.in_(subscription_ids),
            WebhookEventDelivery.outbox_event_id.in_(outbox_ids),
        )
    ).all()
    existing_lookup = {(row[0], row[1]) for row in existing_pairs}

    now = datetime.now(timezone.utc)
    created = 0
    for subscription in subscriptions:
        patterns = subscription.events_json or ["*"]
        for event in outbox_rows:
            pair = (subscription.id, event.id)
            if pair in existing_lookup:
                continue
            if not _matches_event_pattern(event.event_type, patterns):
                continue
            db.add(
                WebhookEventDelivery(
                    id=str(uuid.uuid4()),
                    business_id=business_id,
                    subscription_id=subscription.id,
                    outbox_event_id=event.id,
                    event_type=event.event_type,
                    payload_json=event.payload_json or {},
                    status="pending",
                    attempt_count=0,
                    max_attempts=subscription.max_attempts,
                    next_attempt_at=now,
                    last_error=None,
                )
            )
            created += 1
            existing_lookup.add(pair)
    return created


def dispatch_due_webhook_deliveries(
    db: Session,
    *,
    business_id: str,
    limit: int = 100,
    subscription_id: str | None = None,
) -> WebhookDispatchSummary:
    enqueued = enqueue_webhook_deliveries(
        db,
        business_id=business_id,
        subscription_id=subscription_id,
        event_limit=max(limit * 4, 100),
    )
    if enqueued:
        db.flush()
    now = datetime.now(timezone.utc)
    stmt = select(WebhookEventDelivery).where(
        and_(
            WebhookEventDelivery.business_id == business_id,
            WebhookEventDelivery.status.in_(["pending", "failed"]),
        )
    )
    if subscription_id:
        stmt = stmt.where(WebhookEventDelivery.subscription_id == subscription_id)

    deliveries = db.execute(
        stmt.order_by(WebhookEventDelivery.created_at.asc()).limit(limit)
    ).scalars().all()
    if not deliveries:
        return WebhookDispatchSummary(
            enqueued=enqueued,
            processed=0,
            delivered=0,
            failed=0,
            dead_lettered=0,
        )

    subscription_ids = sorted({item.subscription_id for item in deliveries})
    subscriptions = db.execute(
        select(WebhookSubscription).where(WebhookSubscription.id.in_(subscription_ids))
    ).scalars().all()
    subscription_by_id = {item.id: item for item in subscriptions}

    processed = 0
    delivered = 0
    failed = 0
    dead_lettered = 0
    for delivery in deliveries:
        processed += 1
        subscription = subscription_by_id.get(delivery.subscription_id)
        delivery.attempt_count += 1
        signature_header = None

        if not subscription or subscription.status != "active":
            response_code = 410
            response_body = "Subscription inactive or missing"
        else:
            payload = {
                "delivery_id": delivery.id,
                "outbox_event_id": delivery.outbox_event_id,
                "event_type": delivery.event_type,
                "occurred_at": delivery.created_at.isoformat(),
                "data": delivery.payload_json or {},
            }
            payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            secret = decrypt_webhook_secret(subscription.secret_encrypted)
            signature_header = build_webhook_signature(
                signing_secret=secret,
                payload_bytes=payload_bytes,
            )
            response_code, response_body = _simulate_webhook_post(
                endpoint_url=subscription.endpoint_url,
                payload_bytes=payload_bytes,
                signature=signature_header,
            )

        if 200 <= response_code < 300:
            delivery.status = "delivered"
            delivery.last_error = None
            delivery.last_response_code = response_code
            delivery.delivered_at = now
            if subscription:
                subscription.last_delivery_at = now
            delivered += 1
            attempt_status = "delivered"
        else:
            delivery.last_error = response_body[:255]
            delivery.last_response_code = response_code
            if delivery.attempt_count >= delivery.max_attempts:
                delivery.status = "dead_letter"
                dead_lettered += 1
                attempt_status = "dead_letter"
            else:
                retry_seconds = subscription.retry_seconds if subscription else 300
                delivery.status = "failed"
                delivery.next_attempt_at = now + timedelta(seconds=retry_seconds)
                failed += 1
                attempt_status = "failed"

        db.add(
            WebhookDeliveryAttempt(
                id=str(uuid.uuid4()),
                webhook_delivery_id=delivery.id,
                attempt_number=delivery.attempt_count,
                status=attempt_status,
                response_code=response_code,
                response_body=response_body[:500],
                signature=signature_header,
            )
        )

    return WebhookDispatchSummary(
        enqueued=enqueued,
        processed=processed,
        delivered=delivered,
        failed=failed,
        dead_lettered=dead_lettered,
    )
