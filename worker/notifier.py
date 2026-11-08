from __future__ import annotations

import logging
import statistics

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

log = logging.getLogger(__name__)


def _fmt(price: int | None, currency: str = "BYN") -> str:
    if not price:
        return "—"
    return f"{price:,}".replace(",", " ") + f" {currency}"


def _badge(price: int | None, median: float | None) -> str:
    if not price or not median:
        return "⚪"
    r = price / median
    if r <= 0.7:
        return "💚"
    if r <= 0.9:
        return "🟢"
    if r <= 1.1:
        return "⚪"
    if r <= 1.3:
        return "🟠"
    return "🔴"


def _escape(s: str) -> str:
    return (s or "").replace("<", "&lt;").replace(">", "&gt;")


def build_message(sub, new_items: list[dict], all_items: list[dict]) -> str:
    prices = [r["price"] for r in all_items if r.get("price")]
    median = statistics.median(prices) if prices else None

    crit = []
    if sub.brand:
        crit.append(sub.brand)
    if sub.model:
        crit.append(sub.model)
    if sub.year_from or sub.year_to:
        crit.append(f"{sub.year_from or '...'}–{sub.year_to or '...'}")
    if sub.price_from or sub.price_to:
        crit.append(f"${sub.price_from or '...'}–${sub.price_to or '...'}")

    lines = [
        f"🔔 <b>Новые объявления по подписке #{sub.id}</b>",
        f"<i>{_escape(' '.join(crit)) or '—'}</i>",
    ]
    if median:
        lines.append(f"Медиана: <b>{_fmt(int(median))}</b>")
    lines.append("")

    for r in new_items:
        b = _badge(r.get("price"), median)
        title = _escape(r["title"])
        price = _fmt(r.get("price"), r.get("currency", "BYN"))
        year = r.get("year") or "—"
        lines.append(f"{b} <b>{price}</b> · {title} · {year}")
        params = (r.get("params") or "").strip()
        if params and params != str(year):
            lines.append(f"<i>{_escape(params)}</i>")
        lines.append(f'<a href="{r["url"]}">→ Открыть</a>')
        lines.append("")
    return "\n".join(lines).rstrip()


async def send_new(bot: Bot, chat_id: int, sub, new_items: list[dict], all_items: list[dict]) -> None:
    if not new_items:
        return
    text = build_message(sub, new_items, all_items)
    if len(text) > 4000:
        text = text[:3990] + "\n\n<i>(усечено)</i>"
    try:
        await bot.send_message(
            chat_id,
            text,
            disable_web_page_preview=True,
        )
    except TelegramBadRequest as e:
        log.warning("send_new fail chat=%s sub=%s: %s", chat_id, sub.id, e)