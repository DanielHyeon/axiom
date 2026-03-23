"""Twin 서비스 DB 연결."""
import os
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)
DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", settings.DATABASE_SCHEMA)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base(metadata=MetaData(schema=DATABASE_SCHEMA))


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def ensure_schema(conn) -> None:
    import re
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', DATABASE_SCHEMA):
        raise ValueError(f"Invalid schema name: {DATABASE_SCHEMA}")
    await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DATABASE_SCHEMA}"))


async def init_database() -> None:
    async with engine.begin() as conn:
        await ensure_schema(conn)
        await conn.run_sync(Base.metadata.create_all)
