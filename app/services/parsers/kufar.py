from __future__ import annotations

import logging
import re
from typing import Any

from curl_cffi.requests import AsyncSession

log = logging.getLogger(__name__)

KUFAR_API = "https://api.kufar.by/search-api/v2/search"
KUFAR_WEB = "https://auto.kufar.by"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Origin": "https://auto.kufar.by",
    "Referer": "https://auto.kufar.by/",
}

# Категория "Легковые автомобили" на Kufar
CAR_CATEGORY = "2010"


async def search(criteria: dict[str, Any], limit: int = 50) -> list[dict]:
    """Async-поиск на Kufar через внутренний JSON API.

    criteria: brand, model, year_from, year_to, price_from (USD), price_to (USD),
              fuel_type, transmission, mileage_to
    Returns: [{id, title, year, price (BYN), currency, url, params}]
    """
    # Kufar принимает query как текст. brand+model -> query
    q_parts: list[str] = []
    if criteria.get("brand"):
        q_parts.append(str(criteria["brand"]))
    if criteria.get("model"):
        q_parts.append(str(criteria["model"]))
    query = " ".join(q_parts).strip()

    # price в BYN (Kufar принимает BYN). USD -> BYN * 3.27
    price_from_byn = int(criteria["price_from"] * 3.27) if criteria.get("price_from") else None
    price_to_byn = int(criteria["price_to"] * 3.27) if criteria.get("price_to") else None

    params = {
        "cat": CAR_CATEGORY,
        "size": min(200, max(1, limit)),
        "sort": "lst.d",  # дата (новые)
        "lang": "ru",
    }
    if query:
        params["query"] = query
    if price_from_byn:
        params["prc"] = f"r:{price_from_byn},100000000000"
    if price_to_byn and not price_from_byn:
        params["prc"] = f"r:0,{price_to_byn}"
    elif price_from_byn and price_to_byn:
        params["prc"] = f"r:{price_from_byn},{price_to_byn}"

    try:
        async with AsyncSession(impersonate="chrome124", headers=HEADERS, timeout=25) as s:
            r = await s.get(KUFAR_API, params=params)
            if r.status_code != 200:
                log.warning("kufar HTTP %s", r.status_code)
                return []
            data = r.json()
    except Exception as e:
        log.warning("kufar request fail: %s", e)
        return []

    items = _parse(data, limit)
    if criteria.get("year_from") or criteria.get("year_to") or criteria.get("mileage_to"):
        items = _postfilter(items, criteria)
    log.info("kufar: %d results (query=%r)", len(items), query)
    return items


def _parse(data: dict, limit: int) -> list[dict]:
    if not isinstance(data, dict):
        return []
    ads = data.get("ads") or data.get("items") or []
    if not isinstance(ads, list):
        return []
    out: list[dict] = []
    for ad in ads[:limit]:
        try:
            if not isinstance(ad, dict):
                continue
            ad_id = ad.get("ad_id") or ad.get("id")
            title = ad.get("subject") or ad.get("title") or "—"

            # параметры: год, двигатель, КПП, пробег
            params_text = ""
            year = None
            body = ad.get("body") or {}
            # ad["params"] или ad["body"]["params"]
            ad_params = ad.get("params") or body.get("params") or []
            parts: list[str] = []
            for p in ad_params:
                if isinstance(p, dict):
                    label = p.get("label") or ""
                    value = p.get("value") or ""
                    if label and value:
                        parts.append(f"{label}: {value}")
                        if "год" in label.lower() or "year" in label.lower():
                            m = re.search(r"(19|20)\d{2}", str(value))
                            if m:
                                year = int(m.group(0))
            params_text = ", ".join(parts)

            # цена
            price_byn = None
            currency = "BYN"
            price = ad.get("price_byn") or ad.get("price")
            if isinstance(price, dict):
                price_byn = price.get("amount") or price.get("value")
                currency = price.get("currency", "BYN")
            elif isinstance(price, (int, float)):
                price_byn = int(price)

            # url
            url = ad.get("ad_link") or ad.get("url")
            if not url and ad_id:
                url = f"{KUFAR_WEB}/item/{ad_id}"
            if not url:
                continue

            out.append({
                "id": str(ad_id) if ad_id else url,
                "title": str(title),
                "year": year,
                "price": price_byn,
                "currency": currency,
                "url": url,
                "params": params_text,
            })
        except Exception:
            continue
    return out


def _postfilter(items: list[dict], criteria: dict) -> list[dict]:
    yf = criteria.get("year_from")
    yt = criteria.get("year_to")
    mil = criteria.get("mileage_to")
    out = []
    for r in items:
        y = r.get("year")
        if yf and y and y < yf:
            continue
        if yt and y and y > yt:
            continue
        if mil:
            m = re.search(r"(\d[\d\s]{2,})\s*км", r.get("params") or "")
            if m:
                try:
                    if int(re.sub(r"\D", "", m.group(1))) > mil:
                        continue
                except Exception:
                    pass
        out.append(r)
    return out