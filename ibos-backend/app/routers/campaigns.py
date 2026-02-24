import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.campaign import (
    Campaign,
    CampaignRecipient,
    CampaignTemplate,
    CustomerConsent,
    CustomerSegment,
    RetentionTrigger,
    RetentionTriggerRun,
)
from app.models.customer import Customer, CustomerTagLink
from app.models.integration import AppInstallation, OutboundMessage
from app.models.order import Order
from app.models.user import User
from app.schemas.campaign import (
    CampaignCreateIn,
    CampaignDispatchIn,
    CampaignDispatchOut,
    CampaignListOut,
    CampaignMetricsOut,
    CampaignOut,
    CampaignRecipientListOut,
    CampaignRecipientOut,
    CampaignTemplateCreateIn,
    CampaignTemplateListOut,
    CampaignTemplateOut,
    CampaignTemplateUpdateIn,
    CustomerConsentListOut,
    CustomerConsentOut,
    CustomerConsentUpsertIn,
    CustomerSegmentCreateIn,
    CustomerSegmentListOut,
    CustomerSegmentOut,
    CustomerSegmentUpdateIn,
    RetentionTriggerCreateIn,
    RetentionTriggerListOut,
    RetentionTriggerOut,
    RetentionTriggerRunOut,
    RetentionTriggerRunRequestIn,
    SegmentFiltersIn,
    SegmentPreviewOut,
)
from app.schemas.common import PaginationMeta
from app.services.audit_service import log_audit_event
from app.services.integration_service import queue_outbox_event
from app.services.messaging_provider import MessageSendRequest, get_messaging_provider

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@dataclass
class _AudienceProfile:
    customer: Customer
    total_spent: float
    order_count: int
    last_order_at: datetime | None
    channels: set[str]
    tag_ids: set[str]


