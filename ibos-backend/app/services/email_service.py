from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
import smtplib
from typing import Literal

from app.core.config import settings

EmailDeliveryStatus = Literal["sent", "not_configured", "failed"]


@dataclass(frozen=True)
class EmailDeliveryResult:
    status: EmailDeliveryStatus
    detail: str | None = None


def _smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_sender_email)


def _build_team_invite_body(
    *,
    business_name: str,
    inviter_name: str,
    invitee_role: str,
    invitation_token: str,
    expires_at: datetime,
    invite_link: str | None,
) -> str:
    lines = [
        f"You have been invited to join {business_name} on MoniDesk.",
        "",
        f"Invited by: {inviter_name}",
        f"Role: {invitee_role}",
        f"Expires: {expires_at.isoformat()}",
        "",
    ]
    if invite_link:
        lines.append(f"Accept invitation: {invite_link}")
    else:
        lines.append("Use this invitation token on the registration page:")
        lines.append(invitation_token)
    lines.append("")
    lines.append("If you were not expecting this invitation, you can ignore this email.")
    return "\n".join(lines)


def send_team_invitation_email(
    *,
    recipient_email: str,
    business_name: str,
    inviter_name: str,
    invitee_role: str,
    invitation_token: str,
    expires_at: datetime,
    invite_link: str | None,
) -> EmailDeliveryResult:
    if not _smtp_configured():
        return EmailDeliveryResult(
            status="not_configured",
            detail="SMTP not configured",
        )

    message = EmailMessage()
    message["Subject"] = f"Invitation to join {business_name} on MoniDesk"
    message["From"] = settings.smtp_sender_email
    message["To"] = recipient_email
    if settings.smtp_reply_to_email:
        message["Reply-To"] = settings.smtp_reply_to_email
    message.set_content(
        _build_team_invite_body(
            business_name=business_name,
            inviter_name=inviter_name,
            invitee_role=invitee_role,
            invitation_token=invitation_token,
            expires_at=expires_at,
            invite_link=invite_link,
        )
    )

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=20,
            ) as server:
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password or "")
                server.send_message(message)
        else:
            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=20,
            ) as server:
                if settings.smtp_use_starttls:
                    server.starttls()
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password or "")
                server.send_message(message)
    except Exception as exc:  # noqa: BLE001 - expose short status back to caller
        return EmailDeliveryResult(status="failed", detail=str(exc))

    return EmailDeliveryResult(status="sent", detail=None)
