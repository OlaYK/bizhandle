from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_docs import error_responses
from app.core.deps import get_db
from app.core.permissions import require_permission
from app.core.security_current import BusinessAccess, get_current_business, get_current_user
from app.models.ai_copilot import AIGeneratedInsight, AIGovernanceTrace, AIPrescriptiveAction, AIRiskAlertConfig, AIRiskAlertEvent
from app.models.user import User
from app.schemas.ai import (
    AIAnalyticsAssistantMetricOut,
    AIAnalyticsAssistantOut,
    AIAnalyticsAssistantQueryIn,
    AIAskIn,
    AIFeatureSnapshotOut,
    AIGovernanceTraceDetailOut,
    AIGovernanceTraceListOut,
    AIGovernanceTraceOut,
    AIInsightV2ListOut,
    AIInsightV2Out,
    AIInsightsGenerateOut,
    AIPrescriptiveActionListOut,
    AIPrescriptiveActionOut,
    AIPrescriptiveDecisionIn,
    AIRiskAlertConfigIn,
    AIRiskAlertConfigOut,
    AIRiskAlertEventListOut,
    AIRiskAlertEventOut,
    AIRiskAlertRunOut,
    AIResponseOut,
    AITokenUsageOut,
)
from app.services.ai_service import (
    answer_analytics_assistant_query,
    answer_business_question,
    create_governance_trace,
    evaluate_risk_alerts,
    generate_insight,
    generate_v2_insights,
    get_or_create_risk_alert_config,
    latest_feature_snapshot,
    refresh_feature_snapshot,
    update_risk_alert_config,
)
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/ai", tags=["ai"])


def _feature_snapshot_out(snapshot) -> AIFeatureSnapshotOut:
    return AIFeatureSnapshotOut(
        id=snapshot.id,
        window_start_date=snapshot.window_start_date,
        window_end_date=snapshot.window_end_date,
        orders_count=int(snapshot.orders_count or 0),
        paid_orders_count=int(snapshot.paid_orders_count or 0),
        gross_revenue=float(snapshot.gross_revenue or 0),
        refunds_count=int(snapshot.refunds_count or 0),
        refunds_amount=float(snapshot.refunds_amount or 0),
        net_revenue=float(snapshot.net_revenue or 0),
        expenses_total=float(snapshot.expenses_total or 0),
        refund_rate=float(snapshot.refund_rate or 0),
        stockout_events_count=int(snapshot.stockout_events_count or 0),
        campaigns_sent_count=int(snapshot.campaigns_sent_count or 0),
        campaigns_failed_count=int(snapshot.campaigns_failed_count or 0),
        repeat_customers_count=int(snapshot.repeat_customers_count or 0),
        created_at=snapshot.created_at,
    )


def _insight_v2_out(insight: AIGeneratedInsight) -> AIInsightV2Out:
    return AIInsightV2Out(
        id=insight.id,
        feature_snapshot_id=insight.feature_snapshot_id,
        insight_type=insight.insight_type,
        severity=insight.severity,
        title=insight.title,
        summary=insight.summary,
        confidence_score=float(insight.confidence_score or 0),
        status=insight.status,
        context_json=insight.context_json,
        created_at=insight.created_at,
    )


def _action_out(action: AIPrescriptiveAction) -> AIPrescriptiveActionOut:
    return AIPrescriptiveActionOut(
        id=action.id,
        insight_id=action.insight_id,
        action_type=action.action_type,
        title=action.title,
        description=action.description,
        payload_json=action.payload_json,
        status=action.status,
        decision_note=action.decision_note,
        decided_by_user_id=action.decided_by_user_id,
        decided_at=action.decided_at,
        executed_at=action.executed_at,
        created_at=action.created_at,
        updated_at=action.updated_at,
    )


