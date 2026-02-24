import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.business import Business
from app.models.customer import Customer
from app.models.developer import (
    MarketplaceAppListing,
    PublicApiKey,
    WebhookEventDelivery,
    WebhookSubscription,
)
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.schemas.common import PaginationMeta
from app.schemas.developer import (
    DeveloperPortalDocOut,
    DeveloperPortalDocsOut,
    MarketplaceListingCreateIn,
    MarketplaceListingListOut,
    MarketplaceListingOut,
    MarketplaceListingPublishIn,
    MarketplaceListingReviewIn,
    PublicApiBusinessOut,
    PublicApiCustomerListOut,
    PublicApiCustomerOut,
    PublicApiKeyCreateIn,
    PublicApiKeyCreateOut,
    PublicApiKeyListOut,
    PublicApiKeyOut,
    PublicApiKeyRotateOut,
    PublicApiOrderListOut,
    PublicApiOrderOut,
    PublicApiProductListOut,
    PublicApiProductOut,
    PublicApiScopeCatalogOut,
    PublicApiScopeOut,
    WebhookDeliveryListOut,
    WebhookDeliveryOut,
    WebhookDispatchOut,
    WebhookSubscriptionCreateIn,
    WebhookSubscriptionCreateOut,
    WebhookSubscriptionListOut,
    WebhookSubscriptionOut,
    WebhookSubscriptionRotateSecretOut,
    WebhookSubscriptionUpdateIn,
)
from app.services.audit_service import log_audit_event
from app.services.developer_service import (
    PUBLIC_API_SCOPE_CATALOG,
    dispatch_due_webhook_deliveries,
    encrypt_webhook_secret,
    generate_api_key_material,
    generate_webhook_secret,
    has_scope,
    normalize_scopes,
    resolve_public_api_principal,
    validate_scope_keys,
)

router = APIRouter(prefix="/developer", tags=["developer"])
public_router = APIRouter(prefix="/public/v1", tags=["developer"])


