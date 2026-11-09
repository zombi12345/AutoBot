from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp

from app.config import settings

log = logging.getLogger(__name__)

REEF_URL = "https://api.reefapi.com/kufar/v1/search"
CAR_CATEGORY = "2010"  # leaf: Легковые авто
USD_TO_BYN = 3.27


async def search(criteria: dict[str, Any], limit: int = 50) -> list[dict]:
    key = settings.reef_api_key
    if not key:
        log.warning("kufar: REEF_API_KEY не задан")
        return []

    q_parts: list[str] = []
    if criteria.get("brand"):
        q_parts.append(str(criteria["brand"]))
    if criteria.get("model"):
        q_parts.append(str(criteria["model"]))
    query = " ".join(q_parts).strip()

    body: dict[str, Any] = {
        "category": CAR_CATEGORY,
        "size": min(200, max(1, limit)),
        "sort": "newest",
    }
    if query:
        body["query"] = query
    if criteria.get("price_from"):
        body["price_min"] = int(criteria["price_from"] * USD_TO_BYN)
    if criteria.get("price_to"):
        body["price_max"] = int(criteria["price_to"] * USD_TO_BYN)

    headers = {"x-api-key": key, "content-type": "application/json"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as s:
            async with s.post(REEF_URL, headers=headers, json=body) as r:
                if r.status != 200:
                    log.warning("kufar reef HTTP %s: %s", r.status, (await r.text())[:300])
                    return []
                data = await r.json()
    except Exception as e:
        log.warning("kufar reef fail: %s", e)
        return []

    rows = (data.get("data") or {}).get("listings") or []
    if not isinstance(rows, list):
        log.warning("kufar: listings not list: %s", str(data)[:200])
        return []
    items = _parse(rows, limit)

    # fallback: query не дал — берём категорию и фильтруем в Python
    if not items and query:
        log.info("kufar: query=%r -> 0, fallback category-only", query)
        body.pop("query", None)
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as s2:
                async with s2.post(REEF_URL, headers=headers, json=body) as r2:
                    if r2.status == 200:
                        data2 = await r2.json()
                        rows2 = (data2.get("data") or {}).get("listings") or []
                        items = _parse(rows2, limit)
                        items = _filter_by_brand_model(items, criteria)
        except Exception as e:
            log.warning("kufar fallback fail: %s", e)

    if criteria.get("year_from") or criteria.get("year_to"):
        items = _postfilter(items, criteria)

    log.info("kufar: %d results (query=%r)", len(items), query)
    return items


def _parse(rows: list, limit: int) -> list[dict]:
    out: list[dict] = []
    for ad in rows[:limit]:
        try:
            if not isinstance(ad, dict):
                continue
            ad_id = ad.get("listing_id") or ad.get("id")
            title = ad.get("title") or "—"
            url = ad.get("url") or (f"https://auto.kufar.by/vi/{ad_id}" if ad_id else None)
            if not url:
                continue
            price = ad.get("price_byn") or ad.get("price")
            currency = "BYN"
            if not ad.get("price_byn") and ad.get("price_currency"):
                currency = ad.get("price_currency")

            # год из title (Kufar не даёт body в search)
            year = None
            m = re.search(r"\b(19|20)\d{2}\b", str(title))
            if m:
                year = int(m.group(0))

            # params: title + регион
            parts = [title]
            if ad.get("region_name"):
                parts.append(f"регион: {ad['region_name']}")
            if ad.get("posted_at"):
                parts.append(f"опубликовано: {str(ad['posted_at'])[:10]}")

            out.append({
                "id": str(ad_id) if ad_id else url,
                "title": str(title),
                "year": year,
                "price": int(price) if price else None,
                "currency": currency,
                "url": url,
                "params": " · ".join(parts),
            })
        except Exception:
            continue
    return out


def _filter_by_brand_model(items: list[dict], criteria: dict) -> list[dict]:
    brand = (criteria.get("brand") or "").lower()
    model = (criteria.get("model") or "").lower()
    if not brand and not model:
        return items
    out = []
    for r in items:
        text = (r.get("title", "") + " " + r.get("params", "")).lower()
        if brand and brand not in text:
            continue
        if model and model not in text:
            continue
        out.append(r)
    return out


def _postfilter(items: list[dict], criteria: dict) -> list[dict]:
    yf, yt = criteria.get("year_from"), criteria.get("year_to")
    out = []
    for r in items:
        y = r.get("year")
        if yf and y and y < yf:
            continue
        if yt and y and y > yt:
            continue
        out.append(r)
    return out