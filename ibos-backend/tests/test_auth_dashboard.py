import hashlib
import hmac
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select, update

from app.core.google_auth import GoogleIdentity
from app.core.config import settings
from app.core.security import hash_password
from app.models.business import Business
from app.models.business_membership import BusinessMembership
from app.models.checkout import CheckoutSession, CheckoutWebhookEvent
from app.models.developer import MarketplaceAppListing, PublicApiKey, WebhookEventDelivery
from app.models.expense import Expense
from app.models.invoice import InvoiceEvent
from app.models.order import Order
from app.models.sales import Sale
from app.models.team_invitation import TeamInvitation
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


def _signed_webhook_headers(payload: dict) -> tuple[dict[str, str], str]:
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = hmac.new(
        settings.payment_webhook_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Monidesk-Signature": f"sha256={signature}",
    }
    return headers, payload_bytes.decode("utf-8")


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


def test_auth_register_creates_owner_membership(test_context):
    client, session_local = test_context

    register_res = _register(client, email="membership-owner@example.com")
    assert register_res.status_code == 200, register_res.text

    db = session_local()
    try:
        user = db.execute(
            select(User).where(User.email == "membership-owner@example.com")
        ).scalar_one()
        business = db.execute(
            select(Business).where(Business.owner_user_id == user.id)
        ).scalar_one()
        membership = db.execute(
            select(BusinessMembership).where(
                BusinessMembership.business_id == business.id,
                BusinessMembership.user_id == user.id,
            )
        ).scalar_one_or_none()
    finally:
        db.close()

    assert membership is not None
    assert membership.role == "owner"
    assert membership.is_active is True


def test_team_invitation_register_with_invite_flow(test_context):
    client, session_local = test_context

    owner_register = _register(client, email="invite-owner@example.com", full_name="Invite Owner")
    assert owner_register.status_code == 200, owner_register.text
    owner_token = owner_register.json()["access_token"]

    create_invite = client.post(
        "/team/invitations",
        json={
            "email": "invited-user@example.com",
            "role": "staff",
            "expires_in_days": 7,
        },
        headers=_auth_headers(owner_token),
    )
    assert create_invite.status_code == 200, create_invite.text
    invitation_payload = create_invite.json()
    invite_token = invitation_payload["invitation_token"]
    invitation_id = invitation_payload["invitation_id"]
    assert invite_token.startswith("ti_")
    assert invitation_payload["status"] == "pending"

    register_with_invite = client.post(
        "/auth/register-with-invite",
        json={
            "invitation_token": invite_token,
            "email": "invited-user@example.com",
            "full_name": "Invited User",
            "password": "password123",
            "username": "invited_user",
        },
    )
    assert register_with_invite.status_code == 200, register_with_invite.text
    invited_token = register_with_invite.json()["access_token"]

    invited_profile = client.get("/auth/me", headers=_auth_headers(invited_token))
    assert invited_profile.status_code == 200, invited_profile.text
    assert invited_profile.json()["business_name"] == "Invite Owner Biz"

    owner_team = client.get("/team/members", headers=_auth_headers(owner_token))
    assert owner_team.status_code == 200, owner_team.text
    invited_member = next(
        (item for item in owner_team.json()["items"] if item["email"] == "invited-user@example.com"),
        None,
    )
    assert invited_member is not None
    assert invited_member["role"] == "staff"
    assert invited_member["is_active"] is True

    db = session_local()
    try:
        invitation_row = db.execute(
            select(TeamInvitation).where(TeamInvitation.id == invitation_id)
        ).scalar_one()
    finally:
        db.close()

    assert invitation_row.status == "accepted"
    assert invitation_row.accepted_at is not None


def test_team_invitation_accept_for_existing_registered_user(test_context):
    client, session_local = test_context

    owner_register = _register(client, email="team-owner@example.com", full_name="Team Owner")
    assert owner_register.status_code == 200, owner_register.text
    owner_token = owner_register.json()["access_token"]

    db = session_local()
    try:
        existing_user = User(
            id=str(uuid.uuid4()),
            email="existing-member@example.com",
            username="existing_member",
            full_name="Existing Member",
            hashed_password=hash_password("password123"),
        )
        db.add(existing_user)
        db.commit()
    finally:
        db.close()

    create_invite = client.post(
        "/team/invitations",
        json={
            "email": "existing-member@example.com",
            "role": "admin",
            "expires_in_days": 5,
        },
        headers=_auth_headers(owner_token),
    )
    assert create_invite.status_code == 200, create_invite.text
    invite_token = create_invite.json()["invitation_token"]
    invitation_id = create_invite.json()["invitation_id"]

    existing_login = client.post(
        "/auth/login",
        json={"identifier": "existing-member@example.com", "password": "password123"},
    )
    assert existing_login.status_code == 200, existing_login.text
    existing_token = existing_login.json()["access_token"]

    accept_invite = client.post(
        "/team/invitations/accept",
        json={"invitation_token": invite_token},
        headers=_auth_headers(existing_token),
    )
    assert accept_invite.status_code == 200, accept_invite.text
    assert accept_invite.json()["email"] == "existing-member@example.com"
    assert accept_invite.json()["role"] == "admin"

    duplicate_accept = client.post(
        "/team/invitations/accept",
        json={"invitation_token": invite_token},
        headers=_auth_headers(existing_token),
    )
    assert duplicate_accept.status_code == 400, duplicate_accept.text

    team_members = client.get("/team/members", headers=_auth_headers(owner_token))
    assert team_members.status_code == 200, team_members.text
    member_payload = next(
        (item for item in team_members.json()["items"] if item["email"] == "existing-member@example.com"),
        None,
    )
    assert member_payload is not None
    assert member_payload["role"] == "admin"

    db = session_local()
    try:
        invitation_row = db.execute(
            select(TeamInvitation).where(TeamInvitation.id == invitation_id)
        ).scalar_one()
    finally:
        db.close()

    assert invitation_row.status == "accepted"
    assert invitation_row.accepted_by_user_id is not None


def test_auth_me_uses_membership_business_for_non_owner_member(test_context):
    client, session_local = test_context

    owner_register = _register(client, email="member-biz-owner@example.com", full_name="Member Biz")
    assert owner_register.status_code == 200, owner_register.text

    db = session_local()
    try:
        owner_user = db.execute(
            select(User).where(User.email == "member-biz-owner@example.com")
        ).scalar_one()
        owner_business = db.execute(
            select(Business).where(Business.owner_user_id == owner_user.id)
        ).scalar_one()

        staff_user = User(
            id=str(uuid.uuid4()),
            email="staff-member@example.com",
            username="staff_member",
            hashed_password=hash_password("password123"),
            full_name="Staff Member",
        )
        db.add(staff_user)
        db.flush()

        db.add(
            BusinessMembership(
                id=str(uuid.uuid4()),
                business_id=owner_business.id,
                user_id=staff_user.id,
                role="staff",
                is_active=True,
            )
        )
        db.commit()
        expected_business_name = owner_business.name
    finally:
        db.close()

    login_res = client.post(
        "/auth/login",
        json={"identifier": "staff-member@example.com", "password": "password123"},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]

    me_res = client.get("/auth/me", headers=_auth_headers(token))
    assert me_res.status_code == 200, me_res.text
    assert me_res.json()["business_name"] == expected_business_name

    summary_res = client.get("/dashboard/summary", headers=_auth_headers(token))
    assert summary_res.status_code == 200, summary_res.text


def test_auth_business_resolution_falls_back_to_legacy_owner_linkage(test_context):
    client, session_local = test_context

    register_res = _register(client, email="legacy-fallback-owner@example.com")
    assert register_res.status_code == 200, register_res.text
    token = register_res.json()["access_token"]

    db = session_local()
    try:
        user = db.execute(
            select(User).where(User.email == "legacy-fallback-owner@example.com")
        ).scalar_one()
        business = db.execute(
            select(Business).where(Business.owner_user_id == user.id)
        ).scalar_one()
        db.execute(
            delete(BusinessMembership).where(
                BusinessMembership.business_id == business.id,
                BusinessMembership.user_id == user.id,
            )
        )
        db.commit()
    finally:
        db.close()

    me_res = client.get("/auth/me", headers=_auth_headers(token))
    assert me_res.status_code == 200, me_res.text
    assert me_res.json()["business_name"] == "Owner Biz"

    summary_res = client.get("/dashboard/summary", headers=_auth_headers(token))
    assert summary_res.status_code == 200, summary_res.text


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


def test_auth_profile_read_and_update(test_context):
    client, _ = test_context

    register_res = _register(
        client,
        email="profile-owner@example.com",
        full_name="Profile Owner",
    )
    assert register_res.status_code == 200, register_res.text
    token = register_res.json()["access_token"]

    me_res = client.get("/auth/me", headers=_auth_headers(token))
    assert me_res.status_code == 200, me_res.text
    me_payload = me_res.json()
    assert me_payload["email"] == "profile-owner@example.com"
    assert me_payload["full_name"] == "Profile Owner"
    assert me_payload["business_name"] == "Profile Owner Biz"
    assert me_payload["base_currency"] == "USD"
    assert me_payload["pending_order_timeout_minutes"] == 60
    old_username = me_payload["username"]

    update_res = client.patch(
        "/auth/me",
        json={
            "full_name": "Profile Owner Updated",
            "username": "profile_owner_updated",
            "business_name": "Profile Labs",
            "base_currency": "NGN",
            "pending_order_timeout_minutes": 45,
        },
        headers=_auth_headers(token),
    )
    assert update_res.status_code == 200, update_res.text
    updated_payload = update_res.json()
    assert updated_payload["full_name"] == "Profile Owner Updated"
    assert updated_payload["username"] == "profile_owner_updated"
    assert updated_payload["business_name"] == "Profile Labs"
    assert updated_payload["base_currency"] == "NGN"
    assert updated_payload["pending_order_timeout_minutes"] == 45

    old_username_login = client.post(
        "/auth/login",
        json={"identifier": old_username, "password": "password123"},
    )
    assert old_username_login.status_code == 401, old_username_login.text

    new_username_login = client.post(
        "/auth/login",
        json={"identifier": "profile_owner_updated", "password": "password123"},
    )
    assert new_username_login.status_code == 200, new_username_login.text


def test_auth_profile_update_rejects_existing_username(test_context):
    client, _ = test_context

    owner_1 = _register(client, email="profile-one@example.com", full_name="Profile One")
    owner_2 = _register(client, email="profile-two@example.com", full_name="Profile Two")
    assert owner_1.status_code == 200, owner_1.text
    assert owner_2.status_code == 200, owner_2.text

    owner_1_token = owner_1.json()["access_token"]
    owner_2_token = owner_2.json()["access_token"]

    owner_2_me = client.get("/auth/me", headers=_auth_headers(owner_2_token))
    assert owner_2_me.status_code == 200, owner_2_me.text
    owner_2_username = owner_2_me.json()["username"]

    conflict_res = client.patch(
        "/auth/me",
        json={"username": owner_2_username},
        headers=_auth_headers(owner_1_token),
    )
    assert conflict_res.status_code == 400, conflict_res.text
    assert "Username already taken" in conflict_res.text


def test_auth_currency_catalog_endpoint(test_context):
    client, _ = test_context

    register_res = _register(client, email="currency-owner@example.com")
    assert register_res.status_code == 200, register_res.text
    token = register_res.json()["access_token"]

    currencies_res = client.get("/auth/currencies", headers=_auth_headers(token))
    assert currencies_res.status_code == 200, currencies_res.text
    codes = {item["code"] for item in currencies_res.json()["items"]}
    assert {"USD", "NGN", "EUR", "GBP", "JPY"}.issubset(codes)


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


def test_dashboard_credit_profile_returns_weighted_breakdown(test_context):
    client, _ = test_context

    owner = _register(client, email="credit-owner@example.com")
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
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 100}],
        },
        headers=_auth_headers(token),
    )
    assert sale_res.status_code == 200, sale_res.text

    expense_res = client.post(
        "/expenses",
        json={"category": "logistics", "amount": 20.0},
        headers=_auth_headers(token),
    )
    assert expense_res.status_code == 200, expense_res.text

    credit_res = client.get("/dashboard/credit-profile", headers=_auth_headers(token))
    assert credit_res.status_code == 200, credit_res.text

    payload = credit_res.json()
    assert 0 <= payload["overall_score"] <= 100
    assert payload["grade"] in {"excellent", "good", "fair", "weak"}
    assert len(payload["metrics"]) == 5
    assert payload["sales_total"] == pytest.approx(200.0)
    assert payload["expense_total"] == pytest.approx(20.0)
    assert payload["profit_simple"] == pytest.approx(180.0)
    assert isinstance(payload["recommendations"], list)


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


def test_refund_options_show_remaining_quantities(test_context):
    client, _ = test_context

    owner = _register(client, email="refund-options-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 6},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    sale_res = client.post(
        "/sales",
        json={
            "payment_method": "transfer",
            "channel": "instagram",
            "items": [{"variant_id": variant_id, "qty": 4, "unit_price": 75}],
        },
        headers=_auth_headers(token),
    )
    assert sale_res.status_code == 200, sale_res.text
    sale_id = sale_res.json()["id"]

    partial_refund = client.post(
        f"/sales/{sale_id}/refund",
        json={
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 75}],
        },
        headers=_auth_headers(token),
    )
    assert partial_refund.status_code == 200, partial_refund.text

    options_res = client.get(
        f"/sales/{sale_id}/refund-options",
        headers=_auth_headers(token),
    )
    assert options_res.status_code == 200, options_res.text
    options_payload = options_res.json()
    assert options_payload["payment_method"] == "transfer"
    assert options_payload["channel"] == "instagram"
    assert len(options_payload["items"]) == 1
    option = options_payload["items"][0]
    assert option["variant_id"] == variant_id
    assert option["sold_qty"] == 4
    assert option["refunded_qty"] == 1
    assert option["refundable_qty"] == 3
    assert option["default_unit_price"] == pytest.approx(75.0)


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


def test_team_owner_can_manage_members_and_view_audit_logs(test_context):
    client, session_local = test_context

    owner = _register(client, email="team-owner@example.com")
    assert owner.status_code == 200, owner.text
    owner_token = owner.json()["access_token"]

    db = session_local()
    try:
        staff_user = User(
            id=str(uuid.uuid4()),
            email="team-staff@example.com",
            username="team_staff",
            hashed_password=hash_password("password123"),
            full_name="Team Staff",
        )
        db.add(staff_user)
        db.commit()
    finally:
        db.close()

    add_res = client.post(
        "/team/members",
        json={"email": "team-staff@example.com", "role": "staff"},
        headers=_auth_headers(owner_token),
    )
    assert add_res.status_code == 200, add_res.text
    membership_id = add_res.json()["membership_id"]

    list_res = client.get("/team/members", headers=_auth_headers(owner_token))
    assert list_res.status_code == 200, list_res.text
    emails = [item["email"] for item in list_res.json()["items"]]
    assert "team-staff@example.com" in emails

    promote_res = client.patch(
        f"/team/members/{membership_id}",
        json={"role": "admin"},
        headers=_auth_headers(owner_token),
    )
    assert promote_res.status_code == 200, promote_res.text
    assert promote_res.json()["role"] == "admin"

    deactivate_res = client.delete(
        f"/team/members/{membership_id}",
        headers=_auth_headers(owner_token),
    )
    assert deactivate_res.status_code == 204, deactivate_res.text

    audit_res = client.get("/audit-logs", headers=_auth_headers(owner_token))
    assert audit_res.status_code == 200, audit_res.text
    actions = {item["action"] for item in audit_res.json()["items"]}
    assert "team.member.added" in actions
    assert "team.member.updated" in actions
    assert "team.member.deactivated" in actions


