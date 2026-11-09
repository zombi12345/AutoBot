"""D-13: добавить поля fuel/transmission/body/mileage_to в search_subscriptions.

Идемпотентно: ALTER TABLE ... ADD COLUMN IF NOT EXISTS (SQLite 3.35+).
Для старых версий — try/except.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.base import engine

log = logging.getLogger(__name__)

COLUMNS = [
    ("fuel_type", "VARCHAR(32)"),
    ("transmission", "VARCHAR(32)"),
    ("body_type", "VARCHAR(32)"),
    ("mileage_to", "INTEGER"),
    ("engine_cc_from", "INTEGER"),
    ("engine_cc_to", "INTEGER"),
]


async def up() -> None:
    async with engine.begin() as conn:
        for name, typ in COLUMNS:
            try:
                await conn.execute(text(
                    f"ALTER TABLE search_subscriptions ADD COLUMN {name} {typ}"
                ))
                log.info("added column %s", name)
            except Exception as e:
                # уже есть
                log.debug("column %s: %s", name, e)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(up())