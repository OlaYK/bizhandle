from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine_kwargs: dict[str, object] = {
    # Detect and recover from stale pooled connections.
    "pool_pre_ping": True,
}

if not settings.database_url.lower().startswith("sqlite"):
    # Tune SQLAlchemy pool for networked databases (e.g., Neon/Postgres).
    engine_kwargs.update(
        {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout_seconds,
            "pool_recycle": settings.db_pool_recycle_seconds,
        }
    )

engine = create_engine(settings.database_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
