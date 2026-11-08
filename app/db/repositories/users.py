from __future__ import annotations

from sqlalchemy import select

from app.config import settings
from app.db.base import async_session_maker
from app.db.models.user import User


async def get_or_create_user(
    telegram_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
) -> User:
    async with async_session_maker() as s:
        stmt = select(User).where(User.telegram_id == telegram_id)
        user = (await s.execute(stmt)).scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, username=username, first_name=first_name)
            s.add(user)
            await s.commit()
            await s.refresh(user)
            return user
        changed = False
        if username is not None and user.username != username:
            user.username = username
            changed = True
        if first_name is not None and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if changed:
            await s.commit()
        return user


async def is_admin(telegram_id: int) -> bool:
    """Учитывает и settings.admin_ids, и флаг is_admin в БД (playbook D4)."""
    if telegram_id in settings.admin_ids:
        return True
    async with async_session_maker() as s:
        stmt = select(User).where(User.telegram_id == telegram_id)
        user = (await s.execute(stmt)).scalar_one_or_none()
        return bool(user and user.is_admin)