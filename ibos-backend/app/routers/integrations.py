import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.integration import (
    AppInstallation,
    IntegrationOutboxEvent,
    IntegrationSecret,
    OutboundMessage,
)
from app.models.user import User
from app.schemas.common import PaginationMeta
from app.schemas.integration import (
    AppInstallationIn,
    AppInstallationListOut,
    AppInstallationOut,
    IntegrationDispatchOut,
    IntegrationEmitOut,
    IntegrationEventEmitIn,
    IntegrationMessageListOut,
    IntegrationMessageOut,
    IntegrationMessageSendIn,
    IntegrationOutboxEventListOut,
    IntegrationOutboxEventOut,
    IntegrationSecretListOut,
    IntegrationSecretOut,
    IntegrationSecretUpsertIn,
)
from app.services.audit_service import log_audit_event
from app.services.integration_service import (
    dispatch_due_outbox_events,
    encrypt_secret,
    queue_outbox_event,
)
from app.services.messaging_provider import MessageSendRequest, get_messaging_provider

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _installation_out(installation: AppInstallation) -> AppInstallationOut:
    return AppInstallationOut(
        id=installation.id,
        app_key=installation.app_key,
        display_name=installation.display_name,
        status=installation.status,
        permissions=installation.permissions_json or [],
        config_json=installation.config_json,
        installed_at=installation.installed_at,
        disconnected_at=installation.disconnected_at,
        updated_at=installation.updated_at,
    )


