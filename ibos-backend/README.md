# IBOS Backend - AI-Powered Informal Business OS

## Overview
This is the backend for IBOS, an informal business operating system designed to help micro-entrepreneurs manage their products, sales, inventory, and expenses.

## Tech Stack
- **Framework:** FastAPI
- **Database:** PostgreSQL (SQLAlchemy + Alembic)
- **Environment Management:** Poetry
- **Security:** JWT (python-jose) + Bcrypt (passlib)

## Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Poetry

### Local Development
1. Clone the repository
2. Install dependencies:
   ```bash
   poetry install
   ```
3. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
4. Start with Docker Compose (API + Postgres):
   ```bash
   docker compose up -d --build
   ```
5. Run database migrations:
   ```bash
   poetry run alembic upgrade head
   ```
6. Or run API locally (DB can still run in Docker):
   ```bash
   poetry run uvicorn app.main:app --reload
   ```
7. Run tests:
   ```bash
   poetry run pytest -q
   ```
8. Optional integration tests (requires dedicated Postgres URL):
   ```bash
   set TEST_POSTGRES_DATABASE_URL=postgresql+psycopg://...
   poetry run pytest -m integration -q
   ```

## Required Environment Variables
Fill these in `.env` before production deployment:

- `SECRET_KEY`
- `DATABASE_URL`
- `OPENAI_API_KEY` (only if `AI_PROVIDER=openai`)
- `GOOGLE_CLIENT_ID` (only if using Google auth)
- `AUTH_RATE_LIMIT_MAX_ATTEMPTS` (optional, default `5`)
- `AUTH_RATE_LIMIT_WINDOW_SECONDS` (optional, default `300`)
- `AUTH_RATE_LIMIT_LOCK_SECONDS` (optional, default `900`)
- `LOW_STOCK_DEFAULT_THRESHOLD` (optional, default `5`)

`AI_PROVIDER` defaults to `stub`, so OpenAI keys are optional for local development.

## Core Endpoints
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/token`
- `POST /auth/google`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /auth/change-password`
- `POST /products`
- `POST /products/{product_id}/variants`
- `GET /products`
- `GET /products/{product_id}/variants`
- `POST /inventory/stock-in`
- `POST /inventory/adjust`
- `GET /inventory/stock/{variant_id}`
- `GET /inventory/ledger`
- `GET /inventory/low-stock`
- `POST /sales`
- `POST /sales/{sale_id}/refund`
- `GET /sales`
- `POST /expenses`
- `GET /expenses`
- `GET /dashboard/summary`
- `POST /ai/ask`
- `GET /ai/insights/daily`
- `GET /health`
- `GET /ready`

## API Documentation
Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Response Conventions
- Error responses use a uniform envelope:
  - `{"error": {"code", "message", "request_id", "path", "details"}}`
- Paginated list endpoints use:
  - `{"items": [...], "pagination": {"total", "limit", "offset", "count", "has_next"}}`

## Security Notes
- `.env` is intentionally ignored and should never be committed.
- Rotate secrets if they were ever exposed in chat, screenshots, logs, or commits.
- To purge old secrets from git history, use a history-rewrite tool on a clean clone
  (for example `git filter-repo`), then force-push and rotate credentials again.

## Swagger Testing Flow
1. Call `POST /auth/register` with the example payload.
2. Click **Authorize** in Swagger UI.
3. Enter your `email` (or `username`) in the `username` field and your password.
4. Test protected endpoints in this order:
   - `POST /products`
   - `POST /products/{product_id}/variants`
   - `POST /inventory/stock-in`
   - `POST /sales`
   - `POST /expenses`
   - `GET /dashboard/summary`
