"""D-18: fuzzy-нормализация существующих подписок.

brand: "Мерседес" -> "Mercedes-Benz"
model: "glk350" -> "GLK"
engine_cc: из "glk350" -> 3400-3600
"""
import asyncio
import logging

from sqlalchemy import select

from app.data.cars_full import BRANDS, BRAND_NAMES
from app.db.base import async_session_maker
from app.db.models import SearchSubscription
from app.utils.fuzzy import find_brand, find_model

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def up() -> None:
    async with async_session_maker() as s:
        subs = list((await s.execute(select(SearchSubscription))).scalars().all())
        changed = 0
        for sub in subs:
            old_b, old_m = sub.brand, sub.model
            new_b, new_m = old_b, old_m

            if old_b:
                canon, _ = find_brand(old_b, BRAND_NAMES)
                if canon and canon != old_b:
                    new_b = canon
            if old_m and new_b and new_b in BRANDS:
                canon, _ = find_model(old_m, BRANDS[new_b])
                if canon and canon != old_m:
                    new_m = canon

            if new_b != old_b or new_m != old_m:
                sub.brand = new_b
                sub.model = new_m
                changed += 1
                log.info("sub #%s: %r/%r -> %r/%r", sub.id, old_b, old_m, new_b, new_m)

        if changed:
            await s.commit()
        log.info("migration done: %d/%d updated", changed, len(subs))


if __name__ == "__main__":
    asyncio.run(up())