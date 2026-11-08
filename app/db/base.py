from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite") or ":///" not in url:
        return
    rel = url.split(":///", 1)[1]
    if not rel or rel == ":memory:":
        return
    p = Path(rel)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

engine = create_async_engine(settings.database_url, echo=False, future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    import app.db.models  # noqa: F401  (регистрация таблиц)
    from sqlalchemy.orm import configure_mappers
    configure_mappers()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session