import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.automation import (
    AutomationDiscount,
    AutomationRule,
    AutomationRuleRun,
    AutomationRuleStep,
    AutomationTask,
)
from app.models.customer import Customer, CustomerTag, CustomerTagLink
from app.models.integration import AppInstallation, IntegrationOutboxEvent, OutboundMessage
from app.services.integration_service import queue_outbox_event
from app.services.messaging_provider import MessageSendRequest, get_messaging_provider


_TEMPLATE_VAR_RE = re.compile(r"{{\s*([a-zA-Z0-9_.]+)\s*}}")
_VALID_ACTION_TYPES = {"send_message", "tag_customer", "create_task", "apply_discount"}
_VALID_DISCOUNT_KINDS = {"percentage", "fixed"}

CompensationFn = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class AutomationOutboxSummary:
    processed_events: int
    matched_rules: int
    triggered_runs: int
    successful_runs: int
    failed_runs: int
    blocked_runs: int
    skipped_runs: int


@dataclass(frozen=True)
class SimulationResult:
    status: str
    blocked_reason: str | None
    error_message: str | None
    steps: list[dict[str, Any]]


_AUTOMATION_TEMPLATE_LIBRARY: list[dict[str, Any]] = [
    {
        "template_key": "abandoned_cart",
        "name": "Abandoned Cart Recovery",
        "description": "Recover abandoned carts with a one-time incentive and immediate follow-up.",
        "trigger_event_type": "checkout.abandoned_cart",
        "default_conditions": [
            {"field": "payload.customer_id", "operator": "exists", "value": None, "case_sensitive": False},
            {"field": "payload.checkout_url", "operator": "exists", "value": None, "case_sensitive": False},
        ],
        "default_actions": [
            {
                "type": "apply_discount",
                "config_json": {
                    "code_prefix": "CART",
                    "kind": "percentage",
                    "value": 10,
                    "max_redemptions": 1,
                    "expires_in_days": 3,
                    "target_customer_id_from": "payload.customer_id",
                },
            },
            {
                "type": "send_message",
                "config_json": {
                    "provider": "whatsapp_stub",
                    "recipient_from": "payload.phone",
                    "content": (
                        "Hi {{payload.customer_name}}, your cart is still waiting. "
                        "Use code {{actions.apply_discount.code}} today: {{payload.checkout_url}}"
                    ),
                },
            },
            {
                "type": "create_task",
                "config_json": {
                    "title": "Abandoned cart follow-up {{payload.checkout_session_id}}",
                    "description": "Follow up customer {{payload.customer_name}} on abandoned cart recovery.",
                    "due_in_hours": 12,
                },
            },
        ],
    },
    {
        "template_key": "overdue_invoice",
        "name": "Overdue Invoice Follow-up",
        "description": "Tag overdue customers and send a payment reminder.",
        "trigger_event_type": "invoice.overdue",
        "default_conditions": [
            {"field": "payload.customer_id", "operator": "exists", "value": None, "case_sensitive": False},
            {"field": "payload.amount_due", "operator": "gt", "value": 0, "case_sensitive": False},
        ],
        "default_actions": [
            {
                "type": "tag_customer",
                "config_json": {
                    "customer_id_from": "payload.customer_id",
                    "tag_name": "Overdue Invoice",
                    "tag_color": "#dc2626",
                },
            },
            {
                "type": "send_message",
                "config_json": {
                    "provider": "whatsapp_stub",
                    "recipient_from": "payload.phone",
                    "content": (
                        "Hi {{payload.customer_name}}, invoice {{payload.invoice_id}} of "
                        "{{payload.amount_due}} is overdue. Please complete payment today."
                    ),
                },
            },
            {
                "type": "create_task",
                "config_json": {
                    "title": "Collect overdue invoice {{payload.invoice_id}}",
                    "description": "Manual follow-up for customer {{payload.customer_id}}.",
                    "due_in_hours": 24,
                },
            },
        ],
    },
    {
        "template_key": "low_stock",
        "name": "Low Stock Operations Alert",
        "description": "Create an internal replenishment task when stock drops below threshold.",
        "trigger_event_type": "inventory.low_stock",
        "default_conditions": [
            {"field": "payload.variant_id", "operator": "exists", "value": None, "case_sensitive": False},
            {"field": "payload.stock", "operator": "lte", "value": 5, "case_sensitive": False},
        ],
        "default_actions": [
            {
                "type": "create_task",
                "config_json": {
                    "title": "Restock variant {{payload.variant_id}}",
                    "description": "Current stock {{payload.stock}} is at or below threshold {{payload.threshold}}.",
                    "due_in_hours": 8,
                },
            },
            {
                "type": "send_message",
                "config_json": {
                    "provider": "whatsapp_stub",
                    "recipient_from": "payload.procurement_phone",
                    "content": (
                        "Inventory alert: variant {{payload.variant_id}} is low at {{payload.stock}} units. "
                        "Please replenish urgently."
                    ),
                },
            },
        ],
    },
]