def test_team_staff_cannot_manage_team_or_view_audit_logs(test_context):
    client, session_local = test_context

    owner = _register(client, email="team-owner-2@example.com")
    assert owner.status_code == 200, owner.text

    db = session_local()
    try:
        owner_user = db.execute(
            select(User).where(User.email == "team-owner-2@example.com")
        ).scalar_one()
        business = db.execute(
            select(Business).where(Business.owner_user_id == owner_user.id)
        ).scalar_one()

        staff_user = User(
            id=str(uuid.uuid4()),
            email="team-staff-2@example.com",
            username="team_staff_2",
            hashed_password=hash_password("password123"),
            full_name="Team Staff Two",
        )
        db.add(staff_user)
        db.flush()
        db.add(
            BusinessMembership(
                id=str(uuid.uuid4()),
                business_id=business.id,
                user_id=staff_user.id,
                role="staff",
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    staff_login = client.post(
        "/auth/login",
        json={"identifier": "team-staff-2@example.com", "password": "password123"},
    )
    assert staff_login.status_code == 200, staff_login.text
    staff_token = staff_login.json()["access_token"]

    team_list_res = client.get("/team/members", headers=_auth_headers(staff_token))
    assert team_list_res.status_code == 403, team_list_res.text

    audit_res = client.get("/audit-logs", headers=_auth_headers(staff_token))
    assert audit_res.status_code == 403, audit_res.text


def test_team_admin_cannot_modify_owner_or_assign_admin_role(test_context):
    client, session_local = test_context

    owner = _register(client, email="team-owner-3@example.com")
    assert owner.status_code == 200, owner.text

    db = session_local()
    try:
        owner_user = db.execute(
            select(User).where(User.email == "team-owner-3@example.com")
        ).scalar_one()
        business = db.execute(
            select(Business).where(Business.owner_user_id == owner_user.id)
        ).scalar_one()
        owner_membership = db.execute(
            select(BusinessMembership).where(
                BusinessMembership.business_id == business.id,
                BusinessMembership.user_id == owner_user.id,
            )
        ).scalar_one()
        owner_membership_id = owner_membership.id

        admin_user = User(
            id=str(uuid.uuid4()),
            email="team-admin@example.com",
            username="team_admin",
            hashed_password=hash_password("password123"),
            full_name="Team Admin",
        )
        target_user = User(
            id=str(uuid.uuid4()),
            email="team-target@example.com",
            username="team_target",
            hashed_password=hash_password("password123"),
            full_name="Team Target",
        )
        db.add_all([admin_user, target_user])
        db.flush()
        db.add(
            BusinessMembership(
                id=str(uuid.uuid4()),
                business_id=business.id,
                user_id=admin_user.id,
                role="admin",
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    admin_login = client.post(
        "/auth/login",
        json={"identifier": "team-admin@example.com", "password": "password123"},
    )
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["access_token"]

    owner_update = client.patch(
        f"/team/members/{owner_membership_id}",
        json={"role": "staff"},
        headers=_auth_headers(admin_token),
    )
    assert owner_update.status_code == 403, owner_update.text

    add_admin_res = client.post(
        "/team/members",
        json={"email": "team-target@example.com", "role": "admin"},
        headers=_auth_headers(admin_token),
    )
    assert add_admin_res.status_code == 403, add_admin_res.text

    add_staff_res = client.post(
        "/team/members",
        json={"email": "team-target@example.com", "role": "staff"},
        headers=_auth_headers(admin_token),
    )
    assert add_staff_res.status_code == 200, add_staff_res.text


def test_staff_blocked_from_sensitive_mutations_but_can_record_sales(test_context):
    client, session_local = test_context

    owner = _register(client, email="perm-owner@example.com")
    assert owner.status_code == 200, owner.text
    owner_token = owner.json()["access_token"]

    product_id, variant_id = _create_product_with_variant(client, owner_token)
    stock_res = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 10},
        headers=_auth_headers(owner_token),
    )
    assert stock_res.status_code == 200, stock_res.text

    db = session_local()
    try:
        owner_user = db.execute(select(User).where(User.email == "perm-owner@example.com")).scalar_one()
        business = db.execute(select(Business).where(Business.owner_user_id == owner_user.id)).scalar_one()

        staff_user = User(
            id=str(uuid.uuid4()),
            email="perm-staff@example.com",
            username="perm_staff",
            hashed_password=hash_password("password123"),
            full_name="Perm Staff",
        )
        db.add(staff_user)
        db.flush()
        db.add(
            BusinessMembership(
                id=str(uuid.uuid4()),
                business_id=business.id,
                user_id=staff_user.id,
                role="staff",
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    login_res = client.post(
        "/auth/login",
        json={"identifier": "perm-staff@example.com", "password": "password123"},
    )
    assert login_res.status_code == 200, login_res.text
    staff_token = login_res.json()["access_token"]

    create_product_res = client.post(
        "/products",
        json={"name": "Blocked Product"},
        headers=_auth_headers(staff_token),
    )
    assert create_product_res.status_code == 403, create_product_res.text

    create_variant_res = client.post(
        f"/products/{product_id}/variants",
        json={"size": "12x12", "reorder_level": 1},
        headers=_auth_headers(staff_token),
    )
    assert create_variant_res.status_code == 403, create_variant_res.text

    stock_in_res = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 1},
        headers=_auth_headers(staff_token),
    )
    assert stock_in_res.status_code == 403, stock_in_res.text

    adjust_res = client.post(
        "/inventory/adjust",
        json={"variant_id": variant_id, "qty_delta": -1, "reason": "test"},
        headers=_auth_headers(staff_token),
    )
    assert adjust_res.status_code == 403, adjust_res.text

    expense_res = client.post(
        "/expenses",
        json={"category": "ops", "amount": 10},
        headers=_auth_headers(staff_token),
    )
    assert expense_res.status_code == 403, expense_res.text

    sale_res = client.post(
        "/sales",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 100}],
        },
        headers=_auth_headers(staff_token),
    )
    assert sale_res.status_code == 200, sale_res.text


def test_admin_can_manage_sensitive_mutations_and_logs_are_recorded(test_context):
    client, session_local = test_context

    owner = _register(client, email="perm-owner-2@example.com")
    assert owner.status_code == 200, owner.text
    owner_token = owner.json()["access_token"]

    db = session_local()
    try:
        owner_user = db.execute(select(User).where(User.email == "perm-owner-2@example.com")).scalar_one()
        business = db.execute(select(Business).where(Business.owner_user_id == owner_user.id)).scalar_one()

        admin_user = User(
            id=str(uuid.uuid4()),
            email="perm-admin@example.com",
            username="perm_admin",
            hashed_password=hash_password("password123"),
            full_name="Perm Admin",
        )
        db.add(admin_user)
        db.flush()
        db.add(
            BusinessMembership(
                id=str(uuid.uuid4()),
                business_id=business.id,
                user_id=admin_user.id,
                role="admin",
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    login_res = client.post(
        "/auth/login",
        json={"identifier": "perm-admin@example.com", "password": "password123"},
    )
    assert login_res.status_code == 200, login_res.text
    admin_token = login_res.json()["access_token"]

    product_res = client.post(
        "/products",
        json={"name": "Admin Product", "category": "admin"},
        headers=_auth_headers(admin_token),
    )
    assert product_res.status_code == 200, product_res.text
    product_id = product_res.json()["id"]

    variant_res = client.post(
        f"/products/{product_id}/variants",
        json={"size": "8x8", "reorder_level": 2, "selling_price": 150},
        headers=_auth_headers(admin_token),
    )
    assert variant_res.status_code == 200, variant_res.text
    variant_id = variant_res.json()["id"]

    stock_res = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 5},
        headers=_auth_headers(admin_token),
    )
    assert stock_res.status_code == 200, stock_res.text

    adjust_res = client.post(
        "/inventory/adjust",
        json={"variant_id": variant_id, "qty_delta": -1, "reason": "damaged"},
        headers=_auth_headers(admin_token),
    )
    assert adjust_res.status_code == 200, adjust_res.text

    expense_res = client.post(
        "/expenses",
        json={"category": "utilities", "amount": 20},
        headers=_auth_headers(admin_token),
    )
    assert expense_res.status_code == 200, expense_res.text

    sale_res = client.post(
        "/sales",
        json={
            "payment_method": "transfer",
            "channel": "instagram",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 150}],
        },
        headers=_auth_headers(admin_token),
    )
    assert sale_res.status_code == 200, sale_res.text
    sale_id = sale_res.json()["id"]

    refund_res = client.post(
        f"/sales/{sale_id}/refund",
        json={"items": [{"variant_id": variant_id, "qty": 1}]},
        headers=_auth_headers(admin_token),
    )
    assert refund_res.status_code == 200, refund_res.text

    audit_res = client.get("/audit-logs", headers=_auth_headers(admin_token))
    assert audit_res.status_code == 200, audit_res.text
    actions = {item["action"] for item in audit_res.json()["items"]}
    assert "product.create" in actions
    assert "product.variant.create" in actions
    assert "inventory.stock_in" in actions
    assert "inventory.adjust" in actions
    assert "expense.create" in actions
    assert "sale.create" in actions
    assert "sale.refund.create" in actions


def test_orders_create_list_and_paid_conversion_to_sale_is_idempotent(test_context):
    client, _ = test_context

    owner = _register(client, email="orders-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)
    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 5},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    create_order = client.post(
        "/orders",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "note": "Collect on pickup",
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 120}],
        },
        headers=_auth_headers(token),
    )
    assert create_order.status_code == 200, create_order.text
    order_id = create_order.json()["id"]
    assert create_order.json()["status"] == "pending"
    assert create_order.json()["sale_id"] is None

    list_orders = client.get("/orders?status=pending", headers=_auth_headers(token))
    assert list_orders.status_code == 200, list_orders.text
    assert list_orders.json()["pagination"]["total"] >= 1

    mark_paid = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "paid"},
        headers=_auth_headers(token),
    )
    assert mark_paid.status_code == 200, mark_paid.text
    sale_id = mark_paid.json()["sale_id"]
    assert sale_id
    assert mark_paid.json()["status"] == "paid"

    mark_paid_again = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "paid"},
        headers=_auth_headers(token),
    )
    assert mark_paid_again.status_code == 200, mark_paid_again.text
    assert mark_paid_again.json()["sale_id"] == sale_id

    sales_list = client.get("/sales?include_refunds=false", headers=_auth_headers(token))
    assert sales_list.status_code == 200, sales_list.text
    matching_sales = [item for item in sales_list.json()["items"] if item["id"] == sale_id]
    assert len(matching_sales) == 1

    stock_after = client.get(f"/inventory/stock/{variant_id}", headers=_auth_headers(token))
    assert stock_after.status_code == 200, stock_after.text
    assert stock_after.json()["stock"] == 3


def test_orders_invalid_transition_is_rejected(test_context):
    client, _ = test_context

    owner = _register(client, email="orders-transition-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)
    create_order = client.post(
        "/orders",
        json={
            "payment_method": "transfer",
            "channel": "instagram",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 99}],
        },
        headers=_auth_headers(token),
    )
    assert create_order.status_code == 200, create_order.text
    order_id = create_order.json()["id"]

    invalid_transition = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "fulfilled"},
        headers=_auth_headers(token),
    )
    assert invalid_transition.status_code == 400, invalid_transition.text


def test_orders_staff_can_create_and_update_status(test_context):
    client, session_local = test_context

    owner = _register(client, email="orders-staff-owner@example.com")
    assert owner.status_code == 200, owner.text
    owner_token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, owner_token)
    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 2},
        headers=_auth_headers(owner_token),
    )
    assert stock_in.status_code == 200, stock_in.text

    db = session_local()
    try:
        owner_user = db.execute(
            select(User).where(User.email == "orders-staff-owner@example.com")
        ).scalar_one()
        business = db.execute(
            select(Business).where(Business.owner_user_id == owner_user.id)
        ).scalar_one()

        staff_user = User(
            id=str(uuid.uuid4()),
            email="orders-staff@example.com",
            username="orders_staff",
            hashed_password=hash_password("password123"),
            full_name="Orders Staff",
        )
        db.add(staff_user)
        db.flush()
        db.add(
            BusinessMembership(
                id=str(uuid.uuid4()),
                business_id=business.id,
                user_id=staff_user.id,
                role="staff",
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    staff_login = client.post(
        "/auth/login",
        json={"identifier": "orders-staff@example.com", "password": "password123"},
    )
    assert staff_login.status_code == 200, staff_login.text
    staff_token = staff_login.json()["access_token"]

    create_order = client.post(
        "/orders",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 50}],
        },
        headers=_auth_headers(staff_token),
    )
    assert create_order.status_code == 200, create_order.text
    order_id = create_order.json()["id"]

    update_status = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "paid"},
        headers=_auth_headers(staff_token),
    )
    assert update_status.status_code == 200, update_status.text
    assert update_status.json()["status"] == "paid"
    assert update_status.json()["sale_id"] is not None


def test_orders_list_supports_channel_and_customer_filters(test_context):
    client, _ = test_context

    owner = _register(client, email="orders-filter-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    customer_a_res = client.post(
        "/customers",
        json={"name": "Customer A", "email": "customer.a@example.com"},
        headers=_auth_headers(token),
    )
    assert customer_a_res.status_code == 200, customer_a_res.text
    customer_a_id = customer_a_res.json()["id"]

    customer_b_res = client.post(
        "/customers",
        json={"name": "Customer B", "email": "customer.b@example.com"},
        headers=_auth_headers(token),
    )
    assert customer_b_res.status_code == 200, customer_b_res.text
    customer_b_id = customer_b_res.json()["id"]

    _, variant_id = _create_product_with_variant(client, token)

    order_a = client.post(
        "/orders",
        json={
            "customer_id": customer_a_id,
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 95}],
        },
        headers=_auth_headers(token),
    )
    assert order_a.status_code == 200, order_a.text

    order_b = client.post(
        "/orders",
        json={
            "customer_id": customer_b_id,
            "payment_method": "transfer",
            "channel": "instagram",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 110}],
        },
        headers=_auth_headers(token),
    )
    assert order_b.status_code == 200, order_b.text

    instagram_only = client.get("/orders?channel=instagram", headers=_auth_headers(token))
    assert instagram_only.status_code == 200, instagram_only.text
    assert instagram_only.json()["channel"] == "instagram"
    assert instagram_only.json()["pagination"]["total"] == 1
    assert instagram_only.json()["items"][0]["id"] == order_b.json()["id"]

    customer_a_only = client.get(f"/orders?customer_id={customer_a_id}", headers=_auth_headers(token))
    assert customer_a_only.status_code == 200, customer_a_only.text
    assert customer_a_only.json()["customer_id"] == customer_a_id
    assert customer_a_only.json()["pagination"]["total"] == 1
    assert customer_a_only.json()["items"][0]["id"] == order_a.json()["id"]


def test_orders_pending_timeout_auto_cancels_stale_order(test_context):
    client, session_local = test_context

    owner = _register(client, email="orders-timeout-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)
    create_order = client.post(
        "/orders",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 150}],
        },
        headers=_auth_headers(token),
    )
    assert create_order.status_code == 200, create_order.text
    order_id = create_order.json()["id"]

    db = session_local()
    try:
        owner_user = db.execute(
            select(User).where(User.email == "orders-timeout-owner@example.com")
        ).scalar_one()
        business = db.execute(
            select(Business).where(Business.owner_user_id == owner_user.id)
        ).scalar_one()
        business.pending_order_timeout_minutes = 1
        db.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(minutes=10))
        )
        db.commit()
    finally:
        db.close()

    mark_paid = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "paid"},
        headers=_auth_headers(token),
    )
    assert mark_paid.status_code == 400, mark_paid.text
    assert "Cannot transition order from 'cancelled' to 'paid'" in mark_paid.text

    cancelled_orders = client.get("/orders?status=cancelled", headers=_auth_headers(token))
    assert cancelled_orders.status_code == 200, cancelled_orders.text
    matching_order = next(
        (item for item in cancelled_orders.json()["items"] if item["id"] == order_id),
        None,
    )
    assert matching_order is not None
    assert matching_order["status"] == "cancelled"
    assert "Auto-cancelled" in (matching_order["note"] or "")

    auto_cancel_audit = client.get(
        "/audit-logs?action=order.auto_cancel",
        headers=_auth_headers(token),
    )
    assert auto_cancel_audit.status_code == 200, auto_cancel_audit.text
    assert any(item["target_id"] == order_id for item in auto_cancel_audit.json()["items"])


def test_invoices_create_send_reminder_mark_paid_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="invoice-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    create_customer = client.post(
        "/customers",
        json={"name": "Invoice Flow Customer", "email": "invoice.flow@example.com"},
        headers=_auth_headers(token),
    )
    assert create_customer.status_code == 200, create_customer.text
    customer_id = create_customer.json()["id"]

    _, variant_id = _create_product_with_variant(client, token)
    create_order = client.post(
        "/orders",
        json={
            "customer_id": customer_id,
            "payment_method": "transfer",
            "channel": "instagram",
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 180}],
        },
        headers=_auth_headers(token),
    )
    assert create_order.status_code == 200, create_order.text
    order_id = create_order.json()["id"]

    create_invoice = client.post(
        "/invoices",
        json={
            "customer_id": customer_id,
            "order_id": order_id,
            "currency": "usd",
            "due_date": "2026-02-28",
            "note": "Net 7",
        },
        headers=_auth_headers(token),
    )
    assert create_invoice.status_code == 200, create_invoice.text
    invoice_id = create_invoice.json()["id"]
    assert create_invoice.json()["status"] == "draft"
    assert create_invoice.json()["total_amount"] == 360.0

    send_invoice = client.post(
        f"/invoices/{invoice_id}/send",
        headers=_auth_headers(token),
    )
    assert send_invoice.status_code == 200, send_invoice.text
    assert send_invoice.json()["status"] == "sent"
    assert send_invoice.json()["last_sent_at"] is not None

    reminder = client.post(
        f"/invoices/{invoice_id}/reminders",
        json={"channel": "whatsapp", "note": "Customer requested reminder"},
        headers=_auth_headers(token),
    )
    assert reminder.status_code == 200, reminder.text
    assert reminder.json()["status"] == "sent"

    mark_paid = client.patch(
        f"/invoices/{invoice_id}/mark-paid",
        json={
            "payment_method": "transfer",
            "payment_reference": "bank-ref-100",
            "idempotency_key": "invoice-pay-key-1",
        },
        headers=_auth_headers(token),
    )
    assert mark_paid.status_code == 200, mark_paid.text
    assert mark_paid.json()["status"] == "paid"
    assert mark_paid.json()["amount_paid"] == 360.0
    assert mark_paid.json()["outstanding_amount"] == 0.0
    assert mark_paid.json()["payment_reference"] == "bank-ref-100"

    paid_list = client.get("/invoices?status=paid", headers=_auth_headers(token))
    assert paid_list.status_code == 200, paid_list.text
    assert any(item["id"] == invoice_id for item in paid_list.json()["items"])

    customer_list = client.get(f"/invoices?customer_id={customer_id}", headers=_auth_headers(token))
    assert customer_list.status_code == 200, customer_list.text
    assert customer_list.json()["customer_id"] == customer_id
    assert any(item["id"] == invoice_id for item in customer_list.json()["items"])

    audit_res = client.get("/audit-logs", headers=_auth_headers(token))
    assert audit_res.status_code == 200, audit_res.text
    actions = {item["action"] for item in audit_res.json()["items"]}
    assert "invoice.create" in actions
    assert "invoice.send" in actions
    assert "invoice.reminder.manual" in actions
    assert "invoice.mark_paid" in actions


