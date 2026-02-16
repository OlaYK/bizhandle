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
from app.routers import ai, auth, products, inventory, sales, expenses, dashboard

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Backend API for IBOS.\n\n"
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
        {"name": "inventory", "description": "Stock movements and stock levels."},
        {"name": "sales", "description": "Sales capture and sales history."},
        {"name": "expenses", "description": "Expense capture and expense history."},
        {"name": "dashboard", "description": "Business KPIs and summary metrics."},
        {"name": "ai", "description": "AI assistant and daily insight endpoints."},
    ],
)

setup_observability()
app.middleware("http")(request_logging_middleware)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

cors_origins = settings.cors_origins or ["http://localhost:3000"]
allow_all_origins = "*" in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else cors_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(inventory.router)
app.include_router(sales.router)
app.include_router(expenses.router)
app.include_router(dashboard.router)
app.include_router(ai.router)


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