def list_automation_templates() -> list[dict[str, Any]]:
    return [json.loads(json.dumps(item)) for item in _AUTOMATION_TEMPLATE_LIBRARY]


def get_automation_template(template_key: str) -> dict[str, Any]:
    normalized = (template_key or "").strip().lower()
    for template in _AUTOMATION_TEMPLATE_LIBRARY:
        if template["template_key"] == normalized:
            return json.loads(json.dumps(template))
    available = ", ".join(sorted(item["template_key"] for item in _AUTOMATION_TEMPLATE_LIBRARY))
    raise ValueError(f"Unknown template '{template_key}'. Available: {available}")


def install_template_rule(
    db: Session,
    *,
    business_id: str,
    actor_user_id: str,
    template_key: str,
    activate: bool = True,
) -> tuple[AutomationRule, dict[str, Any]]:
    template = get_automation_template(template_key)
    desired_status = "active" if activate else "inactive"
    existing = db.execute(
        select(AutomationRule).where(
            AutomationRule.business_id == business_id,
            func.lower(AutomationRule.template_key) == template["template_key"],
        )
    ).scalar_one_or_none()

    if existing:
        existing.name = template["name"]
        existing.description = template["description"]
        existing.status = desired_status
        existing.trigger_source = "outbox_event"
        existing.trigger_event_type = template["trigger_event_type"]
        existing.conditions_json = template["default_conditions"]
        existing.actions_json = template["default_actions"]
        existing.updated_by_user_id = actor_user_id
        existing.version += 1
        return existing, template

    rule = AutomationRule(
        id=str(uuid.uuid4()),
        business_id=business_id,
        name=_unique_rule_name(db, business_id=business_id, seed_name=template["name"]),
        description=template["description"],
        status=desired_status,
        trigger_source="outbox_event",
        trigger_event_type=template["trigger_event_type"],
        conditions_json=template["default_conditions"],
        actions_json=template["default_actions"],
        template_key=template["template_key"],
        version=1,
        run_limit_per_hour=120,
        reentry_cooldown_seconds=300,
        rollback_on_failure=True,
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    )
    db.add(rule)
    db.flush()
    return rule, template


def trigger_matches(rule_trigger_event_type: str, event_type: str) -> bool:
    trigger = (rule_trigger_event_type or "").strip().lower()
    event = (event_type or "").strip().lower()
    if not trigger or not event:
        return False
    if trigger == "*" or trigger == event:
        return True
    if "*" in trigger:
        pattern = "^" + re.escape(trigger).replace("\\*", ".*") + "$"
        return re.match(pattern, event) is not None
    return False


