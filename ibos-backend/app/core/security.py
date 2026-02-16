from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt

from app.core.config import settings

import bcrypt

ALGORITHM = "HS256"


class TokenValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TokenMetadata:
    subject: str
    token_type: str
    jti: str
    expires_at: datetime


def hash_password(password: str) -> str:
    # bcrypt hard limit is 72 bytes. We encode as utf-8.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def create_token(
    subject: str,
    expires_delta: timedelta,
    token_type: str,
    jti: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "jti": jti or str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str, *, expected_type: str | None = None) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise TokenValidationError("Invalid token") from exc

    subject = payload.get("sub")
    if not subject:
        raise TokenValidationError("Invalid token subject")

    token_type = payload.get("type")
    if expected_type and token_type != expected_type:
        raise TokenValidationError("Invalid token type")

    if not payload.get("jti"):
        raise TokenValidationError("Invalid token id")

    return payload


def get_token_metadata(token: str, *, expected_type: str | None = None) -> TokenMetadata:
    payload = decode_token(token, expected_type=expected_type)
    exp = payload.get("exp")
    if not exp:
        raise TokenValidationError("Invalid token expiration")
    return TokenMetadata(
        subject=str(payload["sub"]),
        token_type=str(payload["type"]),
        jti=str(payload["jti"]),
        expires_at=datetime.fromtimestamp(int(exp), tz=timezone.utc),
    )


def create_access_token(user_id: str) -> str:
    return create_token(
        subject=user_id,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        token_type="access",
    )

def create_refresh_token(user_id: str) -> str:
    return create_token(
        subject=user_id,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        token_type="refresh",
    )
