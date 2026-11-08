import asyncio
import logging
import os

from aiohttp import web

from app.bot import create_bot, create_dispatcher
from app.config import settings
from app.db import init_db

VERSION = "0.7.4"
log = logging.getLogger("bot")


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


async def start_web_server() -> web.AppRunner:
    web_app = web.Application()
    web_app.router.add_get("/health", handle_health)
    web_app.router.add_get("/version", handle_version)
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

    runner = await start_web_server()
    bot = create_bot()
    dp = create_dispatcher()

    try:
        log.info("bot polling start, version=%s commit=%s", VERSION, git_commit())
        await dp.start_polling(bot)
    finally:
        log.info("bot shutting down")
        await bot.session.close()
        await runner.cleanup()


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