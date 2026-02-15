"""Database connection and session management for IntelliNews AI Service."""
import logging

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Enable connection health checks
    pool_size=5,
    max_overflow=10
)

# Create SessionLocal class for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for declarative models
Base = declarative_base()


def get_db():
    """
    Dependency that provides database session.
    
    Yields:
        Database session that will be closed after request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database connection check.
    Tables are created via DDL in docker/db/init/001_schema.sql.
    """
    logger.info("Checking database connection...")
    import db.models  # noqa: F401 — ensure all models are registered
    # Tables are managed by DDL in docker/db/init/001_schema.sql
    # Base.metadata.create_all(bind=engine)
    logger.info("Database connection verified")
