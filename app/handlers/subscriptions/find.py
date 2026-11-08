from __future__ import annotations

import statistics

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.data.cars_full import BRAND_IDS, MODEL_IDS
from app.db.repositories.subscriptions import get_subscription, mark_checked
from app.services.parsers.avby import search

router = Router(name="subs_find")

MAX_RESULTS = 100
CHUNK_LIMIT = 3500  # Telegram safe (hard limit 4096)

LEGEND = (
    "💚 ниже рынка на 30%+ · 🟢 ниже на 10%+ · ⚪ рынок (±10%) · "
    "🟠 выше на 10%+ · 🔴 выше на 30%+"
)


def _fmt(price: int | None, currency: str = "BYN") -> str:
    if not price:
        return "—"
    return f"{price:,}".replace(",", " ") + f" {currency}"


def _price_badge(price: int | None, median: float | None) -> str:
    if not price or not median:
        return "⚪"
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


def _escape(s: str) -> str:
    return (s or "").replace("<", "&lt;").replace(">", "&gt;")


def _render_item(r: dict, median: float | None) -> str:
    """Одно объявление. Пустая строка между объявлениями — в склейке."""
    badge = _price_badge(r.get("price"), median)
    title = _escape(r["title"])
    price = _fmt(r.get("price"), r.get("currency", "BYN"))
    year = r.get("year") or "—"
    params = (r.get("params") or "").strip()

    lines = [f"{badge} <b>{price}</b> · {title} · {year}"]
    if params and params != str(year):
        lines.append(f"<i>{_escape(params)}</i>")
    lines.append(f'<a href="{r["url"]}">→ Открыть на av.by</a>')
    return "\n".join(lines)


def _build_header(sub, total: int, median: float | None) -> str:
    crit: list[str] = []
    if sub.brand:
        crit.append(sub.brand)
    if sub.model:
        crit.append(sub.model)
    if sub.year_from or sub.year_to:
        crit.append(f"{sub.year_from or '...'}–{sub.year_to or '...'}")
    if sub.price_from or sub.price_to:
        crit.append(f"${sub.price_from or '...'}–${sub.price_to or '...'} (фильтр)")

    lines = [
        f"🔍 <b>Найдено {total} объявлений</b>",
        f"Критерии: <i>{_escape(' '.join(crit)) or '—'}</i>",
    ]
    if median:
        lines.append(f"Медиана: <b>{_fmt(int(median))}</b>")
    lines.append(f"<i>{LEGEND}</i>")
    return "\n".join(lines)


def _split_into_chunks(header: str, items: list[dict], median: float | None) -> list[str]:
    """Разбивает на сообщения ≤ CHUNK_LIMIT. Каждое объявление отделено пустой строкой."""
    rendered = [_render_item(r, median) for r in items]
    # разделитель между объявлениями: два \n (пустая строка)
    SEP = "\n\n"

    chunks: list[str] = []
    current = header
    for rendered_item in rendered:
        candidate = current + SEP + rendered_item if current else rendered_item
        if len(candidate) > CHUNK_LIMIT:
            if current:
                chunks.append(current)
            current = rendered_item
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _build_kb(sub_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="← К подписке", callback_data=f"subs:back:{sub_id}"),
    ]])


async def _run_search(cb: CallbackQuery, sub_id: int) -> None:
    sub = await get_subscription(sub_id)
    if sub is None:
        await cb.answer("Подписка не найдена", show_alert=True)
        return

    if cb.message is not None:
        try:
            await cb.message.edit_text("🔍 <b>Ищу все объявления на av.by…</b>")
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
        results = await search(criteria, limit=MAX_RESULTS)
    except Exception as e:
        if cb.message is not None:
            try:
                await cb.message.edit_text(
                    f"❌ Ошибка поиска: {_escape(str(e))}",
                    reply_markup=_build_kb(sub_id),
                )
            except TelegramBadRequest:
                pass
        return

    if not results:
        txt = "😔 <b>Ничего не найдено.</b>\n\n"
        if not brand_id:
            txt += "💡 Марка вручную — попробуй ✏️ Марка из списка."
        if cb.message is not None:
            try:
                await cb.message.edit_text(txt, reply_markup=_build_kb(sub_id))
            except TelegramBadRequest:
                pass
        return

    try:
        await mark_checked(sub_id, [r["id"] for r in results])
    except Exception:
        pass

    prices = [r["price"] for r in results if r.get("price")]
    median = statistics.median(prices) if prices else None

    header = _build_header(sub, len(results), median)
    chunks = _split_into_chunks(header, results, median)

    if cb.message is not None:
        # первое сообщение — редактируем старое, остальные — send_message
        try:
            await cb.message.edit_text(
                chunks[0],
                reply_markup=_build_kb(sub_id) if len(chunks) == 1 else None,
                disable_web_page_preview=True,
            )
        except TelegramBadRequest:
            pass
        for i, chunk in enumerate(chunks[1:], start=2):
            is_last = i == len(chunks)
            try:
                await cb.message.answer(
                    chunk,
                    reply_markup=_build_kb(sub_id) if is_last else None,
                    disable_web_page_preview=True,
                )
            except TelegramBadRequest:
                pass
        if len(chunks) > 1:
            try:
                await cb.message.answer(
                    f"<i>Показано {len(results)} из {len(results)} · "
                    f"разбито на {len(chunks)} сообщений.</i>",
                    reply_markup=_build_kb(sub_id),
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
    await cb.answer("🔍 Ищу...")
    await _run_search(cb, sub_id)