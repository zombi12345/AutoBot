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


def _median_for_year(year: int | None, all_items: list[dict]) -> float | None:
    """Медиана по объявлениям в окне ±1 год от target, иначе ±2, иначе все."""
    if not year:
        prices = [r["price"] for r in all_items if r.get("price")]
        return statistics.median(prices) if prices else None

    with_year = [r for r in all_items if r.get("year") and r.get("price")]
    if not with_year:
        prices = [r["price"] for r in all_items if r.get("price")]
        return statistics.median(prices) if prices else None

    for delta in (1, 2, 3):
        group = [r["price"] for r in with_year if abs(int(r["year"]) - int(year)) <= delta]
        if len(group) >= 3:
            return statistics.median(group)

    # fallback: все цены
    all_prices = [r["price"] for r in all_items if r.get("price")]
    return statistics.median(all_prices) if all_prices else None


def _escape(s: str) -> str:
    return (s or "").replace("<", "&lt;").replace(">", "&gt;")


def build_message(sub, new_items: list[dict], all_items: list[dict]) -> str:
    overall_prices = [r["price"] for r in all_items if r.get("price")]
    overall_median = statistics.median(overall_prices) if overall_prices else None

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
    if overall_median:
        lines.append(f"Медиана (все годы): <b>{_fmt(int(overall_median))}</b>")
    lines.append("")

    for r in new_items:
        y_median = _median_for_year(r.get("year"), all_items)
        b = _badge(r.get("price"), y_median)
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