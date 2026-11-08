from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

log = logging.getLogger(__name__)

AVBY_API = "https://api.av.by"
AVBY_WEB = "https://cars.av.by"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Origin": "https://cars.av.by",
    "Referer": "https://cars.av.by/",
}

API_ENDPOINTS = (
    "{api}/filtering/cars?page=1&page_size={n}",
    "{api}/offers/cars/search?page=1&per_page={n}",
    "{api}/cars/search?page=1&per_page={n}",
)


async def search(criteria: dict[str, Any], limit: int = 5) -> list[dict]:
    body = _build_body(criteria)

    # 1) API через curl_cffi (обход Cloudflare TLS fingerprint)
    for tmpl in API_ENDPOINTS:
        url = tmpl.format(api=AVBY_API, n=limit)
        data = await _post_api(url, body)
        if data is not None:
            results = _parse_api(data, limit)
            if results:
                log.info("avby: curl_cffi OK, %d results from %s", len(results), url)
                return results

    # 2) HTML fallback (cars.av.by/filter)
    log.info("avby: API failed → HTML fallback")
    html_url = _build_html_url(criteria)
    html = await _get_html(html_url)
    if html:
        results = _parse_html(html, limit)
        if results:
            log.info("avby: HTML fallback OK, %d results", len(results))
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


def _build_html_url(criteria: dict) -> str:
    params: list[tuple[str, str | int]] = []
    if criteria.get("brand_id"):
        params.append(("brands[0][brand]", int(criteria["brand_id"])))
    if criteria.get("model_id"):
        params.append(("brands[0][model]", int(criteria["model_id"])))
    if criteria.get("year_from"):
        params.append(("year[min]", int(criteria["year_from"])))
    if criteria.get("year_to"):
        params.append(("year[max]", int(criteria["year_to"])))
    if criteria.get("price_from"):
        params.append(("price[min]", int(criteria["price_from"])))
    if criteria.get("price_to"):
        params.append(("price[max]", int(criteria["price_to"])))
    if not params and criteria.get("query"):
        params.append(("query", str(criteria["query"])))
    return f"{AVBY_WEB}/filter?{urlencode(params)}"


async def _post_api(url: str, body: dict) -> dict | None:
    try:
        async with AsyncSession(impersonate="chrome124", headers=HEADERS, timeout=20) as s:
            r = await s.post(url, json=body)
            if r.status_code != 200:
                log.warning("avby API %s: %s", r.status_code, url)
                return None
            try:
                return r.json()
            except Exception as e:
                log.warning("avby API json fail: %s", e)
                return None
    except Exception as e:
        log.warning("avby API curl_cffi fail: %s", e)
        return None


async def _get_html(url: str) -> str | None:
    try:
        async with AsyncSession(impersonate="chrome124", headers=HEADERS, timeout=20) as s:
            r = await s.get(url)
            if r.status_code != 200:
                log.warning("avby HTML %s: %s", r.status_code, url)
                return None
            return r.text
    except Exception as e:
        log.warning("avby HTML curl_cffi fail: %s", e)
        return None


def _parse_api(data: dict, limit: int) -> list[dict]:
    if not isinstance(data, dict):
        return []
    items = (
        data.get("adverts") or data.get("offers")
        or data.get("items") or data.get("results") or []
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


_ITEM_SELECTOR = "div.listing-item, .listing-item"


def _parse_html(html: str, limit: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(_ITEM_SELECTOR)
    out: list[dict] = []
    for card in cards[:limit]:
        try:
            link_el = card.select_one("a.listing-item__link, a[href*='/']")
            if not link_el:
                continue
            url = link_el.get("href") or ""
            if url.startswith("/"):
                url = AVBY_WEB + url
            if not url.startswith("http"):
                continue

            title_el = card.select_one(".listing-item__title, .listing-item__link-text")
            title = title_el.get_text(strip=True) if title_el else "—"

            year = None
            params_el = card.select_one(".listing-item__params")
            if params_el:
                m = re.search(r"(19|20)\d{2}", params_el.get_text(" ", strip=True))
                if m:
                    year = int(m.group(0))

            price_usd = None
            price_el = card.select_one(".listing-item__priceusd, .listing-item__price")
            if price_el:
                digits = re.sub(r"\D", "", price_el.get_text())
                if digits:
                    price_usd = int(digits)

            ad_id = url.rstrip("/").split("/")[-1] or url
            out.append({
                "id": ad_id,
                "title": title,
                "year": year,
                "price_usd": price_usd,
                "url": url,
            })
        except Exception:
            continue
    return out