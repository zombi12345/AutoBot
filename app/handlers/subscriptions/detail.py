from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.data.cars_full import BRAND_NAMES
from app.db.repositories.subscriptions import (
    get_subscription,
    pause_subscription,
    resume_subscription,
)
from app.states.subscription import CreateSubscription

router = Router(name="subs_detail")


def render_detail(sub) -> tuple[str, InlineKeyboardMarkup]:
    status_icon = "⏸ paused" if sub.status == "paused" else "▶ active"
    lines = [
        f"📋 <b>Подписка #{sub.id}</b>",
        f"Статус: {status_icon}",
        f"Источник: {sub.source}",
        "",
        f"🚗 Марка: <b>{sub.brand or '—'}</b>",
        f"🚗 Модель: <b>{sub.model or '—'}</b>",
        f"📅 Год: <b>{sub.year_from or '...'}–{sub.year_to or '...'}</b>",
        f"💰 Цена: <b>${sub.price_from or '...'}–${sub.price_to or '...'}</b>",
    ]
    if sub.created_at:
        try:
            lines += ["", f"Создана: {sub.created_at.strftime('%Y-%m-%d %H:%M')}"]
        except Exception:
            pass

    sid = sub.id
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="✏️ Марка", callback_data=f"subs:edit:{sid}:brand"),
         InlineKeyboardButton(text="✏️ Модель", callback_data=f"subs:edit:{sid}:model")],
        [InlineKeyboardButton(text="✏️ Год от", callback_data=f"subs:edit:{sid}:year_from"),
         InlineKeyboardButton(text="✏️ Год до", callback_data=f"subs:edit:{sid}:year_to")],
        [InlineKeyboardButton(text="✏️ Цена от", callback_data=f"subs:edit:{sid}:price_from"),
         InlineKeyboardButton(text="✏️ Цена до", callback_data=f"subs:edit:{sid}:price_to")],
    ]
    if sub.status == "paused":
        rows.append([
            InlineKeyboardButton(text="▶ Продолжить", callback_data=f"subs:d:resume:{sid}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"subs:do:del:{sid}"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text="⏸ Пауза", callback_data=f"subs:d:pause:{sid}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"subs:do:del:{sid}"),
        ])
    rows.append([InlineKeyboardButton(text="← К списку", callback_data="subs:refresh")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def show_detail(cb: CallbackQuery, sub_id: int) -> None:
    sub = await get_subscription(sub_id)
    if sub is None:
        await cb.answer("Подписка не найдена", show_alert=True)
        return
    text, kb = render_detail(sub)
    if cb.message is not None:
        try:
            await cb.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest:
            pass
    await cb.answer()


# ---------- Detail ----------

@router.callback_query(F.data.startswith("subs:info:"))
async def on_info(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    if len(parts) < 3 or not parts[2].isdigit():
        await cb.answer()
        return
    await show_detail(cb, int(parts[2]))


# ---------- Edit entry ----------

@router.callback_query(F.data.startswith("subs:edit:"))
async def on_edit_click(cb: CallbackQuery, state: FSMContext) -> None:
    parts = cb.data.split(":")
    if len(parts) < 4 or not parts[2].isdigit():
        await cb.answer()
        return
    sub_id = int(parts[2])
    field = parts[3]

    sub = await get_subscription(sub_id)
    if sub is None:
        await cb.answer("Подписка не найдена", show_alert=True)
        return

    from app.handlers.subscriptions.create import (
        render_brands, render_models, render_years, render_prices,
    )

    await state.clear()
    await state.update_data(edit_sub_id=sub_id, edit_field=field)

    if field == "brand":
        await state.set_state(CreateSubscription.brand)
        text, kb = render_brands(0)
    elif field == "model":
        if not sub.brand or sub.brand not in BRAND_NAMES:
            await cb.answer("Сначала задай марку через ✏️ Марка", show_alert=True)
            return
        brand_idx = BRAND_NAMES.index(sub.brand)
        await state.update_data(brand=sub.brand, brand_idx=brand_idx)
        await state.set_state(CreateSubscription.model)
        text, kb = render_models(brand_idx)
    elif field == "year_from":
        await state.set_state(CreateSubscription.year_from)
        text, kb = render_years("yf")
    elif field == "year_to":
        await state.set_state(CreateSubscription.year_to)
        text, kb = render_years("yd")
    elif field == "price_from":
        await state.set_state(CreateSubscription.price_from)
        text, kb = render_prices("pf")
    elif field == "price_to":
        await state.set_state(CreateSubscription.price_to)
        text, kb = render_prices("pd")
    else:
        await cb.answer("Неизвестное поле", show_alert=True)
        return

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="← Назад к подписке", callback_data=f"subs:back:{sub_id}"),
    ])

    if cb.message is not None:
        try:
            await cb.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest:
            pass
    await cb.answer()


# ---------- Назад из каскада в карточку ----------

@router.callback_query(F.data.startswith("subs:back:"))
async def on_back_to_detail(cb: CallbackQuery, state: FSMContext) -> None:
    parts = cb.data.split(":")
    if len(parts) < 3 or not parts[2].isdigit():
        await cb.answer()
        return
    await state.clear()
    await show_detail(cb, int(parts[2]))


# ---------- Pause/resume из карточки ----------

@router.callback_query(F.data.startswith("subs:d:pause:"))
async def on_detail_pause(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    if len(parts) < 4 or not parts[3].isdigit():
        await cb.answer()
        return
    sub_id = int(parts[3])
    ok = await pause_subscription(sub_id)
    await cb.answer("⏸ Пауза" if ok else "Не найдено")
    await show_detail(cb, sub_id)


@router.callback_query(F.data.startswith("subs:d:resume:"))
async def on_detail_resume(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    if len(parts) < 4 or not parts[3].isdigit():
        await cb.answer()
        return
    sub_id = int(parts[3])
    ok = await resume_subscription(sub_id)
    await cb.answer("▶ Продолжено" if ok else "Не найдено")
    await show_detail(cb, sub_id)