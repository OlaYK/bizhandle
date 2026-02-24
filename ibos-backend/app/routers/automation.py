import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_business_roles
from app.core.security_current import BusinessAccess, get_current_user
from app.models.automation import AutomationRule, AutomationRuleRun, AutomationRuleStep
from app.models.user import User
from app.schemas.automation import (
    AutomationActionOut,
    AutomationConditionOut,
    AutomationOutboxRunOut,
    AutomationRuleCreateIn,
    AutomationRuleListOut,
    AutomationRuleOut,
    AutomationRuleRunListOut,
    AutomationRuleRunOut,
    AutomationRuleStepOut,
    AutomationRuleTestIn,
    AutomationRuleUpdateIn,
    AutomationTemplateCatalogOut,
    AutomationTemplateInstallIn,
    AutomationTemplateInstallOut,
    AutomationTemplateOut,
)
from app.schemas.common import PaginationMeta
from app.services.audit_service import log_audit_event
from app.services.automation_service import (
    install_template_rule,
    list_automation_templates,
    process_outbox_events,
    simulate_rule,
)

router = APIRouter(prefix="/automations", tags=["automation"])


def _rule_or_404(db: Session, *, business_id: str, rule_id: str) -> AutomationRule:
    rule = db.execute(
        select(AutomationRule).where(
            AutomationRule.id == rule_id,
            AutomationRule.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Automation rule not found")
    return rule


def _run_or_404(db: Session, *, business_id: str, run_id: str) -> AutomationRuleRun:
    run = db.execute(
        select(AutomationRuleRun).where(
            AutomationRuleRun.id == run_id,
            AutomationRuleRun.business_id == business_id,
        )
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Automation run not found")
    return run


def _condition_out(item: dict) -> AutomationConditionOut:
    return AutomationConditionOut(
        field=str(item.get("field") or ""),
        operator=str(item.get("operator") or "eq"),
        value=item.get("value"),
        case_sensitive=bool(item.get("case_sensitive", False)),
    )


def _action_out(item: dict) -> AutomationActionOut:
    return AutomationActionOut(
        type=str(item.get("type") or "create_task"),
        config_json=item.get("config_json") if isinstance(item.get("config_json"), dict) else {},
    )


def _rule_out(rule: AutomationRule) -> AutomationRuleOut:
    conditions = rule.conditions_json if isinstance(rule.conditions_json, list) else []
    actions = rule.actions_json if isinstance(rule.actions_json, list) else []
    return AutomationRuleOut(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        status=rule.status,
        trigger_source=rule.trigger_source,
        trigger_event_type=rule.trigger_event_type,
        conditions=[_condition_out(item) for item in conditions if isinstance(item, dict)],
        actions=[_action_out(item) for item in actions if isinstance(item, dict)],
        template_key=rule.template_key,
        version=rule.version,
        run_limit_per_hour=rule.run_limit_per_hour,
        reentry_cooldown_seconds=rule.reentry_cooldown_seconds,
        rollback_on_failure=rule.rollback_on_failure,
        created_by_user_id=rule.created_by_user_id,
        updated_by_user_id=rule.updated_by_user_id,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _step_out(step: AutomationRuleStep) -> AutomationRuleStepOut:
    return AutomationRuleStepOut(
        id=step.id,
        step_index=step.step_index,
        action_type=step.action_type,
        status=step.status,
        input_json=step.input_json if isinstance(step.input_json, dict) else None,
        output_json=step.output_json if isinstance(step.output_json, dict) else None,
        error_message=step.error_message,
        created_at=step.created_at,
    )


def _template_out(item: dict) -> AutomationTemplateOut:
    conditions = item.get("default_conditions", [])
    actions = item.get("default_actions", [])
    return AutomationTemplateOut(
        template_key=item["template_key"],
        name=item["name"],
        description=item["description"],
        trigger_event_type=item["trigger_event_type"],
        default_conditions=[_condition_out(row) for row in conditions if isinstance(row, dict)],
        default_actions=[_action_out(row) for row in actions if isinstance(row, dict)],
    )


def _steps_by_run_ids(
    db: Session,
    *,
    business_id: str,
    run_ids: list[str],
) -> dict[str, list[AutomationRuleStep]]:
    if not run_ids:
        return {}
    rows = db.execute(
        select(AutomationRuleStep)
        .where(
            AutomationRuleStep.business_id == business_id,
            AutomationRuleStep.rule_run_id.in_(run_ids),
        )
        .order_by(
            AutomationRuleStep.rule_run_id.asc(),
            AutomationRuleStep.step_index.asc(),
            AutomationRuleStep.created_at.asc(),
        )
    ).scalars().all()
    out: dict[str, list[AutomationRuleStep]] = {run_id: [] for run_id in run_ids}
    for row in rows:
        out.setdefault(row.rule_run_id, []).append(row)
    return out


def _run_out(run: AutomationRuleRun, *, steps: list[AutomationRuleStep]) -> AutomationRuleRunOut:
    return AutomationRuleRunOut(
        id=run.id,
        rule_id=run.rule_id,
        trigger_event_id=run.trigger_event_id,
        trigger_event_type=run.trigger_event_type,
        status=run.status,
        blocked_reason=run.blocked_reason,
        error_message=run.error_message,
        steps_total=run.steps_total,
        steps_succeeded=run.steps_succeeded,
        steps_failed=run.steps_failed,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        steps=[_step_out(item) for item in steps],
    )


@router.get(
    "/templates",
    response_model=AutomationTemplateCatalogOut,
    summary="List automation templates",
    responses=error_responses(401, 403, 500),
)
def list_templates(
    _: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    return AutomationTemplateCatalogOut(items=[_template_out(item) for item in list_automation_templates()])


@router.post(
    "/templates/install",
    response_model=AutomationTemplateInstallOut,
    summary="Install automation template",
    responses=error_responses(401, 403, 422, 500),
)
def install_template(
    payload: AutomationTemplateInstallIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    rule, template = install_template_rule(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        template_key=payload.template_key,
        activate=payload.activate,
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="automation.template.install",
        target_type="automation_rule",
        target_id=rule.id,
        metadata_json={"template_key": payload.template_key, "version": rule.version, "status": rule.status},
    )
    db.commit()
    db.refresh(rule)
    return AutomationTemplateInstallOut(template=_template_out(template), rule=_rule_out(rule))


@router.post(
    "/rules",
    response_model=AutomationRuleOut,
    summary="Create automation rule",
    responses=error_responses(401, 403, 409, 422, 500),
)
def create_rule(
    payload: AutomationRuleCreateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    rule = AutomationRule(
        id=str(uuid.uuid4()),
        business_id=access.business.id,
        name=payload.name.strip(),
        description=payload.description,
        status=payload.status,
        trigger_source=payload.trigger_source,
        trigger_event_type=payload.trigger_event_type.strip(),
        conditions_json=[item.model_dump() for item in payload.conditions],
        actions_json=[item.model_dump() for item in payload.actions],
        template_key=payload.template_key,
        version=1,
        run_limit_per_hour=payload.run_limit_per_hour,
        reentry_cooldown_seconds=payload.reentry_cooldown_seconds,
        rollback_on_failure=payload.rollback_on_failure,
        created_by_user_id=actor.id,
        updated_by_user_id=actor.id,
    )
    db.add(rule)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="automation.rule.create",
        target_type="automation_rule",
        target_id=rule.id,
        metadata_json={"name": rule.name, "trigger_event_type": rule.trigger_event_type},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Automation rule name already exists") from None
    db.refresh(rule)
    return _rule_out(rule)


@router.get(
    "/rules",
    response_model=AutomationRuleListOut,
    summary="List automation rules",
    responses=error_responses(401, 403, 422, 500),
)
def list_rules(
    status: str | None = Query(default=None),
    trigger_event_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(AutomationRule.id)).where(AutomationRule.business_id == access.business.id)
    stmt = select(AutomationRule).where(AutomationRule.business_id == access.business.id)
    normalized_status = status.strip().lower() if status else None
    normalized_trigger = trigger_event_type.strip() if trigger_event_type else None
    if normalized_status:
        count_stmt = count_stmt.where(AutomationRule.status == normalized_status)
        stmt = stmt.where(AutomationRule.status == normalized_status)
    if normalized_trigger:
        count_stmt = count_stmt.where(AutomationRule.trigger_event_type == normalized_trigger)
        stmt = stmt.where(AutomationRule.trigger_event_type == normalized_trigger)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        stmt.order_by(AutomationRule.updated_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    items = [_rule_out(row) for row in rows]
    count = len(items)
    return AutomationRuleListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        status=normalized_status,
        trigger_event_type=normalized_trigger,
    )


@router.patch(
    "/rules/{rule_id}",
    response_model=AutomationRuleOut,
    summary="Update automation rule",
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
def update_rule(
    rule_id: str,
    payload: AutomationRuleUpdateIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin")),
    actor: User = Depends(get_current_user),
):
    rule = _rule_or_404(db, business_id=access.business.id, rule_id=rule_id)
    changed = False
    if payload.name is not None:
        rule.name = payload.name.strip()
        changed = True
    if payload.description is not None:
        rule.description = payload.description
        changed = True
    if payload.status is not None:
        rule.status = payload.status
        changed = True
    if payload.trigger_event_type is not None:
        rule.trigger_event_type = payload.trigger_event_type.strip()
        changed = True
    if payload.conditions is not None:
        rule.conditions_json = [item.model_dump() for item in payload.conditions]
        changed = True
    if payload.actions is not None:
        rule.actions_json = [item.model_dump() for item in payload.actions]
        changed = True
    if payload.run_limit_per_hour is not None:
        rule.run_limit_per_hour = payload.run_limit_per_hour
        changed = True
    if payload.reentry_cooldown_seconds is not None:
        rule.reentry_cooldown_seconds = payload.reentry_cooldown_seconds
        changed = True
    if payload.rollback_on_failure is not None:
        rule.rollback_on_failure = payload.rollback_on_failure
        changed = True

    if changed:
        rule.version += 1
        rule.updated_by_user_id = actor.id

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="automation.rule.update",
        target_type="automation_rule",
        target_id=rule.id,
        metadata_json={"version": rule.version, "status": rule.status},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Automation rule name already exists") from None
    db.refresh(rule)
    return _rule_out(rule)


@router.post(
    "/rules/{rule_id}/test",
    response_model=AutomationRuleRunOut,
    summary="Test automation rule against sample payload (dry run)",
    responses=error_responses(401, 403, 404, 422, 500),
)
def test_rule(
    rule_id: str,
    payload: AutomationRuleTestIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    rule = _rule_or_404(db, business_id=access.business.id, rule_id=rule_id)
    event_type = payload.event_type or rule.trigger_event_type
    simulation = simulate_rule(
        db,
        rule=rule,
        event_type=event_type,
        target_app_key=payload.target_app_key,
        payload_json=payload.payload_json,
    )

    now = datetime.now(timezone.utc)
    steps = [
        AutomationRuleStepOut(
            id=item["id"],
            step_index=item["step_index"],
            action_type=item["action_type"],
            status=item["status"],
            input_json=item["input_json"],
            output_json=item["output_json"],
            error_message=item["error_message"],
            created_at=item["created_at"],
        )
        for item in simulation.steps
    ]
    return AutomationRuleRunOut(
        id=f"dry-run-{uuid.uuid4().hex[:10]}",
        rule_id=rule.id,
        trigger_event_id=None,
        trigger_event_type=event_type,
        status=simulation.status,
        blocked_reason=simulation.blocked_reason,
        error_message=simulation.error_message,
        steps_total=len(steps),
        steps_succeeded=sum(1 for step in steps if step.status == "dry_run"),
        steps_failed=sum(1 for step in steps if step.status == "failed"),
        started_at=now,
        completed_at=now,
        created_at=now,
        steps=steps,
    )


@router.post(
    "/outbox/run",
    response_model=AutomationOutboxRunOut,
    summary="Process outbox events against active automation rules",
    responses=error_responses(401, 403, 422, 500),
)
def run_outbox(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
    actor: User = Depends(get_current_user),
):
    summary = process_outbox_events(db, business_id=access.business.id, limit=limit)
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="automation.outbox.run",
        target_type="automation",
        target_id=None,
        metadata_json={
            "processed_events": summary.processed_events,
            "triggered_runs": summary.triggered_runs,
            "successful_runs": summary.successful_runs,
            "failed_runs": summary.failed_runs,
            "blocked_runs": summary.blocked_runs,
        },
    )
    db.commit()
    return AutomationOutboxRunOut(
        processed_events=summary.processed_events,
        matched_rules=summary.matched_rules,
        triggered_runs=summary.triggered_runs,
        successful_runs=summary.successful_runs,
        failed_runs=summary.failed_runs,
        blocked_runs=summary.blocked_runs,
        skipped_runs=summary.skipped_runs,
    )


@router.get(
    "/runs",
    response_model=AutomationRuleRunListOut,
    summary="List automation rule runs with step logs",
    responses=error_responses(401, 403, 422, 500),
)
def list_runs(
    rule_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    count_stmt = select(func.count(AutomationRuleRun.id)).where(AutomationRuleRun.business_id == access.business.id)
    stmt = select(AutomationRuleRun).where(AutomationRuleRun.business_id == access.business.id)

    normalized_rule_id = rule_id.strip() if rule_id else None
    normalized_status = status.strip().lower() if status else None
    if normalized_rule_id:
        count_stmt = count_stmt.where(AutomationRuleRun.rule_id == normalized_rule_id)
        stmt = stmt.where(AutomationRuleRun.rule_id == normalized_rule_id)
    if normalized_status:
        count_stmt = count_stmt.where(AutomationRuleRun.status == normalized_status)
        stmt = stmt.where(AutomationRuleRun.status == normalized_status)

    total = int(db.execute(count_stmt).scalar_one())
    runs = db.execute(
        stmt.order_by(AutomationRuleRun.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    run_ids = [item.id for item in runs]
    steps_map = _steps_by_run_ids(db, business_id=access.business.id, run_ids=run_ids)
    items = [_run_out(run, steps=steps_map.get(run.id, [])) for run in runs]
    count = len(items)
    return AutomationRuleRunListOut(
        items=items,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            count=count,
            has_next=(offset + count) < total,
        ),
        rule_id=normalized_rule_id,
        status=normalized_status,
    )


@router.get(
    "/runs/{run_id}",
    response_model=AutomationRuleRunOut,
    summary="Get automation run details",
    responses=error_responses(401, 403, 404, 500),
)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_business_roles("owner", "admin", "staff")),
):
    run = _run_or_404(db, business_id=access.business.id, run_id=run_id)
    steps = db.execute(
        select(AutomationRuleStep)
        .where(
            AutomationRuleStep.business_id == access.business.id,
            AutomationRuleStep.rule_run_id == run.id,
        )
        .order_by(AutomationRuleStep.step_index.asc(), AutomationRuleStep.created_at.asc())
    ).scalars().all()
    return _run_out(run, steps=steps)
