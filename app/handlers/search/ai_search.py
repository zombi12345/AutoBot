from __future__ import annotations
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from app.services.ai.parser import parse_query

router = Router(name="search_ai")
BTN_AI = "🤖 Умный поиск"

LABELS = [("brand","Марка"),("model","Модель"),("year_from","Год от"),("year_to","Год до"),
          ("price_from","Цена от"),("price_to","Цена до"),("fuel_type","Топливо"),
          ("transmission","КПП"),("body_type","Кузов"),("mileage_to","Пробег до"),
          ("engine_cc_from","Объём от"),("engine_cc_to","Объём до")]


@router.message(F.text == BTN_AI)
async def start_ai(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(awaiting_ai=True)
    await message.answer(
        "🤖 <b>Умный поиск</b>\n\n"
        "Опиши машину своими словами.\n"
        "Пример: <i>BMW X5 2019-2023 дизель автомат до 40000, пробег до 120к</i>"
    )


@router.message(F.text & ~F.text.startswith("/"))
async def on_ai_query(message: Message, state: FSMContext) -> None:
    from app.config import settings
    if not settings.ai_enabled: return
    d = await state.get_data()
    if not d.get("awaiting_ai"): return
    txt = (message.text or "").strip()
    if len(txt) < 5: return

    from app.keyboards.main_menu import BTN_AI, BTN_HELP, BTN_LONG_SEARCH, BTN_MY_SUBS, BTN_SEARCH
    if txt in {BTN_HELP, BTN_MY_SUBS, BTN_SEARCH, BTN_LONG_SEARCH, BTN_AI}: return

    await message.answer("🤖 Разбираю…")
    parsed = await parse_query(txt)
    lines = ["📋 <b>Вот что я понял:</b>",""]
    for k, lbl in LABELS:
        lines.append(f"• {lbl}: {parsed.get(k) if parsed.get(k) is not None else '—'}")
    lines += ["","Всё верно?"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Искать", callback_data="ai:ok")],
        [InlineKeyboardButton(text="✏️ Заново", callback_data="ai:retry")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="ai:cancel")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)
    await state.update_data(ai_parsed=parsed)


@router.callback_query(F.data == "ai:cancel")
async def ai_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if cb.message: await cb.message.edit_text("❌ Отменено")
    await cb.answer()


@router.callback_query(F.data == "ai:retry")
async def ai_retry(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(awaiting_ai=True, ai_parsed=None)
    if cb.message: await cb.message.edit_text("✏️ Напиши запрос заново.")
    await cb.answer()


@router.callback_query(F.data == "ai:ok")
async def ai_ok(cb: CallbackQuery, state: FSMContext) -> None:
    d = await state.get_data()
    parsed = d.get("ai_parsed") or {}
    await state.clear()
    if cb.message:
        await cb.message.edit_text(
            "✅ Понял. Поиск по этим критериям — в следующем шаге.\n\n"
            f"<code>{parsed}</code>"
        )
    await cb.answer()