def test_invoices_mark_paid_idempotency_key_is_safe(test_context):
    client, session_local = test_context

    owner = _register(client, email="invoice-idempotency-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    create_invoice = client.post(
        "/invoices",
        json={
            "currency": "USD",
            "total_amount": 240,
            "send_now": True,
        },
        headers=_auth_headers(token),
    )
    assert create_invoice.status_code == 200, create_invoice.text
    invoice_id = create_invoice.json()["id"]

    first_paid = client.patch(
        f"/invoices/{invoice_id}/mark-paid",
        json={"idempotency_key": "pay-event-001"},
        headers=_auth_headers(token),
    )
    assert first_paid.status_code == 200, first_paid.text
    assert first_paid.json()["status"] == "paid"

    second_paid = client.patch(
        f"/invoices/{invoice_id}/mark-paid",
        json={"idempotency_key": "pay-event-001"},
        headers=_auth_headers(token),
    )
    assert second_paid.status_code == 200, second_paid.text
    assert second_paid.json()["status"] == "paid"

    db = session_local()
    try:
        mark_paid_events = db.execute(
            select(InvoiceEvent).where(
                InvoiceEvent.invoice_id == invoice_id,
                InvoiceEvent.event_type == "mark_paid",
                InvoiceEvent.idempotency_key == "pay-event-001",
            )
        ).scalars().all()
    finally:
        db.close()

    assert len(mark_paid_events) == 1


def test_invoices_auto_overdue_on_list(test_context):
    client, _ = test_context

    owner = _register(client, email="invoice-overdue-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    create_invoice = client.post(
        "/invoices",
        json={
            "currency": "USD",
            "total_amount": 90,
            "due_date": "2020-01-01",
            "send_now": True,
        },
        headers=_auth_headers(token),
    )
    assert create_invoice.status_code == 200, create_invoice.text
    invoice_id = create_invoice.json()["id"]

    list_invoices = client.get("/invoices", headers=_auth_headers(token))
    assert list_invoices.status_code == 200, list_invoices.text
    overdue_invoice = next(
        (item for item in list_invoices.json()["items"] if item["id"] == invoice_id),
        None,
    )
    assert overdue_invoice is not None
    assert overdue_invoice["status"] == "overdue"


def test_customers_crud_search_and_tagging(test_context):
    client, _ = test_context

    owner = _register(client, email="customers-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    create_tag = client.post(
        "/customers/tags",
        json={"name": "VIP", "color": "#16a34a"},
        headers=_auth_headers(token),
    )
    assert create_tag.status_code == 200, create_tag.text
    tag_id = create_tag.json()["id"]

    create_customer_a = client.post(
        "/customers",
        json={
            "name": "Aisha Bello",
            "phone": "+2348011112222",
            "email": "aisha@example.com",
            "note": "Prefers WhatsApp updates",
            "tag_ids": [tag_id],
        },
        headers=_auth_headers(token),
    )
    assert create_customer_a.status_code == 200, create_customer_a.text
    customer_a_id = create_customer_a.json()["id"]

    create_customer_b = client.post(
        "/customers",
        json={
            "name": "Tunde Ade",
            "phone": "+2348022223333",
            "email": "tunde@example.com",
        },
        headers=_auth_headers(token),
    )
    assert create_customer_b.status_code == 200, create_customer_b.text
    customer_b_id = create_customer_b.json()["id"]

    list_all = client.get("/customers", headers=_auth_headers(token))
    assert list_all.status_code == 200, list_all.text
    assert list_all.json()["pagination"]["total"] == 2

    search_aisha = client.get("/customers?q=aisha", headers=_auth_headers(token))
    assert search_aisha.status_code == 200, search_aisha.text
    assert search_aisha.json()["pagination"]["total"] == 1
    assert search_aisha.json()["items"][0]["id"] == customer_a_id
    assert len(search_aisha.json()["items"][0]["tags"]) == 1

    update_customer_b = client.patch(
        f"/customers/{customer_b_id}",
        json={"name": "Tunde Ade Updated", "note": "High-value weekend buyer"},
        headers=_auth_headers(token),
    )
    assert update_customer_b.status_code == 200, update_customer_b.text
    assert update_customer_b.json()["name"] == "Tunde Ade Updated"

    attach_tag = client.post(
        f"/customers/{customer_b_id}/tags/{tag_id}",
        headers=_auth_headers(token),
    )
    assert attach_tag.status_code == 200, attach_tag.text
    assert any(tag["id"] == tag_id for tag in attach_tag.json()["tags"])

    filter_by_tag = client.get(f"/customers?tag_id={tag_id}", headers=_auth_headers(token))
    assert filter_by_tag.status_code == 200, filter_by_tag.text
    assert filter_by_tag.json()["pagination"]["total"] == 2

    detach_tag = client.delete(
        f"/customers/{customer_b_id}/tags/{tag_id}",
        headers=_auth_headers(token),
    )
    assert detach_tag.status_code == 200, detach_tag.text
    assert all(tag["id"] != tag_id for tag in detach_tag.json()["tags"])

    filtered_after_detach = client.get(f"/customers?tag_id={tag_id}", headers=_auth_headers(token))
    assert filtered_after_detach.status_code == 200, filtered_after_detach.text
    assert filtered_after_detach.json()["pagination"]["total"] == 1
    assert filtered_after_detach.json()["items"][0]["id"] == customer_a_id

    delete_customer_b = client.delete(
        f"/customers/{customer_b_id}",
        headers=_auth_headers(token),
    )
    assert delete_customer_b.status_code == 204, delete_customer_b.text

    final_list = client.get("/customers", headers=_auth_headers(token))
    assert final_list.status_code == 200, final_list.text
    assert final_list.json()["pagination"]["total"] == 1

    audit_res = client.get("/audit-logs", headers=_auth_headers(token))
    assert audit_res.status_code == 200, audit_res.text
    actions = {item["action"] for item in audit_res.json()["items"]}
    assert "customer.create" in actions
    assert "customer.update" in actions
    assert "customer.delete" in actions
    assert "customer.tag.create" in actions
    assert "customer.tag.attach" in actions
    assert "customer.tag.detach" in actions


def test_orders_and_invoices_validate_customer_linkage(test_context):
    client, _ = test_context

    owner = _register(client, email="customer-link-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    create_customer = client.post(
        "/customers",
        json={
            "name": "Customer Link",
            "email": "customer.link@example.com",
        },
        headers=_auth_headers(token),
    )
    assert create_customer.status_code == 200, create_customer.text
    customer_id = create_customer.json()["id"]

    create_other_customer = client.post(
        "/customers",
        json={
            "name": "Other Customer",
            "email": "other.customer@example.com",
        },
        headers=_auth_headers(token),
    )
    assert create_other_customer.status_code == 200, create_other_customer.text
    other_customer_id = create_other_customer.json()["id"]

    _, variant_id = _create_product_with_variant(client, token)

    valid_order = client.post(
        "/orders",
        json={
            "customer_id": customer_id,
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 100}],
        },
        headers=_auth_headers(token),
    )
    assert valid_order.status_code == 200, valid_order.text
    order_id = valid_order.json()["id"]

    invalid_order = client.post(
        "/orders",
        json={
            "customer_id": "missing-customer-id",
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 100}],
        },
        headers=_auth_headers(token),
    )
    assert invalid_order.status_code == 404, invalid_order.text
    assert "Customer not found" in invalid_order.text

    valid_invoice = client.post(
        "/invoices",
        json={
            "order_id": order_id,
            "customer_id": customer_id,
            "currency": "USD",
        },
        headers=_auth_headers(token),
    )
    assert valid_invoice.status_code == 200, valid_invoice.text
    assert valid_invoice.json()["status"] == "draft"

    mismatched_invoice = client.post(
        "/invoices",
        json={
            "order_id": order_id,
            "customer_id": other_customer_id,
            "currency": "USD",
        },
        headers=_auth_headers(token),
    )
    assert mismatched_invoice.status_code == 400, mismatched_invoice.text
    assert "must match linked order customer" in mismatched_invoice.text

    invalid_customer_invoice = client.post(
        "/invoices",
        json={
            "customer_id": "missing-customer-id",
            "currency": "USD",
            "total_amount": 50,
        },
        headers=_auth_headers(token),
    )
    assert invalid_customer_invoice.status_code == 404, invalid_customer_invoice.text
    assert "Customer not found" in invalid_customer_invoice.text


def test_customers_import_csv_reports_summary_and_rejections(test_context):
    client, _ = test_context

    owner = _register(client, email="customers-import-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    tag_res = client.post(
        "/customers/tags",
        json={"name": "CSV Import", "color": "#0ea5e9"},
        headers=_auth_headers(token),
    )
    assert tag_res.status_code == 200, tag_res.text
    tag_id = tag_res.json()["id"]

    existing_customer_res = client.post(
        "/customers",
        json={"name": "Existing Customer", "email": "existing@example.com"},
        headers=_auth_headers(token),
    )
    assert existing_customer_res.status_code == 200, existing_customer_res.text

    csv_res = client.post(
        "/customers/import-csv",
        json={
            "csv_content": (
                "name,email,phone,note\n"
                "Aisha Bello,aisha@example.com,+2348011112222,VIP\n"
                ",missing.name@example.com,+2348011113333,No name\n"
                "Bad Email,not-an-email,+2348011114444,Invalid\n"
                "Duplicate Existing,existing@example.com,+2348011115555,Duplicate with DB\n"
                "Repeat One,repeat@example.com,+2348011116666,First repeat\n"
                "Repeat Two,repeat@example.com,+2348011117777,Second repeat duplicate\n"
                "No Email,,+2348011118888,Walk-in customer\n"
            ),
            "has_header": True,
            "delimiter": ",",
            "default_tag_ids": [tag_id],
        },
        headers=_auth_headers(token),
    )
    assert csv_res.status_code == 200, csv_res.text
    payload = csv_res.json()

    assert payload["total_rows"] == 7
    assert payload["imported_count"] == 3
    assert payload["rejected_count"] == 4
    assert len(payload["imported_ids"]) == 3

    rejected_reasons = {row["reason"] for row in payload["rejected_rows"]}
    assert "Missing required name" in rejected_reasons
    assert "Invalid email format" in rejected_reasons
    assert "Email already exists" in rejected_reasons

    customers_res = client.get("/customers?limit=20", headers=_auth_headers(token))
    assert customers_res.status_code == 200, customers_res.text
    customers_payload = customers_res.json()
    assert customers_payload["pagination"]["total"] == 4

    imported_by_name = {
        item["name"]: item
        for item in customers_payload["items"]
        if item["name"] in {"Aisha Bello", "Repeat One", "No Email"}
    }
    assert len(imported_by_name) == 3
    assert all(any(tag["id"] == tag_id for tag in item["tags"]) for item in imported_by_name.values())

    audit_res = client.get("/audit-logs?action=customer.import_csv", headers=_auth_headers(token))
    assert audit_res.status_code == 200, audit_res.text
    assert any(item["action"] == "customer.import_csv" for item in audit_res.json()["items"])


def test_dashboard_customer_insights_returns_repeat_buyers_and_top_customers(test_context):
    client, _ = test_context

    owner = _register(client, email="dashboard-customer-insights-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    customer_a = client.post(
        "/customers",
        json={"name": "Aisha Bello", "email": "insights.aisha@example.com"},
        headers=_auth_headers(token),
    )
    assert customer_a.status_code == 200, customer_a.text
    customer_a_id = customer_a.json()["id"]

    customer_b = client.post(
        "/customers",
        json={"name": "Tunde Ade", "email": "insights.tunde@example.com"},
        headers=_auth_headers(token),
    )
    assert customer_b.status_code == 200, customer_b.text
    customer_b_id = customer_b.json()["id"]

    customer_c = client.post(
        "/customers",
        json={"name": "Idle Customer", "email": "insights.idle@example.com"},
        headers=_auth_headers(token),
    )
    assert customer_c.status_code == 200, customer_c.text

    _, variant_id = _create_product_with_variant(client, token)
    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 10},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    first_order = client.post(
        "/orders",
        json={
            "customer_id": customer_a_id,
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 100}],
        },
        headers=_auth_headers(token),
    )
    assert first_order.status_code == 200, first_order.text
    first_order_id = first_order.json()["id"]

    first_paid = client.patch(
        f"/orders/{first_order_id}/status",
        json={"status": "paid"},
        headers=_auth_headers(token),
    )
    assert first_paid.status_code == 200, first_paid.text

    second_order = client.post(
        "/orders",
        json={
            "customer_id": customer_a_id,
            "payment_method": "transfer",
            "channel": "instagram",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 50}],
        },
        headers=_auth_headers(token),
    )
    assert second_order.status_code == 200, second_order.text
    second_order_id = second_order.json()["id"]

    second_paid = client.patch(
        f"/orders/{second_order_id}/status",
        json={"status": "paid"},
        headers=_auth_headers(token),
    )
    assert second_paid.status_code == 200, second_paid.text

    invoice_res = client.post(
        "/invoices",
        json={
            "customer_id": customer_b_id,
            "currency": "USD",
            "total_amount": 80,
            "due_date": "2026-02-28",
        },
        headers=_auth_headers(token),
    )
    assert invoice_res.status_code == 200, invoice_res.text
    invoice_id = invoice_res.json()["id"]

    invoice_paid = client.patch(
        f"/invoices/{invoice_id}/mark-paid",
        json={"idempotency_key": "dashboard-insights-invoice-paid-1"},
        headers=_auth_headers(token),
    )
    assert invoice_paid.status_code == 200, invoice_paid.text
    assert invoice_paid.json()["status"] == "paid"

    insights_res = client.get("/dashboard/customer-insights", headers=_auth_headers(token))
    assert insights_res.status_code == 200, insights_res.text
    insights_payload = insights_res.json()

    assert insights_payload["total_customers"] == 3
    assert insights_payload["active_customers"] == 2
    assert insights_payload["repeat_buyers"] == 1
    assert len(insights_payload["top_customers"]) == 2
    assert insights_payload["top_customers"][0]["customer_id"] == customer_a_id
    assert insights_payload["top_customers"][0]["customer_name"] == "Aisha Bello"
    assert insights_payload["top_customers"][0]["total_spent"] == pytest.approx(150.0)
    assert insights_payload["top_customers"][0]["transactions"] == 2

    invalid_range = client.get(
        "/dashboard/customer-insights?start_date=2026-02-10&end_date=2026-02-01",
        headers=_auth_headers(token),
    )
    assert invalid_range.status_code == 400, invalid_range.text


