from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.repositories.subscriptions import list_user_subscriptions
from app.db.repositories.users import get_or_create_user
from app.keyboards.main_menu import BTN_MY_SUBS

router = Router(name="subs_list")


def _label(sub) -> str:
    parts: list[str] = []
    if sub.brand:
        parts.append(sub.brand)
    if sub.model:
        parts.append(sub.model)
    if sub.year_from or sub.year_to:
        parts.append(f"{sub.year_from or '...'}–{sub.year_to or '...'}")
    if sub.price_from or sub.price_to:
        parts.append(f"${sub.price_from or '...'}–${sub.price_to or '...'}")
    return " ".join(parts) if parts else "без критериев"


def build_list_kb(subs: list) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for s in subs:
        icon = "⏸" if s.status == "paused" else "▶"
        label = f"{icon} #{s.id} {_label(s)}"
        if len(label) > 55:
            label = label[:52] + "…"
        if s.status == "paused":
            cb = f"subs:do:resume:{s.id}"
            btn = "▶"
        else:
            cb = f"subs:do:pause:{s.id}"
            btn = "⏸"
        rows.append([
            InlineKeyboardButton(text=label, callback_data=f"subs:info:{s.id}"),
            InlineKeyboardButton(text=btn, callback_data=cb),
            InlineKeyboardButton(text="🗑", callback_data=f"subs:do:del:{s.id}"),
        ])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="subs:refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_text(subs: list) -> str:
    if not subs:
        return "📋 Подписок пока нет.\n\nНажми ⏳ Долгий поиск, чтобы создать."
    active = sum(1 for s in subs if s.status == "active")
    paused = len(subs) - active
    lines = [
        f"📋 <b>Мои подписки</b> — всего {len(subs)} (active: {active}, paused: {paused})",
        "",
        "Тапни название → карточка с редактированием.",
    ]
    return "\n".join(lines)


async def _load(user) -> tuple[list, str]:
    db_user = await get_or_create_user(user.id, username=user.username, first_name=user.first_name)
    subs = await list_user_subscriptions(db_user.id)
    return subs, build_text(subs)


@router.message(F.text == BTN_MY_SUBS)
async def show_my_subs(message: Message) -> None:
    u = message.from_user
    if u is None:
        return
    subs, text = await _load(u)
    await message.answer(text, reply_markup=build_list_kb(subs))


@router.callback_query(F.data == "subs:refresh")
async def on_refresh(cb: CallbackQuery) -> None:
    if cb.from_user is None or cb.message is None:
        await cb.answer()
        return
    subs, text = await _load(cb.from_user)
    try:
        await cb.message.edit_text(text, reply_markup=build_list_kb(subs))
    except TelegramBadRequest:
        pass
    await cb.answer("Обновлено")