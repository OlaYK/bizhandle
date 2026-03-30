from sqlalchemy import select

from app.models.checkout import CheckoutSession
from app.models.customer import Customer
from app.models.order import Order
from app.models.privacy_document import CustomerDocument
from test_auth_dashboard import _auth_headers, _create_product_with_variant, _register


def test_orders_list_exposes_location_allocation_summary(test_context):
    client, _ = test_context

    owner = _register(client, email="allocation-summary-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    _, variant_id = _create_product_with_variant(client, token)

    location = client.post(
        "/locations",
        json={"name": "Lekki Hub", "code": "LEK"},
        headers=_auth_headers(token),
    )
    assert location.status_code == 200, location.text
    location_id = location.json()["id"]

    stock_in = client.post(
        f"/locations/{location_id}/stock-in",
        json={"variant_id": variant_id, "qty": 6},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    order = client.post(
        "/orders",
        json={
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 100}],
        },
        headers=_auth_headers(token),
    )
    assert order.status_code == 200, order.text
    order_id = order.json()["id"]

    allocation = client.post(
        "/locations/order-allocations",
        json={"order_id": order_id, "location_id": location_id},
        headers=_auth_headers(token),
    )
    assert allocation.status_code == 200, allocation.text

    orders = client.get("/orders", headers=_auth_headers(token))
    assert orders.status_code == 200, orders.text
    order_row = next(item for item in orders.json()["items"] if item["id"] == order_id)
    assert order_row["allocation"]["location_id"] == location_id
    assert order_row["allocation"]["location_name"] == "Lekki Hub"
    assert order_row["allocation"]["allocated_at"]


