import hashlib
import secrets

from app.core.config import settings


def generate_team_invitation_token() -> str:
    return f"ti_{secrets.token_urlsafe(24)}"


def hash_team_invitation_token(raw_token: str) -> str:
    token_material = f"{settings.secret_key}:{(raw_token or '').strip()}"
    return hashlib.sha256(token_material.encode("utf-8")).hexdigest()
