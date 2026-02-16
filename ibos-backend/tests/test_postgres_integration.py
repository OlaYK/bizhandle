import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _test_pg_url() -> str | None:
    return os.getenv("TEST_POSTGRES_DATABASE_URL")


@pytest.mark.integration
def test_postgres_connection_and_core_tables():
    url = _test_pg_url()
    if not url:
        pytest.skip("Set TEST_POSTGRES_DATABASE_URL to run Postgres integration tests.")

    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar_one() == 1

    table_names = set(inspect(engine).get_table_names())
    assert "users" in table_names
    assert "sales" in table_names
    assert "product_variants" in table_names


@pytest.mark.integration
def test_alembic_upgrade_downgrade_smoke():
    url = _test_pg_url()
    if not url:
        pytest.skip("Set TEST_POSTGRES_DATABASE_URL to run migration smoke tests.")
    if os.getenv("ALLOW_DESTRUCTIVE_MIGRATION_TESTS") != "1":
        pytest.skip("Set ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1 for downgrade smoke test.")

    project_root = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(project_root / "alembic.ini"))

    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "6703cb55cc18")
        command.upgrade(alembic_cfg, "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
