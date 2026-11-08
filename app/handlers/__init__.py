from aiogram import Router

from app.handlers import common, subscriptions


def setup_routers() -> Router:
    root = Router(name="root")
    root.include_router(common.get_router())
    root.include_router(subscriptions.get_router())
    return root