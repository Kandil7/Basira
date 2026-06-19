"""
Database models for PostgreSQL.

Defines the SQLAlchemy models for audit logging and persistence.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config.settings import Settings


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class AuditLog(Base):
    """Audit log entry for tracking agent actions and decisions."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    session_id = Column(String(255), nullable=True, index=True)
    user_query = Column(Text, nullable=True)
    agent = Column(String(100), nullable=True, index=True)
    intent = Column(String(100), nullable=True)
    response = Column(Text, nullable=True)
    tools_used = Column(Text, nullable=True)  # JSON array as string
    sources = Column(Text, nullable=True)  # JSON array as string
    processing_time_ms = Column(Float, nullable=True)
    success = Column(Integer, default=1)  # 1 = success, 0 = failure
    error_message = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON object as string


class ConversationHistory(Base):
    """Persistent conversation history for long-term storage."""

    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    agent = Column(String(100), nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    metadata_json = Column(Text, nullable=True)


# Database engine and session factory
_engine = None
_session_factory = None


def init_database(settings: Settings) -> None:
    """Initialize database engine and session factory."""
    global _engine, _session_factory

    try:
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            echo=settings.app_env == "development",
        )
        _session_factory = sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("database.initialized", url=settings.database_url.split("@")[-1])
    except Exception as e:
        logger.error("database.init_failed", error=str(e))


def get_session() -> AsyncSession | None:
    """Get a database session."""
    if _session_factory is None:
        return None
    return _session_factory()


async def create_tables() -> None:
    """Create all database tables."""
    if _engine is None:
        return
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_database() -> None:
    """Close database connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


import structlog
logger = structlog.get_logger(__name__)
