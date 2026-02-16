import uuid

import pytest
from sqlalchemy import select

from app.core.google_auth import GoogleIdentity
from app.models.business import Business
from app.models.expense import Expense
from app.models.sales import Sale
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
    create_product_res = client.post(
        "/products",
        json={"name": "Ankara Fabric", "category": "fabrics"},
        headers=_auth_headers(token),
    )
    assert create_product_res.status_code == 200, create_product_res.text
    product_id = create_product_res.json()["id"]

    create_variant_res = client.post(
        f"/products/{product_id}/variants",
        json={
            "size": "6x6",
            "label": "Plain",
            "sku": f"ANK-{uuid.uuid4().hex[:6]}",
            "reorder_level": 4,
            "cost_price": 50.0,
            "selling_price": 100.0,
        },
        headers=_auth_headers(token),
    )
    assert create_variant_res.status_code == 200, create_variant_res.text
    variant_id = create_variant_res.json()["id"]

    return product_id, variant_id


def test_auth_register_and_login_email_or_username(test_context):
    client, session_local = test_context

    register_res = _register(client, email="auth-owner@example.com")
    assert register_res.status_code == 200, register_res.text
    register_body = register_res.json()
    assert register_body["token_type"] == "bearer"
    assert register_body["access_token"]
    assert register_body["refresh_token"]

    db = session_local()
    try:
        user = db.execute(
            select(User).where(User.email == "auth-owner@example.com")
        ).scalar_one()
    finally:
        db.close()

    assert len(user.id) == 22

    login_res = client.post(
        "/auth/login",
        json={"identifier": "auth-owner@example.com", "password": "password123"},
    )
    assert login_res.status_code == 200, login_res.text
    login_body = login_res.json()
    assert login_body["token_type"] == "bearer"
    assert login_body["access_token"]
    assert login_body["refresh_token"]

    login_by_username_res = client.post(
        "/auth/login",
        json={"identifier": user.username, "password": "password123"},
    )
    assert login_by_username_res.status_code == 200, login_by_username_res.text


def test_auth_refresh_token_returns_new_access(test_context):
    client, _ = test_context

    register_res = _register(client, email="refresh-owner@example.com")
    assert register_res.status_code == 200, register_res.text

    refresh_res = client.post(
        "/auth/refresh",
        json={"refresh_token": register_res.json()["refresh_token"]},
    )
    assert refresh_res.status_code == 200, refresh_res.text
    refresh_body = refresh_res.json()
    assert refresh_body["access_token"]
    assert refresh_body["refresh_token"]
    assert refresh_body["token_type"] == "bearer"

    second_refresh_res = client.post(
        "/auth/refresh",
        json={"refresh_token": register_res.json()["refresh_token"]},
    )
    assert second_refresh_res.status_code == 401, second_refresh_res.text


def test_auth_logout_revokes_refresh_token(test_context):
    client, _ = test_context

    register_res = _register(client, email="logout-owner@example.com")
    assert register_res.status_code == 200, register_res.text
    refresh_token = register_res.json()["refresh_token"]

    logout_res = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_res.status_code == 200, logout_res.text
    assert logout_res.json()["ok"] is True

    refresh_res = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 401, refresh_res.text


def test_change_password_revokes_active_sessions(test_context):
    client, _ = test_context

    register_res = _register(client, email="password-owner@example.com")
    assert register_res.status_code == 200, register_res.text
    access_token = register_res.json()["access_token"]
    refresh_token = register_res.json()["refresh_token"]

    change_res = client.post(
        "/auth/change-password",
        json={"current_password": "password123", "new_password": "newpassword123"},
        headers=_auth_headers(access_token),
    )
    assert change_res.status_code == 200, change_res.text
    assert change_res.json()["ok"] is True

    old_login = client.post(
        "/auth/login",
        json={"identifier": "password-owner@example.com", "password": "password123"},
    )
    assert old_login.status_code == 401, old_login.text

    new_login = client.post(
        "/auth/login",
        json={"identifier": "password-owner@example.com", "password": "newpassword123"},
    )
    assert new_login.status_code == 200, new_login.text

    old_refresh = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert old_refresh.status_code == 401, old_refresh.text


