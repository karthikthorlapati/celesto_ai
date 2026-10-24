"""Database session and connection management for PostgreSQL / SQLite."""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

# Normalize postgres:// to postgresql:// for SQLAlchemy 2.0
db_url = settings.database_url
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# SQLite connect args vs PostgreSQL connect args
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and idempotent seed record."""
    from app.models import RunModel

    Base.metadata.create_all(bind=engine)

    # Check and insert idempotent seed run: sbx-seeddemo1
    with SessionLocal() as db:
        existing = db.query(RunModel).filter_by(sandbox_name="sbx-seeddemo1").first()
        if not existing:
            seed_run = RunModel(
                run_id="run-seed-001",
                sandbox_name="sbx-seeddemo1",
                problem_id="problem-seed-eval",
                state="succeeded",
                execution_target="celesto_sandbox",
            )
            db.add(seed_run)
            try:
                db.commit()
                logger.info("Inserted idempotent seed run sbx-seeddemo1")
            except Exception as e:
                db.rollback()
                logger.warning(f"Seed run insertion handled conflict: {e}")
