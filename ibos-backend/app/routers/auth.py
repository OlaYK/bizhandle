import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.config import settings
from app.core.deps import get_db
from app.core.google_auth import verify_google_identity_token
from app.core.id_utils import generate_short_token
from app.core.rate_limit import LoginRateLimiter
from app.core.security import (
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    get_token_metadata,
    hash_password,
    verify_password,
)
from app.core.security_current import get_current_user
from app.models.business import Business
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordIn,
    GoogleAuthIn,
    LoginIn,
    LogoutIn,
    RefreshIn,
    RegisterIn,
    TokenOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])
TOKEN_PAIR_RESPONSE = {
    200: {
        "description": "Access and refresh tokens",
        "content": {
            "application/json": {
                "example": {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "token_type": "bearer",
                }
            }
        },
    }
}

login_rate_limiter = LoginRateLimiter(
    max_attempts=settings.auth_rate_limit_max_attempts,
    window_seconds=settings.auth_rate_limit_window_seconds,
    lock_seconds=settings.auth_rate_limit_lock_seconds,
)


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


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_key(identifier: str, client_ip: str) -> str:
    return f"{identifier.strip().lower()}:{client_ip}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _enforce_rate_limit(identifier: str, client_ip: str) -> str:
    key = _rate_key(identifier, client_ip)
    retry_after = login_rate_limiter.check(key)
    if retry_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    return key


def _authenticate_user(db: Session, identifier: str, password: str) -> User:
    normalized_identifier = identifier.strip().lower()
    user = db.execute(
        select(User).where(
            or_(
                func.lower(User.email) == normalized_identifier,
                func.lower(User.username) == normalized_identifier,
            )
        )
    ).scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return user


def _issue_token_pair(
    db: Session, *, user_id: str, client_ip: str | None = None
) -> tuple[TokenOut, str]:
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)
    refresh_meta = get_token_metadata(refresh_token, expected_type="refresh")

    db.add(
        RefreshToken(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token_jti=refresh_meta.jti,
            expires_at=refresh_meta.expires_at,
            created_by_ip=client_ip,
        )
    )

    return (
        TokenOut(access_token=access_token, refresh_token=refresh_token),
        refresh_meta.jti,
    )


@router.post(
    "/register",
    response_model=TokenOut,
    summary="Register a user",
    description="Creates a user and default business, then returns access + refresh tokens.",
    responses={**TOKEN_PAIR_RESPONSE, **error_responses(400, 422, 500)},
)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
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
    token_pair, _ = _issue_token_pair(db, user_id=user.id, client_ip=_client_ip(request))
    db.commit()
    return token_pair


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Login with JSON",
    description="Authenticate with email/username and password.",
    responses={**TOKEN_PAIR_RESPONSE, **error_responses(401, 422, 429, 500)},
)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = _enforce_rate_limit(payload.identifier, _client_ip(request))
    try:
        user = _authenticate_user(db, payload.identifier, payload.password)
    except HTTPException as exc:
        if exc.status_code == 401:
            login_rate_limiter.register_failure(key)
        raise

    login_rate_limiter.register_success(key)
    token_pair, _ = _issue_token_pair(db, user_id=user.id, client_ip=_client_ip(request))
    db.commit()
    return token_pair


@router.post(
    "/token",
    response_model=TokenOut,
    summary="OAuth2 password token (Swagger Authorize)",
    description=(
        "Form-data login endpoint used by Swagger Authorize. "
        "Use your email or username in the `username` field."
    ),
    responses={**TOKEN_PAIR_RESPONSE, **error_responses(401, 422, 429, 500)},
)
def login_for_swagger(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    key = _enforce_rate_limit(form_data.username, _client_ip(request))
    try:
        user = _authenticate_user(db, form_data.username, form_data.password)
    except HTTPException as exc:
        if exc.status_code == 401:
            login_rate_limiter.register_failure(key)
        raise

    login_rate_limiter.register_success(key)
    token_pair, _ = _issue_token_pair(db, user_id=user.id, client_ip=_client_ip(request))
    db.commit()
    return token_pair


@router.post(
    "/google",
    response_model=TokenOut,
    summary="Login/Register with Google",
    description="Verifies Google ID token and returns access + refresh tokens.",
    responses={**TOKEN_PAIR_RESPONSE, **error_responses(400, 401, 422, 500)},
)
def google_auth(payload: GoogleAuthIn, request: Request, db: Session = Depends(get_db)):
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
    token_pair, _ = _issue_token_pair(db, user_id=user.id, client_ip=_client_ip(request))
    db.commit()
    return token_pair


@router.post(
    "/refresh",
    response_model=TokenOut,
    summary="Refresh access token",
    description="Uses a valid refresh token to issue a fresh token pair.",
    responses={**TOKEN_PAIR_RESPONSE, **error_responses(401, 422, 500)},
)
def refresh_tokens(payload: RefreshIn, request: Request, db: Session = Depends(get_db)):
    try:
        refresh_meta = get_token_metadata(payload.refresh_token, expected_type="refresh")
    except TokenValidationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    token_row = db.execute(
        select(RefreshToken).where(
            and_(
                RefreshToken.token_jti == refresh_meta.jti,
                RefreshToken.user_id == refresh_meta.subject,
            )
        )
    ).scalar_one_or_none()
    expires_at = _as_utc(token_row.expires_at) if token_row else None
    if not token_row or token_row.revoked_at is not None or not expires_at or expires_at <= now:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired")

    token_row.revoked_at = now
    token_pair, new_jti = _issue_token_pair(
        db, user_id=refresh_meta.subject, client_ip=_client_ip(request)
    )
    token_row.replaced_by_jti = new_jti
    db.commit()
    return token_pair


@router.post(
    "/logout",
    summary="Logout (revoke refresh token)",
    description="Revokes the provided refresh token.",
    responses=error_responses(422, 500),
)
def logout(payload: LogoutIn, db: Session = Depends(get_db)):
    try:
        refresh_meta = get_token_metadata(payload.refresh_token, expected_type="refresh")
    except TokenValidationError:
        return {"ok": True}

    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_jti == refresh_meta.jti,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()
    return {"ok": True}


@router.post(
    "/change-password",
    summary="Change password",
    description="Changes password and revokes all active refresh tokens for the user.",
    responses=error_responses(400, 401, 422, 500),
)
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different")

    user.hashed_password = hash_password(payload.new_password)
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()
    return {"ok": True}
