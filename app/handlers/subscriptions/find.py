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
    "💚 сильно ниже рынка (−30% и больше)\n"
    "🟢 ниже рынка (−10…−30%)\n"
    "⚪ рынок (±10%)\n"
    "🟠 выше рынка (+10…+30%)\n"
    "🔴 сильно выше рынка (+30% и больше)\n"
    "Рынок = медиана объявлений той же модели ±1 год."
)


def _fmt(price, currency="BYN"):
    if not price:
        return "—"
    return f"{price:,}".replace(",", " ") + f" {currency}"


def _price_badge(price, median):
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


def _escape(s):
    return (s or "").replace("<", "&lt;").replace(">", "&gt;")


def _median_for_year(year, all_items):
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
    all_prices = [r["price"] for r in all_items if r.get("price")]
    return statistics.median(all_prices) if all_prices else None


def _sort_by_value(items, all_items):
    """Сначала 💚 (самые выгодные), потом 🟢, ⚪, 🟠, 🔴."""
    def key(r):
        m = _median_for_year(r.get("year"), all_items)
        p = r.get("price")
        if not p or not m:
            return 2.0  # в середину
        return p / m
    return sorted(items, key=key)


def _render_item(r, all_items):
    m = _median_for_year(r.get("year"), all_items)
    badge = _price_badge(r.get("price"), m)
    title = _escape(r["title"])
    price = _fmt(r.get("price"), r.get("currency", "BYN"))
    year = r.get("year") or "—"
    params = (r.get("params") or "").strip()

    delta_txt = ""
    if m and r.get("price"):
        d = (r["price"] - m) / m * 100
        sign = "+" if d >= 0 else ""
        delta_txt = f" ({sign}{d:.0f}% к медиане)"

    lines = [f"{badge} <b>{price}</b>{delta_txt} · {title} · {year}"]
    if params and params != str(year):
        lines.append(f"<i>{_escape(params)}</i>")
    lines.append(f'<a href="{r["url"]}">→ Открыть на av.by</a>')
    return "\n".join(lines)


def _build_header(sub, page_items, total, offset, page, all_items):
    crit = []
    if sub is not None:
        if sub.brand:
            crit.append(sub.brand)
        if sub.model:
            crit.append(sub.model)
        if sub.year_from or sub.year_to:
            crit.append(f"{sub.year_from or '...'}–{sub.year_to or '...'}")
        if sub.price_from or sub.price_to:
            crit.append(f"${sub.price_from or '...'}–${sub.price_to or '...'}")
        extras = []
        if getattr(sub, "fuel_type", None):
            extras.append(sub.fuel_type)
        if getattr(sub, "transmission", None):
            extras.append(sub.transmission)
        if getattr(sub, "mileage_to", None):
            extras.append(f"пробег≤{sub.mileage_to}")
        if extras:
            crit.append(", ".join(extras))

    start = offset + 1
    end = offset + len(page_items)
    lines = [f"🔍 <b>Найдено {total}</b> · стр. {page} ({start}–{end})"]
    if crit:
        lines.append(f"Критерии: <i>{_escape(' · '.join(crit))}</i>")
    lines.append("")
    lines.append(f"<i>{LEGEND}</i>")
    return "\n".join(lines)


def _build_body(items, all_items):
    SEP = "\n\n"
    return SEP.join(_render_item(r, all_items) for r in items)


def _build_kb(sub_id, page, offset, total, has_more):
    rows = []
    if has_more:
        next_off = offset + PAGE_SIZE
        rows.append([InlineKeyboardButton(
            text=f"🔽 Ещё {PAGE_SIZE} (стр. {page + 1})",
            callback_data=f"subs:find:{sub_id}:{next_off}",
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
            await cb.message.edit_text("🔍 <b>Ищу на av.by…</b>")
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
        "fuel_type": getattr(sub, "fuel_type", None),
        "transmission": getattr(sub, "transmission", None),
        "mileage_to": getattr(sub, "mileage_to", None),
        "engine_cc_from": getattr(sub, "engine_cc_from", None),
        "engine_cc_to": getattr(sub, "engine_cc_to", None),
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
                    f"❌ Ошибка поиска: {_escape(str(e))}",
                    reply_markup=_build_kb(sub_id, 1, 0, 0, False),
                )
            except TelegramBadRequest:
                pass
        return

    if not all_results:
        txt = "😔 <b>Ничего не найдено.</b>\n\n"
        if not brand_id:
            txt += "💡 Марка вручную — попробуй ✏️ Марка из списка."
        if cb.message is not None:
            try:
                await cb.message.edit_text(txt, reply_markup=_build_kb(sub_id, 1, 0, 0, False))
            except TelegramBadRequest:
                pass
        return

    # сортировка: 💚 → 🔴
    all_results = _sort_by_value(all_results, all_results)

    total = len(all_results)
    page_items = all_results[offset:offset + PAGE_SIZE]
    if not page_items:
        await cb.answer("Больше нет")
        return

    page = offset // PAGE_SIZE + 1
    has_more = (offset + PAGE_SIZE) < total
    header = _build_header(sub, page_items, total, offset, page, all_results)
    body = _build_body(page_items, all_results)
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


async def _render_search_results(cb, all_results, parsed_or_d=None):
    """Разовый поиск: без подписки. Сортировка по цвету."""
    if not all_results:
        return
    all_results = _sort_by_value(all_results, all_results)
    total = len(all_results)
    page_items = all_results[:PAGE_SIZE]
    fake_sub = None
    header = _build_header(fake_sub, page_items, total, 0, 1, all_results)
    if isinstance(parsed_or_d, dict) and parsed_or_d:
        parts = []
        for k in ("brand", "model", "fuel_type", "transmission"):
            v = parsed_or_d.get(k)
            if v:
                parts.append(str(v))
        if parsed_or_d.get("year_from") or parsed_or_d.get("year_to"):
            parts.append(f"{parsed_or_d.get('year_from') or '...'}–{parsed_or_d.get('year_to') or '...'}")
        if parsed_or_d.get("price_to"):
            parts.append(f"≤${parsed_or_d['price_to']}")
        if parts:
            header = header.replace("🔍 <b>Найдено", "🔍 <b>Найдено")
    body = _build_body(page_items, all_results)
    text = header + "\n\n" + body
    if len(text) > 4000:
        text = text[:3990] + "\n\n<i>(усечено)</i>"
    if cb.message is not None:
        try:
            await cb.message.edit_text(text, disable_web_page_preview=True)
        except Exception:
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