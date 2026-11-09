import asyncio
import logging
import os

from aiohttp import web

from app.bot import create_bot, create_dispatcher
from app.config import settings
from app.db import init_db
from sqlalchemy import func, select
from app.db.base import async_session_maker
from app.db.models import SearchSubscription
from app.db.models.subscription import SubscriptionStatus
from app.db.repositories.worker_stats import get_stats as get_worker_stats

VERSION = "0.20.2"
log = logging.getLogger("bot")

_BOT_INSTANCE = None


def git_commit() -> str:
    return os.environ.get("RENDER_GIT_COMMIT", "local")


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def handle_version(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "version": VERSION,
            "git_commit": git_commit(),
            "git_branch": os.environ.get("RENDER_GIT_BRANCH", "local"),
            "service": os.environ.get("RENDER_SERVICE_NAME", "local"),
        }
    )


async def handle_admin_stats(request: web.Request) -> web.Response:
    try:
        async with async_session_maker() as s:
            total = (await s.execute(select(func.count(SearchSubscription.id)))).scalar() or 0
            active = (await s.execute(
                select(func.count(SearchSubscription.id)).where(
                    SearchSubscription.status == SubscriptionStatus.ACTIVE
                )
            )).scalar() or 0
            seen_total = 0
            rows = (await s.execute(select(SearchSubscription.seen_listing_ids))).scalars().all()
            for r in rows:
                seen_total += len(r or [])
        ws = await get_worker_stats()
        return web.json_response({
            "subs_total": int(total),
            "subs_active": int(active),
            "subs_paused": int(total) - int(active),
            "seen_total": int(seen_total),
            "sent_total": ws["sent_total"],
            "last_run_at": ws["last_run_at"],
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_admin_run_worker(request: web.Request) -> web.Response:
    try:
        from worker.jobs import run_once as worker_run_once
        bot = _BOT_INSTANCE
        if bot is None:
            return web.json_response({"error": "bot not attached"}, status=500)
        stats = await worker_run_once(bot)
        return web.json_response({"ok": True, **stats})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def handle_admin_run_worker(request: web.Request) -> web.Response:
    try:
        from worker.jobs import run_once as worker_run_once
        bot = _BOT_INSTANCE
        if bot is None:
            return web.json_response({"error": "bot not attached"}, status=500)
        stats = await worker_run_once(bot)
        return web.json_response({"ok": True, **stats})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)


async def start_web_server() -> web.AppRunner:
    web_app = web.Application()
    web_app.router.add_get("/health", handle_health)
    web_app.router.add_get("/version", handle_version)
    web_app.router.add_get("/admin/stats", handle_admin_stats)
    web_app.router.add_post("/admin/run_worker", handle_admin_run_worker)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.port)
    await site.start()
    log.info("web server started on :%s", settings.port)
    return runner


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is empty — заполни .env перед запуском")

    await init_db()
    log.info("db ready: %s", settings.database_url)

    scheduler = None
    if settings.worker_enabled:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from worker.jobs import run_once as worker_run_once
            scheduler = AsyncIOScheduler(timezone="UTC")
            scheduler.add_job(
                worker_run_once,
                trigger="interval",
                seconds=max(60, settings.check_interval_seconds),
                args=[None],  # будет заменено ниже на bot после create_bot
                id="inline_worker",
                next_run_time=None,
            )
            scheduler.start()
            log.info("inline worker started, interval=%ss", settings.check_interval_seconds)
        except Exception as e:
            log.exception("inline worker start fail: %s", e)
            scheduler = None

    runner = await start_web_server()
    bot = create_bot()
    # сохранить bot в module-level для /admin/run_worker
    global _BOT_INSTANCE
    _BOT_INSTANCE = bot
    dp = create_dispatcher()

    if scheduler is not None:
        try:
            from worker.jobs import run_once as worker_run_once
            scheduler.remove_job("inline_worker")
            scheduler.add_job(
                worker_run_once,
                trigger="interval",
                seconds=max(60, settings.check_interval_seconds),
                args=[bot],
                id="inline_worker",
                next_run_time=None,
            )
        except Exception:
            pass

    try:
        log.info("bot polling start, version=%s commit=%s", VERSION, git_commit())
        await dp.start_polling(bot)
    finally:
        log.info("bot shutting down")
        await bot.session.close()
        await runner.cleanup()
        if scheduler is not None:
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                pass


import sys
import warnings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
warnings.filterwarnings("ignore", message=".*Proactor event loop.*")
warnings.filterwarnings("ignore", message=".*Curlm already closed.*")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("stopped")