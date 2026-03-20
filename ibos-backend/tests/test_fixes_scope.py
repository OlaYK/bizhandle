from sqlalchemy import select

from app.models.user import User
from test_auth_dashboard import _auth_headers, _create_product_with_variant, _register


def test_variant_image_supports_update_and_storefront_exposure(test_context):
    client, _ = test_context

    owner = _register(client, email="variant-image-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    storefront = client.put(
        "/storefront/config",
        json={
            "slug": "image-ready-store",
            "display_name": "Image Ready Store",
            "is_published": True,
        },
        headers=_auth_headers(token),
    )
    assert storefront.status_code == 200, storefront.text

    product_res = client.post(
        "/products",
        json={"name": "Velvet Fabric", "category": "fabrics"},
        headers=_auth_headers(token),
    )
    assert product_res.status_code == 200, product_res.text
    product_id = product_res.json()["id"]

    variant_res = client.post(
        f"/products/{product_id}/variants",
        json={
            "size": "4x4",
            "label": "Ruby",
            "sku": "VEL-4X4-RUBY",
            "selling_price": 125,
            "image_url": "https://cdn.example.com/ruby-1.jpg",
        },
        headers=_auth_headers(token),
    )
    assert variant_res.status_code == 200, variant_res.text
    variant_id = variant_res.json()["id"]

    update_variant = client.patch(
        f"/products/{product_id}/variants/{variant_id}",
        json={"image_url": "https://cdn.example.com/ruby-2.jpg"},
        headers=_auth_headers(token),
    )
    assert update_variant.status_code == 200, update_variant.text
    assert update_variant.json()["image_url"] == "https://cdn.example.com/ruby-2.jpg"

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

    variants = client.get(f"/products/{product_id}/variants", headers=_auth_headers(token))
    assert variants.status_code == 200, variants.text
    assert variants.json()["items"][0]["image_url"] == "https://cdn.example.com/ruby-2.jpg"

    public_list = client.get("/storefront/public/image-ready-store/products")
    assert public_list.status_code == 200, public_list.text
    assert public_list.json()["items"][0]["preview_image_url"] == "https://cdn.example.com/ruby-2.jpg"

    public_detail = client.get(f"/storefront/public/image-ready-store/products/{product_id}")
    assert public_detail.status_code == 200, public_detail.text
    assert public_detail.json()["variants"][0]["image_url"] == "https://cdn.example.com/ruby-2.jpg"


def test_analytics_overview_includes_expenses_and_inventory_movements(test_context):
    client, _ = test_context

    owner = _register(client, email="analytics-overview-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 10, "unit_cost": 50},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    sale = client.post(
        "/sales",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 3, "unit_price": 120}],
        },
        headers=_auth_headers(token),
    )
    assert sale.status_code == 200, sale.text

    expense = client.post(
        "/expenses",
        json={"category": "logistics", "amount": 40, "note": "Bike delivery"},
        headers=_auth_headers(token),
    )
    assert expense.status_code == 200, expense.text

    overview = client.get("/analytics/overview", headers=_auth_headers(token))
    assert overview.status_code == 200, overview.text
    payload = overview.json()
    assert payload["summary"]["revenue_total"] > 0
    assert payload["summary"]["expenses_total"] == 40.0
    assert payload["summary"]["stock_in_qty_total"] == 10
    assert payload["summary"]["stock_out_qty_total"] == 3
    assert any(item["category"] == "logistics" for item in payload["expense_categories"])
    assert any(item["reason"] == "stock_in" for item in payload["inventory_movements"])
    assert any(point["sales_count"] >= 1 for point in payload["timeline"])


def test_audit_logs_expose_actor_username_role_and_export_formats(test_context):
    client, _ = test_context

    owner = _register(client, email="audit-export-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    customer = client.post(
        "/customers",
        json={"name": "Audit Buyer", "phone": "+2348000000500"},
        headers=_auth_headers(token),
    )
    assert customer.status_code == 200, customer.text

    audit_logs = client.get("/audit-logs?action=customer.create", headers=_auth_headers(token))
    assert audit_logs.status_code == 200, audit_logs.text
    item = audit_logs.json()["items"][0]
    assert item["actor_username"]
    assert item["actor_role"] == "owner"

    export_csv = client.get("/audit-logs/export?action=customer.create&format=csv", headers=_auth_headers(token))
    assert export_csv.status_code == 200, export_csv.text
    assert export_csv.headers["content-type"].startswith("text/csv")
    assert "actor_username" in export_csv.text
    assert "customer.create" in export_csv.text

    export_pdf = client.get("/audit-logs/export?action=customer.create&format=pdf", headers=_auth_headers(token))
    assert export_pdf.status_code == 200, export_pdf.text
    assert export_pdf.headers["content-type"] == "application/pdf"
    assert export_pdf.content.startswith(b"%PDF")


def test_delete_account_soft_deletes_user_and_blocks_access(test_context):
    client, session_local = test_context

    owner = _register(client, email="delete-account-owner@example.com")
    assert owner.status_code == 200, owner.text
    access_token = owner.json()["access_token"]

    delete_res = client.post(
        "/auth/me/delete",
        json={"current_password": "password123", "confirmation_text": "DELETE"},
        headers=_auth_headers(access_token),
    )
    assert delete_res.status_code == 200, delete_res.text
    assert delete_res.json()["ok"] is True

    me_after_delete = client.get("/auth/me", headers=_auth_headers(access_token))
    assert me_after_delete.status_code == 401, me_after_delete.text

    login_after_delete = client.post(
        "/auth/login",
        json={"identifier": "delete-account-owner@example.com", "password": "password123"},
    )
    assert login_after_delete.status_code == 401, login_after_delete.text

    db = session_local()
    try:
        user = db.execute(select(User)).scalar_one()
    finally:
        db.close()

    assert user.is_deleted is True
    assert user.is_active is False
    assert user.deleted_at is not None
