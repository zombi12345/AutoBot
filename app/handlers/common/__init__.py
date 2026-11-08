from aiogram import Router

from app.handlers.common import start


def get_router() -> Router:
    r = Router(name="common")
    r.include_router(start.router)
    return r