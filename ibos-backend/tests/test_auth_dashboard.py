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
    assert summary["expense_total"] == pytest.approx(30.0)
    assert summary["profit_simple"] == pytest.approx(120.0)
