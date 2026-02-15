from dataclasses import dataclass

from app.core.config import settings


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    full_name: str | None


def verify_google_identity_token(raw_id_token: str) -> GoogleIdentity:
    if not settings.google_client_id:
        raise ValueError("GOOGLE_CLIENT_ID is not configured")

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
    except ImportError as exc:
        raise ValueError("google-auth dependency is not installed") from exc

    try:
        token_info = google_id_token.verify_oauth2_token(
            raw_id_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except Exception as exc:
        raise ValueError("Invalid Google ID token") from exc

    sub = token_info.get("sub")
    email = token_info.get("email")
    email_verified = token_info.get("email_verified")
    full_name = token_info.get("name")

    if not sub:
        raise ValueError("Google token missing subject")
    if not email:
        raise ValueError("Google token missing email")
    if email_verified is not True:
        raise ValueError("Google email is not verified")

    return GoogleIdentity(
        sub=str(sub),
        email=str(email).lower(),
        full_name=str(full_name) if full_name else None,
    )
