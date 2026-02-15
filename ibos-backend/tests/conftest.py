import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.config import settings
from app.core.deps import get_db
from app.db.base import Base
from app.main import app


@pytest.fixture()
def test_context():
    original_secret = settings.secret_key
    settings.secret_key = "test-secret-key"

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, session_local

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    settings.secret_key = original_secret