def test_storefront_config_publish_controls_and_public_catalog(test_context):
    client, _ = test_context

    owner = _register(client, email="storefront-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    config_res = client.put(
        "/storefront/config",
        json={
            "slug": "ankara-house",
            "display_name": "Ankara House",
            "tagline": "Premium fabrics",
            "description": "Quality patterns and plain fabrics.",
            "seo_title": "Ankara House | Premium Fabrics",
            "seo_description": "Shop premium Ankara fabrics with fast delivery.",
            "seo_og_image_url": "https://cdn.example.com/seo-ankara.jpg",
            "accent_color": "#16a34a",
            "policy_shipping": "Ships in 1-3 days",
            "policy_returns": "Return within 7 days",
            "policy_privacy": "Your data is protected",
            "is_published": True,
        },
        headers=_auth_headers(token),
    )
    assert config_res.status_code == 200, config_res.text
    assert config_res.json()["slug"] == "ankara-house"
    assert config_res.json()["is_published"] is True

    product_a_res = client.post(
        "/products",
        json={"name": "Ankara Premium", "category": "fabrics"},
        headers=_auth_headers(token),
    )
    assert product_a_res.status_code == 200, product_a_res.text
    product_a_id = product_a_res.json()["id"]

    variant_a_1 = client.post(
        f"/products/{product_a_id}/variants",
        json={
            "size": "6x6",
            "label": "Plain",
            "sku": "STF-ANK-001",
            "selling_price": 120.0,
            "reorder_level": 2,
        },
        headers=_auth_headers(token),
    )
    assert variant_a_1.status_code == 200, variant_a_1.text
    variant_a_1_id = variant_a_1.json()["id"]

    variant_a_2 = client.post(
        f"/products/{product_a_id}/variants",
        json={
            "size": "8x8",
            "label": "Pattern",
            "sku": "STF-ANK-002",
            "selling_price": 150.0,
            "reorder_level": 2,
        },
        headers=_auth_headers(token),
    )
    assert variant_a_2.status_code == 200, variant_a_2.text
    variant_a_2_id = variant_a_2.json()["id"]

    product_b_res = client.post(
        "/products",
        json={"name": "Adire Classic", "category": "fabrics"},
        headers=_auth_headers(token),
    )
    assert product_b_res.status_code == 200, product_b_res.text
    product_b_id = product_b_res.json()["id"]

    variant_b_1 = client.post(
        f"/products/{product_b_id}/variants",
        json={
            "size": "6x6",
            "label": "Standard",
            "sku": "STF-ADI-001",
            "selling_price": 90.0,
            "reorder_level": 1,
        },
        headers=_auth_headers(token),
    )
    assert variant_b_1.status_code == 200, variant_b_1.text
    variant_b_1_id = variant_b_1.json()["id"]

    publish_product_a = client.patch(
        f"/products/{product_a_id}/publish",
        json={"is_published": True},
        headers=_auth_headers(token),
    )
    assert publish_product_a.status_code == 200, publish_product_a.text
    assert publish_product_a.json()["is_published"] is True

    publish_variant_a1 = client.patch(
        f"/products/{product_a_id}/variants/{variant_a_1_id}/publish",
        json={"is_published": True},
        headers=_auth_headers(token),
    )
    assert publish_variant_a1.status_code == 200, publish_variant_a1.text
    assert publish_variant_a1.json()["is_published"] is True

    publish_product_b = client.patch(
        f"/products/{product_b_id}/publish",
        json={"is_published": True},
        headers=_auth_headers(token),
    )
    assert publish_product_b.status_code == 200, publish_product_b.text

    storefront_profile = client.get("/storefront/public/ankara-house")
    assert storefront_profile.status_code == 200, storefront_profile.text
    assert storefront_profile.json()["display_name"] == "Ankara House"
    assert storefront_profile.json()["seo_title"] == "Ankara House | Premium Fabrics"
    assert storefront_profile.json()["seo_description"] == "Shop premium Ankara fabrics with fast delivery."
    assert storefront_profile.json()["seo_og_image_url"] == "https://cdn.example.com/seo-ankara.jpg"

    list_public = client.get("/storefront/public/ankara-house/products")
    assert list_public.status_code == 200, list_public.text
    list_payload = list_public.json()
    assert list_payload["pagination"]["total"] == 1
    assert list_payload["items"][0]["id"] == product_a_id
    assert list_payload["items"][0]["published_variant_count"] == 1
    assert list_payload["items"][0]["starting_price"] == pytest.approx(120.0)

    search_public = client.get("/storefront/public/ankara-house/products?q=ankara")
    assert search_public.status_code == 200, search_public.text
    assert search_public.json()["pagination"]["total"] == 1
    assert search_public.json()["items"][0]["id"] == product_a_id

    category_filter_public = client.get("/storefront/public/ankara-house/products?category=fabrics")
    assert category_filter_public.status_code == 200, category_filter_public.text
    assert category_filter_public.json()["pagination"]["total"] == 1

    detail_public = client.get(f"/storefront/public/ankara-house/products/{product_a_id}")
    assert detail_public.status_code == 200, detail_public.text
    assert detail_public.json()["id"] == product_a_id
    assert len(detail_public.json()["variants"]) == 1
    assert detail_public.json()["variants"][0]["id"] == variant_a_1_id

    publish_variant_a2 = client.patch(
        f"/products/{product_a_id}/variants/{variant_a_2_id}/publish",
        json={"is_published": True},
        headers=_auth_headers(token),
    )
    assert publish_variant_a2.status_code == 200, publish_variant_a2.text

    detail_after_second_variant = client.get(f"/storefront/public/ankara-house/products/{product_a_id}")
    assert detail_after_second_variant.status_code == 200, detail_after_second_variant.text
    assert len(detail_after_second_variant.json()["variants"]) == 2

    publish_variant_b1 = client.patch(
        f"/products/{product_b_id}/variants/{variant_b_1_id}/publish",
        json={"is_published": False},
        headers=_auth_headers(token),
    )
    assert publish_variant_b1.status_code == 200, publish_variant_b1.text

    list_after_variant_b_unpublished = client.get("/storefront/public/ankara-house/products")
    assert list_after_variant_b_unpublished.status_code == 200, list_after_variant_b_unpublished.text
    ids = {item["id"] for item in list_after_variant_b_unpublished.json()["items"]}
    assert product_a_id in ids
    assert product_b_id not in ids

    audit_res = client.get("/audit-logs", headers=_auth_headers(token))
    assert audit_res.status_code == 200, audit_res.text
    actions = {item["action"] for item in audit_res.json()["items"]}
    assert "storefront.config.upsert" in actions
    assert "product.publish.update" in actions
    assert "product.variant.publish.update" in actions


def test_storefront_public_api_rate_limited(test_context):
    client, _ = test_context

    owner = _register(client, email="storefront-ratelimit-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    config_res = client.put(
        "/storefront/config",
        json={
            "slug": "store-rate-limit",
            "display_name": "Store Rate Limit",
            "is_published": True,
        },
        headers=_auth_headers(token),
    )
    assert config_res.status_code == 200, config_res.text

    product_res = client.post(
        "/products",
        json={"name": "Rate Product", "category": "general"},
        headers=_auth_headers(token),
    )
    assert product_res.status_code == 200, product_res.text
    product_id = product_res.json()["id"]

    variant_res = client.post(
        f"/products/{product_id}/variants",
        json={"size": "One Size", "selling_price": 50.0, "sku": "STF-RATE-001"},
        headers=_auth_headers(token),
    )
    assert variant_res.status_code == 200, variant_res.text
    variant_id = variant_res.json()["id"]

    publish_product = client.patch(
        f"/products/{product_id}/publish",
        json={"is_published": True},
        headers=_auth_headers(token),
    )
    assert publish_product.status_code == 200, publish_product.text

    publish_variant = client.patch(
        f"/products/{product_id}/variants/{variant_id}/publish",
        json={"is_published": True},
        headers=_auth_headers(token),
    )
    assert publish_variant.status_code == 200, publish_variant.text

    from app.routers import storefront as storefront_router

    previous_max_requests = storefront_router.storefront_rate_limiter.max_requests
    previous_window_seconds = storefront_router.storefront_rate_limiter.window_seconds
    storefront_router.storefront_rate_limiter.max_requests = 1
    storefront_router.storefront_rate_limiter.window_seconds = 60
    storefront_router.storefront_rate_limiter.clear()

    try:
        first_req = client.get("/storefront/public/store-rate-limit/products")
        assert first_req.status_code == 200, first_req.text

        second_req = client.get("/storefront/public/store-rate-limit/products")
        assert second_req.status_code == 429, second_req.text
        assert "Retry-After" in second_req.headers
    finally:
        storefront_router.storefront_rate_limiter.max_requests = previous_max_requests
        storefront_router.storefront_rate_limiter.window_seconds = previous_window_seconds
        storefront_router.storefront_rate_limiter.clear()


def test_storefront_custom_domain_dns_verification_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="storefront-domain-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    create_config = client.put(
        "/storefront/config",
        json={
            "slug": "domain-flow-store",
            "display_name": "Domain Flow Store",
            "custom_domain": "shop.domainflow.example",
            "is_published": True,
        },
        headers=_auth_headers(token),
    )
    assert create_config.status_code == 200, create_config.text
    assert create_config.json()["domain_verification_status"] == "pending"
    assert create_config.json()["domain_verified_at"] is None

    status_before = client.get("/storefront/config/domain/status", headers=_auth_headers(token))
    assert status_before.status_code == 200, status_before.text
    assert status_before.json()["custom_domain"] == "shop.domainflow.example"
    assert status_before.json()["verification_status"] == "pending"
    assert status_before.json()["txt_record_name"] == "_monidesk-verification.shop.domainflow.example"
    assert status_before.json()["txt_record_value"] is None

    challenge = client.post("/storefront/config/domain/challenge", headers=_auth_headers(token))
    assert challenge.status_code == 200, challenge.text
    challenge_payload = challenge.json()
    assert challenge_payload["custom_domain"] == "shop.domainflow.example"
    assert challenge_payload["verification_status"] == "pending"
    assert challenge_payload["txt_record_name"] == "_monidesk-verification.shop.domainflow.example"
    assert "monidesk-site-verification=" in challenge_payload["txt_record_value"]

    wrong_verify = client.post(
        "/storefront/config/domain/verify",
        json={"verification_token": "wrong-token"},
        headers=_auth_headers(token),
    )
    assert wrong_verify.status_code == 400, wrong_verify.text
    assert "Invalid verification token" in wrong_verify.text

    verify = client.post(
        "/storefront/config/domain/verify",
        json={"verification_token": challenge_payload["txt_record_value"]},
        headers=_auth_headers(token),
    )
    assert verify.status_code == 200, verify.text
    verify_payload = verify.json()
    assert verify_payload["verification_status"] == "verified"
    assert verify_payload["domain_verified_at"] is not None

    status_after = client.get("/storefront/config/domain/status", headers=_auth_headers(token))
    assert status_after.status_code == 200, status_after.text
    assert status_after.json()["verification_status"] == "verified"
    assert status_after.json()["domain_verified_at"] is not None

    switch_domain = client.put(
        "/storefront/config",
        json={
            "slug": "domain-flow-store",
            "display_name": "Domain Flow Store",
            "custom_domain": "new.domainflow.example",
            "is_published": True,
        },
        headers=_auth_headers(token),
    )
    assert switch_domain.status_code == 200, switch_domain.text
    assert switch_domain.json()["domain_verification_status"] == "pending"
    assert switch_domain.json()["domain_verified_at"] is None

    clear_domain = client.put(
        "/storefront/config",
        json={
            "slug": "domain-flow-store",
            "display_name": "Domain Flow Store",
            "custom_domain": None,
            "is_published": True,
        },
        headers=_auth_headers(token),
    )
    assert clear_domain.status_code == 200, clear_domain.text
    assert clear_domain.json()["domain_verification_status"] == "not_configured"
    assert clear_domain.json()["domain_verified_at"] is None

    status_cleared = client.get("/storefront/config/domain/status", headers=_auth_headers(token))
    assert status_cleared.status_code == 200, status_cleared.text
    assert status_cleared.json()["custom_domain"] is None
    assert status_cleared.json()["verification_status"] == "not_configured"

    audit = client.get("/audit-logs", headers=_auth_headers(token))
    assert audit.status_code == 200, audit.text
    actions = {item["action"] for item in audit.json()["items"]}
    assert "storefront.config.upsert" in actions
    assert "storefront.domain.challenge" in actions
    assert "storefront.domain.verify" in actions


def test_checkout_session_create_public_view_and_place_order(test_context):
    client, _ = test_context

    owner = _register(client, email="checkout-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)
    seed_stock = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 10, "unit_cost": 60},
        headers=_auth_headers(token),
    )
    assert seed_stock.status_code == 200, seed_stock.text

    create_session = client.post(
        "/checkout-sessions",
        json={
            "currency": "USD",
            "payment_method": "transfer",
            "channel": "instagram",
            "expires_in_minutes": 60,
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 125}],
        },
        headers=_auth_headers(token),
    )
    assert create_session.status_code == 200, create_session.text
    session_payload = create_session.json()
    assert session_payload["status"] == "open"
    assert session_payload["payment_provider"] == "stub"
    assert session_payload["checkout_url"].startswith("/checkout/")
    assert session_payload["total_amount"] == pytest.approx(250.0)
    session_token = session_payload["session_token"]

    public_session = client.get(f"/checkout/{session_token}")
    assert public_session.status_code == 200, public_session.text
    public_payload = public_session.json()
    assert public_payload["status"] == "open"
    assert public_payload["total_amount"] == pytest.approx(250.0)
    assert len(public_payload["items"]) == 1
    assert public_payload["items"][0]["variant_id"] == variant_id

    placed = client.post(
        f"/checkout/{session_token}/place-order",
        json={"payment_method": "transfer", "note": "Placed from public checkout"},
    )
    assert placed.status_code == 200, placed.text
    placed_payload = placed.json()
    assert placed_payload["checkout_status"] == "pending_payment"
    assert placed_payload["order_status"] == "pending"
    assert placed_payload["total_amount"] == pytest.approx(250.0)

    orders = client.get("/orders?status=pending", headers=_auth_headers(token))
    assert orders.status_code == 200, orders.text
    assert any(item["id"] == placed_payload["order_id"] for item in orders.json()["items"])

    replay = client.post(f"/checkout/{session_token}/place-order", json={"payment_method": "cash"})
    assert replay.status_code == 400, replay.text
    assert "status=pending_payment" in replay.text


def test_checkout_session_expires_and_blocks_place_order(test_context):
    client, session_local = test_context

    owner = _register(client, email="checkout-expired-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    create_session = client.post(
        "/checkout-sessions",
        json={
            "currency": "USD",
            "payment_method": "transfer",
            "channel": "instagram",
            "expires_in_minutes": 60,
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 99}],
        },
        headers=_auth_headers(token),
    )
    assert create_session.status_code == 200, create_session.text
    session_token = create_session.json()["session_token"]

    db = session_local()
    try:
        checkout = db.execute(
            select(CheckoutSession).where(CheckoutSession.session_token == session_token)
        ).scalar_one()
        checkout.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()
    finally:
        db.close()

    session_after_expiry = client.get(f"/checkout/{session_token}")
    assert session_after_expiry.status_code == 200, session_after_expiry.text
    assert session_after_expiry.json()["status"] == "expired"

    place_after_expiry = client.post(
        f"/checkout/{session_token}/place-order",
        json={"payment_method": "transfer"},
    )
    assert place_after_expiry.status_code == 400, place_after_expiry.text
    assert "status=expired" in place_after_expiry.text


def test_checkout_webhook_marks_order_paid_and_is_idempotent(test_context):
    client, session_local = test_context

    owner = _register(client, email="checkout-webhook-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)
    stock_res = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 8, "unit_cost": 70},
        headers=_auth_headers(token),
    )
    assert stock_res.status_code == 200, stock_res.text

    create_session = client.post(
        "/checkout-sessions",
        json={
            "currency": "USD",
            "payment_method": "transfer",
            "channel": "instagram",
            "expires_in_minutes": 60,
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 150}],
        },
        headers=_auth_headers(token),
    )
    assert create_session.status_code == 200, create_session.text
    session_payload = create_session.json()
    session_token = session_payload["session_token"]
    checkout_session_id = session_payload["id"]

    place_order = client.post(
        f"/checkout/{session_token}/place-order",
        json={"payment_method": "transfer", "note": "Awaiting gateway callback"},
    )
    assert place_order.status_code == 200, place_order.text
    assert place_order.json()["checkout_status"] == "pending_payment"
    order_id = place_order.json()["order_id"]

    webhook_payload = {
        "event_id": f"evt-success-{uuid.uuid4().hex[:8]}",
        "event_type": "payment.succeeded",
        "session_token": session_token,
        "status": "success",
        "amount": 300.0,
    }
    headers, body = _signed_webhook_headers(webhook_payload)
    webhook_res = client.post("/payment-webhooks/stub", content=body, headers=headers)
    assert webhook_res.status_code == 200, webhook_res.text
    webhook_json = webhook_res.json()
    assert webhook_json["ok"] is True
    assert webhook_json["duplicate"] is False
    assert webhook_json["checkout_session_id"] == checkout_session_id
    assert webhook_json["checkout_session_status"] == "paid"
    assert webhook_json["order_id"] == order_id
    assert webhook_json["order_status"] == "paid"

    duplicate_res = client.post("/payment-webhooks/stub", content=body, headers=headers)
    assert duplicate_res.status_code == 200, duplicate_res.text
    duplicate_json = duplicate_res.json()
    assert duplicate_json["ok"] is True
    assert duplicate_json["duplicate"] is True
    assert duplicate_json["checkout_session_id"] == checkout_session_id
    assert duplicate_json["checkout_session_status"] == "paid"
    assert duplicate_json["order_id"] == order_id

    db = session_local()
    try:
        checkout = db.execute(
            select(CheckoutSession).where(CheckoutSession.id == checkout_session_id)
        ).scalar_one()
        order = db.execute(select(Order).where(Order.id == order_id)).scalar_one()
        sales = db.execute(select(Sale).where(Sale.id == order.sale_id)).scalars().all()
        webhook_events = db.execute(
            select(CheckoutWebhookEvent).where(CheckoutWebhookEvent.checkout_session_id == checkout_session_id)
        ).scalars().all()
    finally:
        db.close()

    assert checkout.status == "paid"
    assert order.status == "paid"
    assert order.sale_id is not None
    assert len(sales) == 1
    assert len(webhook_events) == 1

    audit = client.get("/audit-logs", headers=_auth_headers(token))
    assert audit.status_code == 200, audit.text
    audit_actions = {item["action"] for item in audit.json()["items"]}
    assert "checkout.webhook.auto_mark_paid" in audit_actions


