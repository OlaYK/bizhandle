import re
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select

from app.core.deps import get_db
from app.core.google_auth import verify_google_identity_token
from app.core.id_utils import generate_short_token
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.user import User
from app.models.business import Business
from app.schemas.auth import GoogleAuthIn, LoginIn, RegisterIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify_username(seed: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", seed.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        return "user"
    return cleaned[:30]


def _username_exists(db: Session, username: str) -> bool:
    found = db.execute(
        select(User.id).where(func.lower(User.username) == username.lower())
    ).scalar_one_or_none()
    return found is not None


def _generate_unique_username(
    db: Session,
    preferred_username: str | None,
    fallback_seed: str,
) -> str:
    base = _slugify_username(preferred_username or fallback_seed)
    candidate = base
    while _username_exists(db, candidate):
        candidate = f"{base[:22]}_{generate_short_token(6)}"
    return candidate


def _ensure_business(db: Session, user_id: str, business_name: str | None) -> None:
    existing = db.execute(
        select(Business).where(Business.owner_user_id == user_id)
    ).scalar_one_or_none()
    if existing:
        return

    name = (business_name or "").strip() or "My Business"
    db.add(Business(id=str(uuid.uuid4()), owner_user_id=user_id, name=name))


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    normalized_email = payload.email.lower()
    exists = db.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    username = _generate_unique_username(
        db,
        preferred_username=payload.username,
        fallback_seed=normalized_email.split("@")[0],
    )

    user = User(
        email=normalized_email,
        username=username,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    _ensure_business(db, user.id, payload.business_name)
    db.commit()

    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """
    Login with identifier (email or username) and password using JSON.
    """
    return _authenticate(db, payload.identifier, payload.password)


from fastapi.security import OAuth2PasswordRequestForm


@router.post("/token", response_model=TokenOut, include_in_schema=False)
def login_for_swagger(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Helper endpoint for Swagger's 'Authorize' button (uses Form Data).
    """
    return _authenticate(db, form_data.username, form_data.password)


def _authenticate(db: Session, identifier: str, password: str):
    identifier = identifier.strip().lower()
    user = db.execute(
        select(User).where(
            or_(
                func.lower(User.email) == identifier,
                func.lower(User.username) == identifier,
            )
        )
    ).scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/google", response_model=TokenOut)
def google_auth(payload: GoogleAuthIn, db: Session = Depends(get_db)):
    try:
        identity = verify_google_identity_token(payload.id_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = db.execute(
        select(User).where(
            or_(
                User.google_sub == identity.sub,
                func.lower(User.email) == identity.email.lower(),
            )
        )
    ).scalar_one_or_none()

    if user and user.google_sub and user.google_sub != identity.sub:
        raise HTTPException(status_code=401, detail="Google account mismatch")

    if not user:
        username = _generate_unique_username(
            db,
            preferred_username=payload.username,
            fallback_seed=identity.email.split("@")[0],
        )
        user = User(
            email=identity.email,
            username=username,
            full_name=identity.full_name,
            google_sub=identity.sub,
            hashed_password=hash_password(generate_short_token(24)),
        )
        db.add(user)
        db.flush()
    else:
        if not user.google_sub:
            user.google_sub = identity.sub
        if identity.full_name and not user.full_name:
            user.full_name = identity.full_name

    default_biz_name = (
        payload.business_name
        or (f"{identity.full_name}'s Business" if identity.full_name else "My Business")
    )
    _ensure_business(db, user.id, default_biz_name)

    db.commit()

    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )
