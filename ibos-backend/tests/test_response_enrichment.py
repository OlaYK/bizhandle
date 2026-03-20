from datetime import date, timedelta

from test_auth_dashboard import _auth_headers, _create_product_with_variant, _register


def test_orders_include_customer_name_and_currency(test_context):
    client, _ = test_context

    owner = _register(client, email="orders-enrichment-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    customer = client.post(
        "/customers",
        json={"name": "Ada Customer", "phone": "+234800000001"},
        headers=_auth_headers(token),
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["id"]

    _, variant_id = _create_product_with_variant(client, token)
    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 10},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    create_order = client.post(
        "/orders",
        json={
            "customer_id": customer_id,
            "payment_method": "cash",
            "channel": "walk-in",
            "items": [{"variant_id": variant_id, "qty": 2, "unit_price": 100}],
        },
        headers=_auth_headers(token),
    )
    assert create_order.status_code == 200, create_order.text
    assert create_order.json()["currency"] == "USD"

    orders = client.get("/orders", headers=_auth_headers(token))
    assert orders.status_code == 200, orders.text
    payload = orders.json()
    assert payload["base_currency"] == "USD"
    assert payload["items"][0]["customer_id"] == customer_id
    assert payload["items"][0]["customer_name"] == "Ada Customer"
    assert payload["items"][0]["currency"] == "USD"

    order_id = payload["items"][0]["id"]
    mark_paid = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "paid"},
        headers=_auth_headers(token),
    )
    assert mark_paid.status_code == 200, mark_paid.text
    assert mark_paid.json()["customer_name"] == "Ada Customer"
    assert mark_paid.json()["currency"] == "USD"


def test_products_and_variants_expose_default_sku_and_location_stock(test_context):
    client, _ = test_context

    owner = _register(client, email="products-enrichment-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    product = client.post(
        "/products",
        json={"name": "Bedding Set", "category": "home"},
        headers=_auth_headers(token),
    )
    assert product.status_code == 200, product.text
    product_id = product.json()["id"]

    variant_a = client.post(
        f"/products/{product_id}/variants",
        json={
            "size": "Queen",
            "label": "Blue",
            "sku": "BED-QUE-BLU",
            "reorder_level": 3,
            "selling_price": 250.0,
        },
        headers=_auth_headers(token),
    )
    assert variant_a.status_code == 200, variant_a.text
    variant_a_id = variant_a.json()["id"]

    variant_b = client.post(
        f"/products/{product_id}/variants",
        json={
            "size": "King",
            "label": "White",
            "sku": "BED-KNG-WHT",
            "reorder_level": 2,
            "selling_price": 300.0,
        },
        headers=_auth_headers(token),
    )
    assert variant_b.status_code == 200, variant_b.text

    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_a_id, "qty": 7},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    location = client.post(
        "/locations",
        json={"name": "Ikeja Store", "code": "IKJ"},
        headers=_auth_headers(token),
    )
    assert location.status_code == 200, location.text
    location_id = location.json()["id"]

    location_stock_in = client.post(
        f"/locations/{location_id}/stock-in",
        json={"variant_id": variant_a_id, "qty": 4},
        headers=_auth_headers(token),
    )
    assert location_stock_in.status_code == 200, location_stock_in.text
    assert location_stock_in.json()["product_name"] == "Bedding Set"
    assert location_stock_in.json()["location_name"] == "Ikeja Store"
    assert location_stock_in.json()["sku"] == "BED-QUE-BLU"

    products = client.get("/products", headers=_auth_headers(token))
    assert products.status_code == 200, products.text
    product_payload = products.json()["items"][0]
    assert product_payload["variant_count"] == 2
    assert product_payload["default_variant_id"] == variant_a_id
    assert product_payload["default_sku"] == "BED-QUE-BLU"
    assert product_payload["default_selling_price"] == 250.0
    assert product_payload["default_stock"] == 7

    variants = client.get(
        f"/products/{product_id}/variants?location_id={location_id}",
        headers=_auth_headers(token),
    )
    assert variants.status_code == 200, variants.text
    variant_payload = next(item for item in variants.json()["items"] if item["id"] == variant_a_id)
    assert variant_payload["product_name"] == "Bedding Set"
    assert variant_payload["stock"] == 7
    assert variant_payload["location_stock"] == 4


def test_invoices_and_inventory_aging_include_readable_names(test_context):
    client, _ = test_context

    owner = _register(client, email="invoice-aging-owner@example.com")
    assert owner.status_code == 200, owner.text
    token = owner.json()["access_token"]

    customer = client.post(
        "/customers",
        json={"name": "Grace Buyer", "phone": "+234800000002"},
        headers=_auth_headers(token),
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["id"]

    product_id, variant_id = _create_product_with_variant(client, token)
    _ = product_id
    stock_in = client.post(
        "/inventory/stock-in",
        json={"variant_id": variant_id, "qty": 5},
        headers=_auth_headers(token),
    )
    assert stock_in.status_code == 200, stock_in.text

    issue_date = date.today() - timedelta(days=10)
    due_date = date.today() - timedelta(days=2)
    invoice = client.post(
        "/invoices",
        json={
            "customer_id": customer_id,
            "currency": "USD",
            "total_amount": 200.0,
            "issue_date": issue_date.isoformat(),
            "due_date": due_date.isoformat(),
            "send_now": True,
        },
        headers=_auth_headers(token),
    )
    assert invoice.status_code == 200, invoice.text

    invoices = client.get("/invoices", headers=_auth_headers(token))
    assert invoices.status_code == 200, invoices.text
    invoice_payload = invoices.json()["items"][0]
    assert invoice_payload["customer_id"] == customer_id
    assert invoice_payload["customer_name"] == "Grace Buyer"
    assert invoice_payload["currency"] == "USD"

    aging = client.get("/invoices/aging", headers=_auth_headers(token))
    assert aging.status_code == 200, aging.text
    assert aging.json()["top_customers"][0]["customer_name"] == "Grace Buyer"

    statements = client.get(
        f"/invoices/statements?start_date={issue_date.isoformat()}&end_date={date.today().isoformat()}",
        headers=_auth_headers(token),
    )
    assert statements.status_code == 200, statements.text
    assert statements.json()["items"][0]["customer_name"] == "Grace Buyer"

    inventory_aging = client.get("/analytics/inventory-aging", headers=_auth_headers(token))
    assert inventory_aging.status_code == 200, inventory_aging.text
    aging_item = inventory_aging.json()["items"][0]
    assert inventory_aging.json()["base_currency"] == "USD"
    assert aging_item["product_name"] == "Ankara Fabric"
    assert aging_item["sku"]