def _key_out(item: PublicApiKey) -> PublicApiKeyOut:
    return PublicApiKeyOut(
        id=item.id,
        name=item.name,
        key_prefix=item.key_prefix,
        scopes=normalize_scopes(item.scopes_json or []),
        status=item.status,
        version=item.version,
        last_used_at=item.last_used_at,
        expires_at=item.expires_at,
        rotated_at=item.rotated_at,
        revoked_at=item.revoked_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _subscription_out(item: WebhookSubscription) -> WebhookSubscriptionOut:
    return WebhookSubscriptionOut(
        id=item.id,
        name=item.name,
        endpoint_url=item.endpoint_url,
        description=item.description,
        events=item.events_json or ["*"],
        status=item.status,
        max_attempts=item.max_attempts,
        retry_seconds=item.retry_seconds,
        secret_hint=f"{item.secret_encrypted[:4]}...{item.secret_encrypted[-4:]}",
        last_delivery_at=item.last_delivery_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _delivery_out(item: WebhookEventDelivery) -> WebhookDeliveryOut:
    return WebhookDeliveryOut(
        id=item.id,
        subscription_id=item.subscription_id,
        outbox_event_id=item.outbox_event_id,
        event_type=item.event_type,
        status=item.status,
        attempt_count=item.attempt_count,
        max_attempts=item.max_attempts,
        next_attempt_at=item.next_attempt_at,
        last_error=item.last_error,
        last_response_code=item.last_response_code,
        delivered_at=item.delivered_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _marketplace_listing_out(item: MarketplaceAppListing) -> MarketplaceListingOut:
    return MarketplaceListingOut(
        id=item.id,
        app_key=item.app_key,
        display_name=item.display_name,
        description=item.description,
        category=item.category,
        requested_scopes=item.requested_scopes_json or [],
        status=item.status,
        review_notes=item.review_notes,
        submitted_at=item.submitted_at,
        reviewed_at=item.reviewed_at,
        published_at=item.published_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _normalize_event_patterns(events: list[str] | None) -> list[str]:
    values = sorted({item.strip() for item in (events or ["*"]) if item.strip()})
    if not values:
        return ["*"]
    return values


def _require_public_scope(required_scope: str):
    def dependency(
        x_api_key: str | None = Header(default=None, alias="X-Monidesk-Api-Key"),
        db: Session = Depends(get_db),
    ):
        if not x_api_key or not x_api_key.strip():
            raise HTTPException(status_code=401, detail="Missing API key")

        principal = resolve_public_api_principal(db, api_key=x_api_key.strip())
        if not principal:
            raise HTTPException(status_code=401, detail="Invalid API key")

        if not has_scope(list(principal.scopes), required_scope):
            raise HTTPException(status_code=403, detail="Insufficient API key scope")

        db.commit()
        return principal

    return dependency


@router.get(
    "/api/scopes",
    response_model=PublicApiScopeCatalogOut,
    summary="List supported public API scopes",
    responses=error_responses(401, 403, 500),
)
def list_scope_catalog(
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    _ = access
    return PublicApiScopeCatalogOut(
        items=[
            PublicApiScopeOut(scope=scope, description=description)
            for scope, description in sorted(PUBLIC_API_SCOPE_CATALOG.items())
        ]
    )


@router.post(
    "/api-keys",
    response_model=PublicApiKeyCreateOut,
    summary="Create public API key",
    responses=error_responses(400, 401, 403, 409, 422, 500),
)
def create_public_api_key(
    payload: PublicApiKeyCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    scopes = normalize_scopes(payload.scopes)
    try:
        validate_scope_keys(scopes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = db.execute(
        select(PublicApiKey.id).where(
            PublicApiKey.business_id == access.business.id,
            func.lower(PublicApiKey.name) == payload.name.strip().lower(),
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="API key name already exists")

    raw_key, key_prefix, key_hash = generate_api_key_material()
    row = PublicApiKey(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        name=payload.name.strip(),
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes_json=scopes,
        status="active",
        version=1,
        expires_at=payload.expires_at,
        created_by_user_id=actor.id,
    )
    db.add(row)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.api_key.create",
        target_type="public_api_key",
        target_id=row.id,
        metadata_json={
            "name": row.name,
            "scopes": scopes,
            "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
        },
    )
    db.commit()
    db.refresh(row)
    return PublicApiKeyCreateOut(**_key_out(row).model_dump(), api_key=raw_key)


@router.get(
    "/api-keys",
    response_model=PublicApiKeyListOut,
    summary="List public API keys metadata",
    responses=error_responses(401, 403, 500),
)
def list_public_api_keys(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    rows = db.execute(
        select(PublicApiKey)
        .where(PublicApiKey.business_id == access.business.id)
        .order_by(PublicApiKey.updated_at.desc())
    ).scalars().all()
    return PublicApiKeyListOut(items=[_key_out(item) for item in rows])


@router.post(
    "/api-keys/{api_key_id}/rotate",
    response_model=PublicApiKeyRotateOut,
    summary="Rotate public API key",
    responses=error_responses(401, 403, 404, 500),
)
def rotate_public_api_key(
    api_key_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    row = db.execute(
        select(PublicApiKey).where(
            PublicApiKey.id == api_key_id,
            PublicApiKey.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    raw_key, key_prefix, key_hash = generate_api_key_material()
    now = datetime.now(timezone.utc)
    row.key_prefix = key_prefix
    row.key_hash = key_hash
    row.status = "active"
    row.version += 1
    row.rotated_at = now
    row.rotated_by_user_id = actor.id
    row.revoked_at = None
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.api_key.rotate",
        target_type="public_api_key",
        target_id=row.id,
        metadata_json={"name": row.name, "version": row.version},
    )
    db.commit()
    db.refresh(row)
    return PublicApiKeyRotateOut(**_key_out(row).model_dump(), api_key=raw_key)


@router.post(
    "/api-keys/{api_key_id}/revoke",
    response_model=PublicApiKeyOut,
    summary="Revoke public API key",
    responses=error_responses(401, 403, 404, 500),
)
def revoke_public_api_key(
    api_key_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    row = db.execute(
        select(PublicApiKey).where(
            PublicApiKey.id == api_key_id,
            PublicApiKey.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    row.status = "revoked"
    row.revoked_at = datetime.now(timezone.utc)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.api_key.revoke",
        target_type="public_api_key",
        target_id=row.id,
        metadata_json={"name": row.name, "version": row.version},
    )
    db.commit()
    db.refresh(row)
    return _key_out(row)


@router.post(
    "/webhooks/subscriptions",
    response_model=WebhookSubscriptionCreateOut,
    summary="Create webhook subscription",
    responses=error_responses(400, 401, 403, 409, 422, 500),
)
def create_webhook_subscription(
    payload: WebhookSubscriptionCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    endpoint_url = payload.endpoint_url.strip()
    if not (endpoint_url.startswith("http://") or endpoint_url.startswith("https://")):
        raise HTTPException(status_code=400, detail="endpoint_url must start with http:// or https://")

    existing = db.execute(
        select(WebhookSubscription.id).where(
            WebhookSubscription.business_id == access.business.id,
            func.lower(WebhookSubscription.name) == payload.name.strip().lower(),
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Webhook subscription name already exists")

    signing_secret = generate_webhook_secret()
    row = WebhookSubscription(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        name=payload.name.strip(),
        endpoint_url=endpoint_url,
        description=payload.description.strip() if payload.description else None,
        events_json=_normalize_event_patterns(payload.events),
        secret_encrypted=encrypt_webhook_secret(signing_secret),
        status="active",
        max_attempts=payload.max_attempts,
        retry_seconds=payload.retry_seconds,
        created_by_user_id=actor.id,
    )
    db.add(row)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.webhook_subscription.create",
        target_type="webhook_subscription",
        target_id=row.id,
        metadata_json={"name": row.name, "events": row.events_json},
    )
    db.commit()
    db.refresh(row)
    return WebhookSubscriptionCreateOut(
        **_subscription_out(row).model_dump(),
        signing_secret=signing_secret,
    )


@router.get(
    "/webhooks/subscriptions",
    response_model=WebhookSubscriptionListOut,
    summary="List webhook subscriptions",
    responses=error_responses(401, 403, 500),
)
def list_webhook_subscriptions(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    rows = db.execute(
        select(WebhookSubscription)
        .where(WebhookSubscription.business_id == access.business.id)
        .order_by(WebhookSubscription.updated_at.desc())
    ).scalars().all()
    return WebhookSubscriptionListOut(items=[_subscription_out(row) for row in rows])


@router.patch(
    "/webhooks/subscriptions/{subscription_id}",
    response_model=WebhookSubscriptionOut,
    summary="Update webhook subscription",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def update_webhook_subscription(
    subscription_id: str,
    payload: WebhookSubscriptionUpdateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    row = db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == subscription_id,
            WebhookSubscription.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")

    if payload.endpoint_url is not None:
        endpoint_url = payload.endpoint_url.strip()
        if not (endpoint_url.startswith("http://") or endpoint_url.startswith("https://")):
            raise HTTPException(status_code=400, detail="endpoint_url must start with http:// or https://")
        row.endpoint_url = endpoint_url
    if payload.description is not None:
        row.description = payload.description.strip() or None
    if payload.events is not None:
        row.events_json = _normalize_event_patterns(payload.events)
    if payload.status is not None:
        row.status = payload.status
    if payload.max_attempts is not None:
        row.max_attempts = payload.max_attempts
    if payload.retry_seconds is not None:
        row.retry_seconds = payload.retry_seconds
    row.updated_by_user_id = actor.id

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.webhook_subscription.update",
        target_type="webhook_subscription",
        target_id=row.id,
        metadata_json={"status": row.status, "events": row.events_json},
    )
    db.commit()
    db.refresh(row)
    return _subscription_out(row)


@router.post(
    "/webhooks/subscriptions/{subscription_id}/rotate-secret",
    response_model=WebhookSubscriptionRotateSecretOut,
    summary="Rotate webhook signing secret",
    responses=error_responses(401, 403, 404, 500),
)
def rotate_webhook_secret(
    subscription_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    row = db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == subscription_id,
            WebhookSubscription.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")

    signing_secret = generate_webhook_secret()
    row.secret_encrypted = encrypt_webhook_secret(signing_secret)
    row.updated_by_user_id = actor.id
    rotated_at = datetime.now(timezone.utc)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.webhook_subscription.rotate_secret",
        target_type="webhook_subscription",
        target_id=row.id,
        metadata_json={"name": row.name},
    )
    db.commit()
    return WebhookSubscriptionRotateSecretOut(
        subscription_id=row.id,
        signing_secret=signing_secret,
        rotated_at=rotated_at,
    )


@router.get(
    "/webhooks/deliveries",
    response_model=WebhookDeliveryListOut,
    summary="List webhook deliveries",
    responses=error_responses(401, 403, 422, 500),
)
def list_webhook_deliveries(
    subscription_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(WebhookEventDelivery.id)).where(
        WebhookEventDelivery.business_id == access.business.id
    )
    stmt = select(WebhookEventDelivery).where(WebhookEventDelivery.business_id == access.business.id)
    normalized_status = None
    if subscription_id:
        count_stmt = count_stmt.where(WebhookEventDelivery.subscription_id == subscription_id)
        stmt = stmt.where(WebhookEventDelivery.subscription_id == subscription_id)
    if status:
        normalized_status = status.strip().lower()
        count_stmt = count_stmt.where(WebhookEventDelivery.status == normalized_status)
        stmt = stmt.where(WebhookEventDelivery.status == normalized_status)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(WebhookEventDelivery.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [_delivery_out(row) for row in rows]
    count = len(items)
    return WebhookDeliveryListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        subscription_id=subscription_id,
        status=normalized_status,  # type: ignore[arg-type]
    )


@router.post(
    "/webhooks/deliveries/dispatch",
    response_model=WebhookDispatchOut,
    summary="Dispatch pending webhook deliveries",
    responses=error_responses(401, 403, 422, 500),
)
def dispatch_webhook_deliveries(
    limit: int = Query(default=100, ge=1, le=1000),
    subscription_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    summary = dispatch_due_webhook_deliveries(
        db,
        business_id=access.business.id,
        limit=limit,
        subscription_id=subscription_id,
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.webhook_dispatch.run",
        target_type="webhook_delivery",
        target_id=subscription_id,
        metadata_json={
            "limit": limit,
            "enqueued": summary.enqueued,
            "processed": summary.processed,
            "delivered": summary.delivered,
            "failed": summary.failed,
            "dead_lettered": summary.dead_lettered,
        },
    )
    db.commit()
    return WebhookDispatchOut(
        enqueued=summary.enqueued,
        processed=summary.processed,
        delivered=summary.delivered,
        failed=summary.failed,
        dead_lettered=summary.dead_lettered,
    )


@router.get(
    "/portal/docs",
    response_model=DeveloperPortalDocsOut,
    summary="List developer portal docs and quickstarts",
    responses=error_responses(401, 403, 500),
)
def list_developer_portal_docs(
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    _ = access
    return DeveloperPortalDocsOut(
        items=[
            DeveloperPortalDocOut(
                section="api",
                title="Public API v1 Scope and Auth Model",
                summary="Authentication strategy, scope matrix, and tenancy guarantees.",
                relative_path="docs/developer/public-api-v1-scope-and-auth.md",
            ),
            DeveloperPortalDocOut(
                section="portal",
                title="Developer Portal Guide",
                summary="API key lifecycle, webhook subscriptions, and delivery observability.",
                relative_path="docs/developer/developer-portal-guide.md",
            ),
            DeveloperPortalDocOut(
                section="sdk",
                title="Node SDK Quickstart",
                summary="Install SDK starter, authenticate with API key, and list products.",
                relative_path="docs/sdk/node-quickstart.md",
            ),
            DeveloperPortalDocOut(
                section="sdk",
                title="Python SDK Quickstart",
                summary="Create client, call public endpoints, and verify webhook signature.",
                relative_path="docs/sdk/python-quickstart.md",
            ),
            DeveloperPortalDocOut(
                section="marketplace",
                title="Marketplace Governance Workflow",
                summary="Submission, review, approval, and publication process for partner apps.",
                relative_path="docs/developer/marketplace-governance-workflow.md",
            ),
        ],
        generated_at=datetime.now(timezone.utc),
    )


@router.post(
    "/marketplace/apps",
    response_model=MarketplaceListingOut,
    summary="Create marketplace listing draft",
    responses=error_responses(401, 403, 409, 422, 500),
)
def create_marketplace_listing(
    payload: MarketplaceListingCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    existing = db.execute(
        select(MarketplaceAppListing.id).where(
            MarketplaceAppListing.business_id == access.business.id,
            func.lower(MarketplaceAppListing.app_key) == payload.app_key.strip().lower(),
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Marketplace app key already exists")

    requested_scopes = normalize_scopes(payload.requested_scopes)
    try:
        validate_scope_keys(requested_scopes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row = MarketplaceAppListing(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        app_key=payload.app_key.strip().lower(),
        display_name=payload.display_name.strip(),
        description=payload.description.strip(),
        category=payload.category.strip().lower(),
        requested_scopes_json=requested_scopes,
        status="draft",
        created_by_user_id=actor.id,
    )
    db.add(row)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.marketplace_listing.create",
        target_type="marketplace_listing",
        target_id=row.id,
        metadata_json={"app_key": row.app_key, "status": row.status},
    )
    db.commit()
    db.refresh(row)
    return _marketplace_listing_out(row)


@router.get(
    "/marketplace/apps",
    response_model=MarketplaceListingListOut,
    summary="List marketplace listings",
    responses=error_responses(401, 403, 422, 500),
)
def list_marketplace_listings(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(MarketplaceAppListing.id)).where(
        MarketplaceAppListing.business_id == access.business.id
    )
    stmt = select(MarketplaceAppListing).where(MarketplaceAppListing.business_id == access.business.id)
    normalized_status = None
    if status:
        normalized_status = status.strip().lower()
        count_stmt = count_stmt.where(MarketplaceAppListing.status == normalized_status)
        stmt = stmt.where(MarketplaceAppListing.status == normalized_status)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(MarketplaceAppListing.updated_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [_marketplace_listing_out(row) for row in rows]
    count = len(items)
    return MarketplaceListingListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        status=normalized_status,  # type: ignore[arg-type]
    )


@router.post(
    "/marketplace/apps/{listing_id}/submit",
    response_model=MarketplaceListingOut,
    summary="Submit marketplace listing for review",
    responses=error_responses(400, 401, 403, 404, 500),
)
def submit_marketplace_listing(
    listing_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    row = db.execute(
        select(MarketplaceAppListing).where(
            MarketplaceAppListing.id == listing_id,
            MarketplaceAppListing.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Marketplace listing not found")
    if row.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Listing can only be submitted from draft or rejected status")

    row.status = "submitted"
    row.submitted_at = datetime.now(timezone.utc)
    row.updated_by_user_id = actor.id
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.marketplace_listing.submit",
        target_type="marketplace_listing",
        target_id=row.id,
        metadata_json={"app_key": row.app_key, "status": row.status},
    )
    db.commit()
    db.refresh(row)
    return _marketplace_listing_out(row)


@router.post(
    "/marketplace/apps/{listing_id}/review",
    response_model=MarketplaceListingOut,
    summary="Review marketplace listing",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def review_marketplace_listing(
    listing_id: str,
    payload: MarketplaceListingReviewIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    row = db.execute(
        select(MarketplaceAppListing).where(
            MarketplaceAppListing.id == listing_id,
            MarketplaceAppListing.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Marketplace listing not found")
    if row.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=400, detail="Listing is not in a reviewable state")

    row.status = payload.decision
    row.review_notes = payload.review_notes.strip() if payload.review_notes else None
    row.reviewed_by_user_id = actor.id
    row.reviewed_at = datetime.now(timezone.utc)
    row.updated_by_user_id = actor.id
    if payload.decision != "approved":
        row.published_at = None

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.marketplace_listing.review",
        target_type="marketplace_listing",
        target_id=row.id,
        metadata_json={"decision": payload.decision, "notes": row.review_notes},
    )
    db.commit()
    db.refresh(row)
    return _marketplace_listing_out(row)


@router.post(
    "/marketplace/apps/{listing_id}/publish",
    response_model=MarketplaceListingOut,
    summary="Publish or unpublish marketplace listing",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def publish_marketplace_listing(
    listing_id: str,
    payload: MarketplaceListingPublishIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    row = db.execute(
        select(MarketplaceAppListing).where(
            MarketplaceAppListing.id == listing_id,
            MarketplaceAppListing.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Marketplace listing not found")

    if payload.publish:
        if row.status != "approved":
            raise HTTPException(status_code=400, detail="Only approved listings can be published")
        row.status = "published"
        row.published_at = datetime.now(timezone.utc)
    else:
        if row.status != "published":
            raise HTTPException(status_code=400, detail="Only published listings can be unpublished")
        row.status = "approved"
        row.published_at = None
    row.updated_by_user_id = actor.id

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="developer.marketplace_listing.publish",
        target_type="marketplace_listing",
        target_id=row.id,
        metadata_json={"publish": payload.publish, "status": row.status},
    )
    db.commit()
    db.refresh(row)
    return _marketplace_listing_out(row)


@public_router.get(
    "/me",
    response_model=PublicApiBusinessOut,
    summary="Get business profile using API key",
    responses=error_responses(401, 403, 500),
)
def public_me(
    principal=Depends(_require_public_scope("business:read")),
    db: Session = Depends(get_db),
):
    business = db.execute(select(Business).where(Business.id == principal.business_id)).scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return PublicApiBusinessOut(
        business_id=business.id,
        business_name=business.name,
        base_currency=business.base_currency,
    )


@public_router.get(
    "/products",
    response_model=PublicApiProductListOut,
    summary="List products using API key",
    responses=error_responses(401, 403, 422, 500),
)
def public_list_products(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    is_published: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal=Depends(_require_public_scope("products:read")),
    db: Session = Depends(get_db),
):
    count_stmt = select(func.count(Product.id)).where(Product.business_id == principal.business_id)
    stmt = select(Product).where(Product.business_id == principal.business_id)
    normalized_q = None
    if q and q.strip():
        normalized_q = q.strip().lower()
        like_pattern = f"%{normalized_q}%"
        count_stmt = count_stmt.where(func.lower(Product.name).like(like_pattern))
        stmt = stmt.where(func.lower(Product.name).like(like_pattern))
    if category and category.strip():
        normalized_category = category.strip().lower()
        count_stmt = count_stmt.where(func.lower(Product.category) == normalized_category)
        stmt = stmt.where(func.lower(Product.category) == normalized_category)
        category = normalized_category
    if is_published is not None:
        count_stmt = count_stmt.where(Product.is_published.is_(is_published))
        stmt = stmt.where(Product.is_published.is_(is_published))

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(stmt.order_by(Product.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    items = [
        PublicApiProductOut(
            id=row.id,
            name=row.name,
            category=row.category,
            is_published=bool(row.is_published),
            created_at=row.created_at,
        )
        for row in rows
    ]
    count = len(items)
    return PublicApiProductListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        q=normalized_q,
        category=category,
        is_published=is_published,
    )


@public_router.get(
    "/orders",
    response_model=PublicApiOrderListOut,
    summary="List orders using API key",
    responses=error_responses(401, 403, 422, 500),
)
def public_list_orders(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal=Depends(_require_public_scope("orders:read")),
    db: Session = Depends(get_db),
):
    count_stmt = select(func.count(Order.id)).where(Order.business_id == principal.business_id)
    stmt = select(Order).where(Order.business_id == principal.business_id)
    normalized_status = None
    if status and status.strip():
        normalized_status = status.strip().lower()
        count_stmt = count_stmt.where(Order.status == normalized_status)
        stmt = stmt.where(Order.status == normalized_status)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(stmt.order_by(Order.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    items = [
        PublicApiOrderOut(
            id=row.id,
            customer_id=row.customer_id,
            payment_method=row.payment_method,
            channel=row.channel,
            status=row.status,
            total_amount=float(row.total_amount),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    count = len(items)
    return PublicApiOrderListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        status=normalized_status,
    )


@public_router.get(
    "/customers",
    response_model=PublicApiCustomerListOut,
    summary="List customers using API key",
    responses=error_responses(401, 403, 422, 500),
)
def public_list_customers(
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal=Depends(_require_public_scope("customers:read")),
    db: Session = Depends(get_db),
):
    count_stmt = select(func.count(Customer.id)).where(Customer.business_id == principal.business_id)
    stmt = select(Customer).where(Customer.business_id == principal.business_id)
    normalized_q = None
    if q and q.strip():
        normalized_q = q.strip().lower()
        like_pattern = f"%{normalized_q}%"
        count_stmt = count_stmt.where(
            or_(
                func.lower(Customer.name).like(like_pattern),
                func.lower(func.coalesce(Customer.email, "")).like(like_pattern),
                func.lower(func.coalesce(Customer.phone, "")).like(like_pattern),
            )
        )
        stmt = stmt.where(
            or_(
                func.lower(Customer.name).like(like_pattern),
                func.lower(func.coalesce(Customer.email, "")).like(like_pattern),
                func.lower(func.coalesce(Customer.phone, "")).like(like_pattern),
            )
        )

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(Customer.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [
        PublicApiCustomerOut(
            id=row.id,
            name=row.name,
            email=row.email,
            phone=row.phone,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    count = len(items)
    return PublicApiCustomerListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        q=normalized_q,
    )
