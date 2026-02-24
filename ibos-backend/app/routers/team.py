import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.business_membership import BusinessMembership
from app.models.team_invitation import TeamInvitation
from app.models.user import User
from app.schemas.common import PaginationMeta
from app.schemas.team import (
    TeamInvitationAcceptIn,
    TeamInvitationCreateIn,
    TeamInvitationCreateOut,
    TeamInvitationListOut,
    TeamInvitationOut,
    TeamMemberCreateIn,
    TeamMemberListOut,
    TeamMemberOut,
    TeamMemberUpdateIn,
)
from app.services.audit_service import log_audit_event
from app.services.team_invitation_service import (
    generate_team_invitation_token,
    hash_team_invitation_token,
)

router = APIRouter(prefix="/team", tags=["team"])


def _member_out(membership: BusinessMembership, user: User) -> TeamMemberOut:
    return TeamMemberOut(
        membership_id=membership.id,
        user_id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=membership.role,
        is_active=membership.is_active,
        created_at=membership.created_at,
    )


def _membership_in_business(
    db: Session,
    *,
    business_id: str,
    membership_id: str,
) -> tuple[BusinessMembership, User] | None:
    row = db.execute(
        select(BusinessMembership, User)
        .join(User, User.id == BusinessMembership.user_id)
        .where(
            BusinessMembership.id == membership_id,
            BusinessMembership.business_id == business_id,
        )
    ).first()
    if not row:
        return None
    return row[0], row[1]


def _invitation_out(invitation: TeamInvitation) -> TeamInvitationOut:
    return TeamInvitationOut(
        invitation_id=invitation.id,
        business_id=invitation.business_id,
        invited_by_user_id=invitation.invited_by_user_id,
        accepted_by_user_id=invitation.accepted_by_user_id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
        invited_at=invitation.invited_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
    )


def _is_invitation_expired(invitation: TeamInvitation) -> bool:
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def _resolve_pending_invitation_by_token(db: Session, invitation_token: str) -> TeamInvitation:
    invitation = db.execute(
        select(TeamInvitation).where(
            TeamInvitation.token_hash == hash_team_invitation_token(invitation_token)
        )
    ).scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if invitation.status != "pending" or invitation.revoked_at is not None:
        raise HTTPException(status_code=400, detail="Invitation is no longer active")

    if _is_invitation_expired(invitation):
        invitation.status = "expired"
        raise HTTPException(status_code=400, detail="Invitation has expired")

    return invitation


def _enforce_manage_rules(
    *,
    actor_access: BusinessAccess,
    actor_user_id: str,
    target_membership: BusinessMembership,
    new_role: str | None,
    new_is_active: bool | None,
) -> None:
    actor_role = actor_access.role.lower()
    target_role = (target_membership.role or "").lower()

    if target_membership.user_id == actor_user_id and new_is_active is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own membership")

    if target_role == "owner" and actor_role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can modify owner memberships")

    if actor_role == "admin":
        if target_role in {"owner", "admin"} and target_membership.user_id != actor_user_id:
            raise HTTPException(status_code=403, detail="Admins cannot modify owner/admin memberships")
        if new_role in {"owner", "admin"}:
            raise HTTPException(status_code=403, detail="Admins cannot assign owner/admin roles")

    if new_role == "owner" and actor_role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can assign owner role")

    if target_role == "owner" and new_is_active is False:
        raise HTTPException(status_code=400, detail="Owner memberships cannot be deactivated")