def evaluate_conditions(
    *,
    context: dict[str, Any],
    conditions: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    for condition in conditions:
        field = str(condition.get("field") or "").strip()
        operator = str(condition.get("operator") or "eq").strip().lower()
        expected = condition.get("value")
        case_sensitive = bool(condition.get("case_sensitive", False))
        actual = _resolve_path(context, field)
        if _condition_matches(actual, operator=operator, expected=expected, case_sensitive=case_sensitive):
            continue
        return (
            False,
            f"Condition failed: {field or '<missing field>'} {operator} {expected!r}",
        )
    return True, None


def simulate_rule(
    db: Session,
    *,
    rule: AutomationRule,
    event_type: str,
    target_app_key: str,
    payload_json: dict[str, Any] | None,
) -> SimulationResult:
    normalized_payload = _normalize_payload(payload_json)
    normalized_event_type = (event_type or rule.trigger_event_type or "").strip()
    context = {
        "event_type": normalized_event_type,
        "target_app_key": (target_app_key or "automation").strip().lower(),
        "payload": normalized_payload,
        "event_id": None,
        "event_created_at": datetime.now(timezone.utc).isoformat(),
        "actions": {},
        "last_action": None,
    }

    conditions = _normalize_conditions(rule.conditions_json)
    condition_passed, condition_reason = evaluate_conditions(context=context, conditions=conditions)
    if not condition_passed:
        return SimulationResult(
            status="skipped",
            blocked_reason=condition_reason,
            error_message=None,
            steps=[],
        )

    steps: list[dict[str, Any]] = []
    actions = _normalize_actions(rule.actions_json)
    if not actions:
        return SimulationResult(
            status="skipped",
            blocked_reason="No actions configured on rule",
            error_message=None,
            steps=[],
        )

    run_error: str | None = None
    for step_index, action in enumerate(actions, start=1):
        action_type = str(action.get("type") or "").strip().lower()
        config_json = _normalize_action_config(action.get("config_json"))
        step_input = {"type": action_type, "config_json": config_json}
        try:
            output_json, _ = _execute_action(
                db,
                business_id=rule.business_id,
                rule=rule,
                rule_run=None,
                action_type=action_type,
                config_json=config_json,
                context=context,
                dry_run=True,
            )
            status = "dry_run"
            error_message = None
            if isinstance(output_json, dict):
                context["actions"][action_type] = output_json
                context["last_action"] = output_json
        except Exception as exc:  # noqa: BLE001
            output_json = None
            status = "failed"
            error_message = _short_error(exc)
            run_error = error_message

        steps.append(
            {
                "id": None,
                "step_index": step_index,
                "action_type": action_type,
                "status": status,
                "input_json": step_input,
                "output_json": output_json if isinstance(output_json, dict) else None,
                "error_message": error_message,
                "created_at": None,
            }
        )
        if run_error:
            break

    return SimulationResult(
        status="failed" if run_error else "dry_run",
        blocked_reason=None,
        error_message=run_error,
        steps=steps,
    )


def execute_rule(
    db: Session,
    *,
    rule: AutomationRule,
    event_type: str,
    target_app_key: str,
    payload_json: dict[str, Any] | None,
    trigger_event_id: str | None,
) -> tuple[AutomationRuleRun, bool]:
    if trigger_event_id:
        existing = db.execute(
            select(AutomationRuleRun).where(
                AutomationRuleRun.rule_id == rule.id,
                AutomationRuleRun.trigger_event_id == trigger_event_id,
            )
        ).scalar_one_or_none()
        if existing:
            return existing, False

    now = datetime.now(timezone.utc)
    normalized_event_type = (event_type or rule.trigger_event_type or "").strip()
    normalized_payload = _normalize_payload(payload_json)
    fingerprint = _build_trigger_fingerprint(
        event_type=normalized_event_type,
        payload_json=normalized_payload,
        trigger_event_id=trigger_event_id,
    )
    context = {
        "event_type": normalized_event_type,
        "target_app_key": (target_app_key or "automation").strip().lower(),
        "payload": normalized_payload,
        "event_id": trigger_event_id,
        "event_created_at": now.isoformat(),
        "actions": {},
        "last_action": None,
    }

    conditions = _normalize_conditions(rule.conditions_json)
    condition_passed, condition_reason = evaluate_conditions(context=context, conditions=conditions)
    if not condition_passed:
        run = _create_terminal_run(
            db,
            rule=rule,
            trigger_event_id=trigger_event_id,
            trigger_event_type=normalized_event_type,
            payload_json=normalized_payload,
            trigger_fingerprint=fingerprint,
            status="skipped",
            blocked_reason=condition_reason,
            error_message=None,
        )
        return run, True

    if _is_rate_limited(db, rule=rule, now=now):
        run = _create_terminal_run(
            db,
            rule=rule,
            trigger_event_id=trigger_event_id,
            trigger_event_type=normalized_event_type,
            payload_json=normalized_payload,
            trigger_fingerprint=fingerprint,
            status="blocked",
            blocked_reason="Rate limit reached for rule in the last hour",
            error_message=None,
        )
        return run, True

    if _is_loop_detected(db, rule=rule, now=now, trigger_fingerprint=fingerprint):
        run = _create_terminal_run(
            db,
            rule=rule,
            trigger_event_id=trigger_event_id,
            trigger_event_type=normalized_event_type,
            payload_json=normalized_payload,
            trigger_fingerprint=fingerprint,
            status="blocked",
            blocked_reason="Loop prevention triggered by repeated event fingerprint",
            error_message=None,
        )
        return run, True

    actions = _normalize_actions(rule.actions_json)
    if not actions:
        run = _create_terminal_run(
            db,
            rule=rule,
            trigger_event_id=trigger_event_id,
            trigger_event_type=normalized_event_type,
            payload_json=normalized_payload,
            trigger_fingerprint=fingerprint,
            status="skipped",
            blocked_reason="No actions configured on rule",
            error_message=None,
        )
        return run, True

    run = AutomationRuleRun(
        id=str(uuid.uuid4()),
        business_id=rule.business_id,
        rule_id=rule.id,
        trigger_event_id=trigger_event_id,
        trigger_event_type=normalized_event_type,
        trigger_payload_json=normalized_payload,
        trigger_fingerprint=fingerprint,
        status="pending",
        blocked_reason=None,
        error_message=None,
        steps_total=0,
        steps_succeeded=0,
        steps_failed=0,
        started_at=now,
        completed_at=None,
    )
    db.add(run)
    db.flush()

    compensations: list[tuple[AutomationRuleStep, CompensationFn]] = []
    step_records: list[AutomationRuleStep] = []
    run_error: str | None = None

    for step_index, action in enumerate(actions, start=1):
        action_type = str(action.get("type") or "").strip().lower()
        config_json = _normalize_action_config(action.get("config_json"))
        step = AutomationRuleStep(
            id=str(uuid.uuid4()),
            business_id=rule.business_id,
            rule_run_id=run.id,
            rule_id=rule.id,
            step_index=step_index,
            action_type=action_type,
            status="pending",
            input_json={"type": action_type, "config_json": config_json},
            output_json=None,
            error_message=None,
        )
        db.add(step)
        db.flush()
        step_records.append(step)

        try:
            output_json, compensation = _execute_action(
                db,
                business_id=rule.business_id,
                rule=rule,
                rule_run=run,
                action_type=action_type,
                config_json=config_json,
                context=context,
                dry_run=False,
            )
            step.status = "success"
            step.output_json = output_json if isinstance(output_json, dict) else None
            if compensation:
                compensations.append((step, compensation))
            if isinstance(output_json, dict):
                context["actions"][action_type] = output_json
                context["last_action"] = output_json
        except Exception as exc:  # noqa: BLE001
            run_error = _short_error(exc)
            step.status = "failed"
            step.error_message = run_error
            break

    if run_error and rule.rollback_on_failure and compensations:
        for step, compensation in reversed(compensations):
            try:
                details = compensation()
                output_json = dict(step.output_json or {})
                output_json["rollback"] = {"status": "applied", "details": details}
                step.output_json = output_json
                step.status = "rolled_back"
            except Exception as exc:  # noqa: BLE001
                output_json = dict(step.output_json or {})
                output_json["rollback"] = {"status": "failed", "error": _short_error(exc)}
                step.output_json = output_json

    statuses = [item.status for item in step_records]
    run.steps_total = len(step_records)
    run.steps_succeeded = sum(1 for item in statuses if item in {"success", "rolled_back"})
    run.steps_failed = sum(1 for item in statuses if item == "failed")
    run.status = "failed" if run_error else "success"
    run.error_message = run_error
    run.completed_at = datetime.now(timezone.utc)
    return run, True


def process_outbox_events(
    db: Session,
    *,
    business_id: str,
    limit: int = 100,
) -> AutomationOutboxSummary:
    rules = db.execute(
        select(AutomationRule).where(
            AutomationRule.business_id == business_id,
            AutomationRule.status == "active",
        )
    ).scalars().all()
    if not rules:
        return AutomationOutboxSummary(
            processed_events=0,
            matched_rules=0,
            triggered_runs=0,
            successful_runs=0,
            failed_runs=0,
            blocked_runs=0,
            skipped_runs=0,
        )

    events = db.execute(
        select(IntegrationOutboxEvent)
        .where(IntegrationOutboxEvent.business_id == business_id)
        .order_by(IntegrationOutboxEvent.created_at.asc())
        .limit(limit)
    ).scalars().all()

    mutable = {
        "processed_events": 0,
        "matched_rules": 0,
        "triggered_runs": 0,
        "successful_runs": 0,
        "failed_runs": 0,
        "blocked_runs": 0,
        "skipped_runs": 0,
    }

    for event in events:
        mutable["processed_events"] += 1
        matching_rules = [rule for rule in rules if trigger_matches(rule.trigger_event_type, event.event_type)]
        mutable["matched_rules"] += len(matching_rules)
        for rule in matching_rules:
            run, created = execute_rule(
                db,
                rule=rule,
                event_type=event.event_type,
                target_app_key=event.target_app_key,
                payload_json=event.payload_json,
                trigger_event_id=event.id,
            )
            if not created:
                continue
            mutable["triggered_runs"] += 1
            if run.status == "success":
                mutable["successful_runs"] += 1
            elif run.status == "failed":
                mutable["failed_runs"] += 1
            elif run.status == "blocked":
                mutable["blocked_runs"] += 1
            elif run.status == "skipped":
                mutable["skipped_runs"] += 1

    return AutomationOutboxSummary(**mutable)


def _create_terminal_run(
    db: Session,
    *,
    rule: AutomationRule,
    trigger_event_id: str | None,
    trigger_event_type: str,
    payload_json: dict[str, Any],
    trigger_fingerprint: str | None,
    status: str,
    blocked_reason: str | None,
    error_message: str | None,
) -> AutomationRuleRun:
    now = datetime.now(timezone.utc)
    run = AutomationRuleRun(
        id=str(uuid.uuid4()),
        business_id=rule.business_id,
        rule_id=rule.id,
        trigger_event_id=trigger_event_id,
        trigger_event_type=trigger_event_type,
        trigger_payload_json=payload_json,
        trigger_fingerprint=trigger_fingerprint,
        status=status,
        blocked_reason=blocked_reason,
        error_message=error_message,
        steps_total=0,
        steps_succeeded=0,
        steps_failed=0,
        started_at=now,
        completed_at=now,
    )
    db.add(run)
    db.flush()
    return run


def _is_rate_limited(db: Session, *, rule: AutomationRule, now: datetime) -> bool:
    lookback = now - timedelta(hours=1)
    count = int(
        db.execute(
            select(func.count(AutomationRuleRun.id)).where(
                AutomationRuleRun.rule_id == rule.id,
                AutomationRuleRun.created_at >= lookback,
                AutomationRuleRun.status.in_(["success", "failed", "blocked"]),
            )
        ).scalar_one()
        or 0
    )
    return count >= max(int(rule.run_limit_per_hour or 0), 1)


def _is_loop_detected(
    db: Session,
    *,
    rule: AutomationRule,
    now: datetime,
    trigger_fingerprint: str | None,
) -> bool:
    cooldown = int(rule.reentry_cooldown_seconds or 0)
    if cooldown <= 0 or not trigger_fingerprint:
        return False
    cutoff = now - timedelta(seconds=cooldown)
    existing = db.execute(
        select(AutomationRuleRun.id).where(
            AutomationRuleRun.rule_id == rule.id,
            AutomationRuleRun.trigger_fingerprint == trigger_fingerprint,
            AutomationRuleRun.created_at >= cutoff,
            AutomationRuleRun.status.in_(["success", "failed", "blocked"]),
        )
    ).scalar_one_or_none()
    return existing is not None


def _build_trigger_fingerprint(
    *,
    event_type: str,
    payload_json: dict[str, Any],
    trigger_event_id: str | None,
) -> str | None:
    for key in (
        "entity_id",
        "event_id",
        "id",
        "order_id",
        "invoice_id",
        "checkout_session_id",
        "customer_id",
        "variant_id",
        "sku",
    ):
        value = payload_json.get(key)
        if value is not None and str(value).strip():
            return f"{event_type}:{value}"[:160]

    if trigger_event_id:
        return f"{event_type}:{trigger_event_id}"[:160]

    if payload_json:
        stable = json.dumps(payload_json, sort_keys=True, default=str)
        return f"{event_type}:{stable}"[:160]
    return event_type[:160] if event_type else None


def _execute_action(
    db: Session,
    *,
    business_id: str,
    rule: AutomationRule,
    rule_run: AutomationRuleRun | None,
    action_type: str,
    config_json: dict[str, Any],
    context: dict[str, Any],
    dry_run: bool,
) -> tuple[dict[str, Any], CompensationFn | None]:
    normalized = action_type.strip().lower()
    if normalized not in _VALID_ACTION_TYPES:
        raise ValueError(f"Unsupported action type '{action_type}'")

    if normalized == "send_message":
        return _action_send_message(
            db,
            business_id=business_id,
            rule=rule,
            rule_run=rule_run,
            config_json=config_json,
            context=context,
            dry_run=dry_run,
        )
    if normalized == "tag_customer":
        return _action_tag_customer(
            db,
            business_id=business_id,
            config_json=config_json,
            context=context,
            dry_run=dry_run,
        )
    if normalized == "create_task":
        return _action_create_task(
            db,
            business_id=business_id,
            rule_run=rule_run,
            config_json=config_json,
            context=context,
            dry_run=dry_run,
        )
    return _action_apply_discount(
        db,
        business_id=business_id,
        rule_run=rule_run,
        config_json=config_json,
        context=context,
        dry_run=dry_run,
    )


def _action_send_message(
    db: Session,
    *,
    business_id: str,
    rule: AutomationRule,
    rule_run: AutomationRuleRun | None,
    config_json: dict[str, Any],
    context: dict[str, Any],
    dry_run: bool,
) -> tuple[dict[str, Any], CompensationFn | None]:
    provider = str(config_json.get("provider") or settings.messaging_provider_default).strip().lower()
    recipient = str(config_json.get("recipient") or "").strip()
    recipient_from = str(config_json.get("recipient_from") or "").strip()
    if not recipient and recipient_from:
        resolved = _resolve_path(context, recipient_from)
        if resolved is not None:
            recipient = str(resolved).strip()

    if not recipient:
        customer_id_from = str(config_json.get("customer_id_from") or "payload.customer_id")
        customer_id = _resolve_path(context, customer_id_from)
        if customer_id:
            customer = db.execute(
                select(Customer).where(
                    Customer.business_id == business_id,
                    Customer.id == str(customer_id),
                )
            ).scalar_one_or_none()
            if customer:
                recipient = (customer.phone or customer.email or "").strip()

    if not recipient:
        raise ValueError("send_message action requires recipient or resolvable recipient_from")

    content_template = str(config_json.get("content") or "Automation notification").strip()
    content = _render_template(content_template, context).strip()
    if not content:
        raise ValueError("send_message action requires non-empty content")

    if provider.startswith("whatsapp"):
        connected = db.execute(
            select(AppInstallation.id).where(
                AppInstallation.business_id == business_id,
                AppInstallation.app_key == "whatsapp",
                AppInstallation.status == "connected",
            )
        ).scalar_one_or_none()
        if not connected:
            raise ValueError("WhatsApp connector is not connected")

    if dry_run:
        return (
            {
                "provider": provider,
                "recipient": recipient,
                "content_preview": content,
                "dry_run": True,
            },
            None,
        )

    provider_impl = get_messaging_provider(provider)
    result = provider_impl.send_message(
        MessageSendRequest(
            business_id=business_id,
            recipient=recipient,
            content=content,
        )
    )
    outbound_message = OutboundMessage(
        id=str(uuid.uuid4()),
        business_id=business_id,
        provider=result.provider,
        recipient=recipient,
        content=content,
        status=result.status,
        external_message_id=result.message_id,
        error_message=None,
    )
    db.add(outbound_message)
    db.flush()
    queue_outbox_event(
        db,
        business_id=business_id,
        event_type="automation.message.sent",
        target_app_key="whatsapp" if result.provider.startswith("whatsapp") else result.provider,
        payload_json={
            "rule_id": rule.id,
            "rule_run_id": rule_run.id if rule_run else None,
            "provider": result.provider,
            "recipient": recipient,
            "outbound_message_id": outbound_message.id,
        },
    )
    return (
        {
            "provider": result.provider,
            "status": result.status,
            "recipient": recipient,
            "message_id": result.message_id,
            "outbound_message_id": outbound_message.id,
        },
        None,
    )


def _action_tag_customer(
    db: Session,
    *,
    business_id: str,
    config_json: dict[str, Any],
    context: dict[str, Any],
    dry_run: bool,
) -> tuple[dict[str, Any], CompensationFn | None]:
    customer_id = _resolve_customer_id(config_json=config_json, context=context)
    if not customer_id:
        raise ValueError("tag_customer action requires customer_id or customer_id_from")

    customer = db.execute(
        select(Customer).where(
            Customer.business_id == business_id,
            Customer.id == customer_id,
        )
    ).scalar_one_or_none()
    if not customer:
        raise ValueError("Customer not found for tag_customer action")

    tag_id = str(config_json.get("tag_id") or "").strip()
    tag_name = str(config_json.get("tag_name") or "").strip()
    tag_color = str(config_json.get("tag_color") or "#0ea5e9").strip() or "#0ea5e9"
    if not tag_id and not tag_name:
        raise ValueError("tag_customer action requires tag_id or tag_name")

    created_tag_id: str | None = None
    if tag_id:
        tag = db.execute(
            select(CustomerTag).where(
                CustomerTag.business_id == business_id,
                CustomerTag.id == tag_id,
            )
        ).scalar_one_or_none()
        if not tag:
            raise ValueError("Tag not found for tag_customer action")
    else:
        tag = db.execute(
            select(CustomerTag).where(
                CustomerTag.business_id == business_id,
                func.lower(CustomerTag.name) == tag_name.lower(),
            )
        ).scalar_one_or_none()
        if not tag and not dry_run:
            tag = CustomerTag(
                id=str(uuid.uuid4()),
                business_id=business_id,
                name=tag_name,
                color=tag_color,
            )
            db.add(tag)
            db.flush()
            created_tag_id = tag.id

    if dry_run:
        return (
            {
                "customer_id": customer_id,
                "tag_id": tag.id if tag else None,
                "tag_name": tag.name if tag else tag_name,
                "would_create_tag": tag is None and bool(tag_name),
                "dry_run": True,
            },
            None,
        )

    assert tag is not None
    existing_link = db.execute(
        select(CustomerTagLink).where(
            CustomerTagLink.business_id == business_id,
            CustomerTagLink.customer_id == customer_id,
            CustomerTagLink.tag_id == tag.id,
        )
    ).scalar_one_or_none()

    created_link_id: str | None = None
    if not existing_link:
        link = CustomerTagLink(
            id=str(uuid.uuid4()),
            business_id=business_id,
            customer_id=customer_id,
            tag_id=tag.id,
        )
        db.add(link)
        db.flush()
        created_link_id = link.id

    def _rollback() -> dict[str, Any]:
        deleted_link = False
        deleted_tag = False
        if created_link_id:
            link = db.execute(
                select(CustomerTagLink).where(
                    CustomerTagLink.business_id == business_id,
                    CustomerTagLink.id == created_link_id,
                )
            ).scalar_one_or_none()
            if link:
                db.delete(link)
                deleted_link = True
        if created_tag_id:
            links_count = int(
                db.execute(
                    select(func.count(CustomerTagLink.id)).where(
                        CustomerTagLink.business_id == business_id,
                        CustomerTagLink.tag_id == created_tag_id,
                    )
                ).scalar_one()
                or 0
            )
            if links_count == 0:
                created_tag = db.execute(
                    select(CustomerTag).where(
                        CustomerTag.business_id == business_id,
                        CustomerTag.id == created_tag_id,
                    )
                ).scalar_one_or_none()
                if created_tag:
                    db.delete(created_tag)
                    deleted_tag = True
        return {
            "deleted_link": deleted_link,
            "deleted_tag": deleted_tag,
        }

    return (
        {
            "customer_id": customer_id,
            "tag_id": tag.id,
            "tag_name": tag.name,
            "link_created": created_link_id is not None,
        },
        _rollback if created_link_id or created_tag_id else None,
    )


def _action_create_task(
    db: Session,
    *,
    business_id: str,
    rule_run: AutomationRuleRun | None,
    config_json: dict[str, Any],
    context: dict[str, Any],
    dry_run: bool,
) -> tuple[dict[str, Any], CompensationFn | None]:
    title_template = str(config_json.get("title") or "").strip()
    if not title_template:
        raise ValueError("create_task action requires title")

    title = _render_template(title_template, context).strip()
    if not title:
        raise ValueError("create_task action title resolved to empty")

    description_template = str(config_json.get("description") or "").strip()
    description = _render_template(description_template, context).strip() if description_template else None

    due_in_hours = int(config_json.get("due_in_hours") or 0)
    due_at = datetime.now(timezone.utc) + timedelta(hours=due_in_hours) if due_in_hours > 0 else None
    assignee_user_id = str(config_json.get("assignee_user_id") or "").strip() or None

    if dry_run:
        return (
            {
                "title": title,
                "description": description,
                "due_at": due_at.isoformat() if due_at else None,
                "assignee_user_id": assignee_user_id,
                "dry_run": True,
            },
            None,
        )

    task = AutomationTask(
        id=str(uuid.uuid4()),
        business_id=business_id,
        rule_run_id=rule_run.id if rule_run else None,
        title=title,
        description=description,
        status="open",
        assignee_user_id=assignee_user_id,
        due_at=due_at,
    )
    db.add(task)
    db.flush()

    def _rollback() -> dict[str, Any]:
        existing = db.execute(
            select(AutomationTask).where(
                AutomationTask.business_id == business_id,
                AutomationTask.id == task.id,
            )
        ).scalar_one_or_none()
        if existing:
            db.delete(existing)
            return {"deleted_task_id": task.id}
        return {"deleted_task_id": None}

    return (
        {
            "task_id": task.id,
            "title": task.title,
            "status": task.status,
            "due_at": task.due_at.isoformat() if task.due_at else None,
        },
        _rollback,
    )


def _action_apply_discount(
    db: Session,
    *,
    business_id: str,
    rule_run: AutomationRuleRun | None,
    config_json: dict[str, Any],
    context: dict[str, Any],
    dry_run: bool,
) -> tuple[dict[str, Any], CompensationFn | None]:
    kind = str(config_json.get("kind") or "percentage").strip().lower()
    if kind not in _VALID_DISCOUNT_KINDS:
        raise ValueError("apply_discount action kind must be percentage or fixed")

    value = float(config_json.get("value") or 0)
    if value <= 0:
        raise ValueError("apply_discount action value must be greater than 0")
    if kind == "percentage" and value > 100:
        raise ValueError("apply_discount percentage value cannot exceed 100")

    code = str(config_json.get("code") or "").strip().upper()
    code_prefix = str(config_json.get("code_prefix") or "AUTO").strip().upper()
    if not code:
        code = f"{code_prefix}-{uuid.uuid4().hex[:8].upper()}"
    code = _ensure_unique_discount_code(db, business_id=business_id, code=code)

    max_redemptions = config_json.get("max_redemptions")
    max_redemptions_value: int | None = None
    if max_redemptions is not None:
        max_redemptions_value = int(max_redemptions)
        if max_redemptions_value <= 0:
            raise ValueError("apply_discount max_redemptions must be greater than 0")

    target_customer_id = str(config_json.get("target_customer_id") or "").strip() or None
    target_customer_id_from = str(config_json.get("target_customer_id_from") or "").strip()
    if not target_customer_id and target_customer_id_from:
        resolved = _resolve_path(context, target_customer_id_from)
        target_customer_id = str(resolved).strip() if resolved is not None else None

    if target_customer_id:
        customer = db.execute(
            select(Customer.id).where(
                Customer.business_id == business_id,
                Customer.id == target_customer_id,
            )
        ).scalar_one_or_none()
        if not customer:
            raise ValueError("Target customer for discount was not found")

    expires_in_days = int(config_json.get("expires_in_days") or 0)
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days) if expires_in_days > 0 else None

    if dry_run:
        return (
            {
                "code": code,
                "kind": kind,
                "value": value,
                "max_redemptions": max_redemptions_value,
                "target_customer_id": target_customer_id,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "dry_run": True,
            },
            None,
        )

    discount = AutomationDiscount(
        id=str(uuid.uuid4()),
        business_id=business_id,
        rule_run_id=rule_run.id if rule_run else None,
        code=code,
        kind=kind,
        value=value,
        max_redemptions=max_redemptions_value,
        target_customer_id=target_customer_id,
        expires_at=expires_at,
        status="active",
    )
    db.add(discount)
    db.flush()

    def _rollback() -> dict[str, Any]:
        existing = db.execute(
            select(AutomationDiscount).where(
                AutomationDiscount.business_id == business_id,
                AutomationDiscount.id == discount.id,
            )
        ).scalar_one_or_none()
        if existing:
            existing.status = "inactive"
            return {"discount_id": existing.id, "status": existing.status}
        return {"discount_id": None, "status": "missing"}

    return (
        {
            "discount_id": discount.id,
            "code": discount.code,
            "kind": discount.kind,
            "value": discount.value,
            "target_customer_id": discount.target_customer_id,
            "expires_at": discount.expires_at.isoformat() if discount.expires_at else None,
        },
        _rollback,
    )


