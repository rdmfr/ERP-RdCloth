import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger("rdcloth.db")

class Base(DeclarativeBase):
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_MOCK_DB = os.environ.get("USE_MOCK_DB", "false").lower() in ("1", "true", "yes")

# If mock db or no URL provided, default to in-memory SQLite for automated tests/development
if USE_MOCK_DB or not DATABASE_URL:
    DATABASE_URL = "sqlite+aiosqlite:///:memory:"

connect_args = {}
engine_kwargs = {"echo": False}

if DATABASE_URL.startswith("postgresql+asyncpg://"):
    # Critical for PgBouncer in transaction pooling mode:
    # Disable prepared statement caching to avoid "prepared statement already exists" error
    connect_args["prepared_statement_cache_size"] = 0
    engine_kwargs["connect_args"] = connect_args
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "15"))
    engine_kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "10"))
elif DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized.")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@asynccontextmanager
async def db_transaction():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            yield session