@router.get(
    "/members",
    response_model=TeamMemberListOut,
    summary="List team memberships",
    responses={**error_responses(401, 403, 422, 500)},
)
def list_team_members(
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
):
    count_stmt = select(func.count(BusinessMembership.id)).where(
        BusinessMembership.business_id == access.business.id
    )
    data_stmt = (
        select(BusinessMembership, User)
        .join(User, User.id == BusinessMembership.user_id)
        .where(BusinessMembership.business_id == access.business.id)
    )
    if not include_inactive:
        count_stmt = count_stmt.where(BusinessMembership.is_active.is_(True))
        data_stmt = data_stmt.where(BusinessMembership.is_active.is_(True))

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        data_stmt.order_by(BusinessMembership.created_at.asc()).offset(offset).limit(limit)
    ).all()

    items = [_member_out(membership, user) for membership, user in rows]
    count = len(items)
    return TeamMemberListOut(
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
    "/invitations",
    response_model=TeamInvitationCreateOut,
    summary="Create team invitation",
    responses={**error_responses(400, 401, 403, 409, 422, 500)},
)
def create_team_invitation(
    payload: TeamInvitationCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    requested_role = payload.role.lower()
    if access.role == "admin" and requested_role in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Admins cannot invite owner/admin roles")

    normalized_email = payload.email.lower().strip()
    existing_member = db.execute(
        select(BusinessMembership)
        .join(User, User.id == BusinessMembership.user_id)
        .where(
            BusinessMembership.business_id == access.business.id,
            BusinessMembership.is_active.is_(True),
            func.lower(User.email) == normalized_email,
        )
    ).scalar_one_or_none()
    if existing_member:
        raise HTTPException(status_code=409, detail="User is already an active team member")

    now = datetime.now(timezone.utc)
    pending_invite = db.execute(
        select(TeamInvitation).where(
            TeamInvitation.business_id == access.business.id,
            func.lower(TeamInvitation.email) == normalized_email,
            TeamInvitation.status == "pending",
        )
    ).scalar_one_or_none()
    if pending_invite:
        if _is_invitation_expired(pending_invite):
            pending_invite.status = "expired"
        else:
            raise HTTPException(status_code=409, detail="An active invitation already exists for this email")

    raw_token = generate_team_invitation_token()
    invitation = TeamInvitation(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        invited_by_user_id=actor.id,
        email=normalized_email,
        role=requested_role,
        token_hash=hash_team_invitation_token(raw_token),
        status="pending",
        expires_at=now + timedelta(days=payload.expires_in_days),
    )
    db.add(invitation)

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="team.invitation.created",
        target_type="team_invitation",
        target_id=invitation.id,
        metadata_json={
            "email": normalized_email,
            "role": requested_role,
            "expires_in_days": payload.expires_in_days,
        },
    )
    db.commit()
    db.refresh(invitation)
    return TeamInvitationCreateOut(
        **_invitation_out(invitation).model_dump(),
        invitation_token=raw_token,
    )


@router.get(
    "/invitations",
    response_model=TeamInvitationListOut,
    summary="List team invitations",
    responses={**error_responses(401, 403, 422, 500)},
)
def list_team_invitations(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
):
    now = datetime.now(timezone.utc)
    db.execute(
        update(TeamInvitation)
        .where(
            TeamInvitation.business_id == access.business.id,
            TeamInvitation.status == "pending",
            TeamInvitation.expires_at <= now,
        )
        .values(status="expired")
    )
    db.commit()

    count_stmt = select(func.count(TeamInvitation.id)).where(
        TeamInvitation.business_id == access.business.id
    )
    data_stmt = select(TeamInvitation).where(TeamInvitation.business_id == access.business.id)
    if status_filter:
        normalized_status = status_filter.strip().lower()
        count_stmt = count_stmt.where(TeamInvitation.status == normalized_status)
        data_stmt = data_stmt.where(TeamInvitation.status == normalized_status)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        data_stmt.order_by(TeamInvitation.invited_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [_invitation_out(item) for item in rows]
    count = len(items)
    return TeamInvitationListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
    )


