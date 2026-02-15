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
4. Start the database:
   ```bash
   docker compose up -d
   ```
5. Run the application:
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

## API Documentation
Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
