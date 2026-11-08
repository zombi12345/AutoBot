from aiogram import Router

from app.handlers.subscriptions import actions, create, detail, find, my_subs


def get_router() -> Router:
    r = Router(name="subscriptions")
    r.include_router(create.router)
    r.include_router(detail.router)
    r.include_router(find.router)
    r.include_router(my_subs.router)
    r.include_router(actions.router)
    return r