@router.delete(
    "/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke team invitation",
    responses={**error_responses(400, 401, 403, 404, 500)},
)
def revoke_team_invitation(
    invitation_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    invitation = db.execute(
        select(TeamInvitation).where(
            TeamInvitation.id == invitation_id,
            TeamInvitation.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending invitations can be revoked")

    invitation.status = "revoked"
    invitation.revoked_at = datetime.now(timezone.utc)

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="team.invitation.revoked",
        target_type="team_invitation",
        target_id=invitation.id,
        metadata_json={"email": invitation.email, "role": invitation.role},
    )
    db.commit()
    return None


@router.post(
    "/invitations/accept",
    response_model=TeamMemberOut,
    summary="Accept invitation for current user",
    responses={**error_responses(400, 401, 403, 404, 409, 422, 500)},
)
def accept_team_invitation(
    payload: TeamInvitationAcceptIn,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    invitation = _resolve_pending_invitation_by_token(db, payload.invitation_token)
    if invitation.email.lower() != actor.email.lower():
        raise HTTPException(status_code=403, detail="Invitation email does not match your account")

    membership = db.execute(
        select(BusinessMembership).where(
            BusinessMembership.business_id == invitation.business_id,
            BusinessMembership.user_id == actor.id,
        )
    ).scalar_one_or_none()

    if membership and membership.is_active:
        raise HTTPException(status_code=409, detail="You are already an active team member")

    if membership:
        previous_state = {"role": membership.role, "is_active": membership.is_active}
        membership.role = invitation.role
        membership.is_active = True
    else:
        previous_state = None
        membership = BusinessMembership(
            id=str(uuid.uuid4()),
            business_id=invitation.business_id,
            user_id=actor.id,
            role=invitation.role,
            is_active=True,
        )
        db.add(membership)

    now = datetime.now(timezone.utc)
    invitation.status = "accepted"
    invitation.accepted_by_user_id = actor.id
    invitation.accepted_at = now

    log_audit_event(
        db,
        business_id=invitation.business_id,
        actor_user_id=actor.id,
        action="team.invitation.accepted",
        target_type="team_invitation",
        target_id=invitation.id,
        metadata_json={
            "email": invitation.email,
            "role": invitation.role,
            "membership_previous": previous_state,
            "membership_next": {"role": membership.role, "is_active": membership.is_active},
        },
    )

    db.commit()
    db.refresh(membership)
    return _member_out(membership, actor)


@router.post(
    "/members",
    response_model=TeamMemberOut,
    summary="Add team member",
    responses={**error_responses(400, 401, 403, 404, 409, 422, 500)},
)
def add_team_member(
    payload: TeamMemberCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    target_user = db.execute(
        select(User).where(func.lower(User.email) == payload.email.lower())
    ).scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if access.role == "admin" and payload.role in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Admins cannot assign owner/admin roles")

    existing = db.execute(
        select(BusinessMembership).where(
            BusinessMembership.business_id == access.business.id,
            BusinessMembership.user_id == target_user.id,
        )
    ).scalar_one_or_none()
    if existing and existing.is_active:
        raise HTTPException(status_code=409, detail="User is already an active team member")

    if existing:
        previous_state = {"role": existing.role, "is_active": existing.is_active}
        existing.role = payload.role
        existing.is_active = True
        membership = existing
        action = "team.member.reactivated"
    else:
        membership = BusinessMembership(
            id=str(uuid.uuid4()),
            business_id=access.business.id,
            user_id=target_user.id,
            role=payload.role,
            is_active=True,
        )
        db.add(membership)
        previous_state = None
        action = "team.member.added"

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action=action,
        target_type="business_membership",
        target_id=membership.id,
        metadata_json={
            "user_id": target_user.id,
            "email": target_user.email,
            "previous": previous_state,
            "next": {"role": membership.role, "is_active": membership.is_active},
        },
    )
    db.commit()
    db.refresh(membership)
    return _member_out(membership, target_user)


@router.patch(
    "/members/{membership_id}",
    response_model=TeamMemberOut,
    summary="Update team member",
    responses={**error_responses(400, 401, 403, 404, 422, 500)},
)
def update_team_member(
    membership_id: str,
    payload: TeamMemberUpdateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    membership_with_user = _membership_in_business(
        db, business_id=access.business.id, membership_id=membership_id
    )
    if not membership_with_user:
        raise HTTPException(status_code=404, detail="Membership not found")
    membership, member_user = membership_with_user

    _enforce_manage_rules(
        actor_access=access,
        actor_user_id=actor.id,
        target_membership=membership,
        new_role=payload.role,
        new_is_active=payload.is_active,
    )

    previous_state = {"role": membership.role, "is_active": membership.is_active}
    if payload.role is not None:
        membership.role = payload.role
    if payload.is_active is not None:
        membership.is_active = payload.is_active

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="team.member.updated",
        target_type="business_membership",
        target_id=membership.id,
        metadata_json={
            "user_id": member_user.id,
            "email": member_user.email,
            "previous": previous_state,
            "next": {"role": membership.role, "is_active": membership.is_active},
        },
    )
    db.commit()
    db.refresh(membership)
    return _member_out(membership, member_user)


@router.delete(
    "/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate team member",
    responses={**error_responses(400, 401, 403, 404, 500)},
)
def deactivate_team_member(
    membership_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    membership_with_user = _membership_in_business(
        db, business_id=access.business.id, membership_id=membership_id
    )
    if not membership_with_user:
        raise HTTPException(status_code=404, detail="Membership not found")
    membership, member_user = membership_with_user

    _enforce_manage_rules(
        actor_access=access,
        actor_user_id=actor.id,
        target_membership=membership,
        new_role=None,
        new_is_active=False,
    )
    if not membership.is_active:
        return None

    previous_state = {"role": membership.role, "is_active": membership.is_active}
    membership.is_active = False
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="team.member.deactivated",
        target_type="business_membership",
        target_id=membership.id,
        metadata_json={
            "user_id": member_user.id,
            "email": member_user.email,
            "previous": previous_state,
            "next": {"role": membership.role, "is_active": membership.is_active},
        },
    )
    db.commit()
    return None