def test_checkout_retry_and_payments_summary_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="checkout-retry-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    create_session = client.post(
        "/checkout-sessions",
        json={
            "currency": "USD",
            "payment_method": "transfer",
            "channel": "instagram",
            "expires_in_minutes": 60,
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 80}],
        },
        headers=_auth_headers(token),
    )
    assert create_session.status_code == 200, create_session.text
    session_payload = create_session.json()
    checkout_session_id = session_payload["id"]
    session_token = session_payload["session_token"]
    initial_payment_reference = session_payload["payment_reference"]

    placed = client.post(
        f"/checkout/{session_token}/place-order",
        json={"payment_method": "transfer"},
    )
    assert placed.status_code == 200, placed.text
    assert placed.json()["checkout_status"] == "pending_payment"

    failed_payload = {
        "event_id": f"evt-failed-{uuid.uuid4().hex[:8]}",
        "event_type": "payment.failed",
        "session_token": session_token,
        "status": "failed",
        "amount": 80.0,
    }
    failed_headers, failed_body = _signed_webhook_headers(failed_payload)
    failed_res = client.post("/payment-webhooks/stub", content=failed_body, headers=failed_headers)
    assert failed_res.status_code == 200, failed_res.text
    assert failed_res.json()["checkout_session_status"] == "payment_failed"

    retry_res = client.post(
        f"/checkout-sessions/{checkout_session_id}/retry-payment",
        headers=_auth_headers(token),
    )
    assert retry_res.status_code == 200, retry_res.text
    retry_payload = retry_res.json()
    assert retry_payload["checkout_status"] == "pending_payment"
    assert retry_payload["payment_provider"] == "stub"
    assert retry_payload["payment_reference"]
    assert retry_payload["payment_reference"] != initial_payment_reference

    list_res = client.get("/checkout-sessions?status=pending_payment", headers=_auth_headers(token))
    assert list_res.status_code == 200, list_res.text
    assert any(item["id"] == checkout_session_id for item in list_res.json()["items"])

    summary_res = client.get("/checkout-sessions/payments-summary", headers=_auth_headers(token))
    assert summary_res.status_code == 200, summary_res.text
    summary_payload = summary_res.json()
    assert summary_payload["total_sessions"] == 1
    assert summary_payload["pending_payment_count"] == 1
    assert summary_payload["failed_count"] == 0
    assert summary_payload["paid_count"] == 0
    assert summary_payload["reconciled_count"] == 0
    assert summary_payload["unreconciled_count"] == 0


def test_checkout_webhook_signature_validation_and_summary_date_filter(test_context):
    client, _ = test_context

    owner = _register(client, email="checkout-signature-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    create_session = client.post(
        "/checkout-sessions",
        json={
            "currency": "USD",
            "payment_method": "transfer",
            "channel": "instagram",
            "expires_in_minutes": 60,
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 90}],
        },
        headers=_auth_headers(token),
    )
    assert create_session.status_code == 200, create_session.text
    session_token = create_session.json()["session_token"]

    placed = client.post(
        f"/checkout/{session_token}/place-order",
        json={"payment_method": "transfer"},
    )
    assert placed.status_code == 200, placed.text

    unsigned_payload = {
        "event_id": f"evt-unsigned-{uuid.uuid4().hex[:8]}",
        "event_type": "payment.succeeded",
        "session_token": session_token,
        "status": "success",
    }
    unsigned_res = client.post("/payment-webhooks/stub", json=unsigned_payload)
    assert unsigned_res.status_code == 401, unsigned_res.text
    assert "Missing webhook signature" in unsigned_res.text

    summary_range_res = client.get(
        "/checkout-sessions/payments-summary?start_date=2026-03-10&end_date=2026-03-01",
        headers=_auth_headers(token),
    )
    assert summary_range_res.status_code == 400, summary_range_res.text
    assert "end_date cannot be before start_date" in summary_range_res.text


def test_shipping_quote_selection_and_shipment_tracking_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="shipping-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)
    stock_seed = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 20, "unit_cost": 40},
        headers=_auth_headers(token),
    )
    assert stock_seed.status_code == 200, stock_seed.text

    configure_shipping = client.put(
        "/shipping/settings",
        json={
            "default_origin_country": "NG",
            "default_origin_state": "Lagos",
            "default_origin_city": "Ikeja",
            "handling_fee": 3,
            "currency": "USD",
            "zones": [{"zone_name": "Lagos Zone", "country": "NG", "state": "Lagos"}],
            "service_rules": [
                {
                    "provider": "stub_carrier",
                    "service_code": "same_day",
                    "service_name": "Same Day",
                    "zone_name": "Lagos Zone",
                    "base_rate": 10,
                    "per_kg_rate": 2,
                    "min_eta_days": 1,
                    "max_eta_days": 1,
                }
            ],
        },
        headers=_auth_headers(token),
    )
    assert configure_shipping.status_code == 200, configure_shipping.text
    assert configure_shipping.json()["currency"] == "USD"
    assert len(configure_shipping.json()["zones"]) == 1

    create_session = client.post(
        "/checkout-sessions",
        json={
            "currency": "USD",
            "payment_method": "transfer",
            "channel": "instagram",
            "expires_in_minutes": 60,
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 120}],
        },
        headers=_auth_headers(token),
    )
    assert create_session.status_code == 200, create_session.text
    session_payload = create_session.json()
    session_token = session_payload["session_token"]
    checkout_session_id = session_payload["id"]

    quote = client.post(
        f"/shipping/checkout/{session_token}/quote",
        json={
            "destination_country": "NG",
            "destination_state": "Lagos",
            "destination_city": "Lekki",
            "destination_postal_code": "100211",
            "total_weight_kg": 1.5,
        },
    )
    assert quote.status_code == 200, quote.text
    quote_payload = quote.json()
    assert quote_payload["checkout_session_token"] == session_token
    assert len(quote_payload["options"]) >= 1
    selected_option = quote_payload["options"][0]

    select_rate = client.post(
        f"/shipping/checkout/{session_token}/select-rate",
        json={
            "provider": selected_option["provider"],
            "service_code": selected_option["service_code"],
            "service_name": selected_option["service_name"],
            "zone_name": selected_option["zone_name"],
            "amount": selected_option["amount"],
            "currency": selected_option["currency"],
            "eta_min_days": selected_option["eta_min_days"],
            "eta_max_days": selected_option["eta_max_days"],
        },
    )
    assert select_rate.status_code == 200, select_rate.text
    assert select_rate.json()["checkout_session_id"] == checkout_session_id

    placed = client.post(
        f"/checkout/{session_token}/place-order",
        json={"payment_method": "transfer"},
    )
    assert placed.status_code == 200, placed.text
    order_id = placed.json()["order_id"]

    webhook_payload = {
        "event_id": f"evt-ship-{uuid.uuid4().hex[:8]}",
        "event_type": "payment.succeeded",
        "session_token": session_token,
        "status": "success",
    }
    webhook_headers, webhook_body = _signed_webhook_headers(webhook_payload)
    webhook = client.post("/payment-webhooks/stub", content=webhook_body, headers=webhook_headers)
    assert webhook.status_code == 200, webhook.text
    assert webhook.json()["order_status"] == "paid"

    shipment = client.post(
        "/shipping/shipments",
        json={
            "order_id": order_id,
            "checkout_session_id": checkout_session_id,
            "provider": selected_option["provider"],
            "service_code": selected_option["service_code"],
            "service_name": selected_option["service_name"],
            "shipping_cost": selected_option["amount"],
            "currency": "USD",
            "recipient_name": "Jane Doe",
            "recipient_phone": "+2348000000000",
            "address_line1": "12 Adeola Odeku",
            "city": "Lagos",
            "state": "Lagos",
            "country": "NG",
            "postal_code": "100211",
        },
        headers=_auth_headers(token),
    )
    assert shipment.status_code == 200, shipment.text
    shipment_payload = shipment.json()
    shipment_id = shipment_payload["id"]
    assert shipment_payload["status"] == "label_purchased"
    assert shipment_payload["tracking_number"]

    sync_first = client.post(
        f"/shipping/shipments/{shipment_id}/sync-tracking",
        headers=_auth_headers(token),
    )
    assert sync_first.status_code == 200, sync_first.text
    assert sync_first.json()["shipment_status"] == "in_transit"
    assert sync_first.json()["order_status"] == "processing"

    sync_second = client.post(
        f"/shipping/shipments/{shipment_id}/sync-tracking",
        headers=_auth_headers(token),
    )
    assert sync_second.status_code == 200, sync_second.text
    assert sync_second.json()["shipment_status"] == "delivered"
    assert sync_second.json()["order_status"] == "fulfilled"

    shipment_list = client.get("/shipping/shipments", headers=_auth_headers(token))
    assert shipment_list.status_code == 200, shipment_list.text
    assert any(item["id"] == shipment_id for item in shipment_list.json()["items"])


def test_locations_stock_transfer_scope_and_order_allocation_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="locations-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    create_location_a = client.post(
        "/locations",
        json={"name": "Main Warehouse", "code": "MAIN"},
        headers=_auth_headers(token),
    )
    assert create_location_a.status_code == 200, create_location_a.text
    location_a = create_location_a.json()["id"]

    create_location_b = client.post(
        "/locations",
        json={"name": "Lekki Store", "code": "LEKKI"},
        headers=_auth_headers(token),
    )
    assert create_location_b.status_code == 200, create_location_b.text
    location_b = create_location_b.json()["id"]

    stock_in_a = client.post(
        f"/locations/{location_a}/stock-in",
        json={"variant_id": variant_id, "qty": 9},
        headers=_auth_headers(token),
    )
    assert stock_in_a.status_code == 200, stock_in_a.text
    assert stock_in_a.json()["stock"] == 9

    transfer = client.post(
        "/locations/transfers",
        json={
            "from_location_id": location_a,
            "to_location_id": location_b,
            "items": [{"variant_id": variant_id, "qty": 4}],
        },
        headers=_auth_headers(token),
    )
    assert transfer.status_code == 200, transfer.text
    transfer_payload = transfer.json()
    assert transfer_payload["status"] == "completed"
    assert transfer_payload["items"][0]["qty"] == 4

    stock_a = client.get(
        f"/locations/{location_a}/stock/{variant_id}",
        headers=_auth_headers(token),
    )
    stock_b = client.get(
        f"/locations/{location_b}/stock/{variant_id}",
        headers=_auth_headers(token),
    )
    assert stock_a.status_code == 200, stock_a.text
    assert stock_b.status_code == 200, stock_b.text
    assert stock_a.json()["stock"] == 5
    assert stock_b.json()["stock"] == 4

    team = client.get("/team/members", headers=_auth_headers(token))
    assert team.status_code == 200, team.text
    membership_id = team.json()["items"][0]["membership_id"]

    scope = client.put(
        f"/locations/{location_a}/membership-scopes/{membership_id}",
        json={"can_manage_inventory": True},
        headers=_auth_headers(token),
    )
    assert scope.status_code == 200, scope.text
    assert scope.json()["can_manage_inventory"] is True

    create_order = client.post(
        "/orders",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 120}],
        },
        headers=_auth_headers(token),
    )
    assert create_order.status_code == 200, create_order.text
    order_id = create_order.json()["id"]

    allocation = client.post(
        "/locations/order-allocations",
        json={"order_id": order_id, "location_id": location_b},
        headers=_auth_headers(token),
    )
    assert allocation.status_code == 200, allocation.text
    assert allocation.json()["order_id"] == order_id
    assert allocation.json()["location_id"] == location_b

    stock_b_after = client.get(
        f"/locations/{location_b}/stock/{variant_id}",
        headers=_auth_headers(token),
    )
    assert stock_b_after.status_code == 200, stock_b_after.text
    assert stock_b_after.json()["stock"] == 2

    low_stock = client.get(
        "/locations/low-stock?location_id={}&threshold=3".format(location_b),
        headers=_auth_headers(token),
    )
    assert low_stock.status_code == 200, low_stock.text
    assert any(item["location_id"] == location_b for item in low_stock.json()["items"])


def test_locations_deactivate_activate_and_alias_update_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="locations-toggle-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    create_location = client.post(
        "/locations",
        json={"name": "Toggle Branch", "code": "TOGGLE"},
        headers=_auth_headers(token),
    )
    assert create_location.status_code == 200, create_location.text
    location_id = create_location.json()["id"]
    assert create_location.json()["is_active"] is True

    # Frontend sends camelCase field name; backend should accept it.
    deactivate_via_patch = client.patch(
        f"/locations/{location_id}",
        json={"isActive": False},
        headers=_auth_headers(token),
    )
    assert deactivate_via_patch.status_code == 200, deactivate_via_patch.text
    assert deactivate_via_patch.json()["is_active"] is False

    list_active_only = client.get("/locations", headers=_auth_headers(token))
    assert list_active_only.status_code == 200, list_active_only.text
    assert all(item["id"] != location_id for item in list_active_only.json()["items"])

    activate = client.post(
        f"/locations/{location_id}/activate",
        headers=_auth_headers(token),
    )
    assert activate.status_code == 200, activate.text
    assert activate.json()["is_active"] is True

    deactivate = client.post(
        f"/locations/{location_id}/deactivate",
        headers=_auth_headers(token),
    )
    assert deactivate.status_code == 200, deactivate.text
    assert deactivate.json()["is_active"] is False

    list_with_inactive = client.get("/locations?include_inactive=true", headers=_auth_headers(token))
    assert list_with_inactive.status_code == 200, list_with_inactive.text
    located = next((item for item in list_with_inactive.json()["items"] if item["id"] == location_id), None)
    assert located is not None
    assert located["is_active"] is False


def test_integrations_vault_lifecycle_outbox_and_messaging_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="integrations-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    secret_create = client.put(
        "/integrations/secrets",
        json={"provider": "meta", "key_name": "pixel_token", "secret_value": "abc123"},
        headers=_auth_headers(token),
    )
    assert secret_create.status_code == 200, secret_create.text
    assert secret_create.json()["version"] == 1

    secret_rotate = client.put(
        "/integrations/secrets",
        json={"provider": "meta", "key_name": "pixel_token", "secret_value": "rotated456"},
        headers=_auth_headers(token),
    )
    assert secret_rotate.status_code == 200, secret_rotate.text
    assert secret_rotate.json()["version"] == 2

    connect_meta = client.post(
        "/integrations/apps/install",
        json={
            "app_key": "meta_pixel",
            "display_name": "Meta Pixel",
            "permissions": ["events:write"],
            "config_json": {"pixel_id": "PIX-001"},
        },
        headers=_auth_headers(token),
    )
    assert connect_meta.status_code == 200, connect_meta.text
    assert connect_meta.json()["status"] == "connected"

    connect_ga = client.post(
        "/integrations/apps/install",
        json={
            "app_key": "google_analytics",
            "display_name": "Google Analytics",
            "permissions": ["events:write"],
            "config_json": {"measurement_id": "G-001"},
        },
        headers=_auth_headers(token),
    )
    assert connect_ga.status_code == 200, connect_ga.text

    connect_whatsapp = client.post(
        "/integrations/apps/install",
        json={
            "app_key": "whatsapp",
            "display_name": "WhatsApp Cloud",
            "permissions": ["messages:write"],
        },
        headers=_auth_headers(token),
    )
    assert connect_whatsapp.status_code == 200, connect_whatsapp.text

    storefront_config = client.put(
        "/storefront/config",
        json={"slug": "integration-store", "display_name": "Integration Store", "is_published": True},
        headers=_auth_headers(token),
    )
    assert storefront_config.status_code == 200, storefront_config.text

    public_store = client.get("/storefront/public/integration-store")
    assert public_store.status_code == 200, public_store.text

    outbox_before = client.get("/integrations/outbox/events", headers=_auth_headers(token))
    assert outbox_before.status_code == 200, outbox_before.text
    assert outbox_before.json()["pagination"]["total"] >= 2

    dispatch = client.post("/integrations/outbox/dispatch", headers=_auth_headers(token))
    assert dispatch.status_code == 200, dispatch.text
    dispatch_payload = dispatch.json()
    assert dispatch_payload["processed"] >= 2
    assert dispatch_payload["delivered"] >= 2

    emit_unknown = client.post(
        "/integrations/outbox/emit",
        json={
            "event_type": "custom.event",
            "target_app_key": "unknown_app",
            "payload_json": {"k": "v"},
        },
        headers=_auth_headers(token),
    )
    assert emit_unknown.status_code == 200, emit_unknown.text
    unknown_event_id = emit_unknown.json()["event_id"]

    dispatch_unknown = client.post("/integrations/outbox/dispatch", headers=_auth_headers(token))
    assert dispatch_unknown.status_code == 200, dispatch_unknown.text
    assert dispatch_unknown.json()["failed"] >= 1

    outbox_filtered = client.get(
        "/integrations/outbox/events?target_app_key=unknown_app",
        headers=_auth_headers(token),
    )
    assert outbox_filtered.status_code == 200, outbox_filtered.text
    unknown_items = outbox_filtered.json()["items"]
    assert any(item["id"] == unknown_event_id for item in unknown_items)

    send_message = client.post(
        "/integrations/messages/send",
        json={
            "provider": "whatsapp_stub",
            "recipient": "+2348000001111",
            "content": "Your order is ready for pickup.",
        },
        headers=_auth_headers(token),
    )
    assert send_message.status_code == 200, send_message.text
    assert send_message.json()["status"] == "sent"

    list_messages = client.get("/integrations/messages", headers=_auth_headers(token))
    assert list_messages.status_code == 200, list_messages.text
    assert list_messages.json()["pagination"]["total"] >= 1


