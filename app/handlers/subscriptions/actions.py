from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.db.repositories.subscriptions import (
    delete_subscription,
    list_user_subscriptions,
    pause_subscription,
    resume_subscription,
)
from app.db.repositories.users import get_or_create_user
from app.handlers.subscriptions.my_subs import build_list_kb, build_text

router = Router(name="subs_actions")


async def _reload(cb: CallbackQuery) -> None:
    if cb.from_user is None or cb.message is None:
        await cb.answer()
        return
    db_user = await get_or_create_user(cb.from_user.id,
                                       username=cb.from_user.username,
                                       first_name=cb.from_user.first_name)
    subs = await list_user_subscriptions(db_user.id)
    try:
        await cb.message.edit_text(build_text(subs), reply_markup=build_list_kb(subs))
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("subs:do:pause:"))
async def on_pause(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[3])
    ok = await pause_subscription(sub_id)
    await cb.answer("⏸ Пауза" if ok else "Не найдено")
    await _reload(cb)


@router.callback_query(F.data.startswith("subs:do:resume:"))
async def on_resume(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[3])
    ok = await resume_subscription(sub_id)
    await cb.answer("▶ Продолжено" if ok else "Не найдено")
    await _reload(cb)


# --- delete: подтверждение ---

@router.callback_query(F.data.startswith("subs:do:del:"))
async def on_del_ask(cb: CallbackQuery) -> None:
    sub_id = cb.data.split(":")[3]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"subs:do:del_ok:{sub_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="subs:do:del_no"),
    ]])
    if cb.message is not None:
        try:
            await cb.message.edit_text(f"🗑 Удалить подписку #{sub_id}? Это необратимо.",
                                       reply_markup=kb)
        except TelegramBadRequest:
            pass
    await cb.answer()


@router.callback_query(F.data.startswith("subs:do:del_ok:"))
async def on_del_confirm(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[3])
    ok = await delete_subscription(sub_id)
    await cb.answer("🗑 Удалено" if ok else "Не найдено")
    await _reload(cb)


@router.callback_query(F.data == "subs:do:del_no")
async def on_del_cancel(cb: CallbackQuery) -> None:
    await cb.answer("Отменено")
    await _reload(cb)