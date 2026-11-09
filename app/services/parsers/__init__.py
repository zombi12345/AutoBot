from app.services.parsers import avby, kufar, kufar_html
from app.services.parsers.registry import SOURCES, register, search_by_source

# AV.BY: HTML через curl_cffi (работает стабильно)
register("avby", avby.search, fallback=None)

# KUFAR: HTML (бесплатно) = основной, ReefAPI = fallback (платные кредиты)
register("kufar", kufar_html.search, fallback=kufar.search)


async def search(source: str, criteria: dict, limit: int = 50) -> list[dict]:
    return await search_by_source(source, criteria, limit)


__all__ = ["avby", "kufar", "kufar_html", "search", "SOURCES", "search_by_source"]