def test_invoice_preview_supports_delivery_options_and_channel_validation(test_context):
    client, _ = test_context

    owner = _register(client, email="invoice-preview-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    customer = client.post(
        "/customers",
        json={"name": "Preview Buyer", "phone": "+2348000000200"},
        headers=_auth_headers(token),
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["id"]

    _, variant_id = _create_product_with_variant(client, token)
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
    order_id = order.json()["id"]

    invoice = client.post(
        "/invoices",
        json={"customer_id": customer_id, "order_id": order_id, "currency": "USD"},
        headers=_auth_headers(token),
    )
    assert invoice.status_code == 200, invoice.text
    invoice_id = invoice.json()["id"]

    preview = client.get(f"/invoices/{invoice_id}/preview", headers=_auth_headers(token))
    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload["recommended_channel"] == "whatsapp"
    assert preview_payload["line_items"][0]["product_name"] == "Ankara Fabric"
    assert any(
        item["channel"] == "email" and item["ready"] is False
        for item in preview_payload["delivery_options"]
    )
    assert any(
        item["channel"] == "whatsapp"
        and item["ready"] is True
        and item["recipient"] == "+2348000000200"
        for item in preview_payload["delivery_options"]
    )

    invalid_send = client.post(
        f"/invoices/{invoice_id}/send",
        json={"channel": "email"},
        headers=_auth_headers(token),
    )
    assert invalid_send.status_code == 400, invalid_send.text
    assert "email" in invalid_send.text.lower()

    valid_send = client.post(
        f"/invoices/{invoice_id}/send",
        json={"channel": "whatsapp", "note": "Customer prefers WhatsApp"},
        headers=_auth_headers(token),
    )
    assert valid_send.status_code == 200, valid_send.text
    assert valid_send.json()["status"] == "sent"


def test_audit_logs_are_redacted_and_readable(test_context):
    client, _ = test_context

    owner = _register(client, email="audit-readable-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    invoice = client.post(
        "/invoices",
        json={"currency": "USD", "total_amount": 240, "send_now": True},
        headers=_auth_headers(token),
    )
    assert invoice.status_code == 200, invoice.text
    invoice_id = invoice.json()["id"]

    mark_paid = client.patch(
        f"/invoices/{invoice_id}/mark-paid",
        json={
            "payment_method": "transfer",
            "payment_reference": "bank-ref-100",
            "idempotency_key": "audit-pay-12345",
        },
        headers=_auth_headers(token),
    )
    assert mark_paid.status_code == 200, mark_paid.text

    audit_logs = client.get(
        "/audit-logs?action=invoice.mark_paid",
        headers=_auth_headers(token),
    )
    assert audit_logs.status_code == 200, audit_logs.text
    audit_item = audit_logs.json()["items"][0]
    assert audit_item["actor_name"] == "Owner"
    assert audit_item["actor_email"] != "audit-readable-owner@example.com"
    assert "@" in audit_item["actor_email"]
    assert audit_item["summary"].startswith("Invoice Mark Paid")
    assert audit_item["target_label"].startswith("Invoice ")
    assert audit_item["metadata_json"]["payment_reference"] != "bank-ref-100"
    assert audit_item["metadata_json"]["idempotency_key"] != "audit-pay-12345"
    assert any("currency:" in preview for preview in audit_item["metadata_preview"])


def test_customer_documents_support_public_signing_and_pii_export(test_context):
    client, session_local = test_context

    owner = _register(client, email="privacy-doc-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    customer = client.post(
        "/customers",
        json={
            "name": "Consent Buyer",
            "email": "consent@example.com",
            "phone": "+2348000000300",
        },
        headers=_auth_headers(token),
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["id"]

    document = client.post(
        "/privacy/customer-documents",
        json={
            "customer_id": customer_id,
            "document_type": "consent_form",
            "title": "Delivery Consent",
            "consent_text": "I agree that MoniDesk may process my order details for delivery.",
            "expires_in_days": 14,
            "metadata_json": {"source": "checkout"},
        },
        headers=_auth_headers(token),
    )
    assert document.status_code == 200, document.text
    document_payload = document.json()
    assert document_payload["status"] == "pending_signature"
    assert document_payload["customer_name"] == "Consent Buyer"
    assert document_payload["share_url"].startswith("/privacy/customer-documents/sign/")

    list_documents = client.get("/privacy/customer-documents", headers=_auth_headers(token))
    assert list_documents.status_code == 200, list_documents.text
    assert any(item["id"] == document_payload["id"] for item in list_documents.json()["items"])

    public_document = client.get(document_payload["share_url"])
    assert public_document.status_code == 200, public_document.text
    assert public_document.json()["status"] == "pending_signature"

    signed = client.post(
        document_payload["share_url"],
        json={"accepted": True, "signer_name": "Consent Buyer"},
    )
    assert signed.status_code == 200, signed.text
    assert signed.json()["status"] == "signed"
    assert signed.json()["signed_by_name"] == "Consent Buyer"

    export_res = client.get(
        f"/privacy/customers/{customer_id}/export",
        headers=_auth_headers(token),
    )
    assert export_res.status_code == 200, export_res.text
    export_payload = export_res.json()
    assert len(export_payload["documents"]) == 1
    assert export_payload["documents"][0]["id"] == document_payload["id"]
    assert export_payload["documents"][0]["status"] == "signed"

    db = session_local()
    try:
        stored = db.execute(
            select(CustomerDocument).where(CustomerDocument.id == document_payload["id"])
        ).scalar_one()
    finally:
        db.close()

    assert stored.status == "signed"
    assert stored.signed_by_name == "Consent Buyer"


def test_storefront_cart_checkout_creates_guest_customer_and_enriches_public_session(test_context):
    client, session_local = test_context

    owner = _register(client, email="storefront-cart-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    config = client.put(
        "/storefront/config",
        json={
            "slug": "cart-ready-store",
            "display_name": "Cart Ready Store",
            "is_published": True,
        },
        headers=_auth_headers(token),
    )
    assert config.status_code == 200, config.text

    product_a_id, variant_a_id = _create_product_with_variant(client, token)
    publish_product_a = client.patch(
        f"/products/{product_a_id}/publish",
        json={"is_published": True},
        headers=_auth_headers(token),
    )
    assert publish_product_a.status_code == 200, publish_product_a.text
    publish_variant_a = client.patch(
        f"/products/{product_a_id}/variants/{variant_a_id}/publish",
        json={"is_published": True},
        headers=_auth_headers(token),
    )
    assert publish_variant_a.status_code == 200, publish_variant_a.text

    product_b = client.post(
        "/products",
        json={"name": "Aso Oke Deluxe", "category": "fabrics"},
        headers=_auth_headers(token),
    )
    assert product_b.status_code == 200, product_b.text
    product_b_id = product_b.json()["id"]

    variant_b = client.post(
        f"/products/{product_b_id}/variants",
        json={
            "size": "Premium Roll",
            "label": "Gold Trim",
            "sku": "ASO-OKE-001",
            "reorder_level": 2,
            "cost_price": 80,
            "selling_price": 140,
        },
        headers=_auth_headers(token),
    )
    assert variant_b.status_code == 200, variant_b.text
    variant_b_id = variant_b.json()["id"]

    publish_product_b = client.patch(
        f"/products/{product_b_id}/publish",
        json={"is_published": True},
        headers=_auth_headers(token),
    )
    assert publish_product_b.status_code == 200, publish_product_b.text
    publish_variant_b = client.patch(
        f"/products/{product_b_id}/variants/{variant_b_id}/publish",
        json={"is_published": True},
        headers=_auth_headers(token),
    )
    assert publish_variant_b.status_code == 200, publish_variant_b.text

    cart_session = client.post(
        "/checkout/storefront/cart-ready-store/cart-session",
        json={
            "payment_method": "transfer",
            "channel": "instagram",
            "note": "Cart checkout",
            "items": [
                {"variant_id": variant_a_id, "qty": 2},
                {"variant_id": variant_b_id, "qty": 1},
            ],
        },
    )
    assert cart_session.status_code == 200, cart_session.text
    cart_payload = cart_session.json()
    assert cart_payload["status"] == "open"
    assert cart_payload["total_amount"] == 340.0
    session_token = cart_payload["session_token"]

    public_session = client.get(f"/checkout/{session_token}")
    assert public_session.status_code == 200, public_session.text
    public_payload = public_session.json()
    assert public_payload["payment_provider"] == "stub"
    assert public_payload["payment_reference"]
    assert len(public_payload["items"]) == 2
    item_by_variant = {item["variant_id"]: item for item in public_payload["items"]}
    assert item_by_variant[variant_a_id]["product_name"] == "Ankara Fabric"
    assert item_by_variant[variant_a_id]["sku"]
    assert item_by_variant[variant_b_id]["product_name"] == "Aso Oke Deluxe"
    assert item_by_variant[variant_b_id]["label"] == "Gold Trim"

    place_order = client.post(
        f"/checkout/{session_token}/place-order",
        json={
            "payment_method": "transfer",
            "customer_name": "Guest Buyer",
            "customer_email": "guestbuyer@example.com",
            "customer_phone": "+2348000000400",
        },
    )
    assert place_order.status_code == 200, place_order.text
    place_order_payload = place_order.json()
    assert place_order_payload["checkout_status"] == "pending_payment"
    assert place_order_payload["customer_id"]

    db = session_local()
    try:
        customer = db.execute(
            select(Customer).where(Customer.id == place_order_payload["customer_id"])
        ).scalar_one()
        order = db.execute(
            select(Order).where(Order.id == place_order_payload["order_id"])
        ).scalar_one()
        checkout = db.execute(
            select(CheckoutSession).where(CheckoutSession.session_token == session_token)
        ).scalar_one()
    finally:
        db.close()

    assert customer.name == "Guest Buyer"
    assert customer.email == "guestbuyer@example.com"
    assert order.customer_id == customer.id
    assert checkout.customer_id == customer.id
