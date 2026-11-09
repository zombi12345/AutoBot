"""Реестр парсеров с fallback и уведомлением админа."""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from aiogram import Bot

log = logging.getLogger(__name__)

# тип: async-функция search(criteria, limit) -> list[dict]
ParserFn = Callable[[dict, int], Awaitable[list[dict]]]


class ParserSource:
    def __init__(self, name: str, primary: ParserFn, fallback: ParserFn | None = None):
        self.name = name
        self.primary = primary
        self.fallback = fallback
        self.primary_fails = 0
        self.fallback_active = False

    async def search(self, criteria: dict, limit: int = 50) -> list[dict]:
        """Пробует primary, при ошибке/пустом результате — fallback."""
        try:
            results = await self.primary(criteria, limit)
            if results:
                self.primary_fails = 0
                self.fallback_active = False
                return results
            log.warning("%s: primary вернул 0 результатов", self.name)
            self.primary_fails += 1
        except Exception as e:
            log.warning("%s: primary упал: %s", self.name, e)
            self.primary_fails += 1

        if self.fallback is None:
            return []

        if self.primary_fails >= 2 and not self.fallback_active:
            self.fallback_active = True
            log.error("%s: переключение на fallback после %d ошибок", self.name, self.primary_fails)

        try:
            log.info("%s: fallback", self.name)
            results = await self.fallback(criteria, limit)
            return results
        except Exception as e:
            log.error("%s: fallback тоже упал: %s", self.name, e)
            return []


# Глобальные источники (регистрируются в parsers/__init__.py)
SOURCES: dict[str, ParserSource] = {}


def register(name: str, primary: ParserFn, fallback: ParserFn | None = None) -> None:
    SOURCES[name] = ParserSource(name, primary, fallback)


async def search_by_source(name: str, criteria: dict, limit: int = 50) -> list[dict]:
    src = SOURCES.get(name)
    if src is None:
        log.warning("unknown source: %s", name)
        return []
    return await src.search(criteria, limit)


async def notify_admin(bot: Bot, admin_ids: list[int], text: str) -> None:
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            log.warning("notify_admin fail %s: %s", admin_id, e)