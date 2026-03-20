import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

_REDACTED_KEY_FRAGMENTS = {
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "signature",
    "api_key",
    "client_secret",
    "private_key",
    "refresh_token",
    "access_token",
    "webhook_secret",
}
_MASKED_KEY_FRAGMENTS = {
    "email",
    "phone",
    "payment_reference",
    "idempotency_key",
    "recipient",
}


def _mask_email(value: str) -> str:
    cleaned = value.strip()
    if "@" not in cleaned:
        return "***"
    local, domain = cleaned.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "*"
    else:
        masked_local = local[:1] + "*" * max(len(local) - 2, 1) + local[-1:]
    return f"{masked_local}@{domain}"


def _mask_phone(value: str) -> str:
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"{digits[:2]}***{digits[-2:]}"


def _mask_reference(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) <= 4:
        return "***"
    return f"{cleaned[:2]}***{cleaned[-2:]}"


def sanitize_audit_metadata(metadata_json: Any) -> Any:
    if isinstance(metadata_json, dict):
        sanitized: dict[str, Any] = {}
        for key, value in metadata_json.items():
            normalized_key = str(key or "").strip().lower()
            if any(fragment in normalized_key for fragment in _REDACTED_KEY_FRAGMENTS):
                sanitized[key] = "<redacted>"
                continue
            if any(fragment in normalized_key for fragment in _MASKED_KEY_FRAGMENTS):
                if value is None:
                    sanitized[key] = None
                elif "email" in normalized_key:
                    sanitized[key] = _mask_email(str(value))
                elif "phone" in normalized_key:
                    sanitized[key] = _mask_phone(str(value))
                else:
                    sanitized[key] = _mask_reference(str(value))
                continue
            sanitized[key] = sanitize_audit_metadata(value)
        return sanitized
    if isinstance(metadata_json, list):
        return [sanitize_audit_metadata(item) for item in metadata_json]
    if isinstance(metadata_json, str):
        return metadata_json if len(metadata_json) <= 255 else metadata_json[:252] + "..."
    return metadata_json


def build_audit_target_label(
    *,
    target_type: str,
    target_id: str | None,
    metadata_json: dict[str, Any] | None,
) -> str | None:
    metadata = metadata_json or {}
    for key in ("location_name", "customer_name", "product_name", "name", "title"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    normalized_target = target_type.replace("_", " ").strip().title()
    if target_id:
        return f"{normalized_target} {target_id[:8]}"
    return normalized_target or None


def build_audit_summary(
    *,
    action: str,
    target_type: str,
    target_id: str | None,
    metadata_json: dict[str, Any] | None,
) -> str:
    normalized_action = action.replace(".", " ").replace("_", " ").strip().title()
    target_label = build_audit_target_label(
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata_json,
    )
    if target_label:
        return f"{normalized_action} on {target_label}"
    return normalized_action


def build_audit_metadata_preview(metadata_json: dict[str, Any] | None) -> list[str]:
    if not metadata_json:
        return []
    preview: list[str] = []
    for key, value in metadata_json.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            preview.append(f"{key}: {value}")
        elif isinstance(value, list):
            preview.append(f"{key}: {len(value)} item(s)")
        elif isinstance(value, dict):
            preview.append(f"{key}: {len(value)} field(s)")
        if len(preview) >= 5:
            break
    return preview


def log_audit_event(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> AuditLog:
    sanitized_metadata = sanitize_audit_metadata(metadata_json)
    event = AuditLog(
        id=str(uuid.uuid4()),
        business_id=business_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=sanitized_metadata,
    )
    db.add(event)
    return event