def test_auth_login_rate_limited_after_repeated_failures(test_context):
    client, _ = test_context

    register_res = _register(client, email="ratelimit-owner@example.com")
    assert register_res.status_code == 200, register_res.text

    for _ in range(5):
        failed_login = client.post(
            "/auth/login",
            json={"identifier": "ratelimit-owner@example.com", "password": "wrongpass"},
        )
        assert failed_login.status_code == 401, failed_login.text

    blocked_login = client.post(
        "/auth/login",
        json={"identifier": "ratelimit-owner@example.com", "password": "wrongpass"},
    )
    assert blocked_login.status_code == 429, blocked_login.text


def test_google_auth_register_or_login(test_context, monkeypatch):
    client, session_local = test_context

    from app.routers import auth as auth_router

    def fake_verify_google_token(_: str) -> GoogleIdentity:
        return GoogleIdentity(
            sub="google-sub-123",
            email="google-owner@example.com",
            full_name="Google Owner",
        )

    monkeypatch.setattr(
        auth_router,
        "verify_google_identity_token",
        fake_verify_google_token,
    )

    first_google_login = client.post(
        "/auth/google",
        json={"id_token": "dummy-token", "business_name": "Google Biz"},
    )
    assert first_google_login.status_code == 200, first_google_login.text
    first_body = first_google_login.json()
    assert first_body["access_token"]
    assert first_body["refresh_token"]

    second_google_login = client.post(
        "/auth/google",
        json={"id_token": "dummy-token"},
    )
    assert second_google_login.status_code == 200, second_google_login.text

    db = session_local()
    try:
        user = db.execute(
            select(User).where(User.email == "google-owner@example.com")
        ).scalar_one()
        assert user.google_sub == "google-sub-123"
        assert len(user.id) == 22
    finally:
        db.close()


def test_dashboard_summary_is_tenant_isolated(test_context):
    client, session_local = test_context

    owner_1 = _register(client, email="owner1@example.com", full_name="Owner One")
    owner_2 = _register(client, email="owner2@example.com", full_name="Owner Two")
    assert owner_1.status_code == 200, owner_1.text
    assert owner_2.status_code == 200, owner_2.text

    owner_1_token = owner_1.json()["access_token"]

    db = session_local()
    try:
        user_1 = db.execute(select(User).where(User.email == "owner1@example.com")).scalar_one()
        user_2 = db.execute(select(User).where(User.email == "owner2@example.com")).scalar_one()
        biz_1 = db.execute(select(Business).where(Business.owner_user_id == user_1.id)).scalar_one()
        biz_2 = db.execute(select(Business).where(Business.owner_user_id == user_2.id)).scalar_one()

        db.add_all(
            [
                Sale(
                    id=str(uuid.uuid4()),
                    business_id=biz_1.id,
                    payment_method="cash",
                    channel="whatsapp",
                    total_amount=150.0,
                ),
                Sale(
                    id=str(uuid.uuid4()),
                    business_id=biz_2.id,
                    payment_method="pos",
                    channel="instagram",
                    total_amount=999.0,
                ),
                Expense(
                    id=str(uuid.uuid4()),
                    business_id=biz_1.id,
                    category="logistics",
                    amount=30.0,
                    note="dispatch",
                ),
                Expense(
                    id=str(uuid.uuid4()),
                    business_id=biz_2.id,
                    category="rent",
                    amount=400.0,
                    note="store",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    summary_res = client.get(
        "/dashboard/summary",
        headers={"Authorization": f"Bearer {owner_1_token}"},
    )
    assert summary_res.status_code == 200, summary_res.text
    summary = summary_res.json()

    assert summary["sales_total"] == pytest.approx(150.0)
    assert summary["sales_count"] == 1
    assert summary["average_sale_value"] == pytest.approx(150.0)
    assert summary["expense_total"] == pytest.approx(30.0)
    assert summary["expense_count"] == 1
    assert summary["profit_simple"] == pytest.approx(120.0)


def test_sales_prevent_duplicate_variant_oversell(test_context):
    client, _ = test_context

    owner = _register(client, email="sales-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    stock_res = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 5},
        headers=_auth_headers(token),
    )
    assert stock_res.status_code == 200, stock_res.text

    oversell_res = client.post(
        "/sales",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [
                {"variant_id": variant_id, "qty": 3, "unit_price": 100},
                {"variant_id": variant_id, "qty": 3, "unit_price": 100},
            ],
        },
        headers=_auth_headers(token),
    )
    assert oversell_res.status_code == 400, oversell_res.text
    assert "Insufficient stock" in oversell_res.text


def test_inventory_stock_endpoint_is_tenant_isolated(test_context):
    client, _ = test_context

    owner_1 = _register(client, email="tenant1@example.com")
    owner_2 = _register(client, email="tenant2@example.com")
    assert owner_1.status_code == 200, owner_1.text
    assert owner_2.status_code == 200, owner_2.text

    token_1 = owner_1.json()["access_token"]
    token_2 = owner_2.json()["access_token"]

    _, variant_id_owner_2 = _create_product_with_variant(client, token_2)

    stock_lookup = client.get(
        f"/inventory/stock/{variant_id_owner_2}",
        headers=_auth_headers(token_1),
    )
    assert stock_lookup.status_code == 404, stock_lookup.text


def test_sales_and_expenses_list_endpoints(test_context):
    client, _ = test_context

    owner = _register(client, email="list-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    stock_res = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 10},
        headers=_auth_headers(token),
    )
    assert stock_res.status_code == 200, stock_res.text

    sale_res = client.post(
        "/sales",
        json={
            "payment_method": "transfer",
            "channel": "instagram",
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 120}],
        },
        headers=_auth_headers(token),
    )
    assert sale_res.status_code == 200, sale_res.text

    expense_res = client.post(
        "/expenses",
        json={"category": "logistics", "amount": 20.0, "note": "delivery"},
        headers=_auth_headers(token),
    )
    assert expense_res.status_code == 200, expense_res.text

    sales_list = client.get("/sales?limit=10&offset=0", headers=_auth_headers(token))
    assert sales_list.status_code == 200, sales_list.text
    sales_payload = sales_list.json()
    assert sales_payload["pagination"]["total"] == 1
    assert sales_payload["items"][0]["channel"] == "instagram"

    expenses_list = client.get("/expenses?limit=10&offset=0", headers=_auth_headers(token))
    assert expenses_list.status_code == 200, expenses_list.text
    expenses_payload = expenses_list.json()
    assert expenses_payload["pagination"]["total"] == 1
    assert expenses_payload["items"][0]["category"] == "logistics"