def _risk_config_out(config: AIRiskAlertConfig) -> AIRiskAlertConfigOut:
    return AIRiskAlertConfigOut(
        id=config.id,
        enabled=bool(config.enabled),
        refund_rate_threshold=float(config.refund_rate_threshold),
        stockout_threshold=int(config.stockout_threshold),
        cashflow_margin_threshold=float(config.cashflow_margin_threshold),
        channels=list(config.channels_json or []),
        updated_by_user_id=config.updated_by_user_id,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _risk_event_out(event: AIRiskAlertEvent) -> AIRiskAlertEventOut:
    return AIRiskAlertEventOut(
        id=event.id,
        alert_type=event.alert_type,
        severity=event.severity,
        status=event.status,
        message=event.message,
        triggered_value=float(event.triggered_value or 0),
        threshold_value=float(event.threshold_value or 0),
        channels=list(event.channels_json or []),
        context_json=event.context_json,
        created_at=event.created_at,
    )


def _trace_out(trace: AIGovernanceTrace) -> AIGovernanceTraceOut:
    return AIGovernanceTraceOut(
        id=trace.id,
        trace_type=trace.trace_type,
        actor_user_id=trace.actor_user_id,
        feature_snapshot_id=trace.feature_snapshot_id,
        created_at=trace.created_at,
    )


def _trace_detail_out(trace: AIGovernanceTrace) -> AIGovernanceTraceDetailOut:
    return AIGovernanceTraceDetailOut(
        id=trace.id,
        trace_type=trace.trace_type,
        actor_user_id=trace.actor_user_id,
        feature_snapshot_id=trace.feature_snapshot_id,
        created_at=trace.created_at,
        prompt=trace.prompt,
        context_json=trace.context_json,
        output_json=trace.output_json,
    )


@router.post(
    "/ask",
    response_model=AIResponseOut,
    summary="Ask AI about your business",
    responses=error_responses(400, 401, 404, 422, 500),
)
def ask_business_question(
    payload: AIAskIn,
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
    actor: User = Depends(get_current_user),
):
    try:
        result = answer_business_question(db, business_id=biz.id, question=payload.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(result.log)
    trace = create_governance_trace(
        db,
        business_id=biz.id,
        trace_type="ai.ask",
        actor_user_id=actor.id,
        feature_snapshot_id=None,
        prompt=payload.question.strip(),
        context_json=result.log.metadata_json if isinstance(result.log.metadata_json, dict) else None,
        output_json={"response": result.response, "model": result.log.model},
    )
    db.commit()
    db.refresh(result.log)
    db.refresh(trace)

    return AIResponseOut(
        id=result.log.id,
        insight_type=result.log.insight_type,
        response=result.response,
        provider=result.log.provider,
        model=result.log.model,
        token_usage=AITokenUsageOut(
            prompt_tokens=result.log.prompt_tokens,
            completion_tokens=result.log.completion_tokens,
            total_tokens=result.log.total_tokens,
        ),
        estimated_cost_usd=result.log.estimated_cost_usd,
    )


@router.get(
    "/insights/daily",
    response_model=AIResponseOut,
    summary="Generate daily AI insight",
    responses=error_responses(400, 401, 404, 422, 500),
)
def get_daily_insight(
    db: Session = Depends(get_db),
    biz=Depends(get_current_business),
    actor: User = Depends(get_current_user),
):
    try:
        result = generate_insight(db, business_id=biz.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(result.log)
    trace = create_governance_trace(
        db,
        business_id=biz.id,
        trace_type="ai.daily_insight",
        actor_user_id=actor.id,
        feature_snapshot_id=None,
        prompt="Generate daily insight",
        context_json=result.log.metadata_json if isinstance(result.log.metadata_json, dict) else None,
        output_json={"response": result.response, "model": result.log.model},
    )
    db.commit()
    db.refresh(result.log)
    db.refresh(trace)

    return AIResponseOut(
        id=result.log.id,
        insight_type=result.log.insight_type,
        response=result.response,
        provider=result.log.provider,
        model=result.log.model,
        token_usage=AITokenUsageOut(
            prompt_tokens=result.log.prompt_tokens,
            completion_tokens=result.log.completion_tokens,
            total_tokens=result.log.total_tokens,
        ),
        estimated_cost_usd=result.log.estimated_cost_usd,
    )


@router.post(
    "/feature-store/refresh",
    response_model=AIFeatureSnapshotOut,
    summary="Refresh AI event-aware feature store snapshot",
    responses=error_responses(400, 401, 403, 422, 500),
)
def refresh_ai_feature_store(
    window_days: int = Query(default=30, ge=7, le=120),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.feature_store.refresh")),
    actor: User = Depends(get_current_user),
):
    snapshot = refresh_feature_snapshot(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        window_days=window_days,
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="ai.feature_store.refresh",
        target_type="ai_feature_snapshot",
        target_id=snapshot.id,
        metadata_json={
            "window_days": window_days,
            "window_start_date": snapshot.window_start_date.isoformat(),
            "window_end_date": snapshot.window_end_date.isoformat(),
        },
    )
    create_governance_trace(
        db,
        business_id=access.business.id,
        trace_type="feature_store.refresh",
        actor_user_id=actor.id,
        feature_snapshot_id=snapshot.id,
        prompt=f"Refresh feature store window_days={window_days}",
        context_json={
            "window_start_date": snapshot.window_start_date.isoformat(),
            "window_end_date": snapshot.window_end_date.isoformat(),
        },
        output_json={"snapshot_id": snapshot.id},
    )
    db.commit()
    db.refresh(snapshot)
    return _feature_snapshot_out(snapshot)


@router.get(
    "/feature-store/latest",
    response_model=AIFeatureSnapshotOut,
    summary="Get latest AI feature store snapshot",
    responses=error_responses(401, 403, 404, 500),
)
def get_latest_ai_feature_store_snapshot(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.feature_store.view")),
):
    snapshot = latest_feature_snapshot(db, business_id=access.business.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No AI feature snapshot found. Run refresh first.")
    return _feature_snapshot_out(snapshot)


@router.post(
    "/insights/v2/generate",
    response_model=AIInsightsGenerateOut,
    summary="Generate AI insight taxonomy v2 with prescriptive actions",
    responses=error_responses(400, 401, 403, 422, 500),
)
def generate_ai_insights_v2(
    window_days: int = Query(default=30, ge=7, le=120),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.insights.v2.generate")),
    actor: User = Depends(get_current_user),
):
    snapshot, insights, actions = generate_v2_insights(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        window_days=window_days,
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="ai.insights.v2.generate",
        target_type="ai_generated_insight",
        target_id=None,
        metadata_json={
            "window_days": window_days,
            "insights_created": len(insights),
            "actions_created": len(actions),
            "feature_snapshot_id": snapshot.id,
        },
    )
    create_governance_trace(
        db,
        business_id=access.business.id,
        trace_type="insights_v2.generate",
        actor_user_id=actor.id,
        feature_snapshot_id=snapshot.id,
        prompt=f"Generate insight taxonomy v2 window_days={window_days}",
        context_json={"window_days": window_days, "feature_snapshot_id": snapshot.id},
        output_json={
            "insight_ids": [item.id for item in insights],
            "action_ids": [item.id for item in actions],
        },
    )
    db.commit()
    db.refresh(snapshot)
    return AIInsightsGenerateOut(
        snapshot=_feature_snapshot_out(snapshot),
        insights=[_insight_v2_out(item) for item in insights],
        actions_created=len(actions),
    )


@router.get(
    "/insights/v2",
    response_model=AIInsightV2ListOut,
    summary="List AI insight taxonomy v2 items",
    responses=error_responses(401, 403, 500),
)
def list_ai_insights_v2(
    status: str | None = Query(default=None),
    insight_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.insights.v2.view")),
):
    stmt = select(AIGeneratedInsight).where(AIGeneratedInsight.business_id == access.business.id)
    if status and status.strip():
        stmt = stmt.where(AIGeneratedInsight.status == status.strip().lower())
    if insight_type and insight_type.strip():
        stmt = stmt.where(AIGeneratedInsight.insight_type == insight_type.strip().lower())
    rows = db.execute(stmt.order_by(AIGeneratedInsight.created_at.desc())).scalars().all()
    return AIInsightV2ListOut(
        items=[_insight_v2_out(item) for item in rows],
        status=status.strip().lower() if status else None,
        insight_type=insight_type.strip().lower() if insight_type else None,
    )


@router.get(
    "/actions",
    response_model=AIPrescriptiveActionListOut,
    summary="List AI prescriptive actions",
    responses=error_responses(401, 403, 500),
)
def list_ai_prescriptive_actions(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.actions.view")),
):
    stmt = select(AIPrescriptiveAction).where(AIPrescriptiveAction.business_id == access.business.id)
    if status and status.strip():
        stmt = stmt.where(AIPrescriptiveAction.status == status.strip().lower())
    rows = db.execute(stmt.order_by(AIPrescriptiveAction.created_at.desc())).scalars().all()
    return AIPrescriptiveActionListOut(
        items=[_action_out(item) for item in rows],
        status=status.strip().lower() if status else None,
    )


@router.post(
    "/actions/{action_id}/decision",
    response_model=AIPrescriptiveActionOut,
    summary="Approve or reject AI prescriptive action",
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
def decide_ai_prescriptive_action(
    action_id: str,
    payload: AIPrescriptiveDecisionIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.actions.review")),
    actor: User = Depends(get_current_user),
):
    action = db.execute(
        select(AIPrescriptiveAction).where(
            AIPrescriptiveAction.id == action_id,
            AIPrescriptiveAction.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=404, detail="AI action not found")
    if action.status != "proposed":
        raise HTTPException(status_code=400, detail="Action can only be decided from proposed state")

    action.status = "approved" if payload.decision == "approve" else "rejected"
    action.decision_note = payload.note
    action.decided_by_user_id = actor.id
    action.decided_at = datetime.now(timezone.utc)

    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="ai.action.decision",
        target_type="ai_prescriptive_action",
        target_id=action.id,
        metadata_json={
            "decision": payload.decision,
            "insight_id": action.insight_id,
            "note_present": bool(payload.note and payload.note.strip()),
        },
    )
    db.commit()
    db.refresh(action)
    return _action_out(action)


@router.post(
    "/analytics-assistant/query",
    response_model=AIAnalyticsAssistantOut,
    summary="Answer natural-language analytics query from curated metrics",
    responses=error_responses(400, 401, 403, 422, 500),
)
def query_analytics_assistant(
    payload: AIAnalyticsAssistantQueryIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.analytics.assistant.query")),
    actor: User = Depends(get_current_user),
):
    result = answer_analytics_assistant_query(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        question=payload.question,
        window_days=payload.window_days,
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="ai.analytics_assistant.query",
        target_type="ai_governance_trace",
        target_id=result.trace.id,
        metadata_json={"window_days": payload.window_days},
    )
    db.commit()
    db.refresh(result.trace)
    return AIAnalyticsAssistantOut(
        answer=result.answer,
        grounded_metrics=[
            AIAnalyticsAssistantMetricOut(key=item.key, value=item.value, source=item.source)
            for item in result.metrics
        ],
        trace_id=result.trace.id,
    )


@router.get(
    "/risk-alerts/config",
    response_model=AIRiskAlertConfigOut,
    summary="Get AI proactive risk-alert configuration",
    responses=error_responses(401, 403, 500),
)
def get_risk_alert_config(
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.risk_alerts.config.view")),
    actor: User = Depends(get_current_user),
):
    config = get_or_create_risk_alert_config(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
    )
    db.commit()
    db.refresh(config)
    return _risk_config_out(config)


@router.put(
    "/risk-alerts/config",
    response_model=AIRiskAlertConfigOut,
    summary="Update AI proactive risk-alert thresholds and channels",
    responses=error_responses(400, 401, 403, 422, 500),
)
def put_risk_alert_config(
    payload: AIRiskAlertConfigIn,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.risk_alerts.config.manage")),
    actor: User = Depends(get_current_user),
):
    config = update_risk_alert_config(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        enabled=payload.enabled,
        refund_rate_threshold=payload.refund_rate_threshold,
        stockout_threshold=payload.stockout_threshold,
        cashflow_margin_threshold=payload.cashflow_margin_threshold,
        channels=payload.channels,
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="ai.risk_alerts.config.update",
        target_type="ai_risk_alert_config",
        target_id=config.id,
        metadata_json={
            "enabled": payload.enabled,
            "refund_rate_threshold": payload.refund_rate_threshold,
            "stockout_threshold": payload.stockout_threshold,
            "cashflow_margin_threshold": payload.cashflow_margin_threshold,
            "channels": payload.channels,
        },
    )
    create_governance_trace(
        db,
        business_id=access.business.id,
        trace_type="risk_alerts.config.update",
        actor_user_id=actor.id,
        feature_snapshot_id=None,
        prompt="Update risk-alert config",
        context_json={
            "refund_rate_threshold": payload.refund_rate_threshold,
            "stockout_threshold": payload.stockout_threshold,
            "cashflow_margin_threshold": payload.cashflow_margin_threshold,
            "channels": payload.channels,
        },
        output_json={"config_id": config.id},
    )
    db.commit()
    db.refresh(config)
    return _risk_config_out(config)


@router.post(
    "/risk-alerts/run",
    response_model=AIRiskAlertRunOut,
    summary="Evaluate proactive AI risk alerts",
    responses=error_responses(401, 403, 422, 500),
)
def run_risk_alerts(
    window_days: int = Query(default=30, ge=7, le=120),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.risk_alerts.run")),
    actor: User = Depends(get_current_user),
):
    result = evaluate_risk_alerts(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        window_days=window_days,
    )
    create_governance_trace(
        db,
        business_id=access.business.id,
        trace_type="risk_alerts.run",
        actor_user_id=actor.id,
        feature_snapshot_id=result.snapshot.id,
        prompt=f"Run risk alerts window_days={window_days}",
        context_json={
            "window_days": window_days,
            "feature_snapshot_id": result.snapshot.id,
        },
        output_json={
            "triggered_count": len(result.events),
            "event_ids": [item.id for item in result.events],
        },
    )
    log_audit_event(
        db,
        business_id=access.business.id,
        actor_user_id=actor.id,
        action="ai.risk_alerts.run",
        target_type="ai_risk_alert_event",
        target_id=None,
        metadata_json={
            "window_days": window_days,
            "triggered_count": len(result.events),
            "feature_snapshot_id": result.snapshot.id,
        },
    )
    db.commit()
    db.refresh(result.snapshot)
    for event in result.events:
        db.refresh(event)
    return AIRiskAlertRunOut(
        triggered_count=len(result.events),
        snapshot_id=result.snapshot.id,
        events=[_risk_event_out(item) for item in result.events],
    )


@router.get(
    "/risk-alerts/events",
    response_model=AIRiskAlertEventListOut,
    summary="List proactive AI risk-alert events",
    responses=error_responses(401, 403, 500),
)
def list_risk_alert_events(
    status: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.risk_alerts.events.view")),
):
    stmt = select(AIRiskAlertEvent).where(AIRiskAlertEvent.business_id == access.business.id)
    if status and status.strip():
        stmt = stmt.where(AIRiskAlertEvent.status == status.strip().lower())
    if alert_type and alert_type.strip():
        stmt = stmt.where(AIRiskAlertEvent.alert_type == alert_type.strip().lower())
    rows = db.execute(stmt.order_by(AIRiskAlertEvent.created_at.desc())).scalars().all()
    return AIRiskAlertEventListOut(
        items=[_risk_event_out(item) for item in rows],
        status=status.strip().lower() if status else None,
        alert_type=alert_type.strip().lower() if alert_type else None,
    )


@router.get(
    "/governance/traces",
    response_model=AIGovernanceTraceListOut,
    summary="List AI governance traces for auditability",
    responses=error_responses(401, 403, 500),
)
def list_governance_traces(
    trace_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.governance.view")),
):
    stmt = select(AIGovernanceTrace).where(AIGovernanceTrace.business_id == access.business.id)
    if trace_type and trace_type.strip():
        stmt = stmt.where(AIGovernanceTrace.trace_type == trace_type.strip().lower())
    rows = db.execute(stmt.order_by(AIGovernanceTrace.created_at.desc())).scalars().all()
    return AIGovernanceTraceListOut(
        items=[_trace_out(item) for item in rows],
        trace_type=trace_type.strip().lower() if trace_type else None,
    )


@router.get(
    "/governance/traces/{trace_id}",
    response_model=AIGovernanceTraceDetailOut,
    summary="Get AI governance trace details",
    responses=error_responses(401, 403, 404, 500),
)
def get_governance_trace_detail(
    trace_id: str,
    db: Session = Depends(get_db),
    access: BusinessAccess = Depends(require_permission("ai.governance.view")),
):
    trace = db.execute(
        select(AIGovernanceTrace).where(
            AIGovernanceTrace.id == trace_id,
            AIGovernanceTrace.business_id == access.business.id,
        )
    ).scalar_one_or_none()
    if trace is None:
        raise HTTPException(status_code=404, detail="Governance trace not found")
    return _trace_detail_out(trace)
