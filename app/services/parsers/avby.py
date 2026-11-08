from __future__ import annotations

import logging
from typing import Any

import aiohttp

log = logging.getLogger(__name__)

AVBY_API = "https://api.av.by"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

ENDPOINTS = (
    "{api}/filtering/cars?page=1&page_size={n}",
    "{api}/offers/cars/search?page=1&per_page={n}",
    "{api}/cars/search?page=1&per_page={n}",
)


async def search(criteria: dict[str, Any], limit: int = 5) -> list[dict]:
    """Ищет объявления на av.by.

    criteria keys: brand_id, model_id, year_from, year_to, price_from, price_to, query
    Returns: [{id, title, year, price_usd, url}]
    """
    body = _build_body(criteria)
    for tmpl in ENDPOINTS:
        url = tmpl.format(api=AVBY_API, n=limit)
        try:
            data = await _post(url, body)
        except Exception as e:
            log.warning("avby endpoint %s failed: %s", url, e)
            continue
        if not data:
            continue
        results = _parse(data, limit)
        if results:
            log.info("avby: %d results from %s", len(results), url)
            return results
    log.info("avby: no results for %s", body)
    return []


def _build_body(criteria: dict) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if criteria.get("brand_id"):
        body["brand"] = [int(criteria["brand_id"])]
    if criteria.get("model_id"):
        body["model"] = [int(criteria["model_id"])]
    year: dict[str, int] = {}
    if criteria.get("year_from"):
        year["from"] = int(criteria["year_from"])
    if criteria.get("year_to"):
        year["to"] = int(criteria["year_to"])
    if year:
        body["year"] = year
    price: dict[str, int] = {}
    if criteria.get("price_from"):
        price["from"] = int(criteria["price_from"])
    if criteria.get("price_to"):
        price["to"] = int(criteria["price_to"])
    if price:
        body["price"] = price
    if criteria.get("query"):
        body["query"] = str(criteria["query"])
    return body


async def _post(url: str, body: dict) -> dict | None:
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as s:
        async with s.post(url, json=body) as r:
            if r.status != 200:
                log.warning("avby HTTP %s: %s", r.status, url)
                return None
            try:
                return await r.json()
            except Exception as e:
                log.warning("avby json decode fail: %s", e)
                return None


def _parse(data: dict, limit: int) -> list[dict]:
    if not isinstance(data, dict):
        return []
    items = (
        data.get("adverts")
        or data.get("offers")
        or data.get("items")
        or data.get("results")
        or []
    )
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for ad in items[:limit]:
        try:
            if not isinstance(ad, dict):
                continue
            ad_id = ad.get("id")
            title = ad.get("title") or ad.get("name") or "—"
            year = ad.get("year")
            if year is None and isinstance(ad.get("properties"), dict):
                year = ad["properties"].get("year")
            price_usd = None
            if isinstance(ad.get("price"), dict):
                price_usd = (ad["price"].get("usd") or {}).get("amount")
            url = ad.get("publicUrl") or ad.get("url")
            if not url and ad_id:
                url = f"https://cars.av.by/{ad_id}"
            if not url:
                continue
            out.append({
                "id": str(ad_id) if ad_id else url,
                "title": str(title),
                "year": year,
                "price_usd": price_usd,
                "url": url,
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out