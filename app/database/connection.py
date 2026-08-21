from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
import logging
from app.config import settings
from app.database.models import Base

logger = logging.getLogger(__name__)


def get_database_url():
    return f"mysql+mysqlconnector://{settings.mysql_user}:{settings.mysql_password}@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}"


def create_db_engine():
    db_url = get_database_url()
    logger.info(f"Creating database engine for: {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")

    engine = create_engine(
        db_url,
        echo=settings.debug,
        pool_pre_ping=True,  # Test connections before using them
        pool_recycle=3600,  # Recycle connections every hour
        pool_size=10,
        max_overflow=20,
    )

    return engine


def init_db():
    """Initialize database tables"""
    engine = create_db_engine()
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise
    return engine


engine = init_db()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