def test_campaigns_segments_consent_dispatch_metrics_and_retention_trigger_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="campaign-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    customer_one = client.post(
        "/customers",
        json={
            "name": "Campaign Customer One",
            "phone": "+2348000000001",
            "email": "campaign-customer-one@example.com",
        },
        headers=_auth_headers(token),
    )
    assert customer_one.status_code == 200, customer_one.text
    customer_one_id = customer_one.json()["id"]

    customer_two = client.post(
        "/customers",
        json={
            "name": "Campaign Customer Two",
            "phone": "+2348000000002",
            "email": "campaign-customer-two@example.com",
        },
        headers=_auth_headers(token),
    )
    assert customer_two.status_code == 200, customer_two.text
    customer_two_id = customer_two.json()["id"]

    segment = client.post(
        "/campaigns/segments",
        json={
            "name": "Customers With Phone",
            "description": "All customers that have a phone number",
            "filters": {"has_phone": True},
        },
        headers=_auth_headers(token),
    )
    assert segment.status_code == 200, segment.text
    segment_id = segment.json()["id"]

    preview = client.post(f"/campaigns/segments/{segment_id}/preview", headers=_auth_headers(token))
    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload["total_customers"] == 2
    assert customer_one_id in preview_payload["customer_ids"]
    assert customer_two_id in preview_payload["customer_ids"]

    template = client.post(
        "/campaigns/templates",
        json={
            "name": "Winback WhatsApp Template",
            "channel": "whatsapp",
            "content": "Hi {{name}}, we miss you at MoniDesk.",
            "status": "draft",
        },
        headers=_auth_headers(token),
    )
    assert template.status_code == 200, template.text
    template_id = template.json()["id"]
    assert template.json()["status"] == "draft"

    blocked_send = client.post(
        "/campaigns",
        json={
            "name": "Draft Template Send Attempt",
            "segment_id": segment_id,
            "template_id": template_id,
            "channel": "whatsapp",
            "provider": "whatsapp_stub",
            "send_now": True,
        },
        headers=_auth_headers(token),
    )
    assert blocked_send.status_code == 400, blocked_send.text
    assert "approved" in blocked_send.text

    approve_template = client.patch(
        f"/campaigns/templates/{template_id}",
        json={"status": "approved"},
        headers=_auth_headers(token),
    )
    assert approve_template.status_code == 200, approve_template.text
    assert approve_template.json()["status"] == "approved"

    connect_whatsapp = client.post(
        "/integrations/apps/install",
        json={
            "app_key": "whatsapp",
            "display_name": "WhatsApp Cloud",
            "permissions": ["messages:write"],
        },
        headers=_auth_headers(token),
    )
    assert connect_whatsapp.status_code == 200, connect_whatsapp.text

    unsubscribe = client.put(
        "/campaigns/consent",
        json={
            "customer_id": customer_two_id,
            "channel": "whatsapp",
            "status": "unsubscribed",
            "source": "manual_test",
        },
        headers=_auth_headers(token),
    )
    assert unsubscribe.status_code == 200, unsubscribe.text
    assert unsubscribe.json()["status"] == "unsubscribed"

    campaign = client.post(
        "/campaigns",
        json={
            "name": "Winback Campaign 01",
            "segment_id": segment_id,
            "template_id": template_id,
            "channel": "whatsapp",
            "provider": "whatsapp_stub",
            "send_now": True,
        },
        headers=_auth_headers(token),
    )
    assert campaign.status_code == 200, campaign.text
    campaign_payload = campaign.json()
    campaign_id = campaign_payload["id"]
    assert campaign_payload["total_recipients"] == 2
    assert campaign_payload["suppressed_count"] >= 1
    assert campaign_payload["sent_count"] + campaign_payload["failed_count"] >= 1

    recipients = client.get(f"/campaigns/{campaign_id}/recipients", headers=_auth_headers(token))
    assert recipients.status_code == 200, recipients.text
    recipient_statuses = {item["status"] for item in recipients.json()["items"]}
    assert "suppressed" in recipient_statuses
    assert "sent" in recipient_statuses or "delivered" in recipient_statuses or "failed" in recipient_statuses

    dispatch_again = client.post(f"/campaigns/{campaign_id}/dispatch", json={}, headers=_auth_headers(token))
    assert dispatch_again.status_code == 200, dispatch_again.text
    assert dispatch_again.json()["campaign_id"] == campaign_id

    campaign_metrics = client.get(f"/campaigns/{campaign_id}/metrics", headers=_auth_headers(token))
    assert campaign_metrics.status_code == 200, campaign_metrics.text
    campaign_metrics_payload = campaign_metrics.json()
    assert campaign_metrics_payload["recipients_total"] == 2
    assert campaign_metrics_payload["suppressed_count"] >= 1
    assert campaign_metrics_payload["sent_count"] + campaign_metrics_payload["failed_count"] >= 1

    aggregate_metrics = client.get("/campaigns/metrics", headers=_auth_headers(token))
    assert aggregate_metrics.status_code == 200, aggregate_metrics.text
    assert aggregate_metrics.json()["campaigns_total"] >= 1

    trigger = client.post(
        "/campaigns/retention-triggers",
        json={
            "name": "Repeat Purchase Nudge Trigger",
            "trigger_type": "repeat_purchase_nudge",
            "status": "active",
            "segment_id": segment_id,
            "template_id": template_id,
            "channel": "whatsapp",
            "provider": "whatsapp_stub",
            "config_json": {"window_days": 30},
        },
        headers=_auth_headers(token),
    )
    assert trigger.status_code == 200, trigger.text
    trigger_id = trigger.json()["id"]

    trigger_run = client.post(
        f"/campaigns/retention-triggers/{trigger_id}/run",
        json={"auto_dispatch": True},
        headers=_auth_headers(token),
    )
    assert trigger_run.status_code == 200, trigger_run.text
    trigger_run_payload = trigger_run.json()
    assert trigger_run_payload["retention_trigger_id"] == trigger_id
    assert trigger_run_payload["campaign_id"] is not None
    assert trigger_run_payload["processed_count"] >= 2
    assert trigger_run_payload["skipped_count"] >= 1

    campaigns_list = client.get("/campaigns?limit=20&offset=0", headers=_auth_headers(token))
    assert campaigns_list.status_code == 200, campaigns_list.text
    assert any(item["id"] == campaign_id for item in campaigns_list.json()["items"])


def test_invoices_advanced_receivables_templates_partials_aging_and_statements(test_context):
    client, _ = test_context

    owner = _register(client, email="invoice-advanced-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    customer = client.post(
        "/customers",
        json={
            "name": "Advanced Receivables Customer",
            "email": "advanced.receivables@example.com",
        },
        headers=_auth_headers(token),
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["id"]

    fx_quote = client.get(
        "/invoices/fx-quote?from_currency=EUR&to_currency=USD",
        headers=_auth_headers(token),
    )
    assert fx_quote.status_code == 200, fx_quote.text
    assert fx_quote.json()["from_currency"] == "EUR"
    assert fx_quote.json()["to_currency"] == "USD"
    assert fx_quote.json()["rate"] > 0

    template = client.put(
        "/invoices/templates",
        json={
            "name": "MoniDesk Premium",
            "status": "active",
            "is_default": True,
            "brand_name": "MoniDesk",
            "primary_color": "#0ea5e9",
            "footer_text": "Thank you for your business.",
            "config_json": {"layout": "modern"},
        },
        headers=_auth_headers(token),
    )
    assert template.status_code == 200, template.text
    template_id = template.json()["id"]
    assert template.json()["is_default"] is True

    today = datetime.now(timezone.utc).date()
    create_invoice = client.post(
        "/invoices",
        json={
            "customer_id": customer_id,
            "currency": "EUR",
            "total_amount": 300,
            "issue_date": today.isoformat(),
            "due_date": (today + timedelta(days=7)).isoformat(),
            "template_id": template_id,
            "reminder_policy": {
                "enabled": True,
                "first_delay_days": 0,
                "cadence_days": 2,
                "max_reminders": 3,
                "escalation_after_days": 2,
                "channels": ["email", "whatsapp"],
            },
            "installments": [
                {"due_date": (today + timedelta(days=1)).isoformat(), "amount": 120},
                {"due_date": (today + timedelta(days=7)).isoformat(), "amount": 180},
            ],
            "send_now": True,
        },
        headers=_auth_headers(token),
    )
    assert create_invoice.status_code == 200, create_invoice.text
    invoice_id = create_invoice.json()["id"]
    assert create_invoice.json()["status"] == "sent"
    assert create_invoice.json()["currency"] == "EUR"
    assert create_invoice.json()["base_currency"] == "USD"
    assert create_invoice.json()["total_amount_base"] > 0

    list_installments = client.get(
        f"/invoices/{invoice_id}/installments",
        headers=_auth_headers(token),
    )
    assert list_installments.status_code == 200, list_installments.text
    assert len(list_installments.json()["items"]) == 2
    assert list_installments.json()["total_scheduled"] == pytest.approx(300.0)

    first_payment = client.post(
        f"/invoices/{invoice_id}/payments",
        json={
            "amount": 120,
            "payment_method": "transfer",
            "payment_reference": "adv-pay-001",
            "idempotency_key": "adv-pay-001",
        },
        headers=_auth_headers(token),
    )
    assert first_payment.status_code == 200, first_payment.text
    assert first_payment.json()["amount"] == pytest.approx(120.0)

    partial_list = client.get("/invoices?status=partially_paid", headers=_auth_headers(token))
    assert partial_list.status_code == 200, partial_list.text
    invoice_row = next((item for item in partial_list.json()["items"] if item["id"] == invoice_id), None)
    assert invoice_row is not None
    assert invoice_row["amount_paid"] == pytest.approx(120.0)
    assert invoice_row["outstanding_amount"] == pytest.approx(180.0)

    mark_paid = client.patch(
        f"/invoices/{invoice_id}/mark-paid",
        json={
            "amount": 180,
            "payment_method": "transfer",
            "payment_reference": "adv-pay-002",
            "idempotency_key": "adv-mark-paid-002",
        },
        headers=_auth_headers(token),
    )
    assert mark_paid.status_code == 200, mark_paid.text
    assert mark_paid.json()["status"] == "paid"
    assert mark_paid.json()["outstanding_amount"] == pytest.approx(0.0)

    list_payments = client.get(
        f"/invoices/{invoice_id}/payments",
        headers=_auth_headers(token),
    )
    assert list_payments.status_code == 200, list_payments.text
    assert list_payments.json()["pagination"]["total"] == 2

    upsert_policy = client.put(
        f"/invoices/{invoice_id}/reminder-policy",
        json={
            "enabled": True,
            "first_delay_days": 0,
            "cadence_days": 1,
            "max_reminders": 2,
            "escalation_after_days": 1,
            "channels": ["email"],
        },
        headers=_auth_headers(token),
    )
    assert upsert_policy.status_code == 200, upsert_policy.text
    assert upsert_policy.json()["enabled"] is True

    old_due_invoice = client.post(
        "/invoices",
        json={
            "customer_id": customer_id,
            "currency": "USD",
            "total_amount": 90,
            "due_date": "2025-01-01",
            "reminder_policy": {
                "enabled": True,
                "first_delay_days": 0,
                "cadence_days": 1,
                "max_reminders": 2,
                "escalation_after_days": 1,
                "channels": ["email"],
            },
            "send_now": True,
        },
        headers=_auth_headers(token),
    )
    assert old_due_invoice.status_code == 200, old_due_invoice.text
    old_due_invoice_id = old_due_invoice.json()["id"]

    list_after_old_due = client.get("/invoices", headers=_auth_headers(token))
    assert list_after_old_due.status_code == 200, list_after_old_due.text
    overdue_row = next(
        (item for item in list_after_old_due.json()["items"] if item["id"] == old_due_invoice_id),
        None,
    )
    assert overdue_row is not None
    assert overdue_row["status"] == "overdue"

    reminder_run = client.post("/invoices/reminders/run-due", headers=_auth_headers(token))
    assert reminder_run.status_code == 200, reminder_run.text
    assert reminder_run.json()["processed_count"] >= 1
    assert reminder_run.json()["reminders_created"] >= 1

    aging = client.get("/invoices/aging", headers=_auth_headers(token))
    assert aging.status_code == 200, aging.text
    aging_payload = aging.json()
    assert aging_payload["base_currency"] == "USD"
    assert aging_payload["overdue_count"] >= 1
    assert aging_payload["total_outstanding"] >= 90

    statements = client.get(
        f"/invoices/statements?start_date={today.isoformat()}&end_date={(today + timedelta(days=1)).isoformat()}",
        headers=_auth_headers(token),
    )
    assert statements.status_code == 200, statements.text
    assert len(statements.json()["items"]) >= 1

    export = client.get(
        f"/invoices/statements/export?start_date={today.isoformat()}&end_date={(today + timedelta(days=1)).isoformat()}",
        headers=_auth_headers(token),
    )
    assert export.status_code == 200, export.text
    assert export.json()["row_count"] >= 1
    assert "customer_id" in export.json()["csv_content"]


def test_analytics_pos_offline_and_privacy_hardening_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="analytics-pos-privacy-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 12},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    open_shift = client.post(
        "/pos/shifts/open",
        json={"opening_cash": 100},
        headers=_auth_headers(token),
    )
    assert open_shift.status_code == 200, open_shift.text
    shift_id = open_shift.json()["id"]

    sync_payload = {
        "conflict_policy": "adjust_to_available",
        "orders": [
            {
                "client_event_id": "offline-order-evt-001",
                "payment_method": "cash",
                "channel": "walk-in",
                "items": [
                    {
                        "variant_id": variant_id,
                        "qty": 2,
                        "unit_price": 120,
                    }
                ],
            }
        ],
    }
    offline_sync = client.post(
        "/pos/offline-orders/sync",
        json=sync_payload,
        headers=_auth_headers(token),
    )
    assert offline_sync.status_code == 200, offline_sync.text
    assert offline_sync.json()["created"] == 1
    assert offline_sync.json()["processed"] == 1

    offline_sync_duplicate = client.post(
        "/pos/offline-orders/sync",
        json=sync_payload,
        headers=_auth_headers(token),
    )
    assert offline_sync_duplicate.status_code == 200, offline_sync_duplicate.text
    assert offline_sync_duplicate.json()["duplicate"] >= 1

    close_shift = client.post(
        f"/pos/shifts/{shift_id}/close",
        json={"closing_cash": 340},
        headers=_auth_headers(token),
    )
    assert close_shift.status_code == 200, close_shift.text
    assert close_shift.json()["status"] == "closed"
    assert close_shift.json()["expected_cash"] == pytest.approx(340.0)

    refresh_mart = client.post(
        "/analytics/mart/refresh",
        headers=_auth_headers(token),
    )
    assert refresh_mart.status_code == 200, refresh_mart.text
    assert refresh_mart.json()["rows_refreshed"] >= 1

    profitability = client.get(
        "/analytics/channel-profitability",
        headers=_auth_headers(token),
    )
    assert profitability.status_code == 200, profitability.text
    assert len(profitability.json()["items"]) >= 1

    cohorts = client.get("/analytics/cohorts?months_after=1", headers=_auth_headers(token))
    assert cohorts.status_code == 200, cohorts.text

    inventory_aging = client.get("/analytics/inventory-aging", headers=_auth_headers(token))
    assert inventory_aging.status_code == 200, inventory_aging.text
    assert inventory_aging.json()["total_estimated_inventory_value"] >= 0

    attribution_event = client.post(
        "/analytics/attribution-events",
        json={
            "event_type": "order_conversion",
            "channel": "instagram",
            "source": "meta_ads",
            "medium": "cpc",
            "campaign_name": "Promo A",
            "revenue_amount": 120.0,
        },
        headers=_auth_headers(token),
    )
    assert attribution_event.status_code == 200, attribution_event.text
    assert attribution_event.json()["channel"] == "instagram"

    schedule = client.post(
        "/analytics/reports/schedules",
        json={
            "name": "Weekly Profitability Report",
            "report_type": "channel_profitability",
            "frequency": "weekly",
            "recipient_email": "ops@example.com",
            "status": "active",
        },
        headers=_auth_headers(token),
    )
    assert schedule.status_code == 200, schedule.text
    schedule_id = schedule.json()["id"]
    assert schedule.json()["report_type"] == "channel_profitability"

    list_schedules = client.get(
        "/analytics/reports/schedules",
        headers=_auth_headers(token),
    )
    assert list_schedules.status_code == 200, list_schedules.text
    assert any(item["id"] == schedule_id for item in list_schedules.json()["items"])

    export_report = client.get(
        "/analytics/reports/export?report_type=channel_profitability",
        headers=_auth_headers(token),
    )
    assert export_report.status_code == 200, export_report.text
    assert "channel" in export_report.json()["csv_content"]

    customer = client.post(
        "/customers",
        json={
            "name": "Privacy Customer",
            "phone": "+2348000111122",
            "email": "privacy.customer@example.com",
        },
        headers=_auth_headers(token),
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["id"]

    order = client.post(
        "/orders",
        json={
            "customer_id": customer_id,
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 100}],
        },
        headers=_auth_headers(token),
    )
    assert order.status_code == 200, order.text

    invoice = client.post(
        "/invoices",
        json={
            "customer_id": customer_id,
            "currency": "USD",
            "total_amount": 100,
        },
        headers=_auth_headers(token),
    )
    assert invoice.status_code == 200, invoice.text

    rbac_matrix = client.get("/privacy/rbac/matrix", headers=_auth_headers(token))
    assert rbac_matrix.status_code == 200, rbac_matrix.text
    roles = {item["role"] for item in rbac_matrix.json()["items"]}
    assert {"owner", "admin", "staff"}.issubset(roles)

    pii_export = client.get(
        f"/privacy/customers/{customer_id}/export",
        headers=_auth_headers(token),
    )
    assert pii_export.status_code == 200, pii_export.text
    assert pii_export.json()["customer"]["email"] == "privacy.customer@example.com"
    pii_export_pdf = client.get(
        f"/privacy/customers/{customer_id}/export/download",
        headers=_auth_headers(token),
    )
    assert pii_export_pdf.status_code == 200, pii_export_pdf.text
    assert pii_export_pdf.headers["content-type"].startswith("application/pdf")
    assert pii_export_pdf.headers["content-disposition"].endswith(".pdf\"")
    assert pii_export_pdf.content.startswith(b"%PDF")

    pii_delete = client.delete(
        f"/privacy/customers/{customer_id}",
        headers=_auth_headers(token),
    )
    assert pii_delete.status_code == 200, pii_delete.text
    assert pii_delete.json()["anonymized"] is True

    archive = client.post(
        f"/privacy/audit-archive?cutoff_date={date.today().isoformat()}&delete_archived=true",
        headers=_auth_headers(token),
    )
    assert archive.status_code == 200, archive.text
    assert archive.json()["records_count"] >= 1


