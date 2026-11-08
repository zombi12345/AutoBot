from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.data.cars_full import BRAND_IDS, MODEL_IDS
from app.db.repositories.subscriptions import get_subscription, mark_checked
from app.services.parsers.avby import search

router = Router(name="subs_find")


def _fmt_price(p) -> str:
    if not p:
        return "—"
    return f"${p:,}".replace(",", " ")


@router.callback_query(F.data.startswith("subs:find:"))
async def on_find(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    if len(parts) < 3 or not parts[2].isdigit():
        await cb.answer()
        return
    sub_id = int(parts[2])
    sub = await get_subscription(sub_id)
    if sub is None:
        await cb.answer("Подписка не найдена", show_alert=True)
        return
    await cb.answer("🔍 Ищу...")
    if cb.message is not None:
        try:
            await cb.message.edit_text("🔍 <b>Ищу объявления на av.by…</b>")
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
        results = await search(criteria, limit=5)
    except Exception as e:
        results = []
        if cb.message is not None:
            try:
                await cb.message.edit_text(f"❌ Ошибка поиска: {e}")
            except TelegramBadRequest:
                pass
        return

    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="← К подписке", callback_data=f"subs:back:{sub_id}"),
    ]])

    if not results:
        txt = "😔 <b>Ничего не найдено</b> по критериям подписки.\n\n"
        if not brand_id:
            txt += "💡 Марка введена вручную — попробуй пересохранить через ✏️ Марка (из списка)."
        if cb.message is not None:
            try:
                await cb.message.edit_text(txt, reply_markup=back_kb)
            except TelegramBadRequest:
                pass
        return

    try:
        await mark_checked(sub_id, [r["id"] for r in results])
    except Exception:
        pass

    lines = [f"🔍 <b>Найдено {len(results)} на av.by:</b>", ""]
    for r in results:
        title = r["title"].replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"• <a href=\"{r['url']}\">{title}</a>")
        lines.append(f"  {r.get('year') or '—'} · {_fmt_price(r.get('price_usd'))}")
    lines += ["", "<i>Тапни название — откроется объявление.</i>"]

    if cb.message is not None:
        try:
            await cb.message.edit_text(
                "\n".join(lines),
                reply_markup=back_kb,
                disable_web_page_preview=True,
            )
        except TelegramBadRequest:
            pass