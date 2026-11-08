from __future__ import annotations

import statistics

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.data.cars_full import BRAND_IDS, MODEL_IDS
from app.db.repositories.subscriptions import get_subscription, mark_checked
from app.services.parsers.avby import search

router = Router(name="subs_find")

PAGE_SIZE = 15


def _fmt_price(p) -> str:
    if not p:
        return "—"
    return f"${p:,}".replace(",", " ")


def _price_badge(price: int | None, median: float | None) -> str:
    if not price or not median:
        return "⚪"
    ratio = price / median
    if ratio <= 0.7:
        return "💚"  # сильно ниже рынка
    if ratio <= 0.9:
        return "🟢"  # ниже рынка
    if ratio <= 1.1:
        return "⚪"  # рынок
    if ratio <= 1.3:
        return "🟠"  # выше рынка
    return "🔴"  # сильно выше


def _escape(s: str) -> str:
    return (s or "").replace("<", "&lt;").replace(">", "&gt;")


def _build_message(sub, results: list[dict], page: int, has_more: bool) -> str:
    prices = [r["price_usd"] for r in results if r.get("price_usd") and r["price_usd"] > 0]
    median = statistics.median(prices) if prices else None

    crit: list[str] = []
    if sub.brand:
        crit.append(sub.brand)
    if sub.model:
        crit.append(sub.model)
    if sub.year_from or sub.year_to:
        crit.append(f"{sub.year_from or '...'}–{sub.year_to or '...'}")
    if sub.price_from or sub.price_to:
        crit.append(f"${sub.price_from or '...'}–${sub.price_to or '...'}")

    lines = [
        f"🔍 <b>Стр. {page}</b> · {len(results)} объявлений",
        f"Критерии: <i>{_escape(' '.join(crit)) or '—'}</i>",
    ]
    if median:
        lines.append(f"Медиана: <b>{_fmt_price(int(median))}</b> (💚 ниже · 🔴 выше)")
    lines.append("")

    for r in results:
        badge = _price_badge(r.get("price_usd"), median)
        title = _escape(r["title"])
        price = _fmt_price(r.get("price_usd"))
        year = r.get("year") or "—"
        head = f"{badge} <b>{price}</b> · {title} · {year}"
        lines.append(head)
        params = (r.get("params") or "").strip()
        if params and params != str(year):
            lines.append(f"   <i>{_escape(params)}</i>")
        lines.append(f"   <a href=\"{r['url']}\">→ Открыть на av.by</a>")

    if has_more:
        lines += ["", "💡 Есть ещё — жми «Показать ещё»."]
    return "\n".join(lines)


def _build_kb(sub_id: int, page: int, has_more: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_more:
        rows.append([InlineKeyboardButton(
            text=f"🔽 Показать ещё (стр. {page + 1})",
            callback_data=f"subs:find:{sub_id}:{page + 1}",
        )])
    rows.append([InlineKeyboardButton(text="← К подписке", callback_data=f"subs:back:{sub_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _run_search(cb: CallbackQuery, sub_id: int, page: int) -> None:
    sub = await get_subscription(sub_id)
    if sub is None:
        await cb.answer("Подписка не найдена", show_alert=True)
        return

    if cb.message is not None:
        try:
            await cb.message.edit_text(f"🔍 <b>Ищу на av.by… (стр. {page})</b>")
        except TelegramBadRequest:
            pass

    brand_id = BRAND_IDS.get(sub.brand) if sub.brand else None
    model_id: int | None = None
    if brand_id and sub.model:
        model_id = (MODEL_IDS.get(sub.brand) or {}).get(sub.model)

    criteria = {
        "brand_id": brand_id,
        "model_id": model_id,
        "year_from": sub.year_from,
        "year_to": sub.year_to,
        "price_from": sub.price_from,
        "price_to": sub.price_to,
        "query": None,
    }
    if not brand_id:
        q = " ".join(x for x in [sub.brand, sub.model] if x).strip()
        criteria["query"] = q or None

    try:
        results = await search(criteria, limit=PAGE_SIZE, page=page)
    except Exception as e:
        if cb.message is not None:
            try:
                await cb.message.edit_text(
                    f"❌ Ошибка поиска: {_escape(str(e))}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="← К подписке", callback_data=f"subs:back:{sub_id}"),
                    ]]),
                )
            except TelegramBadRequest:
                pass
        return

    if not results:
        txt = f"😔 <b>Стр. {page}: ничего не найдено</b>.\n\n"
        if not brand_id:
            txt += "💡 Марка вручную — попробуй ✏️ Марка из списка для точного ID."
        if cb.message is not None:
            try:
                await cb.message.edit_text(txt, reply_markup=_build_kb(sub_id, page, False))
            except TelegramBadRequest:
                pass
        return

    try:
        await mark_checked(sub_id, [r["id"] for r in results])
    except Exception:
        pass

    has_more = len(results) >= PAGE_SIZE
    text = _build_message(sub, results, page, has_more)

    if cb.message is not None:
        try:
            await cb.message.edit_text(
                text, reply_markup=_build_kb(sub_id, page, has_more),
                disable_web_page_preview=True,
            )
        except TelegramBadRequest:
            pass


@router.callback_query(F.data.startswith("subs:find:"))
async def on_find(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    if len(parts) < 3 or not parts[2].isdigit():
        await cb.answer()
        return
    sub_id = int(parts[2])
    page = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 1
    await cb.answer("🔍 Ищу...")
    await _run_search(cb, sub_id, page)