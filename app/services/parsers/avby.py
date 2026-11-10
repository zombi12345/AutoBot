from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

log = logging.getLogger(__name__)

AVBY_API = "https://api.av.by"
AVBY_WEB = "https://workers-playground-patient-cherry-83db.asasinjan2006.workers.dev"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Origin": "https://workers-playground-patient-cherry-83db.asasinjan2006.workers.dev",
    "Referer": "https://workers-playground-patient-cherry-83db.asasinjan2006.workers.dev/",
}

API_ENDPOINTS = (
    "{api}/filtering/cars?page=1&page_size={n}",
    "{api}/offers/cars/search?page=1&per_page={n}",
)

MAX_TOTAL = 100
MAX_PAGES = 5


_FUEL_RU = {
    "gasoline": ["бензин", "petrol", "gasoline"],
    "diesel": ["дизель", "diesel"],
    "hybrid": ["гибрид", "hybrid"],
    "electric": ["электро", "electric", "ev"],
    "gas": ["газ", "lpg"],
}
_TRANS_RU = {
    "automatic": ["автомат", "акпп", "automatic", "at"],
    "manual": ["механика", "мкпп", "manual", "mt"],
    "variator": ["вариатор", "cvt"],
    "robot": ["робот", "dsg", "robot"],
}


USD_TO_BYN = 3.27


def _apply_postfilter(items: list[dict], criteria: dict) -> list[dict]:
    if not criteria:
        return items
    fuel = criteria.get("fuel_type")
    trans = criteria.get("transmission")
    mil = criteria.get("mileage_to")
    p_from = criteria.get("price_from")
    p_to = criteria.get("price_to")
    cc_from = criteria.get("engine_cc_from")
    cc_to = criteria.get("engine_cc_to")

    p_from_byn = int(p_from * USD_TO_BYN) if p_from else None
    p_to_byn = int(p_to * USD_TO_BYN) if p_to else None

    out = []
    for r in items:
        params = (r.get("params") or "").lower()
        price = r.get("price")
        if fuel:
            keys = _FUEL_RU.get(fuel, [fuel])
            if not any(k in params for k in keys):
                continue
        if trans:
            keys = _TRANS_RU.get(trans, [trans])
            if not any(k in params for k in keys):
                continue
        if mil:
            import re as _re
            m = _re.search(r"(\d[\d\s]{2,})\s*км", params)
            if m:
                try:
                    val = int(_re.sub(r"\D", "", m.group(1)))
                    if val > mil:
                        continue
                except Exception:
                    pass
        if price and p_from_byn and price < p_from_byn:
            continue
        if price and p_to_byn and price > p_to_byn:
            continue
        if cc_from or cc_to:
            import re as _re
            m = _re.search(r"(\d[.,]\d)\s*л", params)
            if m:
                try:
                    cc = int(float(m.group(1).replace(",", ".")) * 1000)
                    if cc_from and cc < cc_from:
                        continue
                    if cc_to and cc > cc_to:
                        continue
                except Exception:
                    pass
        out.append(r)
    return out


def _resolve_ids(criteria: dict) -> dict:
    """Если brand/model пришли строками — ищем id через справочник."""
    from app.data.cars_full import BRANDS, BRAND_IDS, MODEL_IDS
    out = dict(criteria)
    brand = out.get("brand")
    if brand and not out.get("brand_id"):
        if brand in BRAND_IDS:
            out["brand_id"] = BRAND_IDS[brand]
        else:
            from app.utils.fuzzy import find_brand
            canon, _ = find_brand(brand, list(BRAND_IDS.keys()))
            if canon:
                out["brand_id"] = BRAND_IDS[canon]
                out["brand"] = canon
    brand = out.get("brand")
    model = out.get("model")
    if model and not out.get("model_id") and brand and brand in MODEL_IDS:
        mids = MODEL_IDS[brand]
        if model in mids:
            out["model_id"] = mids[model]
        else:
            from app.utils.fuzzy import find_model
            canon, _ = find_model(model, list(mids.keys()))
            if canon:
                out["model_id"] = mids[canon]
                out["model"] = canon
    return out


async def search(criteria: dict[str, Any], limit: int = MAX_TOTAL) -> list[dict]:
    criteria = _resolve_ids(criteria)
    """Ищет объявления на av.by. Собирает с нескольких страниц HTML."""
    body = _build_body(criteria)

    # 1) API (может 404 — ок)
    for tmpl in API_ENDPOINTS:
        url = tmpl.format(api=AVBY_API, n=limit)
        data = await _post_api(url, body)
        if data is not None:
            results = _parse_api(data, limit)
            if results:
                log.info("avby: API OK, %d results", len(results))
                return results

    # 2) HTML: обход страниц
    out: list[dict] = []
    seen_ids: set[str] = set()
    pages_tried = 0
    async with AsyncSession(impersonate="chrome124", headers=HEADERS, timeout=25) as s:
        for page in range(1, MAX_PAGES + 1):
            if len(out) >= limit:
                break
            html_url = _build_html_url(criteria, page=page)
            html = await _get_html(s, html_url)
            if not html:
                break
            pages_tried += 1
            page_items = _parse_html(html, limit - len(out))
            if not page_items:
                break
            new_items = [r for r in page_items if r["id"] not in seen_ids]
            if not new_items:
                break
            for r in new_items:
                seen_ids.add(r["id"])
                out.append(r)
            log.info("avby: page %s → %d new (total %d)", page, len(new_items), len(out))

    if out:
        before = len(out)
        out = _apply_postfilter(out, criteria)
        log.info("avby: HTML fallback OK, %d results from %d pages (postfilter: %d -> %d)", before, pages_tried, before, len(out))
    else:
        log.info("avby: no results for %s", body)
    return out


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
    # D-15: расширенные фильтры
    if criteria.get("fuel_type"):
        body["fuel"] = [str(criteria["fuel_type"])]
    if criteria.get("transmission"):
        body["transmission"] = [str(criteria["transmission"])]
    mileage: dict[str, int] = {}
    if criteria.get("mileage_to"):
        mileage["to"] = int(criteria["mileage_to"])
    if mileage:
        body["mileage"] = mileage
    engine: dict[str, int] = {}
    if criteria.get("engine_cc_from"):
        engine["from"] = int(criteria["engine_cc_from"])
    if criteria.get("engine_cc_to"):
        engine["to"] = int(criteria["engine_cc_to"])
    if engine:
        body["engine_cc"] = engine
    if criteria.get("query"):
        body["query"] = str(criteria["query"])
    return body