def _segment_or_404(db: Session, *, business_id: str, segment_id: str) -> CustomerSegment:
    row = db.execute(
        select(CustomerSegment).where(
            CustomerSegment.id == segment_id,
            CustomerSegment.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Segment not found")
    return row


def _template_or_404(db: Session, *, business_id: str, template_id: str) -> CampaignTemplate:
    row = db.execute(
        select(CampaignTemplate).where(
            CampaignTemplate.id == template_id,
            CampaignTemplate.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return row


def _campaign_or_404(db: Session, *, business_id: str, campaign_id: str) -> Campaign:
    row = db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return row


def _trigger_or_404(db: Session, *, business_id: str, trigger_id: str) -> RetentionTrigger:
    row = db.execute(
        select(RetentionTrigger).where(
            RetentionTrigger.id == trigger_id,
            RetentionTrigger.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Retention trigger not found")
    return row


def _segment_filters_from_json(value: dict | None) -> SegmentFiltersIn:
    try:
        return SegmentFiltersIn.model_validate(value or {})
    except ValidationError:
        return SegmentFiltersIn()


def _segment_out(segment: CustomerSegment) -> CustomerSegmentOut:
    return CustomerSegmentOut(
        id=segment.id,
        name=segment.name,
        description=segment.description,
        filters=_segment_filters_from_json(segment.filters_json),
        is_active=segment.is_active,
        created_at=segment.created_at,
        updated_at=segment.updated_at,
    )


def _template_out(template: CampaignTemplate) -> CampaignTemplateOut:
    return CampaignTemplateOut(
        id=template.id,
        name=template.name,
        channel=template.channel,
        content=template.content,
        status=template.status,
        created_by_user_id=template.created_by_user_id,
        approved_by_user_id=template.approved_by_user_id,
        approved_at=template.approved_at,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _campaign_out(campaign: Campaign) -> CampaignOut:
    return CampaignOut(
        id=campaign.id,
        name=campaign.name,
        segment_id=campaign.segment_id,
        template_id=campaign.template_id,
        channel=campaign.channel,
        provider=campaign.provider,
        message_content=campaign.message_content,
        status=campaign.status,
        scheduled_at=campaign.scheduled_at,
        started_at=campaign.started_at,
        completed_at=campaign.completed_at,
        total_recipients=campaign.total_recipients,
        sent_count=campaign.sent_count,
        delivered_count=campaign.delivered_count,
        opened_count=campaign.opened_count,
        replied_count=campaign.replied_count,
        failed_count=campaign.failed_count,
        suppressed_count=campaign.suppressed_count,
        skipped_count=campaign.skipped_count,
        created_by_user_id=campaign.created_by_user_id,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


def _recipient_out(recipient: CampaignRecipient) -> CampaignRecipientOut:
    return CampaignRecipientOut(
        id=recipient.id,
        campaign_id=recipient.campaign_id,
        customer_id=recipient.customer_id,
        recipient=recipient.recipient,
        status=recipient.status,
        outbound_message_id=recipient.outbound_message_id,
        error_message=recipient.error_message,
        sent_at=recipient.sent_at,
        delivered_at=recipient.delivered_at,
        opened_at=recipient.opened_at,
        replied_at=recipient.replied_at,
        created_at=recipient.created_at,
        updated_at=recipient.updated_at,
    )


def _consent_out(consent: CustomerConsent) -> CustomerConsentOut:
    return CustomerConsentOut(
        id=consent.id,
        customer_id=consent.customer_id,
        channel=consent.channel,
        status=consent.status,
        source=consent.source,
        note=consent.note,
        opted_at=consent.opted_at,
        updated_at=consent.updated_at,
    )


def _retention_trigger_out(trigger: RetentionTrigger) -> RetentionTriggerOut:
    return RetentionTriggerOut(
        id=trigger.id,
        name=trigger.name,
        trigger_type=trigger.trigger_type,
        status=trigger.status,
        segment_id=trigger.segment_id,
        template_id=trigger.template_id,
        channel=trigger.channel,
        provider=trigger.provider,
        config_json=trigger.config_json,
        created_by_user_id=trigger.created_by_user_id,
        last_run_at=trigger.last_run_at,
        created_at=trigger.created_at,
        updated_at=trigger.updated_at,
    )


def _customer_profiles(db: Session, *, business_id: str) -> dict[str, _AudienceProfile]:
    customers = db.execute(select(Customer).where(Customer.business_id == business_id)).scalars().all()
    profiles = {
        customer.id: _AudienceProfile(
            customer=customer,
            total_spent=0.0,
            order_count=0,
            last_order_at=None,
            channels=set(),
            tag_ids=set(),
        )
        for customer in customers
    }
    if not profiles:
        return profiles

    order_rows = db.execute(
        select(Order.customer_id, Order.total_amount, Order.channel, Order.created_at, Order.status).where(
            Order.business_id == business_id,
            Order.customer_id.is_not(None),
        )
    ).all()
    tracked_statuses = {"pending", "paid", "processing", "fulfilled"}
    for customer_id, total_amount, channel, created_at, status in order_rows:
        if not customer_id or customer_id not in profiles or status not in tracked_statuses:
            continue
        profile = profiles[customer_id]
        profile.total_spent += float(total_amount or 0)
        profile.order_count += 1
        if channel:
            profile.channels.add(channel)
        if created_at and (profile.last_order_at is None or created_at > profile.last_order_at):
            profile.last_order_at = created_at

    tag_rows = db.execute(
        select(CustomerTagLink.customer_id, CustomerTagLink.tag_id).where(
            CustomerTagLink.business_id == business_id,
            CustomerTagLink.customer_id.in_(list(profiles.keys())),
        )
    ).all()
    for customer_id, tag_id in tag_rows:
        if customer_id in profiles:
            profiles[customer_id].tag_ids.add(tag_id)
    return profiles


def _matches_segment_filters(profile: _AudienceProfile, filters: SegmentFiltersIn, *, now: datetime) -> bool:
    if filters.q:
        haystack = " ".join([profile.customer.name or "", profile.customer.email or "", profile.customer.phone or ""]).lower()
        if filters.q.strip().lower() not in haystack:
            return False
    if filters.tag_ids_any and not profile.tag_ids.intersection(set(filters.tag_ids_any)):
        return False
    if filters.min_total_spent is not None and profile.total_spent < float(filters.min_total_spent):
        return False
    if filters.min_order_count is not None and profile.order_count < filters.min_order_count:
        return False
    if filters.channels_any and not profile.channels.intersection(set(filters.channels_any)):
        return False
    if filters.has_email is True and not profile.customer.email:
        return False
    if filters.has_email is False and profile.customer.email:
        return False
    if filters.has_phone is True and not profile.customer.phone:
        return False
    if filters.has_phone is False and profile.customer.phone:
        return False
    if filters.last_order_before_days is not None:
        if not profile.last_order_at:
            return False
        if profile.last_order_at > (now - timedelta(days=filters.last_order_before_days)):
            return False
    if filters.last_order_within_days is not None:
        if not profile.last_order_at:
            return False
        if profile.last_order_at < (now - timedelta(days=filters.last_order_within_days)):
            return False
    return True


def _evaluate_segment_customer_ids(db: Session, *, business_id: str, filters: SegmentFiltersIn) -> list[str]:
    profiles = _customer_profiles(db, business_id=business_id)
    now = datetime.now(timezone.utc)
    out = [customer_id for customer_id, profile in profiles.items() if _matches_segment_filters(profile, filters, now=now)]
    out.sort()
    return out


def _resolve_customer_recipient(customer: Customer, *, channel: str) -> str | None:
    if channel in {"whatsapp", "sms"}:
        return customer.phone or None
    if channel == "email":
        return customer.email or None
    return customer.phone or customer.email or None


def _consent_status_map(
    db: Session,
    *,
    business_id: str,
    customer_ids: list[str],
    channel: str,
) -> dict[str, str]:
    if not customer_ids:
        return {}
    rows = db.execute(
        select(CustomerConsent.customer_id, CustomerConsent.status).where(
            CustomerConsent.business_id == business_id,
            CustomerConsent.channel == channel,
            CustomerConsent.customer_id.in_(customer_ids),
        )
    ).all()
    return {customer_id: status for customer_id, status in rows}


def _sync_campaign_counts(db: Session, *, campaign: Campaign) -> None:
    rows = db.execute(
        select(CampaignRecipient.status, func.count(CampaignRecipient.id))
        .where(CampaignRecipient.campaign_id == campaign.id)
        .group_by(CampaignRecipient.status)
    ).all()
    counts = {status: int(count) for status, count in rows}
    campaign.total_recipients = sum(counts.values())
    campaign.sent_count = counts.get("sent", 0)
    campaign.delivered_count = counts.get("delivered", 0) + counts.get("sent", 0)
    campaign.opened_count = counts.get("opened", 0)
    campaign.replied_count = counts.get("replied", 0)
    campaign.failed_count = counts.get("failed", 0)
    campaign.suppressed_count = counts.get("suppressed", 0)
    campaign.skipped_count = counts.get("skipped", 0)


def _resolve_campaign_audience_customer_ids(
    db: Session,
    *,
    business_id: str,
    segment_id: str | None,
    explicit_customer_ids: list[str],
) -> list[str]:
    if explicit_customer_ids:
        customer_ids = list(dict.fromkeys(explicit_customer_ids))
        existing_ids = db.execute(
            select(Customer.id).where(Customer.business_id == business_id, Customer.id.in_(customer_ids))
        ).scalars().all()
        if len(existing_ids) != len(customer_ids):
            raise HTTPException(status_code=404, detail="One or more explicit customers not found")
        return customer_ids
    if segment_id:
        segment = _segment_or_404(db, business_id=business_id, segment_id=segment_id)
        return _evaluate_segment_customer_ids(
            db,
            business_id=business_id,
            filters=_segment_filters_from_json(segment.filters_json),
        )
    return db.execute(select(Customer.id).where(Customer.business_id == business_id)).scalars().all()


def _create_campaign_recipients(db: Session, *, campaign: Campaign, customers: list[Customer]) -> None:
    consent_map = _consent_status_map(
        db,
        business_id=campaign.business_id,
        customer_ids=[customer.id for customer in customers],
        channel=campaign.channel,
    )
    for customer in customers:
        consent_status = consent_map.get(customer.id, "subscribed")
        contact = _resolve_customer_recipient(customer, channel=campaign.channel)
        if consent_status == "unsubscribed":
            status = "suppressed"
            recipient = contact or f"customer:{customer.id}"
            error = "Customer opted out"
        elif not contact:
            status = "skipped"
            recipient = f"customer:{customer.id}"
            error = f"Missing {campaign.channel} contact"
        else:
            status = "queued"
            recipient = contact
            error = None
        db.add(
            CampaignRecipient(
                id=str(uuid.uuid4()),
                campaign_id=campaign.id,
                business_id=campaign.business_id,
                customer_id=customer.id,
                recipient=recipient,
                status=status,
                error_message=error,
            )
        )


def _dispatch_campaign(
    db: Session,
    *,
    campaign: Campaign,
    actor: User,
    provider_name: str | None = None,
) -> CampaignDispatchOut:
    if campaign.channel == "whatsapp":
        whatsapp_connected = db.execute(
            select(AppInstallation.id).where(
                AppInstallation.business_id == campaign.business_id,
                AppInstallation.app_key == "whatsapp",
                AppInstallation.status == "connected",
            )
        ).scalar_one_or_none()
        if not whatsapp_connected:
            raise HTTPException(status_code=400, detail="WhatsApp connector is not connected")

    provider_key = (provider_name or campaign.provider).strip().lower()
    provider = get_messaging_provider(provider_key)
    campaign.provider = provider_key

    rows = db.execute(
        select(CampaignRecipient).where(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.status == "queued",
        )
    ).scalars().all()

    now = datetime.now(timezone.utc)
    if rows and campaign.started_at is None:
        campaign.started_at = now
    campaign.status = "sending"

    processed = 0
    sent = 0
    failed = 0
    for row in rows:
        processed += 1
        try:
            result = provider.send_message(
                MessageSendRequest(
                    business_id=campaign.business_id,
                    recipient=row.recipient,
                    content=campaign.message_content,
                )
            )
            message = OutboundMessage(
                id=str(uuid.uuid4()),
                business_id=campaign.business_id,
                provider=result.provider,
                recipient=row.recipient,
                content=campaign.message_content,
                status=result.status,
                external_message_id=result.message_id,
                error_message=None,
            )
            db.add(message)
            db.flush()
            queue_outbox_event(
                db,
                business_id=campaign.business_id,
                event_type="campaign.message.sent",
                target_app_key="whatsapp" if campaign.channel == "whatsapp" else campaign.channel,
                payload_json={"campaign_id": campaign.id, "recipient_id": row.id, "customer_id": row.customer_id},
            )
            row.status = "sent"
            row.error_message = None
            row.outbound_message_id = message.id
            row.sent_at = now
            row.delivered_at = now
            sent += 1
        except Exception as exc:
            row.status = "failed"
            row.error_message = str(exc)[:255]
            failed += 1

    db.flush()
    _sync_campaign_counts(db, campaign=campaign)
    remaining = db.execute(
        select(func.count(CampaignRecipient.id)).where(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.status == "queued",
        )
    ).scalar_one()
    if int(remaining) == 0:
        campaign.status = "completed" if campaign.sent_count > 0 or campaign.failed_count == 0 else "failed"
        campaign.completed_at = datetime.now(timezone.utc)

    log_audit_event(
        db,
        business_id=campaign.business_id,
        actor_user_id=actor.id,
        action="campaign.dispatch",
        target_type="campaign",
        target_id=campaign.id,
        metadata_json={"processed": processed, "sent": sent, "failed": failed, "campaign_status": campaign.status},
    )
    return CampaignDispatchOut(
        campaign_id=campaign.id,
        campaign_status=campaign.status,
        processed=processed,
        sent=sent,
        failed=failed,
        suppressed=campaign.suppressed_count,
        skipped=campaign.skipped_count,
    )


def _create_campaign(db: Session, *, business_id: str, actor: User, payload: CampaignCreateIn) -> Campaign:
    template = _template_or_404(db, business_id=business_id, template_id=payload.template_id) if payload.template_id else None
    content = (payload.content_override or (template.content if template else "")).strip()
    if not content:
        raise HTTPException(status_code=400, detail="Campaign message content is required")
    if payload.send_now and template and template.status != "approved":
        raise HTTPException(status_code=400, detail="Template must be approved before send_now")

    audience_ids = _resolve_campaign_audience_customer_ids(
        db,
        business_id=business_id,
        segment_id=payload.segment_id,
        explicit_customer_ids=payload.explicit_customer_ids,
    )
    customers = (
        db.execute(select(Customer).where(Customer.business_id == business_id, Customer.id.in_(audience_ids)))
        .scalars()
        .all()
        if audience_ids
        else []
    )

    campaign = Campaign(
        id=str(uuid.uuid4()),
        business_id=business_id,
        segment_id=payload.segment_id,
        template_id=payload.template_id,
        name=payload.name,
        channel=payload.channel,
        provider=payload.provider,
        message_content=content,
        status="queued",
        scheduled_at=payload.scheduled_at,
        created_by_user_id=actor.id,
    )
    db.add(campaign)
    db.flush()
    _create_campaign_recipients(db, campaign=campaign, customers=customers)
    db.flush()
    _sync_campaign_counts(db, campaign=campaign)
    queued = db.execute(
        select(func.count(CampaignRecipient.id)).where(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.status == "queued",
        )
    ).scalar_one()
    if int(queued) == 0:
        campaign.status = "completed"
        campaign.completed_at = datetime.now(timezone.utc)
    if payload.send_now and int(queued) > 0:
        _dispatch_campaign(db, campaign=campaign, actor=actor, provider_name=payload.provider)

    log_audit_event(
        db,
        business_id=business_id,
        actor_user_id=actor.id,
        action="campaign.create",
        target_type="campaign",
        target_id=campaign.id,
        metadata_json={"name": campaign.name, "status": campaign.status, "total_recipients": campaign.total_recipients},
    )
    return campaign


def _campaign_metrics(db: Session, *, business_id: str, campaign_id: str | None = None) -> CampaignMetricsOut:
    campaign_count_stmt = select(func.count(Campaign.id)).where(Campaign.business_id == business_id)
    recipient_count_stmt = select(func.count(CampaignRecipient.id)).where(CampaignRecipient.business_id == business_id)
    status_stmt = select(CampaignRecipient.status, func.count(CampaignRecipient.id)).where(CampaignRecipient.business_id == business_id)
    if campaign_id:
        campaign_count_stmt = campaign_count_stmt.where(Campaign.id == campaign_id)
        recipient_count_stmt = recipient_count_stmt.where(CampaignRecipient.campaign_id == campaign_id)
        status_stmt = status_stmt.where(CampaignRecipient.campaign_id == campaign_id)
    campaigns_total = int(db.execute(campaign_count_stmt).scalar_one())
    recipients_total = int(db.execute(recipient_count_stmt).scalar_one())
    rows = db.execute(status_stmt.group_by(CampaignRecipient.status)).all()
    counts = {status: int(count) for status, count in rows}
    sent_count = counts.get("sent", 0)
    delivered_count = counts.get("delivered", 0) + sent_count
    replied_count = counts.get("replied", 0)
    response_rate = round((replied_count / sent_count) * 100, 2) if sent_count else 0.0
    return CampaignMetricsOut(
        campaigns_total=campaigns_total,
        recipients_total=recipients_total,
        queued_count=counts.get("queued", 0),
        sent_count=sent_count,
        delivered_count=delivered_count,
        opened_count=counts.get("opened", 0),
        replied_count=replied_count,
        failed_count=counts.get("failed", 0),
        suppressed_count=counts.get("suppressed", 0),
        skipped_count=counts.get("skipped", 0),
        response_rate=response_rate,
    )


@router.post(
    "/segments",
    response_model=CustomerSegmentOut,
    summary="Create saved customer segment",
    responses=error_responses(400, 401, 403, 409, 422, 500),
)
def create_segment(
    payload: CustomerSegmentCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    existing = db.execute(
        select(CustomerSegment.id).where(
            CustomerSegment.business_id == access.business.id,
            func.lower(CustomerSegment.name) == payload.name.lower(),
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Segment name already exists")

    segment = CustomerSegment(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        name=payload.name,
        description=payload.description,
        filters_json=payload.filters.model_dump(exclude_none=True),
        is_active=True,
        created_by_user_id=actor.id,
    )
    db.add(segment)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="campaign.segment.create",
        target_type="customer_segment",
        target_id=segment.id,
        metadata_json={"name": segment.name},
    )
    db.commit()
    db.refresh(segment)
    return _segment_out(segment)


@router.get(
    "/segments",
    response_model=CustomerSegmentListOut,
    summary="List customer segments",
    responses=error_responses(401, 403, 422, 500),
)
def list_segments(
    q: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(CustomerSegment.id)).where(CustomerSegment.business_id == access.business.id)
    stmt = select(CustomerSegment).where(CustomerSegment.business_id == access.business.id)

    if q and q.strip():
        q_like = f"%{q.strip().lower()}%"
        count_stmt = count_stmt.where(func.lower(CustomerSegment.name).like(q_like))
        stmt = stmt.where(func.lower(CustomerSegment.name).like(q_like))
    if is_active is not None:
        count_stmt = count_stmt.where(CustomerSegment.is_active == is_active)
        stmt = stmt.where(CustomerSegment.is_active == is_active)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(CustomerSegment.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [_segment_out(row) for row in rows]
    count = len(items)
    return CustomerSegmentListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )


@router.patch(
    "/segments/{segment_id}",
    response_model=CustomerSegmentOut,
    summary="Update customer segment",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def update_segment(
    segment_id: str,
    payload: CustomerSegmentUpdateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    segment = _segment_or_404(db, business_id=access.business.id, segment_id=segment_id)

    if payload.name is not None and payload.name.lower() != segment.name.lower():
        existing = db.execute(
            select(CustomerSegment.id).where(
                CustomerSegment.business_id == access.business.id,
                func.lower(CustomerSegment.name) == payload.name.lower(),
                CustomerSegment.id != segment.id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Segment name already exists")
        segment.name = payload.name

    if payload.description is not None:
        segment.description = payload.description
    if payload.filters is not None:
        segment.filters_json = payload.filters.model_dump(exclude_none=True)
    if payload.is_active is not None:
        segment.is_active = payload.is_active

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="campaign.segment.update",
        target_type="customer_segment",
        target_id=segment.id,
        metadata_json={"name": segment.name, "is_active": segment.is_active},
    )
    db.commit()
    db.refresh(segment)
    return _segment_out(segment)


@router.post(
    "/segments/{segment_id}/preview",
    response_model=SegmentPreviewOut,
    summary="Preview segment audience",
    responses=error_responses(401, 403, 404, 500),
)
def preview_segment(
    segment_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    segment = _segment_or_404(db, business_id=access.business.id, segment_id=segment_id)
    customer_ids = _evaluate_segment_customer_ids(
        db,
        business_id=access.business.id,
        filters=_segment_filters_from_json(segment.filters_json),
    )
    return SegmentPreviewOut(
        segment_id=segment.id,
        total_customers=len(customer_ids),
        customer_ids=customer_ids,
    )


@router.post(
    "/templates",
    response_model=CampaignTemplateOut,
    summary="Create campaign template",
    responses=error_responses(400, 401, 403, 409, 422, 500),
)
def create_template(
    payload: CampaignTemplateCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    existing = db.execute(
        select(CampaignTemplate.id).where(
            CampaignTemplate.business_id == access.business.id,
            func.lower(CampaignTemplate.name) == payload.name.lower(),
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Template name already exists")

    status_value = payload.status
    if status_value == "approved" and access.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owner/admin can approve templates")
    approved_by_user_id = actor.id if status_value == "approved" else None
    approved_at = datetime.now(timezone.utc) if status_value == "approved" else None

    template = CampaignTemplate(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        name=payload.name,
        channel=payload.channel,
        content=payload.content,
        status=status_value,
        created_by_user_id=actor.id,
        approved_by_user_id=approved_by_user_id,
        approved_at=approved_at,
    )
    db.add(template)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="campaign.template.create",
        target_type="campaign_template",
        target_id=template.id,
        metadata_json={"name": template.name, "status": template.status},
    )
    db.commit()
    db.refresh(template)
    return _template_out(template)


@router.get(
    "/templates",
    response_model=CampaignTemplateListOut,
    summary="List campaign templates",
    responses=error_responses(401, 403, 422, 500),
)
def list_templates(
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(CampaignTemplate.id)).where(CampaignTemplate.business_id == access.business.id)
    stmt = select(CampaignTemplate).where(CampaignTemplate.business_id == access.business.id)
    if status:
        normalized = status.strip().lower()
        count_stmt = count_stmt.where(CampaignTemplate.status == normalized)
        stmt = stmt.where(CampaignTemplate.status == normalized)
    if channel:
        normalized_channel = channel.strip().lower()
        count_stmt = count_stmt.where(CampaignTemplate.channel == normalized_channel)
        stmt = stmt.where(CampaignTemplate.channel == normalized_channel)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(CampaignTemplate.updated_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [_template_out(row) for row in rows]
    count = len(items)
    return CampaignTemplateListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )


@router.patch(
    "/templates/{template_id}",
    response_model=CampaignTemplateOut,
    summary="Update campaign template",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def update_template(
    template_id: str,
    payload: CampaignTemplateUpdateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    template = _template_or_404(db, business_id=access.business.id, template_id=template_id)

    if payload.name is not None and payload.name.lower() != template.name.lower():
        existing = db.execute(
            select(CampaignTemplate.id).where(
                CampaignTemplate.business_id == access.business.id,
                func.lower(CampaignTemplate.name) == payload.name.lower(),
                CampaignTemplate.id != template.id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Template name already exists")
        template.name = payload.name

    if payload.channel is not None:
        template.channel = payload.channel
    if payload.content is not None:
        template.content = payload.content
    if payload.status is not None:
        if payload.status == "approved" and access.role not in {"owner", "admin"}:
            raise HTTPException(status_code=403, detail="Only owner/admin can approve templates")
        template.status = payload.status
        if payload.status == "approved":
            template.approved_by_user_id = actor.id
            template.approved_at = datetime.now(timezone.utc)
        else:
            template.approved_by_user_id = None
            template.approved_at = None

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="campaign.template.update",
        target_type="campaign_template",
        target_id=template.id,
        metadata_json={"name": template.name, "status": template.status},
    )
    db.commit()
    db.refresh(template)
    return _template_out(template)


@router.put(
    "/consent",
    response_model=CustomerConsentOut,
    summary="Upsert customer consent preference",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def upsert_customer_consent(
    payload: CustomerConsentUpsertIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    customer = db.execute(
        select(Customer).where(
            Customer.id == payload.customer_id,
            Customer.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    consent = db.execute(
        select(CustomerConsent).where(
            CustomerConsent.business_id == access.business.id,
            CustomerConsent.customer_id == payload.customer_id,
            CustomerConsent.channel == payload.channel,
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not consent:
        consent = CustomerConsent(
            id=str(uuid.uuid4()),
            business_id=access.business.id,
            customer_id=payload.customer_id,
            channel=payload.channel,
            status=payload.status,
            source=payload.source,
            note=payload.note,
            opted_at=now,
        )
        db.add(consent)
        action = "campaign.consent.create"
    else:
        consent.status = payload.status
        consent.source = payload.source
        consent.note = payload.note
        consent.opted_at = now
        action = "campaign.consent.update"

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action=action,
        target_type="customer_consent",
        target_id=consent.id,
        metadata_json={
            "customer_id": payload.customer_id,
            "channel": payload.channel,
            "status": payload.status,
        },
    )
    db.commit()
    db.refresh(consent)
    return _consent_out(consent)


@router.get(
    "/consent",
    response_model=CustomerConsentListOut,
    summary="List customer consent preferences",
    responses=error_responses(401, 403, 422, 500),
)
def list_customer_consents(
    channel: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(CustomerConsent.id)).where(CustomerConsent.business_id == access.business.id)
    stmt = select(CustomerConsent).where(CustomerConsent.business_id == access.business.id)
    normalized_channel = channel.strip().lower() if channel and channel.strip() else None
    normalized_status = status.strip().lower() if status and status.strip() else None
    if normalized_channel:
        count_stmt = count_stmt.where(CustomerConsent.channel == normalized_channel)
        stmt = stmt.where(CustomerConsent.channel == normalized_channel)
    if normalized_status:
        count_stmt = count_stmt.where(CustomerConsent.status == normalized_status)
        stmt = stmt.where(CustomerConsent.status == normalized_status)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(CustomerConsent.updated_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [_consent_out(row) for row in rows]
    count = len(items)
    return CustomerConsentListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        channel=normalized_channel,
        status=normalized_status,
    )


@router.post(
    "",
    response_model=CampaignOut,
    summary="Create campaign",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def create_campaign(
    payload: CampaignCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    template = _template_or_404(db, business_id=access.business.id, template_id=payload.template_id) if payload.template_id else None
    if template and template.channel != payload.channel:
        raise HTTPException(status_code=400, detail="Campaign channel must match template channel")
    campaign = _create_campaign(db, business_id=access.business.id, actor=actor, payload=payload)
    db.commit()
    db.refresh(campaign)
    return _campaign_out(campaign)


@router.get(
    "",
    response_model=CampaignListOut,
    summary="List campaigns",
    responses=error_responses(401, 403, 422, 500),
)
def list_campaigns(
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(Campaign.id)).where(Campaign.business_id == access.business.id)
    stmt = select(Campaign).where(Campaign.business_id == access.business.id)
    normalized_status = status.strip().lower() if status and status.strip() else None
    normalized_channel = channel.strip().lower() if channel and channel.strip() else None
    if normalized_status:
        count_stmt = count_stmt.where(Campaign.status == normalized_status)
        stmt = stmt.where(Campaign.status == normalized_status)
    if normalized_channel:
        count_stmt = count_stmt.where(Campaign.channel == normalized_channel)
        stmt = stmt.where(Campaign.channel == normalized_channel)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(stmt.order_by(Campaign.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    items = [_campaign_out(row) for row in rows]
    count = len(items)
    return CampaignListOut(
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


@router.post(
    "/{campaign_id}/dispatch",
    response_model=CampaignDispatchOut,
    summary="Dispatch queued campaign recipients",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def dispatch_campaign(
    campaign_id: str,
    payload: CampaignDispatchIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    campaign = _campaign_or_404(db, business_id=access.business.id, campaign_id=campaign_id)
    if campaign.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cancelled campaign cannot be dispatched")
    try:
        out = _dispatch_campaign(db, campaign=campaign, actor=actor, provider_name=payload.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return out


@router.get(
    "/{campaign_id}/recipients",
    response_model=CampaignRecipientListOut,
    summary="List campaign recipients",
    responses=error_responses(401, 403, 404, 422, 500),
)
def list_campaign_recipients(
    campaign_id: str,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    campaign = _campaign_or_404(db, business_id=access.business.id, campaign_id=campaign_id)
    count_stmt = select(func.count(CampaignRecipient.id)).where(CampaignRecipient.campaign_id == campaign.id)
    stmt = select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id)
    normalized_status = status.strip().lower() if status and status.strip() else None
    if normalized_status:
        count_stmt = count_stmt.where(CampaignRecipient.status == normalized_status)
        stmt = stmt.where(CampaignRecipient.status == normalized_status)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(CampaignRecipient.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [_recipient_out(row) for row in rows]
    count = len(items)
    return CampaignRecipientListOut(
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


@router.get(
    "/metrics",
    response_model=CampaignMetricsOut,
    summary="Campaign metrics summary",
    responses=error_responses(401, 403, 500),
)
def campaign_metrics(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    return _campaign_metrics(db, business_id=access.business.id)


@router.get(
    "/{campaign_id}/metrics",
    response_model=CampaignMetricsOut,
    summary="Campaign metrics by campaign id",
    responses=error_responses(401, 403, 404, 500),
)
def campaign_metrics_by_id(
    campaign_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    _campaign_or_404(db, business_id=access.business.id, campaign_id=campaign_id)
    return _campaign_metrics(db, business_id=access.business.id, campaign_id=campaign_id)


@router.post(
    "/retention-triggers",
    response_model=RetentionTriggerOut,
    summary="Create retention trigger",
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
def create_retention_trigger(
    payload: RetentionTriggerCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    if payload.segment_id:
        _segment_or_404(db, business_id=access.business.id, segment_id=payload.segment_id)
    template = _template_or_404(db, business_id=access.business.id, template_id=payload.template_id) if payload.template_id else None
    if template and template.channel != payload.channel:
        raise HTTPException(status_code=400, detail="Retention trigger channel must match template channel")

    trigger = RetentionTrigger(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        segment_id=payload.segment_id,
        template_id=payload.template_id,
        name=payload.name,
        trigger_type=payload.trigger_type,
        status=payload.status,
        channel=payload.channel,
        provider=payload.provider,
        config_json=payload.config_json,
        created_by_user_id=actor.id,
    )
    db.add(trigger)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="campaign.retention_trigger.create",
        target_type="retention_trigger",
        target_id=trigger.id,
        metadata_json={"name": trigger.name, "status": trigger.status},
    )
    db.commit()
    db.refresh(trigger)
    return _retention_trigger_out(trigger)


@router.get(
    "/retention-triggers",
    response_model=RetentionTriggerListOut,
    summary="List retention triggers",
    responses=error_responses(401, 403, 422, 500),
)
def list_retention_triggers(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    total = int(
        db.execute(
            select(func.count(RetentionTrigger.id)).where(
                RetentionTrigger.business_id == access.business.id
            )
        ).scalar_one()
    )
    rows = db.execute(
        select(RetentionTrigger)
        .where(RetentionTrigger.business_id == access.business.id)
        .order_by(RetentionTrigger.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    items = [_retention_trigger_out(row) for row in rows]
    count = len(items)
    return RetentionTriggerListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )


@router.post(
    "/retention-triggers/{trigger_id}/run",
    response_model=RetentionTriggerRunOut,
    summary="Run retention trigger now",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def run_retention_trigger(
    trigger_id: str,
    payload: RetentionTriggerRunRequestIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    trigger = _trigger_or_404(db, business_id=access.business.id, trigger_id=trigger_id)
    if trigger.status != "active":
        raise HTTPException(status_code=400, detail="Retention trigger is inactive")

    template = _template_or_404(db, business_id=access.business.id, template_id=trigger.template_id) if trigger.template_id else None
    if template and template.status != "approved":
        raise HTTPException(status_code=400, detail="Retention trigger template must be approved")

    fallback_content = (trigger.config_json or {}).get("message", "")
    if not template and not str(fallback_content).strip():
        raise HTTPException(status_code=400, detail="Retention trigger requires template or config_json.message")

    campaign_name = f"{trigger.name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
    campaign_payload = CampaignCreateIn(
        name=campaign_name,
        segment_id=trigger.segment_id,
        template_id=trigger.template_id,
        explicit_customer_ids=[],
        channel=trigger.channel,
        provider=trigger.provider,
        content_override=None if template else str(fallback_content),
        send_now=payload.auto_dispatch,
    )

    try:
        campaign = _create_campaign(
            db,
            business_id=access.business.id,
            actor=actor,
            payload=campaign_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rows = db.execute(
        select(CampaignRecipient.status, func.count(CampaignRecipient.id))
        .where(CampaignRecipient.campaign_id == campaign.id)
        .group_by(CampaignRecipient.status)
    ).all()
    counts = {status: int(count) for status, count in rows}
    processed_count = sum(counts.values())
    queued_count = counts.get("queued", 0)
    skipped_count = counts.get("suppressed", 0) + counts.get("skipped", 0)
    error_count = counts.get("failed", 0)

    trigger_run = RetentionTriggerRun(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        retention_trigger_id=trigger.id,
        campaign_id=campaign.id,
        status=campaign.status,
        processed_count=processed_count,
        queued_count=queued_count,
        skipped_count=skipped_count,
        error_count=error_count,
    )
    db.add(trigger_run)
    trigger.last_run_at = datetime.now(timezone.utc)

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="campaign.retention_trigger.run",
        target_type="retention_trigger",
        target_id=trigger.id,
        metadata_json={
            "run_id": trigger_run.id,
            "campaign_id": campaign.id,
            "campaign_status": campaign.status,
            "processed_count": processed_count,
        },
    )
    db.commit()
    db.refresh(trigger_run)
    return RetentionTriggerRunOut(
        id=trigger_run.id,
        retention_trigger_id=trigger_run.retention_trigger_id,
        campaign_id=trigger_run.campaign_id,
        status=trigger_run.status,
        processed_count=trigger_run.processed_count,
        queued_count=trigger_run.queued_count,
        skipped_count=trigger_run.skipped_count,
        error_count=trigger_run.error_count,
        created_at=trigger_run.created_at,
    )
