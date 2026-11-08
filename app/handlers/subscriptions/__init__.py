from aiogram import Router

from app.handlers.subscriptions import create, my_subs


def get_router() -> Router:
    r = Router(name="subscriptions")
    r.include_router(create.router)
    r.include_router(my_subs.router)
    return r