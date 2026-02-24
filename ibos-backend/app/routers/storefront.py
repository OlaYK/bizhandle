import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.config import settings
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security_current import BusinessAccess, get_current_user
from app.models.product import Product, ProductVariant
from app.models.storefront import StorefrontConfig
from app.models.user import User
from app.schemas.common import PaginationMeta
from app.schemas.storefront import (
    PublicStorefrontOut,
    PublicStorefrontProductDetailOut,
    PublicStorefrontProductListOut,
    PublicStorefrontProductOut,
    PublicStorefrontVariantOut,
    StorefrontDomainChallengeOut,
    StorefrontDomainStatusOut,
    StorefrontDomainVerifyIn,
    StorefrontConfigOut,
    StorefrontConfigUpsertIn,
)
from app.services.audit_service import log_audit_event
from app.services.integration_service import queue_outbox_event

router = APIRouter(prefix="/storefront", tags=["storefront"])

storefront_rate_limiter = SlidingWindowRateLimiter(
    max_requests=settings.storefront_public_rate_limit_requests,
    window_seconds=settings.storefront_public_rate_limit_window_seconds,
)


def _normalize_query(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_domain(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().lower() or None


def _domain_txt_name(domain: str) -> str:
    return f"_monidesk-verification.{domain}"


def _domain_txt_value(token: str) -> str:
    return f"monidesk-site-verification={token}"


def _storefront_out(config: StorefrontConfig) -> StorefrontConfigOut:
    return StorefrontConfigOut(
        id=config.id,
        business_id=config.business_id,
        slug=config.slug,
        display_name=config.display_name,
        tagline=config.tagline,
        description=config.description,
        seo_title=config.seo_title,
        seo_description=config.seo_description,
        seo_og_image_url=config.seo_og_image_url,
        logo_url=config.logo_url,
        accent_color=config.accent_color,
        hero_image_url=config.hero_image_url,
        support_email=config.support_email,
        support_phone=config.support_phone,
        policy_shipping=config.policy_shipping,
        policy_returns=config.policy_returns,
        policy_privacy=config.policy_privacy,
        custom_domain=config.custom_domain,
        domain_verification_status=config.domain_verification_status,
        domain_verification_token=config.domain_verification_token,
        domain_last_checked_at=config.domain_last_checked_at,
        domain_verified_at=config.domain_verified_at,
        is_published=config.is_published,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _public_storefront_or_404(db: Session, *, slug: str) -> StorefrontConfig:
    config = db.execute(
        select(StorefrontConfig).where(
            func.lower(StorefrontConfig.slug) == slug.lower(),
            StorefrontConfig.is_published.is_(True),
        )
    ).scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Storefront not found")
    return config


def _enforce_storefront_public_rate_limit(request: Request) -> None:
    client_ip = (request.client.host if request.client else "unknown").strip() or "unknown"
    retry_after = storefront_rate_limiter.check_and_consume(client_ip)
    if retry_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many storefront requests",
            headers={"Retry-After": str(retry_after)},
        )


def _domain_status_out(config: StorefrontConfig) -> StorefrontDomainStatusOut:
    txt_name = _domain_txt_name(config.custom_domain) if config.custom_domain else None
    txt_value = (
        _domain_txt_value(config.domain_verification_token)
        if config.custom_domain and config.domain_verification_token
        else None
    )
    return StorefrontDomainStatusOut(
        custom_domain=config.custom_domain,
        verification_status=config.domain_verification_status,
        txt_record_name=txt_name,
        txt_record_value=txt_value,
        domain_last_checked_at=config.domain_last_checked_at,
        domain_verified_at=config.domain_verified_at,
    )


def _emit_storefront_analytics_events(
    db: Session,
    *,
    business_id: str,
    event_type: str,
    payload: dict[str, object],
) -> None:
    queue_outbox_event(
        db,
        business_id=business_id,
        event_type=event_type,
        target_app_key="meta_pixel",
        payload_json=payload,
    )
    queue_outbox_event(
        db,
        business_id=business_id,
        event_type=event_type,
        target_app_key="google_analytics",
        payload_json=payload,
    )


@router.put(
    "/config",
    response_model=StorefrontConfigOut,
    summary="Create or update storefront configuration",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def upsert_storefront_config(
    payload: StorefrontConfigUpsertIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    existing_slug = db.execute(
        select(StorefrontConfig.id).where(
            func.lower(StorefrontConfig.slug) == payload.slug.lower(),
            StorefrontConfig.business_id != access.business.id,
        )
    ).scalar_one_or_none()
    if existing_slug:
        raise HTTPException(status_code=409, detail="Storefront slug is already in use")

    config = db.execute(
        select(StorefrontConfig).where(StorefrontConfig.business_id == access.business.id)
    ).scalar_one_or_none()

    if not config:
        config = StorefrontConfig(
            id=str(uuid.uuid4()),
            business_id=access.business.id,
            slug=payload.slug,
            display_name=payload.display_name,
        )
        db.add(config)

    previous_domain = config.custom_domain
    config.slug = payload.slug
    config.display_name = payload.display_name
    config.tagline = payload.tagline
    config.description = payload.description
    config.seo_title = payload.seo_title
    config.seo_description = payload.seo_description
    config.seo_og_image_url = payload.seo_og_image_url
    config.logo_url = payload.logo_url
    config.accent_color = payload.accent_color
    config.hero_image_url = payload.hero_image_url
    config.support_email = str(payload.support_email) if payload.support_email else None
    config.support_phone = payload.support_phone
    config.policy_shipping = payload.policy_shipping
    config.policy_returns = payload.policy_returns
    config.policy_privacy = payload.policy_privacy
    config.custom_domain = _normalize_domain(payload.custom_domain)
    config.is_published = payload.is_published

    if config.custom_domain != previous_domain:
        if config.custom_domain:
            config.domain_verification_status = "pending"
        else:
            config.domain_verification_status = "not_configured"
        config.domain_verification_token = None
        config.domain_verified_at = None
        config.domain_last_checked_at = None

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="storefront.config.upsert",
        target_type="storefront_config",
        target_id=config.id,
        metadata_json={
            "slug": config.slug,
            "is_published": config.is_published,
            "custom_domain": config.custom_domain,
            "domain_verification_status": config.domain_verification_status,
        },
    )
    db.commit()
    db.refresh(config)
    return _storefront_out(config)


@router.get(
    "/config",
    response_model=StorefrontConfigOut,
    summary="Get storefront configuration",
    responses=error_responses(401, 403, 404, 500),
)
def get_storefront_config(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    config = db.execute(
        select(StorefrontConfig).where(StorefrontConfig.business_id == access.business.id)
    ).scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Storefront config not found")
    return _storefront_out(config)


@router.post(
    "/config/domain/challenge",
    response_model=StorefrontDomainChallengeOut,
    summary="Generate custom domain DNS verification challenge",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def generate_domain_verification_challenge(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    config = db.execute(
        select(StorefrontConfig).where(StorefrontConfig.business_id == access.business.id)
    ).scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Storefront config not found")
    if not config.custom_domain:
        raise HTTPException(status_code=400, detail="Set custom_domain before requesting verification")

    token = uuid.uuid4().hex
    config.domain_verification_token = token
    config.domain_verification_status = "pending"
    config.domain_last_checked_at = datetime.now(timezone.utc)

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="storefront.domain.challenge",
        target_type="storefront_config",
        target_id=config.id,
        metadata_json={
            "custom_domain": config.custom_domain,
            "verification_status": config.domain_verification_status,
        },
    )
    db.commit()

    return StorefrontDomainChallengeOut(
        custom_domain=config.custom_domain,
        verification_status=config.domain_verification_status,
        txt_record_name=_domain_txt_name(config.custom_domain),
        txt_record_value=_domain_txt_value(token),
        domain_last_checked_at=config.domain_last_checked_at,
    )


@router.post(
    "/config/domain/verify",
    response_model=StorefrontDomainStatusOut,
    summary="Verify custom domain DNS token",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def verify_custom_domain(
    payload: StorefrontDomainVerifyIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    config = db.execute(
        select(StorefrontConfig).where(StorefrontConfig.business_id == access.business.id)
    ).scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Storefront config not found")
    if not config.custom_domain:
        raise HTTPException(status_code=400, detail="Set custom_domain before verification")
    if not config.domain_verification_token:
        raise HTTPException(status_code=400, detail="Generate domain challenge before verification")

    config.domain_last_checked_at = datetime.now(timezone.utc)
    expected_value = _domain_txt_value(config.domain_verification_token)
    provided_value = payload.verification_token.strip()
    if provided_value not in {config.domain_verification_token, expected_value}:
        config.domain_verification_status = "pending"
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Invalid verification token. Add the expected TXT record and retry.",
        )

    config.domain_verification_status = "verified"
    config.domain_verified_at = datetime.now(timezone.utc)

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="storefront.domain.verify",
        target_type="storefront_config",
        target_id=config.id,
        metadata_json={
            "custom_domain": config.custom_domain,
            "verification_status": config.domain_verification_status,
        },
    )
    db.commit()
    return _domain_status_out(config)


@router.get(
    "/config/domain/status",
    response_model=StorefrontDomainStatusOut,
    summary="Get custom domain verification status",
    responses=error_responses(401, 403, 404, 500),
)
def get_custom_domain_status(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    config = db.execute(
        select(StorefrontConfig).where(StorefrontConfig.business_id == access.business.id)
    ).scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Storefront config not found")
    return _domain_status_out(config)


@router.get(
    "/public/{slug}",
    response_model=PublicStorefrontOut,
    summary="Get public storefront profile",
    responses=error_responses(404, 422, 429, 500),
)
def get_public_storefront(
    slug: str,
    db: Session = Depends(get_db),
    _: None = Depends(_enforce_storefront_public_rate_limit),
):
    config = _public_storefront_or_404(db, slug=slug)
    _emit_storefront_analytics_events(
        db,
        business_id=config.business_id,
        event_type="storefront.page_view",
        payload={"slug": config.slug},
    )
    db.commit()
    return PublicStorefrontOut(
        slug=config.slug,
        display_name=config.display_name,
        tagline=config.tagline,
        description=config.description,
        seo_title=config.seo_title,
        seo_description=config.seo_description,
        seo_og_image_url=config.seo_og_image_url,
        logo_url=config.logo_url,
        accent_color=config.accent_color,
        hero_image_url=config.hero_image_url,
        support_email=config.support_email,
        support_phone=config.support_phone,
        policy_shipping=config.policy_shipping,
        policy_returns=config.policy_returns,
        policy_privacy=config.policy_privacy,
    )


@router.get(
    "/public/{slug}/products",
    response_model=PublicStorefrontProductListOut,
    summary="Browse public storefront products",
    responses=error_responses(404, 422, 429, 500),
)
def list_public_storefront_products(
    slug: str,
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: None = Depends(_enforce_storefront_public_rate_limit),
):
    config = _public_storefront_or_404(db, slug=slug)
    _emit_storefront_analytics_events(
        db,
        business_id=config.business_id,
        event_type="storefront.product_list_view",
        payload={"slug": config.slug, "q": q, "category": category},
    )
    db.commit()
    normalized_q = _normalize_query(q)
    normalized_category = _normalize_query(category)

    stmt = (
        select(
            Product.id,
            Product.name,
            Product.category,
            func.min(ProductVariant.selling_price).label("starting_price"),
            func.count(ProductVariant.id).label("variant_count"),
        )
        .join(
            ProductVariant,
            (ProductVariant.product_id == Product.id)
            & (ProductVariant.business_id == Product.business_id),
        )
        .where(
            Product.business_id == config.business_id,
            Product.active.is_(True),
            Product.is_published.is_(True),
            ProductVariant.is_published.is_(True),
        )
        .group_by(Product.id, Product.name, Product.category)
    )

    if normalized_q:
        like_query = f"%{normalized_q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Product.name).like(like_query),
                func.lower(func.coalesce(Product.category, "")).like(like_query),
            )
        )

    if normalized_category:
        stmt = stmt.where(func.lower(func.coalesce(Product.category, "")) == normalized_category.lower())

    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())

    rows = db.execute(stmt.order_by(Product.name.asc()).offset(offset).limit(limit)).all()
    items = [
        PublicStorefrontProductOut(
            id=product_id,
            name=name,
            category=product_category,
            starting_price=float(starting_price) if starting_price is not None else None,
            published_variant_count=int(variant_count),
        )
        for product_id, name, product_category, starting_price, variant_count in rows
    ]
    count = len(items)
    return PublicStorefrontProductListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        q=normalized_q,
        category=normalized_category,
    )


@router.get(
    "/public/{slug}/products/{product_id}",
    response_model=PublicStorefrontProductDetailOut,
    summary="Get public storefront product detail",
    responses=error_responses(404, 422, 429, 500),
)
def get_public_storefront_product_detail(
    slug: str,
    product_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(_enforce_storefront_public_rate_limit),
):
    config = _public_storefront_or_404(db, slug=slug)

    product = db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.business_id == config.business_id,
            Product.active.is_(True),
            Product.is_published.is_(True),
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    variants = db.execute(
        select(ProductVariant)
        .where(
            ProductVariant.product_id == product.id,
            ProductVariant.business_id == config.business_id,
            ProductVariant.is_published.is_(True),
        )
        .order_by(ProductVariant.created_at.asc())
    ).scalars().all()
    if not variants:
        raise HTTPException(status_code=404, detail="Product not found")

    _emit_storefront_analytics_events(
        db,
        business_id=config.business_id,
        event_type="storefront.product_view",
        payload={"slug": config.slug, "product_id": product.id},
    )
    db.commit()

    return PublicStorefrontProductDetailOut(
        id=product.id,
        name=product.name,
        category=product.category,
        description=None,
        variants=[
            PublicStorefrontVariantOut(
                id=variant.id,
                size=variant.size,
                label=variant.label,
                sku=variant.sku,
                selling_price=float(variant.selling_price) if variant.selling_price is not None else None,
            )
            for variant in variants
        ],
    )
