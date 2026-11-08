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
MAX_RESULTS = 100

LEGEND = (
    "ниже рынка 30%+ / ниже 10%+ / рынок (+-10%) / "
    "выше 10%+ / выше 30%+"
)


def _fmt(price, currency="BYN"):
    if not price:
        return "-"
    return f"{price:,}".replace(",", " ") + f" {currency}"


def _price_badge(price, median):
    if not price or not median:
        return "[ ]"
    ratio = price / median
    if ratio <= 0.7:
        return "💚"
    if ratio <= 0.9:
        return "🟢"
    if ratio <= 1.1:
        return "⚪"
    if ratio <= 1.3:
        return "🟠"
    return "🔴"


def _escape(s):
    return (s or "").replace("<", "&lt;").replace(">", "&gt;")


def _render_item(r, median):
    badge = _price_badge(r.get("price"), median)
    title = _escape(r["title"])
    price = _fmt(r.get("price"), r.get("currency", "BYN"))
    year = r.get("year") or "-"
    params = (r.get("params") or "").strip()

    lines = [f"{badge} <b>{price}</b> | {title} | {year}"]
    if params and params != str(year):
        lines.append(f"<i>{_escape(params)}</i>")
    lines.append(f'<a href="{r["url"]}">→ Открыть на av.by</a>')
    return "\n".join(lines)

def _build_header(sub, page_items, total, offset, page, median):
    crit = []
    if sub.brand:
        crit.append(sub.brand)
    if sub.model:
        crit.append(sub.model)
    if sub.year_from or sub.year_to:
        crit.append(f"{sub.year_from or '...'} - {sub.year_to or '...'}")

    start = offset + 1
    end = offset + len(page_items)
    lines = [
        f"🔍 Найдено {total} · стр. {page} ({start}–{end})",
        f"Критерии: <i>{_escape(' '.join(crit)) or '-'}</i>",
    ]
    if median:
        lines.append(f"Медиана: <b>{_fmt(int(median))}</b>")
    lines.append(f"<i>Цвет: {LEGEND}</i>")
    return "\n".join(lines)


def _build_body(items, median):
    SEP = "\n\n"
    return SEP.join(_render_item(r, median) for r in items)


def _build_kb(sub_id, page, offset, total, has_more):
    rows = []
    if has_more:
        next_offset = offset + PAGE_SIZE
        rows.append([InlineKeyboardButton(
            text=f"🔽 Ещё {PAGE_SIZE} (стр. {page + 1})",
            callback_data=f"subs:find:{sub_id}:{next_offset}",
        )])
    else:
        rows.append([InlineKeyboardButton(
            text=f"✅ Это все ({total})",
            callback_data="subs:noop",
        )])
    rows.append([InlineKeyboardButton(
        text="← К подписке", callback_data=f"subs:back:{sub_id}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _run_search(cb, sub_id, offset):
    sub = await get_subscription(sub_id)
    if sub is None:
        await cb.answer("Подписка не найдена", show_alert=True)
        return

    if cb.message is not None:
        try:
            await cb.message.edit_text("🔍 Ищу на av.by…")
        except TelegramBadRequest:
            pass

    brand_id = BRAND_IDS.get(sub.brand) if sub.brand else None
    model_id = None
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
        all_results = await search(criteria, limit=MAX_RESULTS)
    except Exception as e:
        if cb.message is not None:
            try:
                await cb.message.edit_text(
                    f"Ошибка поиска: {_escape(str(e))}",
                    reply_markup=_build_kb(sub_id, 1, 0, 0, False),
                )
            except TelegramBadRequest:
                pass
        return

    if not all_results:
        txt = "Ничего не найдено."
        if not brand_id:
            txt += " Марка вручную - попробуй редактирование марки из списка."
        if cb.message is not None:
            try:
                await cb.message.edit_text(txt, reply_markup=_build_kb(sub_id, 1, 0, 0, False))
            except TelegramBadRequest:
                pass
        return

    total = len(all_results)
    page_items = all_results[offset:offset + PAGE_SIZE]
    if not page_items:
        await cb.answer("Больше нет")
        return

    prices = [r["price"] for r in all_results if r.get("price")]
    median = statistics.median(prices) if prices else None

    page = offset // PAGE_SIZE + 1
    has_more = (offset + PAGE_SIZE) < total
    header = _build_header(sub, page_items, total, offset, page, median)
    body = _build_body(page_items, median)
    text = header + "\n\n" + body

    if len(text) > 4000:
        text = text[:3990] + "\n\n<i>(усечено, жми Ещё)</i>"

    try:
        await mark_checked(sub_id, [r["id"] for r in page_items])
    except Exception:
        pass

    if cb.message is not None:
        try:
            await cb.message.edit_text(
                text,
                reply_markup=_build_kb(sub_id, page, offset, total, has_more),
                disable_web_page_preview=True,
            )
        except TelegramBadRequest:
            pass


@router.callback_query(F.data.startswith("subs:find:"))
async def on_find(cb):
    parts = cb.data.split(":")
    if len(parts) < 3 or not parts[2].isdigit():
        await cb.answer()
        return
    sub_id = int(parts[2])
    offset = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
    await cb.answer("🔍 Ищу...")
    await _run_search(cb, sub_id, offset)


@router.callback_query(F.data == "subs:noop")
async def on_noop(cb):
    await cb.answer("Это все объявления")