def _outbox_event_out(event: IntegrationOutboxEvent) -> IntegrationOutboxEventOut:
    return IntegrationOutboxEventOut(
        id=event.id,
        event_type=event.event_type,
        target_app_key=event.target_app_key,
        status=event.status,
        attempt_count=event.attempt_count,
        max_attempts=event.max_attempts,
        next_attempt_at=event.next_attempt_at,
        last_error=event.last_error,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


@router.put(
    "/secrets",
    response_model=IntegrationSecretOut,
    summary="Upsert integration secret (with rotation)",
    responses=error_responses(400, 401, 403, 422, 500),
)
def upsert_integration_secret(
    payload: IntegrationSecretUpsertIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    secret = db.execute(
        select(IntegrationSecret).where(
            IntegrationSecret.business_id == access.business.id,
            func.lower(IntegrationSecret.provider) == payload.provider.lower(),
            func.lower(IntegrationSecret.key_name) == payload.key_name.lower(),
        )
    ).scalar_one_or_none()

    encrypted_value = encrypt_secret(payload.secret_value)
    now = datetime.now(timezone.utc)
    if not secret:
        secret = IntegrationSecret(
            id=str(uuid.uuid4()),
            business_id=access.business.id,
            provider=payload.provider.lower(),
            key_name=payload.key_name,
            secret_encrypted=encrypted_value,
            version=1,
            status="active",
            rotated_at=now,
        )
        db.add(secret)
        action = "integration.secret.create"
    else:
        secret.secret_encrypted = encrypted_value
        secret.version += 1
        secret.status = "active"
        secret.rotated_at = now
        action = "integration.secret.rotate"

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action=action,
        target_type="integration_secret",
        target_id=secret.id,
        metadata_json={
            "provider": secret.provider,
            "key_name": secret.key_name,
            "version": secret.version,
        },
    )
    db.commit()
    db.refresh(secret)
    return IntegrationSecretOut(
        id=secret.id,
        provider=secret.provider,
        key_name=secret.key_name,
        version=secret.version,
        status=secret.status,
        rotated_at=secret.rotated_at,
        created_at=secret.created_at,
        updated_at=secret.updated_at,
    )


@router.get(
    "/secrets",
    response_model=IntegrationSecretListOut,
    summary="List integration secrets metadata",
    responses=error_responses(401, 403, 500),
)
def list_integration_secrets(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
):
    rows = db.execute(
        select(IntegrationSecret)
        .where(IntegrationSecret.business_id == access.business.id)
        .order_by(IntegrationSecret.updated_at.desc())
    ).scalars().all()
    return IntegrationSecretListOut(
        items=[
            IntegrationSecretOut(
                id=item.id,
                provider=item.provider,
                key_name=item.key_name,
                version=item.version,
                status=item.status,
                rotated_at=item.rotated_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in rows
        ]
    )


@router.post(
    "/apps/install",
    response_model=AppInstallationOut,
    summary="Install (connect) app",
    responses=error_responses(400, 401, 403, 422, 500),
)
def install_app(
    payload: AppInstallationIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    existing = db.execute(
        select(AppInstallation).where(
            AppInstallation.business_id == access.business.id,
            func.lower(AppInstallation.app_key) == payload.app_key.lower(),
        )
    ).scalar_one_or_none()

    if not existing:
        installation = AppInstallation(
            id=str(uuid.uuid4()),
            business_id=access.business.id,
            app_key=payload.app_key.lower(),
            display_name=payload.display_name,
            status="connected",
            permissions_json=payload.permissions,
            config_json=payload.config_json,
            installed_at=datetime.now(timezone.utc),
            disconnected_at=None,
        )
        db.add(installation)
        action = "integration.app.install"
    else:
        existing.display_name = payload.display_name
        existing.permissions_json = payload.permissions
        existing.config_json = payload.config_json
        existing.status = "connected"
        existing.disconnected_at = None
        installation = existing
        action = "integration.app.reconnect"

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action=action,
        target_type="app_installation",
        target_id=installation.id,
        metadata_json={
            "app_key": installation.app_key,
            "permissions": installation.permissions_json or [],
            "status": installation.status,
        },
    )
    db.commit()
    db.refresh(installation)
    return _installation_out(installation)


@router.post(
    "/apps/{installation_id}/disconnect",
    response_model=AppInstallationOut,
    summary="Disconnect app",
    responses=error_responses(401, 403, 404, 500),
)
def disconnect_app(
    installation_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    installation = db.execute(
        select(AppInstallation).where(
            AppInstallation.id == installation_id,
            AppInstallation.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not installation:
        raise HTTPException(status_code=404, detail="App installation not found")

    installation.status = "disconnected"
    installation.disconnected_at = datetime.now(timezone.utc)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="integration.app.disconnect",
        target_type="app_installation",
        target_id=installation.id,
        metadata_json={"app_key": installation.app_key, "status": installation.status},
    )
    db.commit()
    db.refresh(installation)
    return _installation_out(installation)


@router.get(
    "/apps",
    response_model=AppInstallationListOut,
    summary="List app installations",
    responses=error_responses(401, 403, 500),
)
def list_app_installations(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    rows = db.execute(
        select(AppInstallation)
        .where(AppInstallation.business_id == access.business.id)
        .order_by(AppInstallation.updated_at.desc())
    ).scalars().all()
    return AppInstallationListOut(items=[_installation_out(row) for row in rows])


@router.post(
    "/outbox/emit",
    response_model=IntegrationEmitOut,
    summary="Emit integration outbox event",
    responses=error_responses(401, 403, 422, 500),
)
def emit_outbox_event(
    payload: IntegrationEventEmitIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    event = queue_outbox_event(
        db,
        business_id=access.business.id,
        event_type=payload.event_type,
        target_app_key=payload.target_app_key.lower(),
        payload_json=payload.payload_json,
    )
    db.commit()
    return IntegrationEmitOut(event_id=event.id)


@router.get(
    "/outbox/events",
    response_model=IntegrationOutboxEventListOut,
    summary="List outbox events",
    responses=error_responses(401, 403, 422, 500),
)
def list_outbox_events(
    status: str | None = Query(default=None),
    target_app_key: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(IntegrationOutboxEvent.id)).where(
        IntegrationOutboxEvent.business_id == access.business.id
    )
    stmt = select(IntegrationOutboxEvent).where(
        IntegrationOutboxEvent.business_id == access.business.id
    )
    if status:
        normalized = status.strip().lower()
        count_stmt = count_stmt.where(IntegrationOutboxEvent.status == normalized)
        stmt = stmt.where(IntegrationOutboxEvent.status == normalized)
        status = normalized
    if target_app_key:
        normalized_app = target_app_key.strip().lower()
        count_stmt = count_stmt.where(IntegrationOutboxEvent.target_app_key == normalized_app)
        stmt = stmt.where(IntegrationOutboxEvent.target_app_key == normalized_app)
        target_app_key = normalized_app

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(IntegrationOutboxEvent.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [_outbox_event_out(row) for row in rows]
    count = len(items)
    return IntegrationOutboxEventListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        status=status,
        target_app_key=target_app_key,
    )


@router.post(
    "/outbox/dispatch",
    response_model=IntegrationDispatchOut,
    summary="Dispatch due outbox events",
    responses=error_responses(401, 403, 500),
)
def dispatch_outbox(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
):
    summary = dispatch_due_outbox_events(
        db,
        business_id=access.business.id,
        limit=limit,
    )
    db.commit()
    return IntegrationDispatchOut(
        processed=summary.processed,
        delivered=summary.delivered,
        failed=summary.failed,
        dead_lettered=summary.dead_lettered,
    )


@router.post(
    "/messages/send",
    response_model=IntegrationMessageOut,
    summary="Send outbound message through messaging connector",
    responses=error_responses(400, 401, 403, 422, 500),
)
def send_message(
    payload: IntegrationMessageSendIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    whatsapp_connected = db.execute(
        select(AppInstallation.id).where(
            AppInstallation.business_id == access.business.id,
            AppInstallation.app_key == "whatsapp",
            AppInstallation.status == "connected",
        )
    ).scalar_one_or_none()
    if not whatsapp_connected:
        raise HTTPException(status_code=400, detail="WhatsApp connector is not connected")

    provider = get_messaging_provider(payload.provider)
    result = provider.send_message(
        MessageSendRequest(
            business_id=access.business.id,
            recipient=payload.recipient,
            content=payload.content,
        )
    )

    message = OutboundMessage(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        provider=result.provider,
        recipient=payload.recipient,
        content=payload.content,
        status=result.status,
        external_message_id=result.message_id,
        error_message=None,
    )
    db.add(message)
    queue_outbox_event(
        db,
        business_id=access.business.id,
        event_type="message.sent",
        target_app_key="whatsapp",
        payload_json={"provider": result.provider, "recipient": payload.recipient},
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="integration.message.send",
        target_type="outbound_message",
        target_id=message.id,
        metadata_json={"provider": result.provider, "recipient": payload.recipient, "status": result.status},
    )
    db.commit()
    db.refresh(message)
    return IntegrationMessageOut(
        id=message.id,
        provider=message.provider,
        recipient=message.recipient,
        content=message.content,
        status=message.status,
        external_message_id=message.external_message_id,
        error_message=message.error_message,
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


@router.get(
    "/messages",
    response_model=IntegrationMessageListOut,
    summary="List outbound messages",
    responses=error_responses(401, 403, 422, 500),
)
def list_messages(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(OutboundMessage.id)).where(OutboundMessage.business_id == access.business.id)
    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        select(OutboundMessage)
        .where(OutboundMessage.business_id == access.business.id)
        .order_by(OutboundMessage.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    items = [
        IntegrationMessageOut(
            id=item.id,
            provider=item.provider,
            recipient=item.recipient,
            content=item.content,
            status=item.status,
            external_message_id=item.external_message_id,
            error_message=item.error_message,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in rows
    ]
    count = len(items)
    return IntegrationMessageListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )
