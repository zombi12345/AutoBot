from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.base import async_session_maker
from app.db.models.subscription import SearchSubscription, SubscriptionStatus

_SEEN_LIMIT = 500


async def create_subscription(
    user_id: int,
    *,
    source: str = "avby",
    brand: str | None = None,
    model: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    price_from: int | None = None,
    price_to: int | None = None,
    extra: dict[str, Any] | None = None,
) -> SearchSubscription:
    async with async_session_maker() as s:
        sub = SearchSubscription(
            user_id=user_id,
            source=source,
            brand=brand,
            model=model,
            year_from=year_from,
            year_to=year_to,
            price_from=price_from,
            price_to=price_to,
            extra=extra or {},
            status=SubscriptionStatus.ACTIVE,
            seen_listing_ids=[],
        )
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub


async def list_active_subscriptions() -> list[SearchSubscription]:
    async with async_session_maker() as s:
        stmt = select(SearchSubscription).where(SearchSubscription.status == SubscriptionStatus.ACTIVE)
        return list((await s.execute(stmt)).scalars().all())


async def list_user_subscriptions(user_id: int) -> list[SearchSubscription]:
    async with async_session_maker() as s:
        stmt = (
            select(SearchSubscription)
            .where(SearchSubscription.user_id == user_id)
            .order_by(SearchSubscription.id.desc())
        )
        return list((await s.execute(stmt)).scalars().all())


async def set_status(sub_id: int, status: str) -> bool:
    async with async_session_maker() as s:
        sub = await s.get(SearchSubscription, sub_id)
        if sub is None:
            return False
        sub.status = status
        await s.commit()
        return True


async def pause_subscription(sub_id: int) -> bool:
    return await set_status(sub_id, SubscriptionStatus.PAUSED)


async def resume_subscription(sub_id: int) -> bool:
    return await set_status(sub_id, SubscriptionStatus.ACTIVE)


async def delete_subscription(sub_id: int) -> bool:
    async with async_session_maker() as s:
        sub = await s.get(SearchSubscription, sub_id)
        if sub is None:
            return False
        await s.delete(sub)
        await s.commit()
        return True


async def mark_checked(sub_id: int, new_seen_ids: list[str]) -> None:
    async with async_session_maker() as s:
        sub = await s.get(SearchSubscription, sub_id)
        if sub is None:
            return
        seen = list(sub.seen_listing_ids or [])
        seen_set = set(seen)
        for lid in new_seen_ids:
            if lid not in seen_set:
                seen.append(lid)
                seen_set.add(lid)
        sub.seen_listing_ids = seen[-_SEEN_LIMIT:]
        sub.last_checked_at = datetime.now(timezone.utc)
        await s.commit()

async def get_subscription(sub_id: int) -> SearchSubscription | None:
    async with async_session_maker() as s:
        return await s.get(SearchSubscription, sub_id)


async def update_subscription(sub_id: int, **fields) -> bool:
    allowed = {"brand", "model", "year_from", "year_to", "price_from", "price_to", "status", "source", "extra"}
    async with async_session_maker() as s:
        sub = await s.get(SearchSubscription, sub_id)
        if sub is None:
            return False
        for k, v in fields.items():
            if k in allowed:
                setattr(sub, k, v)
        await s.commit()
        return True