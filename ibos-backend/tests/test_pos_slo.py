import uuid
from time import perf_counter

import pytest
from sqlalchemy import func, select

from app.models.business import Business
from app.models.order import Order
from app.models.user import User


def _register(client, *, email: str, full_name: str = "Owner"):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": full_name,
            "password": "password123",
            "business_name": f"{full_name} Biz",
        },
    )


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_product_with_variant(client, token: str) -> tuple[str, str]:
    create_product = client.post(
        "/products",
        json={"name": "SLO Fabric", "category": "fabrics"},
        headers=_auth_headers(token),
    )
    assert create_product.status_code == 200, create_product.text
    product_id = create_product.json()["id"]

    create_variant = client.post(
        f"/products/{product_id}/variants",
        json={
            "size": "6x6",
            "label": "SLO",
            "sku": f"SLO-{uuid.uuid4().hex[:8]}",
            "reorder_level": 5,
            "cost_price": 40.0,
            "selling_price": 80.0,
        },
        headers=_auth_headers(token),
    )
    assert create_variant.status_code == 200, create_variant.text
    return product_id, create_variant.json()["id"]


def _p95_ms(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, int(round(0.95 * len(ordered))) - 1)
    return ordered[min(index, len(ordered) - 1)]


def test_pos_offline_sync_slo_latency_and_reliability(test_context):
    """
    P3-E13-006:
    Define and enforce POS offline sync SLO thresholds in integration tests.
    """

    client, session_local = test_context

    register = _register(client, email="pos-slo-owner@example.com")
    assert register.status_code == 200, register.text
    token = register.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)
    seed_stock = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 150, "unit_cost": 40},
        headers=_auth_headers(token),
    )
    assert seed_stock.status_code == 200, seed_stock.text

    max_sync_p95_ms = 1200.0
    max_shift_endpoint_ms = 1000.0
    min_sync_success_ratio = 0.99
    sample_size = 25
    unit_price = 80.0

    open_start = perf_counter()
    open_shift = client.post(
        "/pos/shifts/open",
        json={"opening_cash": 100.0, "note": "SLO baseline shift"},
        headers=_auth_headers(token),
    )
    open_ms = (perf_counter() - open_start) * 1000
    assert open_shift.status_code == 200, open_shift.text
    shift_id = open_shift.json()["id"]

    sync_latencies_ms: list[float] = []
    event_payloads: list[dict] = []
    total_processed = 0
    total_created = 0
    total_conflicted = 0

    for idx in range(sample_size):
        event_id = f"pos-slo-evt-{idx:03d}"
        event_payload = {
            "client_event_id": event_id,
            "payment_method": "cash",
            "channel": "walk-in",
            "note": "SLO order",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": unit_price}],
        }
        event_payloads.append(event_payload)
        sync_payload = {"conflict_policy": "reject_conflict", "orders": [event_payload]}

        started = perf_counter()
        sync_res = client.post(
            "/pos/offline-orders/sync",
            json=sync_payload,
            headers=_auth_headers(token),
        )
        duration_ms = (perf_counter() - started) * 1000
        sync_latencies_ms.append(duration_ms)
        assert sync_res.status_code == 200, sync_res.text

        sync_body = sync_res.json()
        total_processed += sync_body["processed"]
        total_created += sync_body["created"]
        total_conflicted += sync_body["conflicted"]
        assert sync_body["processed"] == 1
        assert sync_body["created"] == 1
        assert sync_body["conflicted"] == 0
        assert sync_body["duplicate"] == 0

    sync_success_ratio = total_created / total_processed if total_processed else 0.0
    sync_p95_ms = _p95_ms(sync_latencies_ms)

    assert total_conflicted == 0
    assert sync_success_ratio >= min_sync_success_ratio
    assert sync_p95_ms <= max_sync_p95_ms

    duplicate_replay = client.post(
        "/pos/offline-orders/sync",
        json={"conflict_policy": "reject_conflict", "orders": event_payloads},
        headers=_auth_headers(token),
    )
    assert duplicate_replay.status_code == 200, duplicate_replay.text
    duplicate_body = duplicate_replay.json()
    assert duplicate_body["processed"] == sample_size
    assert duplicate_body["created"] == 0
    assert duplicate_body["conflicted"] == 0
    assert duplicate_body["duplicate"] == sample_size

    current_start = perf_counter()
    current_shift = client.get("/pos/shifts/current", headers=_auth_headers(token))
    current_ms = (perf_counter() - current_start) * 1000
    assert current_shift.status_code == 200, current_shift.text
    assert current_shift.json()["shift"]["id"] == shift_id

    expected_cash = 100.0 + (sample_size * unit_price)
    close_start = perf_counter()
    close_shift = client.post(
        f"/pos/shifts/{shift_id}/close",
        json={"closing_cash": expected_cash, "note": "SLO close"},
        headers=_auth_headers(token),
    )
    close_ms = (perf_counter() - close_start) * 1000
    assert close_shift.status_code == 200, close_shift.text
    assert close_shift.json()["status"] == "closed"
    assert close_shift.json()["expected_cash"] == pytest.approx(expected_cash)
    assert close_shift.json()["cash_difference"] == pytest.approx(0.0)

    assert open_ms <= max_shift_endpoint_ms
    assert current_ms <= max_shift_endpoint_ms
    assert close_ms <= max_shift_endpoint_ms

    db = session_local()
    try:
        user = db.execute(select(User).where(User.email == "pos-slo-owner@example.com")).scalar_one()
        business = db.execute(select(Business).where(Business.owner_user_id == user.id)).scalar_one()
        order_count = int(
            db.execute(select(func.count(Order.id)).where(Order.business_id == business.id)).scalar_one()
        )
    finally:
        db.close()

    assert order_count == sample_size
