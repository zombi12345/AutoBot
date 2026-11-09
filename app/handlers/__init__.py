from aiogram import Router

from app.handlers import common, search, subscriptions


def setup_routers() -> Router:
    root = Router(name="root")
    # порядок важен: специфичные catch-all (AI, state) ПОСЛЕ общих команд
    root.include_router(common.get_router())
    root.include_router(search.get_router())
    root.include_router(subscriptions.get_router())
    return root