def test_ai_copilot_feature_store_insights_and_actions_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="ai-copilot-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 12},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    create_order = client.post(
        "/orders",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 150}],
        },
        headers=_auth_headers(token),
    )
    assert create_order.status_code == 200, create_order.text
    order_id = create_order.json()["id"]

    mark_paid = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "paid"},
        headers=_auth_headers(token),
    )
    assert mark_paid.status_code == 200, mark_paid.text

    sale = client.post(
        "/sales",
        json={
            "payment_method": "transfer",
            "channel": "instagram",
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 200}],
        },
        headers=_auth_headers(token),
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["id"]

    refund = client.post(
        f"/sales/{sale_id}/refund",
        json={"items": [{"variant_id": variant_id, "qty": 1}]},
        headers=_auth_headers(token),
    )
    assert refund.status_code == 200, refund.text

    refresh_feature_store = client.post(
        "/ai/feature-store/refresh?window_days=30",
        headers=_auth_headers(token),
    )
    assert refresh_feature_store.status_code == 200, refresh_feature_store.text
    refresh_payload = refresh_feature_store.json()
    assert refresh_payload["orders_count"] >= 1
    assert refresh_payload["window_end_date"] == date.today().isoformat()

    generate_v2 = client.post(
        "/ai/insights/v2/generate?window_days=30",
        headers=_auth_headers(token),
    )
    assert generate_v2.status_code == 200, generate_v2.text
    generate_payload = generate_v2.json()
    assert generate_payload["actions_created"] >= 1
    assert len(generate_payload["insights"]) >= 1
    assert {
        item["insight_type"] for item in generate_payload["insights"]
    }.issubset({"anomaly", "urgency", "opportunity"})

    latest_snapshot = client.get("/ai/feature-store/latest", headers=_auth_headers(token))
    assert latest_snapshot.status_code == 200, latest_snapshot.text
    assert latest_snapshot.json()["id"] == refresh_payload["id"]

    list_insights = client.get("/ai/insights/v2", headers=_auth_headers(token))
    assert list_insights.status_code == 200, list_insights.text
    assert len(list_insights.json()["items"]) >= 1

    list_actions = client.get("/ai/actions", headers=_auth_headers(token))
    assert list_actions.status_code == 200, list_actions.text
    assert len(list_actions.json()["items"]) >= 1
    first_action_id = list_actions.json()["items"][0]["id"]

    approve_action = client.post(
        f"/ai/actions/{first_action_id}/decision",
        json={"decision": "approve", "note": "approved from test flow"},
        headers=_auth_headers(token),
    )
    assert approve_action.status_code == 200, approve_action.text
    assert approve_action.json()["status"] == "approved"

    approved_actions = client.get("/ai/actions?status=approved", headers=_auth_headers(token))
    assert approved_actions.status_code == 200, approved_actions.text
    assert any(item["id"] == first_action_id for item in approved_actions.json()["items"])


def test_ai_analytics_assistant_risk_alerts_and_governance_traceability(test_context):
    client, _ = test_context

    owner = _register(client, email="ai-risk-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 2},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    create_order = client.post(
        "/orders",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 100}],
        },
        headers=_auth_headers(token),
    )
    assert create_order.status_code == 200, create_order.text
    order_id = create_order.json()["id"]

    mark_paid = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "paid"},
        headers=_auth_headers(token),
    )
    assert mark_paid.status_code == 200, mark_paid.text

    sale = client.post(
        "/sales",
        json={
            "payment_method": "transfer",
            "channel": "instagram",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 120}],
        },
        headers=_auth_headers(token),
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["id"]

    refund = client.post(
        f"/sales/{sale_id}/refund",
        json={"items": [{"variant_id": variant_id, "qty": 1}]},
        headers=_auth_headers(token),
    )
    assert refund.status_code == 200, refund.text

    expense = client.post(
        "/expenses",
        json={"category": "operations", "amount": 180.0},
        headers=_auth_headers(token),
    )
    assert expense.status_code == 200, expense.text

    assistant_query = client.post(
        "/ai/analytics-assistant/query",
        json={"question": "What is my revenue trend?", "window_days": 30},
        headers=_auth_headers(token),
    )
    assert assistant_query.status_code == 200, assistant_query.text
    assistant_payload = assistant_query.json()
    assert assistant_payload["trace_id"]
    assert len(assistant_payload["grounded_metrics"]) >= 1

    config_get = client.get("/ai/risk-alerts/config", headers=_auth_headers(token))
    assert config_get.status_code == 200, config_get.text
    assert "channels" in config_get.json()

    config_put = client.put(
        "/ai/risk-alerts/config",
        json={
            "enabled": True,
            "refund_rate_threshold": 0.05,
            "stockout_threshold": 1,
            "cashflow_margin_threshold": 0.2,
            "channels": ["in_app", "email"],
        },
        headers=_auth_headers(token),
    )
    assert config_put.status_code == 200, config_put.text
    assert config_put.json()["stockout_threshold"] == 1

    run_alerts = client.post(
        "/ai/risk-alerts/run?window_days=30",
        headers=_auth_headers(token),
    )
    assert run_alerts.status_code == 200, run_alerts.text
    run_payload = run_alerts.json()
    assert run_payload["triggered_count"] >= 1
    assert len(run_payload["events"]) >= 1

    list_events = client.get("/ai/risk-alerts/events?status=triggered", headers=_auth_headers(token))
    assert list_events.status_code == 200, list_events.text
    assert len(list_events.json()["items"]) >= 1

    traces = client.get("/ai/governance/traces", headers=_auth_headers(token))
    assert traces.status_code == 200, traces.text
    trace_items = traces.json()["items"]
    assert len(trace_items) >= 1
    assert any(item["trace_type"] == "analytics_assistant.query" for item in trace_items)

    trace_detail = client.get(
        f"/ai/governance/traces/{assistant_payload['trace_id']}",
        headers=_auth_headers(token),
    )
    assert trace_detail.status_code == 200, trace_detail.text
    assert trace_detail.json()["prompt"]


