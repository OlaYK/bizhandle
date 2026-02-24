from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.core.security_current import BusinessAccess, get_current_business_access


def require_business_roles(*allowed_roles: str) -> Callable[[BusinessAccess], BusinessAccess]:
    normalized_allowed = {role.strip().lower() for role in allowed_roles if role.strip()}
    if not normalized_allowed:
        raise ValueError("At least one allowed role is required")

    def dependency(access: BusinessAccess = Depends(get_current_business_access)) -> BusinessAccess:
        current_role = (access.role or "").lower()
        if current_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this action",
            )
        return access

    return dependency


RBAC_V2_PERMISSION_MATRIX: dict[str, set[str]] = {
    "owner": {"*"},
    "admin": {
        "analytics.view",
        "analytics.refresh",
        "analytics.report.export",
        "analytics.report.schedule",
        "marketing.attribution.ingest",
        "pos.offline.sync",
        "pos.shift.manage",
        "privacy.customer.export",
        "privacy.customer.delete",
        "privacy.audit.archive",
        "audit.view",
        "ai.feature_store.refresh",
        "ai.feature_store.view",
        "ai.analytics.assistant.query",
        "ai.insights.v2.generate",
        "ai.insights.v2.view",
        "ai.risk_alerts.config.manage",
        "ai.risk_alerts.config.view",
        "ai.risk_alerts.run",
        "ai.risk_alerts.events.view",
        "ai.governance.view",
        "ai.actions.view",
        "ai.actions.review",
        "credit.profile.v2.view",
        "credit.forecast.view",
        "credit.scenario.simulate",
        "credit.export_pack.generate",
        "credit.guardrails.view",
        "credit.guardrails.manage",
        "credit.improvement.plan.view",
    },
    "staff": {
        "analytics.view",
        "analytics.report.export",
        "pos.offline.sync",
        "pos.shift.manage",
        "privacy.customer.export",
        "ai.feature_store.view",
        "ai.analytics.assistant.query",
        "ai.insights.v2.generate",
        "ai.insights.v2.view",
        "ai.risk_alerts.config.view",
        "ai.risk_alerts.events.view",
        "credit.profile.v2.view",
        "credit.forecast.view",
        "credit.scenario.simulate",
        "credit.export_pack.generate",
        "credit.guardrails.view",
        "credit.improvement.plan.view",
        "ai.actions.view",
    },
}


def role_permissions(role: str) -> set[str]:
    normalized = (role or "").strip().lower()
    return set(RBAC_V2_PERMISSION_MATRIX.get(normalized, set()))


def has_permission(*, role: str, permission: str) -> bool:
    permissions = role_permissions(role)
    if "*" in permissions:
        return True
    return permission in permissions


def require_permission(permission: str) -> Callable[[BusinessAccess], BusinessAccess]:
    normalized_permission = (permission or "").strip().lower()
    if not normalized_permission:
        raise ValueError("Permission key is required")

    def dependency(access: BusinessAccess = Depends(get_current_business_access)) -> BusinessAccess:
        if not has_permission(role=access.role, permission=normalized_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permission for this action",
            )
        return access

    return dependency
