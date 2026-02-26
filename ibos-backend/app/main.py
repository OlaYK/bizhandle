from sqlalchemy import text

from app.core.observability import (
    http_exception_handler,
    request_logging_middleware,
    setup_observability,
    unhandled_exception_handler,
    validation_exception_handler,
)
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import engine
from app.routers import ai, analytics, audit, auth, automation, campaigns, checkout, customers, dashboard, developer, expenses, integrations, inventory, invoices, locations, orders, pos, privacy, products, sales, shipping, storefront, team

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Backend API for MoniDesk.\n\n"
        "Swagger quick test flow:\n"
        "1. Call `POST /auth/register` or `POST /auth/login`.\n"
        "2. Click **Authorize** and use your email/username + password "
        "(OAuth token URL: `/auth/token`).\n"
        "3. Test protected endpoints (`/products`, `/inventory`, `/sales`, `/expenses`, `/dashboard`)."
    ),
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "defaultModelsExpandDepth": 1,
    },
    openapi_tags=[
        {"name": "health", "description": "Service status and quick links."},
        {"name": "auth", "description": "User authentication and token lifecycle."},
        {"name": "products", "description": "Product catalog and variants."},
        {"name": "checkout", "description": "Checkout sessions and shareable checkout links."},
        {"name": "storefront", "description": "Storefront configuration and public catalog endpoints."},
        {"name": "shipping", "description": "Shipping settings, shipment creation, and tracking sync."},
        {"name": "locations", "description": "Multi-location inventory and stock transfer endpoints."},
        {"name": "integrations", "description": "Connected apps, credential vault, event outbox, and messaging connectors."},
        {"name": "automation", "description": "Rules engine runtime, templates, and workflow run logs."},
        {"name": "developer", "description": "Public API keys, webhook subscriptions, developer portal docs, and marketplace workflows."},
        {"name": "inventory", "description": "Stock movements and stock levels."},
        {"name": "orders", "description": "Operational order lifecycle and status tracking."},
        {"name": "invoices", "description": "Invoice lifecycle, reminders, and payment status."},
        {"name": "customers", "description": "Customer profiles, tags, and CRM management endpoints."},
        {"name": "campaigns", "description": "Customer segmentation, campaigns, consent management, and retention triggers."},
        {"name": "analytics", "description": "Advanced analytics, cohorts, profitability, and report export APIs."},
        {"name": "pos", "description": "POS shift operations and offline order synchronization."},
        {"name": "privacy", "description": "RBAC matrix, PII export/delete workflows, and audit archiving."},
        {"name": "sales", "description": "Sales capture and sales history."},
        {"name": "expenses", "description": "Expense capture and expense history."},
        {"name": "dashboard", "description": "Business KPIs and summary metrics."},
        {"name": "ai", "description": "AI assistant, event-aware feature store, v2 insight taxonomy, and action approvals."},
        {"name": "team", "description": "Team membership and role management."},
        {"name": "audit", "description": "Audit trail endpoints for sensitive operations."},
    ],
)

setup_observability()
app.middleware("http")(request_logging_middleware)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

cors_origins = settings.cors_origins or ["http://localhost:3000"]
allow_all_origins = "*" in cors_origins
env_value = settings.env.lower().strip()
allow_origin_regex = settings.cors_origin_regex

if (
    not allow_origin_regex
    and env_value in {"dev", "development", "staging", "stage"}
):
    # Helps local web/mobile-web development where tooling uses dynamic localhost ports.
    allow_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else cors_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(checkout.management_router)
app.include_router(checkout.router)
app.include_router(checkout.webhooks_router)
app.include_router(storefront.router)
app.include_router(shipping.router)
app.include_router(locations.router)
app.include_router(integrations.router)
app.include_router(automation.router)
app.include_router(developer.router)
app.include_router(developer.public_router)
app.include_router(inventory.router)
app.include_router(orders.router)
app.include_router(invoices.router)
app.include_router(customers.router)
app.include_router(campaigns.router)
app.include_router(analytics.router)
app.include_router(pos.router)
app.include_router(privacy.router)
app.include_router(sales.router)
app.include_router(expenses.router)
app.include_router(dashboard.router)
app.include_router(ai.router)
app.include_router(team.router)
app.include_router(audit.router)


@app.get("/", tags=["health"])
def root():
    return {
        "app": settings.app_name,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "ready": "/ready",
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/ready", tags=["health"])
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return {"ok": False}
    return {"ok": True}