def _build_html_url(criteria: dict, page: int = 1) -> str:
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
    if criteria.get("fuel_type"):
        params.append(("fuel[0]", str(criteria["fuel_type"])))
    if criteria.get("transmission"):
        params.append(("transmission[0]", str(criteria["transmission"])))
    if criteria.get("mileage_to"):
        params.append(("mileage[max]", int(criteria["mileage_to"])))
    if criteria.get("engine_cc_from"):
        params.append(("engine_cc[min]", int(criteria["engine_cc_from"])))
    if criteria.get("engine_cc_to"):
        params.append(("engine_cc[max]", int(criteria["engine_cc_to"])))
    if not params and criteria.get("query"):
        params.append(("query", str(criteria["query"])))
    if page > 1:
        params.append(("page", page))
    return f"{AVBY_WEB}/filter?{urlencode(params)}"


async def _post_api(url: str, body: dict) -> dict | None:
    try:
        async with AsyncSession(impersonate="chrome124", headers=HEADERS, timeout=20) as s:
            r = await s.post(url, json=body)
            if r.status_code != 200:
                return None
            try:
                return r.json()
            except Exception:
                return None
    except Exception as e:
        log.warning("avby API curl_cffi fail: %s", e)
        return None


async def _get_html(session: AsyncSession, url: str) -> str | None:
    try:
        r = await session.get(url)
        if r.status_code not in (200, 468):
            log.warning("avby HTML %s: %s", r.status_code, url)
            return None
        return r.text
    except Exception as e:
        log.warning("avby HTML curl_cffi fail: %s", e)
        return None


def _parse_api(data: dict, limit: int) -> list[dict]:
    if not isinstance(data, dict):
        return []
    items = (data.get("adverts") or data.get("offers")
             or data.get("items") or data.get("results") or [])
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
            price_byn = None
            currency = "BYN"
            if isinstance(ad.get("price"), dict):
                p_usd = (ad["price"].get("usd") or {}).get("amount")
                p_byn = (ad["price"].get("byn") or {}).get("amount")
                if p_byn:
                    price_byn = p_byn
                elif p_usd:
                    price_byn = int(p_usd * 3.27)
                    currency = "USD"
            url = ad.get("publicUrl") or ad.get("url")
            if not url and ad_id:
                url = f"https://workers-playground-patient-cherry-83db.asasinjan2006.workers.dev/{ad_id}"
            if not url:
                continue
            out.append({
                "id": str(ad_id) if ad_id else url,
                "title": str(title),
                "year": year,
                "price": price_byn,
                "currency": currency,
                "url": url,
                "params": "",
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


_PRICE_SELECTORS = (
    ".listing-item__priceusd",
    ".listing-item__price-primary",
    ".listing-item__price",
    ".listing-item__prices",
    "[class*='priceusd']",
    "[class*='price-primary']",
)
_TITLE_SELECTORS = (
    ".listing-item__title-text",
    ".listing-item__link-text",
    ".listing-item__title",
)
_ITEM_SELECTOR = "div.listing-item, .listing-item"


def _parse_html(html: str, limit: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(_ITEM_SELECTOR)
    out: list[dict] = []

    for card in cards:
        if len(out) >= limit:
            break
        try:
            link_el = card.select_one("a.listing-item__link, a[href*='/']")
            if not link_el:
                continue
            url = link_el.get("href") or ""
            if url.startswith("/"):
                url = AVBY_WEB + url
            if not url.startswith("http"):
                continue

            title = "—"
            for sel in _TITLE_SELECTORS:
                el = card.select_one(sel)
                if el:
                    t = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
                    if t:
                        title = t
                        break

            year = None
            params_text = ""
            params_el = card.select_one(".listing-item__params")
            if params_el:
                params_text = re.sub(r"\s+", " ", params_el.get_text(" ", strip=True)).strip()
                m = re.search(r"(19|20)\d{2}", params_text)
                if m:
                    year = int(m.group(0))

            price_byn = None
            currency = "BYN"
            for sel in _PRICE_SELECTORS:
                el = card.select_one(sel)
                if not el:
                    continue
                text = el.get_text(" ", strip=True)
                if not text:
                    continue
                low = text.lower()
                if "usd" in low or "$" in text:
                    currency = "USD"
                digits = re.sub(r"[^\d]", "", text)
                if digits and len(digits) >= 3:
                    try:
                        price_byn = int(digits)
                        break
                    except ValueError:
                        continue

            ad_id = url.rstrip("/").split("/")[-1] or url
            out.append({
                "id": ad_id,
                "title": title,
                "year": year,
                "price": price_byn,
                "currency": currency,
                "url": url,
                "params": params_text,
            })
        except Exception:
            continue
    return out