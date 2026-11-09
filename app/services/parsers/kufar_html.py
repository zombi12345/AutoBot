"""Бесплатный HTML-парсер Kufar через curl_cffi."""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

log = logging.getLogger(__name__)

KUFAR_WEB = "https://auto.kufar.by"
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://auto.kufar.by/",
}
USD_TO_BYN = 3.27


async def search(criteria: dict[str, Any], limit: int = 50) -> list[dict]:
    q_parts = []
    if criteria.get("brand"):
        q_parts.append(str(criteria["brand"]))
    if criteria.get("model"):
        q_parts.append(str(criteria["model"]))
    query = " ".join(q_parts).strip()

    params: list[tuple[str, str | int]] = [
        ("cat", "2010"),  # Легковые авто
        ("size", min(200, max(1, limit))),
        ("sort", "lst.d"),
        ("lang", "ru"),
    ]
    if query:
        params.append(("query", query))
    if criteria.get("price_to"):
        params.append(("prc", f"r:0,{int(criteria['price_to'] * USD_TO_BYN)}"))

    url = f"{KUFAR_WEB}/l?"
    try:
        async with AsyncSession(impersonate="chrome124", headers=HEADERS, timeout=25) as s:
            r = await s.get(url, params=params)
            if r.status_code != 200:
                log.warning("kufar_html HTTP %s", r.status_code)
                return []
            html = r.text
    except Exception as e:
        log.warning("kufar_html fail: %s", e)
        return []

    items = _parse_html(html, limit)
    if criteria.get("year_from") or criteria.get("year_to"):
        items = _postfilter(items, criteria)
    log.info("kufar_html: %d results (query=%r)", len(items), query)
    return items


def _parse_html(html: str, limit: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    # Kufar использует <a> с href, содержащим /vi/ (объявление)
    cards = soup.select("a[href*='/vi/']")
    out: list[dict] = []
    seen = set()
    for card in cards:
        if len(out) >= limit:
            break
        try:
            href = card.get("href") or ""
            if not href.startswith("http"):
                href = KUFAR_WEB + href if href.startswith("/") else KUFAR_WEB + "/" + href
            if href in seen:
                continue
            seen.add(href)

            # id из URL
            m = re.search(r"/vi/(\d+)", href)
            ad_id = m.group(1) if m else href

            # title
            title_el = card.select_one("h3, [class*='title'], [class*='subject']")
            title = title_el.get_text(" ", strip=True) if title_el else "—"

            # price
            price = None
            price_el = card.select_one("[class*='price']")
            if price_el:
                text = price_el.get_text(" ", strip=True)
                digits = re.sub(r"[^\d]", "", text)
                if digits and len(digits) >= 3:
                    price = int(digits)

            # year: title -> все <span>/<div> внутри карточки -> params
            year = None
            ym = re.search(r"\b(19|20)\d{2}\b", title)
            if ym:
                year = int(ym.group(0))
            if year is None:
                # Kufar кладёт год в <span> или <div> рядом с ценой
                for el in card.select("span, div, p"):
                    txt = el.get_text(" ", strip=True)
                    ym2 = re.search(r"\b(19|20)\d{2}\b", txt)
                    if ym2 and len(txt) < 30:
                        year = int(ym2.group(0))
                        break

            out.append({
                "id": ad_id,
                "title": title,
                "year": year,
                "price": price,
                "currency": "BYN",
                "url": href,
                "params": title,
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