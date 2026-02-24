# MoniDesk Backend

FastAPI backend for MoniDesk (informal business operating system).

## Current Feature Surface
- Auth and profile: register/login/refresh/logout/password change/Google auth
- Team and security: memberships, RBAC, audit logs, privacy workflows
- Commerce core: products, variants, inventory, sales, refunds, expenses
- Order and receivables: orders, invoices, reminders, statements, AR aging
- Online commerce: storefront, checkout sessions, payment webhooks, shipping
- Operations scale: locations, stock transfers, POS offline sync and shifts
- Growth: CRM, tags, segments, campaigns, retention triggers
- Intelligence: analytics mart, AI insights/actions/risk/governance, credit intelligence
- Automation and platform: workflow automation, integrations, developer API keys/webhooks/marketplace

## Tech Stack
- FastAPI + Pydantic v2
- SQLAlchemy + Alembic
- PostgreSQL (primary)
- Poetry for dependency management
- Pytest for test coverage

## Prerequisites
- Python 3.11+
- Poetry
- Docker + Docker Compose (for local Postgres)
- Node.js 18+ and npm (for frontend)

## Local Run (Recommended)

### 1) Backend setup
```powershell
cd ibos-backend
poetry install
Copy-Item .env.example .env
```

### 2) Start Postgres
```powershell
docker compose up -d db
```

### 3) Run migrations
```powershell
poetry run alembic upgrade head
```

### 4) Start backend API
```powershell
poetry run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 5) Start frontend (new terminal)
```powershell
cd ..\ibos-frontend
npm install
Copy-Item .env.example .env
npm run dev
```

## URLs
- API docs (Swagger): `http://127.0.0.1:8000/docs`
- API docs (ReDoc): `http://127.0.0.1:8000/redoc`
- API health: `http://127.0.0.1:8000/health`
- Frontend app: `http://127.0.0.1:5173`

## Minimal Env Requirements
Required:
- `SECRET_KEY`
- `DATABASE_URL`

Common optional:
- `AI_PROVIDER` (default `stub`)
- `OPENAI_API_KEY` (required only when `AI_PROVIDER=openai`)
- `GOOGLE_CLIENT_ID`
- `PAYMENT_WEBHOOK_SECRET`
- `CORS_ORIGINS`

See `ibos-backend/.env.example` for baseline values.

## Test Commands

### Backend
```powershell
cd ibos-backend
poetry run pytest -q -p no:cacheprovider
```

### Frontend build check
```powershell
cd ibos-frontend
npm run build
```

## Quick API Smoke Flow
1. `POST /auth/register`
2. `POST /products`
3. `POST /products/{product_id}/variants`
4. `POST /inventory/stock-in`
5. `POST /orders`
6. `PATCH /orders/{order_id}/status` (set `paid`)
7. `GET /dashboard/summary`

## Common Local Issues
- `SECRET_KEY` / `DATABASE_URL` missing:
  - Ensure `.env` exists in `ibos-backend` and server is started from that directory.
- Frontend error `VITE_API_BASE_URL is not configured`:
  - Ensure `ibos-frontend/.env` exists (copy from `.env.example`).
- Migration mismatch:
  - Run `poetry run alembic upgrade head` after pulling new changes.

## Security Notes
- Never commit `.env`.
- Rotate secrets if exposed in logs/screenshots/commits.
