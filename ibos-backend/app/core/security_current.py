from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.security import TokenValidationError, decode_token
from app.models.business import Business
from app.models.business_membership import BusinessMembership
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


@dataclass(frozen=True)
class BusinessAccess:
    business: Business
    role: str
    membership_id: str | None


def _membership_role_rank():
    return case(
        (BusinessMembership.role == "owner", 0),
        (BusinessMembership.role == "admin", 1),
        (BusinessMembership.role == "staff", 2),
        else_=3,
    )


def _resolve_business_access(db: Session, user_id: str) -> BusinessAccess | None:
    row = db.execute(
        select(BusinessMembership, Business)
        .join(Business, Business.id == BusinessMembership.business_id)
        .where(
            BusinessMembership.user_id == user_id,
            BusinessMembership.is_active.is_(True),
        )
        .order_by(_membership_role_rank(), BusinessMembership.created_at.asc())
        .limit(1)
    ).first()

    if row:
        membership, business = row
        role = (membership.role or "staff").lower()
        return BusinessAccess(business=business, role=role, membership_id=membership.id)

    # Backward-compatible fallback while old owner-only linkage still exists.
    legacy_business = db.execute(
        select(Business).where(Business.owner_user_id == user_id)
    ).scalar_one_or_none()
    if legacy_business:
        return BusinessAccess(business=legacy_business, role="owner", membership_id=None)

    return None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token, expected_type="access")
    except TokenValidationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user_id = payload.get("sub")
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_business_access(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> BusinessAccess:
    access = _resolve_business_access(db, user.id)
    if not access:
        raise HTTPException(status_code=404, detail="Business not found")
    return access


def get_current_business(access: BusinessAccess = Depends(get_current_business_access)) -> Business:
    return access.business
