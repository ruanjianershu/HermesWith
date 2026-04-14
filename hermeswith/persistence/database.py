"""Database connection and session management for HermesWith."""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://hermeswith:hermeswith@localhost:5432/hermeswith",
)

# Convert postgresql:// to postgresql+asyncpg:// for SQLAlchemy async
if DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

async_engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Sync version for non-async contexts
def get_db():
    """Get database session (sync version for CLI and services)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Use sync driver
    sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    SessionLocal = sessionmaker(bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_db() -> None:
    """Create all database tables."""
    # Import all models to ensure they are registered with Base
    from hermeswith.persistence.models import (
        CompanyDB, APIKeyDB, AuditLogDB, RateLimitDB, EncryptedConfigDB,
        GoalDB, GoalExecutionDB, AgentMemoryDB,
        AgentDB, TaskDB, AgentOutputDB
    )  # noqa: F401
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
