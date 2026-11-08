from __future__ import annotations

import logging

from aiogram import Bot

from app.data.cars_full import BRAND_IDS, MODEL_IDS
from app.db.repositories.subscriptions import (
    list_active_subscriptions,
    mark_checked,
)
from app.db.repositories.users import get_or_create_user  # noqa: F401
from app.db.base import async_session_maker
from app.db.models.user import User
from app.services.parsers.avby import search
from worker.notifier import send_new

log = logging.getLogger("worker.jobs")

MAX_PER_RUN = 15  # не спамить одним объявлением пачкой


async def _get_chat_id(user_id: int) -> int | None:
    async with async_session_maker() as s:
        u = await s.get(User, user_id)
        return u.telegram_id if u else None


async def run_once(bot: Bot) -> dict:
    stats = {"subs": 0, "sent": 0, "errors": 0}
    try:
        subs = await list_active_subscriptions()
    except Exception as e:
        log.exception("list_active_subscriptions fail: %s", e)
        return stats

    stats["subs"] = len(subs)
    if not subs:
        log.info("worker: 0 active subscriptions")
        return stats

    for sub in subs:
        try:
            await _process_one(bot, sub, stats)
        except Exception as e:
            log.exception("sub #%s fail: %s", sub.id, e)
            stats["errors"] += 1
    log.info("worker: subs=%s sent=%s errors=%s", stats["subs"], stats["sent"], stats["errors"])
    return stats


async def _process_one(bot: Bot, sub, stats: dict) -> None:
    chat_id = await _get_chat_id(sub.user_id)
    if chat_id is None:
        return

    brand_id = BRAND_IDS.get(sub.brand) if sub.brand else None
    model_id = None
    if brand_id and sub.model:
        model_id = (MODEL_IDS.get(sub.brand) or {}).get(sub.model)

    criteria = {
        "brand_id": brand_id,
        "model_id": model_id,
        "year_from": sub.year_from,
        "year_to": sub.year_to,
        "price_from": sub.price_from,
        "price_to": sub.price_to,
        "query": None,
    }
    if not brand_id:
        q = " ".join(x for x in [sub.brand, sub.model] if x).strip()
        criteria["query"] = q or None

    results = await search(criteria, limit=MAX_PER_RUN)

    if not results:
        await mark_checked(sub.id, [])
        return

    seen = set(sub.seen_listing_ids or [])
    new_items = [r for r in results if r["id"] not in seen]
    if not new_items:
        await mark_checked(sub.id, [])
        return

    # отправить
    await send_new(bot, chat_id, sub, new_items, results)
    stats["sent"] += len(new_items)

    # запомнить
    await mark_checked(sub.id, [r["id"] for r in new_items])