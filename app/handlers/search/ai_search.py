from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.services.ai.parser import parse_query

router = Router(name="search_ai")

BTN_AI = "🤖 Умный поиск"


@router.message(F.text == BTN_AI)
async def start_ai_search(message: Message) -> None:
    await message.answer(
        "🤖 <b>Умный поиск</b>\n\n"
        "Напиши, какую машину хочешь — я разберу запрос.\n\n"
        "Примеры:\n"
        "• <i>BMW X5 2019-2023 дизель автомат до 40000</i>\n"
        "• <i>Geely Coolray не старше 2022, пробег до 50к</i>\n"
        "• <i>Audi A4 универсал, механика, до 15000</i>"
    )


@router.message(F.text & ~F.text.startswith("/"))
async def on_ai_query(message: Message, state: FSMContext) -> None:
    # реагируем только если FSM в нужном состоянии ИЛИ это первый раз
    # (пока без FSM — просто ловим текст, если AI включён и длина > 5)
    from app.config import settings
    if not settings.ai_enabled:
        return
    txt = (message.text or "").strip()
    if len(txt) < 5:
        return
    if not any(ch.isalpha() for ch in txt):
        return

    # если пользователь просто нажал reply-кнопку из меню — пропускаем
    from app.keyboards.main_menu import BTN_HELP, BTN_MY_SUBS, BTN_SEARCH, BTN_LONG_SEARCH
    if txt in {BTN_HELP, BTN_MY_SUBS, BTN_SEARCH, BTN_LONG_SEARCH, BTN_AI}:
        return

    await message.answer("🤖 Разбираю запрос…")
    parsed = await parse_query(txt)

    # форматируем что поняли
    labels = [
        ("brand", "Марка"), ("model", "Модель"),
        ("year_from", "Год от"), ("year_to", "Год до"),
        ("price_from", "Цена от"), ("price_to", "Цена до"),
        ("fuel_type", "Топливо"), ("transmission", "КПП"),
        ("body_type", "Кузов"), ("mileage_to", "Пробег до"),
        ("engine_cc_from", "Объём от"), ("engine_cc_to", "Объём до"),
    ]
    lines = ["📋 <b>Вот что я понял:</b>", ""]
    for k, label in labels:
        v = parsed.get(k)
        lines.append(f"• {label}: {v if v is not None else '—'}")
    lines += ["", "Всё верно?"]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, искать", callback_data="ai:ok")],
        [InlineKeyboardButton(text="✏️ Поправить", callback_data="ai:edit")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="ai:cancel")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)

    # сохранить parsed в FSM для следующего шага (D-14)
    await state.update_data(ai_parsed=parsed, ai_raw=txt)


@router.callback_query(F.data == "ai:cancel")
async def on_ai_cancel(cb, state: FSMContext) -> None:
    await state.clear()
    if cb.message:
        await cb.message.edit_text("❌ Отменено")
    await cb.answer()


@router.callback_query(F.data == "ai:ok")
async def on_ai_ok(cb, state: FSMContext) -> None:
    d = await state.get_data()
    parsed = d.get("ai_parsed") or {}
    if cb.message:
        await cb.message.edit_text(
            "✅ Понял. В D-14 подключу поиск по этим критериям на av.by.\n\n"
            f"<pre>{parsed}</pre>"
        )
    await cb.answer()