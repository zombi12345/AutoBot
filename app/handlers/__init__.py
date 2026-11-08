from aiogram import Router

from app.handlers import common


def setup_routers() -> Router:
    root = Router(name="root")
    root.include_router(common.get_router())
    return root