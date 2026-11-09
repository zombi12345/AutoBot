from aiogram import Router
from app.handlers.search import ai_search

def get_router() -> Router:
    r = Router(name="search")
    r.include_router(ai_search.router)
    return r