def test_refund_restocks_inventory_and_reduces_net_sales(test_context):
    client, _ = test_context

    owner = _register(client, email="refund-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 5},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    sale_res = client.post(
        "/sales",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 3, "unit_price": 60}],
        },
        headers=_auth_headers(token),
    )
    assert sale_res.status_code == 200, sale_res.text
    sale_id = sale_res.json()["id"]

    refund_res = client.post(
        f"/sales/{sale_id}/refund",
        json={
            "note": "customer return",
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 60}],
        },
        headers=_auth_headers(token),
    )
    assert refund_res.status_code == 200, refund_res.text

    stock_after = client.get(
        f"/inventory/stock/{variant_id}",
        headers=_auth_headers(token),
    )
    assert stock_after.status_code == 200, stock_after.text
    assert stock_after.json()["stock"] == 4

    summary_res = client.get("/dashboard/summary", headers=_auth_headers(token))
    assert summary_res.status_code == 200, summary_res.text
    summary = summary_res.json()
    assert summary["sales_total"] == pytest.approx(60.0)

    excessive_refund = client.post(
        f"/sales/{sale_id}/refund",
        json={"items": [{"variant_id": variant_id, "qty": 5, "unit_price": 60}]},
        headers=_auth_headers(token),
    )
    assert excessive_refund.status_code == 400, excessive_refund.text


def test_inventory_adjustment_and_low_stock_listing(test_context):
    client, _ = test_context

    owner = _register(client, email="inventory-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    product_id, variant_id = _create_product_with_variant(client, token)

    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 5},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    adjust_res = client.post(
        "/inventory/adjust",
        json={
            "variant_id": variant_id,
            "qty_delta": -2,
            "reason": "damaged_stock",
            "note": "damaged while packaging",
        },
        headers=_auth_headers(token),
    )
    assert adjust_res.status_code == 200, adjust_res.text

    stock_after = client.get(
        f"/inventory/stock/{variant_id}",
        headers=_auth_headers(token),
    )
    assert stock_after.status_code == 200, stock_after.text
    assert stock_after.json()["stock"] == 3

    low_stock_res = client.get("/inventory/low-stock", headers=_auth_headers(token))
    assert low_stock_res.status_code == 200, low_stock_res.text
    low_stock_items = low_stock_res.json()["items"]
    assert any(item["variant_id"] == variant_id for item in low_stock_items)

    variants_res = client.get(f"/products/{product_id}/variants", headers=_auth_headers(token))
    assert variants_res.status_code == 200, variants_res.text
    assert variants_res.json()["items"][0]["reorder_level"] == 4