def _normalize_payload(payload_json: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(payload_json, dict):
        return payload_json
    return {}


def _normalize_conditions(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        if not field:
            continue
        normalized.append(
            {
                "field": field,
                "operator": str(item.get("operator") or "eq").strip().lower(),
                "value": item.get("value"),
                "case_sensitive": bool(item.get("case_sensitive", False)),
            }
        )
    return normalized


def _normalize_actions(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        action_type = str(item.get("type") or "").strip().lower()
        if not action_type:
            continue
        normalized.append(
            {
                "type": action_type,
                "config_json": _normalize_action_config(item.get("config_json")),
            }
        )
    return normalized


def _normalize_action_config(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _resolve_customer_id(*, config_json: dict[str, Any], context: dict[str, Any]) -> str | None:
    customer_id = str(config_json.get("customer_id") or "").strip()
    if customer_id:
        return customer_id
    customer_id_from = str(config_json.get("customer_id_from") or "payload.customer_id").strip()
    if not customer_id_from:
        return None
    resolved = _resolve_path(context, customer_id_from)
    if resolved is None:
        return None
    value = str(resolved).strip()
    return value or None


def _resolve_path(container: Any, path: str) -> Any:
    normalized = (path or "").strip()
    if not normalized:
        return None
    if normalized.startswith("$."):
        normalized = normalized[2:]
    elif normalized.startswith("$"):
        normalized = normalized[1:]

    current: Any = container
    for part in [item for item in normalized.split(".") if item]:
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue
        if isinstance(current, list):
            if not part.isdigit():
                return None
            index = int(part)
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


def _condition_matches(
    actual: Any,
    *,
    operator: str,
    expected: Any,
    case_sensitive: bool,
) -> bool:
    op = operator.strip().lower()
    if op == "exists":
        return _has_value(actual)
    if op == "not_exists":
        return not _has_value(actual)

    if op in {"gt", "gte", "lt", "lte"}:
        left = _to_number(actual)
        right = _to_number(expected)
        if left is None or right is None:
            return False
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "lt":
            return left < right
        return left <= right

    if op == "contains":
        if isinstance(actual, str):
            left_text = actual if case_sensitive else actual.lower()
            right_text = str(expected or "")
            right_text = right_text if case_sensitive else right_text.lower()
            return right_text in left_text
        if isinstance(actual, (list, tuple, set)):
            return expected in actual
        return False

    if op == "in":
        if isinstance(expected, (list, tuple, set)):
            return actual in expected
        return False

    if op == "neq":
        return not _equals(actual, expected, case_sensitive=case_sensitive)
    return _equals(actual, expected, case_sensitive=case_sensitive)


def _equals(left: Any, right: Any, *, case_sensitive: bool) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        if case_sensitive:
            return left == right
        return left.lower() == right.lower()
    return left == right


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _render_template(template: str, context: dict[str, Any]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        resolved = _resolve_path(context, key)
        if resolved is None:
            return ""
        if isinstance(resolved, (dict, list)):
            return json.dumps(resolved, ensure_ascii=True)
        return str(resolved)

    return _TEMPLATE_VAR_RE.sub(_replace, template)


def _ensure_unique_discount_code(db: Session, *, business_id: str, code: str) -> str:
    candidate = code.strip().upper()
    if not candidate:
        candidate = f"AUTO-{uuid.uuid4().hex[:8].upper()}"

    index = 2
    while db.execute(
        select(AutomationDiscount.id).where(
            AutomationDiscount.business_id == business_id,
            func.lower(AutomationDiscount.code) == candidate.lower(),
        )
    ).scalar_one_or_none():
        candidate = f"{code}-{index}"
        index += 1
    return candidate


def _unique_rule_name(db: Session, *, business_id: str, seed_name: str) -> str:
    base = (seed_name or "Automation Rule").strip() or "Automation Rule"
    candidate = base
    suffix = 2
    while db.execute(
        select(AutomationRule.id).where(
            AutomationRule.business_id == business_id,
            func.lower(AutomationRule.name) == candidate.lower(),
        )
    ).scalar_one_or_none():
        candidate = f"{base} ({suffix})"
        suffix += 1
    return candidate


def _short_error(value: Exception | str) -> str:
    text = str(value).strip() or "Automation action failed"
    return text[:255]
