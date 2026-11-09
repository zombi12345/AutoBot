from __future__ import annotations

import logging
from typing import Any

import aiohttp

from app.config import settings

log = logging.getLogger(__name__)

REEF_URL = "https://api.reefapi.com/kufar/v1/search"
CAR_CATEGORY = "2010"  # leaf id: Легковые автомобили
USD_TO_BYN = 3.27


async def search(criteria: dict[str, Any], limit: int = 50) -> list[dict]:
    """Kufar через ReefAPI. criteria: brand, model, year_from/to, price_from/to (USD)."""
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

    body: dict[str, Any] = {"category": CAR_CATEGORY, "size": min(200, max(1, limit)), "sort": "newest"}
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
                    log.warning("kufar reef HTTP %s: %s", r.status, (await r.text())[:200])
                    return []
                data = await r.json()
    except Exception as e:
        log.warning("kufar reef fail: %s", e)
        return []

    rows = (data.get("data") or {}).get("ads") or []
    if not isinstance(rows, list):
        return []
    items = _parse(rows, limit)
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
            url = ad.get("url") or (f"https://auto.kufar.by/item/{ad_id}" if ad_id else None)
            if not url:
                continue
            price = ad.get("price_byn")
            if price is None:
                price = ad.get("price")
            currency = ad.get("price_currency") or "BYN"

            year = None
            params_parts: list[str] = []
            attrs = ad.get("attributes") or ad.get("params") or []
            for p in attrs:
                if not isinstance(p, dict):
                    continue
                label = p.get("label") or p.get("name") or ""
                value = p.get("value") or p.get("display_value") or ""
                if label and value:
                    params_parts.append(f"{label}: {value}")
                    if "год" in label.lower() or "year" in label.lower():
                        import re
                        m = re.search(r"(19|20)\d{2}", str(value))
                        if m:
                            year = int(m.group(0))
            out.append({
                "id": str(ad_id) if ad_id else url,
                "title": str(title),
                "year": year,
                "price": int(price) if price else None,
                "currency": currency,
                "url": url,
                "params": ", ".join(params_parts),
            })
        except Exception:
            continue
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