def test_dashboard_credit_v2_forecast_and_scenario_endpoints(test_context):
    client, session_local = test_context

    owner = _register(client, email="credit-v2-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    db = session_local()
    try:
        user = db.execute(select(User).where(User.email == "credit-v2-owner@example.com")).scalar_one()
        business = db.execute(select(Business).where(Business.owner_user_id == user.id)).scalar_one()

        now = datetime.now(timezone.utc)
        seed_sales = [
            Sale(
                id=str(uuid.uuid4()),
                business_id=business.id,
                payment_method="cash",
                channel="walk-in",
                total_amount=120.0,
                kind="sale",
                created_at=now - timedelta(days=52),
            ),
            Sale(
                id=str(uuid.uuid4()),
                business_id=business.id,
                payment_method="transfer",
                channel="instagram",
                total_amount=90.0,
                kind="sale",
                created_at=now - timedelta(days=45),
            ),
            Sale(
                id=str(uuid.uuid4()),
                business_id=business.id,
                payment_method="cash",
                channel="walk-in",
                total_amount=-30.0,
                kind="refund",
                created_at=now - timedelta(days=43),
            ),
            Sale(
                id=str(uuid.uuid4()),
                business_id=business.id,
                payment_method="transfer",
                channel="whatsapp",
                total_amount=240.0,
                kind="sale",
                created_at=now - timedelta(days=12),
            ),
            Sale(
                id=str(uuid.uuid4()),
                business_id=business.id,
                payment_method="pos",
                channel="instagram",
                total_amount=210.0,
                kind="sale",
                created_at=now - timedelta(days=8),
            ),
            Sale(
                id=str(uuid.uuid4()),
                business_id=business.id,
                payment_method="cash",
                channel="walk-in",
                total_amount=-20.0,
                kind="refund",
                created_at=now - timedelta(days=6),
            ),
        ]
        seed_expenses = [
            Expense(
                id=str(uuid.uuid4()),
                business_id=business.id,
                category="rent",
                amount=130.0,
                note="previous window rent",
                created_at=now - timedelta(days=50),
            ),
            Expense(
                id=str(uuid.uuid4()),
                business_id=business.id,
                category="marketing",
                amount=60.0,
                note="previous marketing",
                created_at=now - timedelta(days=42),
            ),
            Expense(
                id=str(uuid.uuid4()),
                business_id=business.id,
                category="logistics",
                amount=90.0,
                note="current logistics",
                created_at=now - timedelta(days=10),
            ),
            Expense(
                id=str(uuid.uuid4()),
                business_id=business.id,
                category="operations",
                amount=70.0,
                note="current operations",
                created_at=now - timedelta(days=4),
            ),
        ]
        db.add_all(seed_sales + seed_expenses)
        db.commit()
    finally:
        db.close()

    profile_v2 = client.get("/dashboard/credit-profile/v2?window_days=30", headers=_auth_headers(token))
    assert profile_v2.status_code == 200, profile_v2.text
    profile_payload = profile_v2.json()
    assert 0 <= profile_payload["overall_score"] <= 100
    assert len(profile_payload["factors"]) == 6
    assert all(item["rationale"] for item in profile_payload["factors"])

    forecast = client.get(
        "/dashboard/credit-forecast?horizon_days=56&history_days=120&interval_days=7",
        headers=_auth_headers(token),
    )
    assert forecast.status_code == 200, forecast.text
    forecast_payload = forecast.json()
    assert forecast_payload["horizon_days"] == 56
    assert len(forecast_payload["intervals"]) == 8
    assert forecast_payload["intervals"][0]["net_lower_bound"] <= forecast_payload["intervals"][0]["net_upper_bound"]

    simulation = client.post(
        "/dashboard/credit-scenarios/simulate",
        json={
            "horizon_days": 56,
            "history_days": 120,
            "interval_days": 7,
            "price_change_pct": 0.08,
            "expense_change_pct": 0.03,
            "restock_investment": 200.0,
            "restock_return_multiplier": 1.4,
        },
        headers=_auth_headers(token),
    )
    assert simulation.status_code == 200, simulation.text
    simulation_payload = simulation.json()
    assert simulation_payload["baseline"]["label"] == "baseline"
    assert simulation_payload["scenario"]["label"] == "scenario"
    assert len(simulation_payload["baseline"]["intervals"]) == len(simulation_payload["scenario"]["intervals"])
    assert simulation_payload["delta"]["net_cashflow_delta"] != 0


def test_dashboard_credit_export_guardrails_and_improvement_plan(test_context):
    client, session_local = test_context

    owner = _register(client, email="credit-ops-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    db = session_local()
    try:
        user = db.execute(select(User).where(User.email == "credit-ops-owner@example.com")).scalar_one()
        business = db.execute(select(Business).where(Business.owner_user_id == user.id)).scalar_one()

        now = datetime.now(timezone.utc)
        db.add_all(
            [
                Sale(
                    id=str(uuid.uuid4()),
                    business_id=business.id,
                    payment_method="cash",
                    channel="walk-in",
                    total_amount=100.0,
                    kind="sale",
                    created_at=now - timedelta(days=48),
                ),
                Sale(
                    id=str(uuid.uuid4()),
                    business_id=business.id,
                    payment_method="transfer",
                    channel="instagram",
                    total_amount=80.0,
                    kind="sale",
                    created_at=now - timedelta(days=44),
                ),
                Sale(
                    id=str(uuid.uuid4()),
                    business_id=business.id,
                    payment_method="cash",
                    channel="walk-in",
                    total_amount=-10.0,
                    kind="refund",
                    created_at=now - timedelta(days=43),
                ),
                Sale(
                    id=str(uuid.uuid4()),
                    business_id=business.id,
                    payment_method="transfer",
                    channel="whatsapp",
                    total_amount=220.0,
                    kind="sale",
                    created_at=now - timedelta(days=9),
                ),
                Sale(
                    id=str(uuid.uuid4()),
                    business_id=business.id,
                    payment_method="pos",
                    channel="instagram",
                    total_amount=180.0,
                    kind="sale",
                    created_at=now - timedelta(days=6),
                ),
                Expense(
                    id=str(uuid.uuid4()),
                    business_id=business.id,
                    category="rent",
                    amount=50.0,
                    note="previous window",
                    created_at=now - timedelta(days=50),
                ),
                Expense(
                    id=str(uuid.uuid4()),
                    business_id=business.id,
                    category="operations",
                    amount=240.0,
                    note="current window high expense",
                    created_at=now - timedelta(days=4),
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    export_pack = client.post(
        "/dashboard/credit-export-pack?window_days=30&history_days=120&horizon_days=90",
        headers=_auth_headers(token),
    )
    assert export_pack.status_code == 200, export_pack.text
    export_payload = export_pack.json()
    assert export_payload["pack_id"]
    assert "credit_profile_v2" in export_payload["bundle_sections"]
    assert len(export_payload["statement_periods"]) >= 1
    assert len(export_payload["score_explanation"]) >= 1
    export_pack_pdf = client.get(
        "/dashboard/credit-export-pack/download?window_days=30&history_days=120&horizon_days=90",
        headers=_auth_headers(token),
    )
    assert export_pack_pdf.status_code == 200, export_pack_pdf.text
    assert export_pack_pdf.headers["content-type"].startswith("application/pdf")
    assert export_pack_pdf.headers["content-disposition"].endswith(".pdf\"")
    assert export_pack_pdf.content.startswith(b"%PDF")

    policy_get = client.get("/dashboard/finance-guardrails/policy", headers=_auth_headers(token))
    assert policy_get.status_code == 200, policy_get.text
    assert policy_get.json()["enabled"] is True

    policy_put = client.put(
        "/dashboard/finance-guardrails/policy",
        json={
            "enabled": True,
            "margin_floor_ratio": 0.45,
            "margin_drop_threshold": 0.02,
            "expense_growth_threshold": 0.05,
            "minimum_cash_buffer": 50.0,
        },
        headers=_auth_headers(token),
    )
    assert policy_put.status_code == 200, policy_put.text
    assert policy_put.json()["margin_floor_ratio"] == pytest.approx(0.45)

    guardrails = client.post(
        "/dashboard/finance-guardrails/evaluate?window_days=30&history_days=120&horizon_days=60&interval_days=7",
        headers=_auth_headers(token),
    )
    assert guardrails.status_code == 200, guardrails.text
    guardrails_payload = guardrails.json()
    assert "policy" in guardrails_payload
    assert len(guardrails_payload["alerts"]) >= 1
    assert {"margin_collapse", "expense_spike", "weak_liquidity"}.intersection(
        {item["alert_type"] for item in guardrails_payload["alerts"]}
    )

    plan = client.get(
        "/dashboard/credit-improvement-plan?window_days=30&target_score=90",
        headers=_auth_headers(token),
    )
    assert plan.status_code == 200, plan.text
    plan_payload = plan.json()
    assert plan_payload["target_score"] == 90
    assert len(plan_payload["actions"]) >= 1
    impacts = [item["estimated_score_impact"] for item in plan_payload["actions"]]
    assert impacts == sorted(impacts, reverse=True)


def test_automation_templates_rule_execution_and_logs_flow(test_context):
    client, _ = test_context

    owner = _register(client, email="automation-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    templates = client.get("/automations/templates", headers=_auth_headers(token))
    assert templates.status_code == 200, templates.text
    template_keys = {item["template_key"] for item in templates.json()["items"]}
    assert {"abandoned_cart", "overdue_invoice", "low_stock"}.issubset(template_keys)

    installed_template = client.post(
        "/automations/templates/install",
        json={"template_key": "abandoned_cart", "activate": True},
        headers=_auth_headers(token),
    )
    assert installed_template.status_code == 200, installed_template.text
    assert installed_template.json()["rule"]["template_key"] == "abandoned_cart"

    connect_whatsapp = client.post(
        "/integrations/apps/install",
        json={
            "app_key": "whatsapp",
            "display_name": "WhatsApp Cloud",
            "permissions": ["messages:write"],
        },
        headers=_auth_headers(token),
    )
    assert connect_whatsapp.status_code == 200, connect_whatsapp.text

    customer = client.post(
        "/customers",
        json={
            "name": "Automation Customer",
            "phone": "+2348011118888",
            "email": "automation.customer@example.com",
        },
        headers=_auth_headers(token),
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["id"]

    rule = client.post(
        "/automations/rules",
        json={
            "name": "Invoice Overdue Follow-up Rule",
            "description": "Apply incentive, tag customer, create task, and send reminder.",
            "trigger_source": "outbox_event",
            "trigger_event_type": "invoice.overdue",
            "conditions": [
                {"field": "payload.amount_due", "operator": "gte", "value": 50}
            ],
            "actions": [
                {
                    "type": "apply_discount",
                    "config_json": {
                        "code_prefix": "PAYNOW",
                        "kind": "percentage",
                        "value": 5,
                        "max_redemptions": 1,
                        "expires_in_days": 5,
                        "target_customer_id_from": "payload.customer_id",
                    },
                },
                {
                    "type": "tag_customer",
                    "config_json": {
                        "customer_id_from": "payload.customer_id",
                        "tag_name": "Overdue Follow-up",
                        "tag_color": "#f97316",
                    },
                },
                {
                    "type": "create_task",
                    "config_json": {
                        "title": "Call {{payload.customer_name}} for invoice {{payload.invoice_id}}",
                        "description": "Amount due is {{payload.amount_due}}.",
                        "due_in_hours": 6,
                    },
                },
                {
                    "type": "send_message",
                    "config_json": {
                        "provider": "whatsapp_stub",
                        "recipient_from": "payload.phone",
                        "content": (
                            "Invoice {{payload.invoice_id}} reminder. "
                            "Use code {{actions.apply_discount.code}} before expiry."
                        ),
                    },
                },
            ],
            "run_limit_per_hour": 3,
            "reentry_cooldown_seconds": 60,
            "rollback_on_failure": True,
        },
        headers=_auth_headers(token),
    )
    assert rule.status_code == 200, rule.text
    rule_payload = rule.json()
    rule_id = rule_payload["id"]
    assert rule_payload["version"] == 1

    emit_event = client.post(
        "/integrations/outbox/emit",
        json={
            "event_type": "invoice.overdue",
            "target_app_key": "whatsapp",
            "payload_json": {
                "invoice_id": "INV-1001",
                "amount_due": 120,
                "customer_id": customer_id,
                "customer_name": "Automation Customer",
                "phone": "+2348011118888",
            },
        },
        headers=_auth_headers(token),
    )
    assert emit_event.status_code == 200, emit_event.text

    run_outbox = client.post("/automations/outbox/run?limit=50", headers=_auth_headers(token))
    assert run_outbox.status_code == 200, run_outbox.text
    outbox_payload = run_outbox.json()
    assert outbox_payload["processed_events"] >= 1
    assert outbox_payload["successful_runs"] >= 1

    runs = client.get(f"/automations/runs?rule_id={rule_id}", headers=_auth_headers(token))
    assert runs.status_code == 200, runs.text
    runs_payload = runs.json()
    assert runs_payload["pagination"]["total"] >= 1
    run_item = runs_payload["items"][0]
    assert run_item["status"] == "success"
    assert run_item["steps_total"] == 4
    action_types = {step["action_type"] for step in run_item["steps"]}
    assert {"apply_discount", "tag_customer", "create_task", "send_message"} == action_types

    run_detail = client.get(f"/automations/runs/{run_item['id']}", headers=_auth_headers(token))
    assert run_detail.status_code == 200, run_detail.text
    assert all(step["status"] in {"success", "rolled_back"} for step in run_detail.json()["steps"])

    customer_lookup = client.get("/customers?q=automation customer", headers=_auth_headers(token))
    assert customer_lookup.status_code == 200, customer_lookup.text
    found_customer = next(
        (item for item in customer_lookup.json()["items"] if item["id"] == customer_id),
        None,
    )
    assert found_customer is not None
    assert any(tag["name"] == "Overdue Follow-up" for tag in found_customer["tags"])

    messages = client.get("/integrations/messages", headers=_auth_headers(token))
    assert messages.status_code == 200, messages.text
    assert any(item["recipient"] == "+2348011118888" for item in messages.json()["items"])

    dry_run = client.post(
        f"/automations/rules/{rule_id}/test",
        json={
            "event_type": "invoice.overdue",
            "target_app_key": "automation",
            "payload_json": {
                "invoice_id": "INV-DRY-1",
                "amount_due": 200,
                "customer_id": customer_id,
                "customer_name": "Automation Customer",
                "phone": "+2348011118888",
            },
        },
        headers=_auth_headers(token),
    )
    assert dry_run.status_code == 200, dry_run.text
    dry_run_payload = dry_run.json()
    assert dry_run_payload["status"] == "dry_run"
    assert dry_run_payload["steps_total"] == 4

    updated = client.patch(
        f"/automations/rules/{rule_id}",
        json={"status": "inactive"},
        headers=_auth_headers(token),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "inactive"
    assert updated.json()["version"] == 2


def test_automation_guardrails_rate_limit_and_loop_prevention(test_context):
    client, _ = test_context

    owner = _register(client, email="automation-guardrails-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    connect_whatsapp = client.post(
        "/integrations/apps/install",
        json={
            "app_key": "whatsapp",
            "display_name": "WhatsApp Cloud",
            "permissions": ["messages:write"],
        },
        headers=_auth_headers(token),
    )
    assert connect_whatsapp.status_code == 200, connect_whatsapp.text

    rate_rule = client.post(
        "/automations/rules",
        json={
            "name": "Rate Limited Rule",
            "trigger_event_type": "automation.rate_limit",
            "conditions": [],
            "actions": [
                {
                    "type": "create_task",
                    "config_json": {"title": "Rate task {{payload.entity_id}}"},
                }
            ],
            "run_limit_per_hour": 1,
            "reentry_cooldown_seconds": 0,
            "rollback_on_failure": True,
        },
        headers=_auth_headers(token),
    )
    assert rate_rule.status_code == 200, rate_rule.text
    rate_rule_id = rate_rule.json()["id"]

    first_rate_event = client.post(
        "/integrations/outbox/emit",
        json={
            "event_type": "automation.rate_limit",
            "target_app_key": "automation",
            "payload_json": {"entity_id": "RATE-1"},
        },
        headers=_auth_headers(token),
    )
    assert first_rate_event.status_code == 200, first_rate_event.text

    first_rate_run = client.post("/automations/outbox/run?limit=50", headers=_auth_headers(token))
    assert first_rate_run.status_code == 200, first_rate_run.text
    assert first_rate_run.json()["successful_runs"] >= 1

    second_rate_event = client.post(
        "/integrations/outbox/emit",
        json={
            "event_type": "automation.rate_limit",
            "target_app_key": "automation",
            "payload_json": {"entity_id": "RATE-2"},
        },
        headers=_auth_headers(token),
    )
    assert second_rate_event.status_code == 200, second_rate_event.text

    second_rate_run = client.post("/automations/outbox/run?limit=50", headers=_auth_headers(token))
    assert second_rate_run.status_code == 200, second_rate_run.text
    assert second_rate_run.json()["blocked_runs"] >= 1

    rate_runs = client.get(
        f"/automations/runs?rule_id={rate_rule_id}&status=blocked",
        headers=_auth_headers(token),
    )
    assert rate_runs.status_code == 200, rate_runs.text
    assert rate_runs.json()["pagination"]["total"] >= 1
    assert "Rate limit reached" in rate_runs.json()["items"][0]["blocked_reason"]

    loop_rule = client.post(
        "/automations/rules",
        json={
            "name": "Loop Guard Rule",
            "trigger_event_type": "automation.loop_guard",
            "conditions": [],
            "actions": [
                {
                    "type": "create_task",
                    "config_json": {"title": "Loop task {{payload.entity_id}}"},
                }
            ],
            "run_limit_per_hour": 10,
            "reentry_cooldown_seconds": 600,
            "rollback_on_failure": True,
        },
        headers=_auth_headers(token),
    )
    assert loop_rule.status_code == 200, loop_rule.text
    loop_rule_id = loop_rule.json()["id"]

    first_loop_event = client.post(
        "/integrations/outbox/emit",
        json={
            "event_type": "automation.loop_guard",
            "target_app_key": "automation",
            "payload_json": {"entity_id": "LOOP-ENTITY-1"},
        },
        headers=_auth_headers(token),
    )
    assert first_loop_event.status_code == 200, first_loop_event.text

    first_loop_run = client.post("/automations/outbox/run?limit=50", headers=_auth_headers(token))
    assert first_loop_run.status_code == 200, first_loop_run.text
    assert first_loop_run.json()["successful_runs"] >= 1

    second_loop_event = client.post(
        "/integrations/outbox/emit",
        json={
            "event_type": "automation.loop_guard",
            "target_app_key": "automation",
            "payload_json": {"entity_id": "LOOP-ENTITY-1"},
        },
        headers=_auth_headers(token),
    )
    assert second_loop_event.status_code == 200, second_loop_event.text

    second_loop_run = client.post("/automations/outbox/run?limit=50", headers=_auth_headers(token))
    assert second_loop_run.status_code == 200, second_loop_run.text
    assert second_loop_run.json()["blocked_runs"] >= 1

    loop_runs = client.get(
        f"/automations/runs?rule_id={loop_rule_id}&status=blocked",
        headers=_auth_headers(token),
    )
    assert loop_runs.status_code == 200, loop_runs.text
    assert loop_runs.json()["pagination"]["total"] >= 1
    assert "Loop prevention" in loop_runs.json()["items"][0]["blocked_reason"]


def test_developer_platform_api_keys_public_api_webhooks_and_marketplace_flow(test_context):
    client, session_local = test_context

    owner = _register(client, email="developer-platform-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    customer = client.post(
        "/customers",
        json={
            "name": "Developer Customer",
            "email": "developer.customer@example.com",
            "phone": "+2348001110000",
        },
        headers=_auth_headers(token),
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["id"]

    order = client.post(
        "/orders",
        json={
            "payment_method": "transfer",
            "channel": "instagram",
            "customer_id": customer_id,
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 120}],
        },
        headers=_auth_headers(token),
    )
    assert order.status_code == 200, order.text

    create_api_key = client.post(
        "/developer/api-keys",
        json={
            "name": "Partner Key",
            "scopes": ["business:read", "products:read", "orders:read", "customers:read"],
        },
        headers=_auth_headers(token),
    )
    assert create_api_key.status_code == 200, create_api_key.text
    api_key_payload = create_api_key.json()
    api_key_id = api_key_payload["id"]
    first_plain_key = api_key_payload["api_key"]

    public_me = client.get("/public/v1/me", headers={"X-Monidesk-Api-Key": first_plain_key})
    assert public_me.status_code == 200, public_me.text
    assert public_me.json()["business_name"] == "Owner Biz"

    public_products = client.get("/public/v1/products", headers={"X-Monidesk-Api-Key": first_plain_key})
    assert public_products.status_code == 200, public_products.text
    assert public_products.json()["pagination"]["total"] >= 1

    public_orders = client.get("/public/v1/orders", headers={"X-Monidesk-Api-Key": first_plain_key})
    assert public_orders.status_code == 200, public_orders.text
    assert public_orders.json()["pagination"]["total"] >= 1

    public_customers = client.get("/public/v1/customers", headers={"X-Monidesk-Api-Key": first_plain_key})
    assert public_customers.status_code == 200, public_customers.text
    assert public_customers.json()["pagination"]["total"] >= 1

    rotated = client.post(f"/developer/api-keys/{api_key_id}/rotate", headers=_auth_headers(token))
    assert rotated.status_code == 200, rotated.text
    second_plain_key = rotated.json()["api_key"]
    assert second_plain_key != first_plain_key

    old_key_access = client.get("/public/v1/me", headers={"X-Monidesk-Api-Key": first_plain_key})
    assert old_key_access.status_code == 401, old_key_access.text

    new_key_access = client.get("/public/v1/me", headers={"X-Monidesk-Api-Key": second_plain_key})
    assert new_key_access.status_code == 200, new_key_access.text

    create_subscription = client.post(
        "/developer/webhooks/subscriptions",
        json={
            "name": "Ops Receiver",
            "endpoint_url": "https://hooks.example.com/receiver",
            "description": "Primary integration endpoint",
            "events": ["storefront.*", "order.created"],
            "max_attempts": 5,
            "retry_seconds": 0,
        },
        headers=_auth_headers(token),
    )
    assert create_subscription.status_code == 200, create_subscription.text
    subscription_id = create_subscription.json()["id"]
    assert create_subscription.json()["signing_secret"].startswith("whsec_")

    emit_event = client.post(
        "/integrations/outbox/emit",
        json={
            "event_type": "storefront.page_view",
            "target_app_key": "meta_pixel",
            "payload_json": {"slug": "developer-platform"},
        },
        headers=_auth_headers(token),
    )
    assert emit_event.status_code == 200, emit_event.text

    dispatch = client.post("/developer/webhooks/deliveries/dispatch?limit=100", headers=_auth_headers(token))
    assert dispatch.status_code == 200, dispatch.text
    assert dispatch.json()["processed"] >= 1
    assert dispatch.json()["delivered"] >= 1

    deliveries = client.get(
        f"/developer/webhooks/deliveries?subscription_id={subscription_id}&status=delivered",
        headers=_auth_headers(token),
    )
    assert deliveries.status_code == 200, deliveries.text
    assert deliveries.json()["pagination"]["total"] >= 1

    docs = client.get("/developer/portal/docs", headers=_auth_headers(token))
    assert docs.status_code == 200, docs.text
    assert any(item["section"] == "sdk" for item in docs.json()["items"])

    listing = client.post(
        "/developer/marketplace/apps",
        json={
            "app_key": "partner_reporting",
            "display_name": "Partner Reporting",
            "description": "Syncs customer and order metrics for external reporting workflows.",
            "category": "analytics",
            "requested_scopes": ["orders:read", "customers:read"],
        },
        headers=_auth_headers(token),
    )
    assert listing.status_code == 200, listing.text
    listing_id = listing.json()["id"]
    assert listing.json()["status"] == "draft"

    submit = client.post(f"/developer/marketplace/apps/{listing_id}/submit", headers=_auth_headers(token))
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == "submitted"

    review = client.post(
        f"/developer/marketplace/apps/{listing_id}/review",
        json={"decision": "approved", "review_notes": "Scope request aligns with usage."},
        headers=_auth_headers(token),
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "approved"

    publish = client.post(
        f"/developer/marketplace/apps/{listing_id}/publish",
        json={"publish": True},
        headers=_auth_headers(token),
    )
    assert publish.status_code == 200, publish.text
    assert publish.json()["status"] == "published"

    db = session_local()
    try:
        key_row = db.execute(select(PublicApiKey).where(PublicApiKey.id == api_key_id)).scalar_one()
        delivery_rows = db.execute(
            select(WebhookEventDelivery).where(WebhookEventDelivery.subscription_id == subscription_id)
        ).scalars().all()
        listing_row = db.execute(
            select(MarketplaceAppListing).where(MarketplaceAppListing.id == listing_id)
        ).scalar_one()
    finally:
        db.close()

    assert key_row.key_hash != second_plain_key
    assert key_row.status == "active"
    assert len(delivery_rows) >= 1
    assert listing_row.status == "published"


def test_developer_platform_scope_enforcement_and_webhook_dead_letter_flow(test_context):
    client, session_local = test_context

    owner = _register(client, email="developer-guardrails-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    create_key = client.post(
        "/developer/api-keys",
        json={"name": "Product Read Key", "scopes": ["products:read"]},
        headers=_auth_headers(token),
    )
    assert create_key.status_code == 200, create_key.text
    api_key = create_key.json()["api_key"]

    products_ok = client.get("/public/v1/products", headers={"X-Monidesk-Api-Key": api_key})
    assert products_ok.status_code == 200, products_ok.text

    orders_forbidden = client.get("/public/v1/orders", headers={"X-Monidesk-Api-Key": api_key})
    assert orders_forbidden.status_code == 403, orders_forbidden.text
    assert "Insufficient API key scope" in orders_forbidden.text

    create_subscription = client.post(
        "/developer/webhooks/subscriptions",
        json={
            "name": "Failing Receiver",
            "endpoint_url": "https://fail.example.com/webhook",
            "events": ["order.created"],
            "max_attempts": 2,
            "retry_seconds": 0,
        },
        headers=_auth_headers(token),
    )
    assert create_subscription.status_code == 200, create_subscription.text
    subscription_id = create_subscription.json()["id"]

    create_order = client.post(
        "/orders",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 1, "unit_price": 90}],
        },
        headers=_auth_headers(token),
    )
    assert create_order.status_code == 200, create_order.text

    emit_event = client.post(
        "/integrations/outbox/emit",
        json={
            "event_type": "order.created",
            "target_app_key": "analytics",
            "payload_json": {"source": "developer-test"},
        },
        headers=_auth_headers(token),
    )
    assert emit_event.status_code == 200, emit_event.text

    first_dispatch = client.post(
        "/developer/webhooks/deliveries/dispatch?limit=50",
        headers=_auth_headers(token),
    )
    assert first_dispatch.status_code == 200, first_dispatch.text
    assert first_dispatch.json()["failed"] >= 1

    second_dispatch = client.post(
        "/developer/webhooks/deliveries/dispatch?limit=50",
        headers=_auth_headers(token),
    )
    assert second_dispatch.status_code == 200, second_dispatch.text
    assert second_dispatch.json()["dead_lettered"] >= 1

    dead_letter_deliveries = client.get(
        "/developer/webhooks/deliveries?status=dead_letter",
        headers=_auth_headers(token),
    )
    assert dead_letter_deliveries.status_code == 200, dead_letter_deliveries.text
    assert dead_letter_deliveries.json()["pagination"]["total"] >= 1

    db = session_local()
    try:
        dead_letter_rows = db.execute(
            select(WebhookEventDelivery).where(
                WebhookEventDelivery.subscription_id == subscription_id,
                WebhookEventDelivery.status == "dead_letter",
            )
        ).scalars().all()
    finally:
        db.close()

    assert len(dead_letter_rows) >= 1
