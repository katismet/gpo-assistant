"""Настройка базы данных."""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings

# Синхронный движок для Alembic и синхронных операций
engine = create_engine(settings.DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Асинхронный движок для основного приложения
async_engine = create_async_engine(
    settings.DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://").replace("postgresql://", "postgresql+psycopg://"),
    echo=settings.DEBUG,
    future=True,
)

# Создание фабрики асинхронных сессий
async_session = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


def get_sync_session():
    """Получить синхронную сессию базы данных."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


async def get_session() -> AsyncSession:
    """Получить асинхронную сессию базы данных."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except:
        s.rollback()
        raise
    finally:
        s.close()


async def init_db() -> None:
    """Инициализация базы данных."""
    async with async_engine.begin() as conn:
        # Создание всех таблиц
        await conn.run_sync(Base.metadata.create_all)
