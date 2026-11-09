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
    print(f"DEBUG on_ai_query: text={message.text!r}", flush=True)
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
    """Пользователь подтвердил parsed — предлагаем искать или сохранить."""
    if cb.message is None or cb.from_user is None:
        await cb.answer()
        return
    d = await state.get_data()
    parsed = d.get("ai_parsed") or {}
    raw = d.get("ai_raw") or ""
    await state.update_data(ai_raw=raw)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Искать сейчас", callback_data="ai:search")],
        [InlineKeyboardButton(text="⏳ Сохранить как подписку", callback_data="ai:save")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="ai:cancel")],
    ])
    await cb.message.edit_text("Что сделать с критериями?", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "ai:search")
async def ai_search(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.message is None or cb.from_user is None:
        await cb.answer()
        return
    d = await state.get_data()
    parsed = d.get("ai_parsed") or {}
    await state.clear()

    from app.data.cars_full import BRAND_IDS, MODEL_IDS
    from app.services.parsers.avby import search as avby_search
    from app.handlers.subscriptions import find as find_mod

    brand = parsed.get("brand")
    model = parsed.get("model")
    brand_id = BRAND_IDS.get(brand) if brand else None
    model_id = None
    if brand_id and model:
        model_id = (MODEL_IDS.get(brand) or {}).get(model)

    criteria = {
        "brand_id": brand_id,
        "model_id": model_id,
        "year_from": parsed.get("year_from"),
        "year_to": parsed.get("year_to"),
        "price_from": parsed.get("price_from"),
        "price_to": parsed.get("price_to"),
        "fuel_type": parsed.get("fuel_type"),
        "transmission": parsed.get("transmission"),
        "mileage_to": parsed.get("mileage_to"),
        "engine_cc_from": parsed.get("engine_cc_from"),
        "engine_cc_to": parsed.get("engine_cc_to"),
        "query": None if brand_id else (f"{brand or ''} {model or ''}".strip() or None),
    }
    await cb.message.edit_text("🔍 Ищу на av.by…")
    try:
        results = await avby_search(criteria, limit=100)
    except Exception as e:
        await cb.message.edit_text(f"❌ Ошибка поиска: {e}")
        await cb.answer()
        return
    if not results:
        await cb.message.edit_text("😔 Ничего не найдено по этим критериям.")
        await cb.answer()
        return
    await find_mod._render_search_results(cb, results, parsed)
    await cb.answer()


@router.callback_query(F.data == "ai:save")
async def ai_save(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.message is None or cb.from_user is None:
        await cb.answer()
        return
    d = await state.get_data()
    parsed = d.get("ai_parsed") or {}
    raw = d.get("ai_raw") or ""
    await state.clear()

    from app.db.repositories.subscriptions import create_subscription
    from app.db.repositories.users import get_or_create_user
    from app.handlers.subscriptions import find as find_mod
    from app.services.parsers.avby import search as avby_search
    from app.data.cars_full import BRAND_IDS, MODEL_IDS
    from app.keyboards.main_menu import main_menu_kb

    u = cb.from_user
    user = await get_or_create_user(u.id, username=u.username, first_name=u.first_name)
    sub = await create_subscription(
        user_id=user.id,
        source="avby",
        brand=parsed.get("brand"),
        model=parsed.get("model"),
        year_from=parsed.get("year_from"),
        year_to=parsed.get("year_to"),
        price_from=parsed.get("price_from"),
        price_to=parsed.get("price_to"),
        fuel_type=parsed.get("fuel_type"),
        transmission=parsed.get("transmission"),
        mileage_to=parsed.get("mileage_to"),
        engine_cc_from=parsed.get("engine_cc_from"),
        engine_cc_to=parsed.get("engine_cc_to"),
        extra={"ai_raw": raw} if raw else None,
    )
    await cb.message.edit_text(f"✅ Подписка #{sub.id} создана по AI-критериям.")
    await cb.message.answer("Смотри в 📋 Мои подписки.", reply_markup=main_menu_kb())
    await cb.answer()