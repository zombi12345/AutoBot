from __future__ import annotations

import asyncio
import logging
import signal
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.db import init_db
from worker.jobs import run_once

log = logging.getLogger("worker")


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is empty")

    await init_db()
    log.info("worker: db ready")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    interval = max(60, settings.check_interval_seconds)
    log.info("worker: interval=%ss", interval)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_once,
        trigger="interval",
        seconds=interval,
        args=[bot],
        id="poll_subs",
        next_run_time=None,  # не запускать сразу — дадим боту стартануть
    )
    scheduler.start()

    # первый прогон через 30 сек после старта
    async def first_run() -> None:
        await asyncio.sleep(30)
        try:
            await run_once(bot)
        except Exception as e:
            log.exception("first run fail: %s", e)

    first_task = asyncio.create_task(first_run())

    stop_event = asyncio.Event()

    def _shutdown(*_):
        log.info("worker: shutdown signal")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_event_loop().add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda *_: stop_event.set())

    try:
        await stop_event.wait()
    finally:
        log.info("worker: stopping")
        scheduler.shutdown(wait=False)
        first_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass