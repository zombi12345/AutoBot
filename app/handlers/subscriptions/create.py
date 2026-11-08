from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.repositories.subscriptions import create_subscription
from app.db.repositories.users import get_or_create_user
from app.keyboards.main_menu import BTN_LONG_SEARCH, main_menu_kb
from app.states.subscription import CreateSubscription

router = Router(name="subs_create")

CB_CONFIRM = "sub_create:confirm"
CB_CANCEL = "sub_create:cancel"

STEPS = [
    (CreateSubscription.brand, "brand", "марку (например: BMW)"),
    (CreateSubscription.model, "model", "модель (например: X5)"),
    (CreateSubscription.year_from, "year_from", "год ОТ (например: 2018)"),
    (CreateSubscription.year_to, "year_to", "год ДО"),
    (CreateSubscription.price_from, "price_from", "цену ОТ, USD"),
    (CreateSubscription.price_to, "price_to", "цену ДО, USD"),
]
STEPS_BY_STATE = {s[0].state: s for s in STEPS}
TEXT_STATES = {CreateSubscription.brand.state, CreateSubscription.model.state}
INT_STATES = {
    CreateSubscription.year_from.state, CreateSubscription.year_to.state,
    CreateSubscription.price_from.state, CreateSubscription.price_to.state,
}


def _step_index(cur: str | None) -> int | None:
    if cur is None:
        return None
    for i, s in enumerate(STEPS):
        if s[0].state == cur:
            return i
    return None


async def _advance(message: Message, state: FSMContext, value: object) -> None:
    cur = await state.get_state()
    idx = _step_index(cur)
    if idx is None:
        return
    _, key, _ = STEPS[idx]
    data = await state.get_data()
    data[key] = value
    await state.update_data(data=data)

    if idx + 1 < len(STEPS):
        nxt = STEPS[idx + 1]
        await state.set_state(nxt[0])
        await message.answer(f"Введи {nxt[2]}\n\n/skip — пропустить, /cancel — отмена.")
    else:
        await state.set_state(CreateSubscription.confirm)
        await _show_preview(message, state)


async def _show_preview(message: Message, state: FSMContext) -> None:
    d = await state.get_data()
    labels = [
        ("brand", "Марка"), ("model", "Модель"),
        ("year_from", "Год от"), ("year_to", "Год до"),
        ("price_from", "Цена от"), ("price_to", "Цена до"),
    ]
    lines = ["📋 <b>Проверь критерии:</b>", ""]
    for key, label in labels:
        v = d.get(key)
        lines.append(f"• {label}: {v if v not in (None, '') else '—'}")
    lines += ["", "Создать подписку?"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Создать", callback_data=CB_CONFIRM),
        InlineKeyboardButton(text="❌ Отмена", callback_data=CB_CANCEL),
    ]])
    await message.answer("\n".join(lines), reply_markup=kb)


@router.message(F.text == BTN_LONG_SEARCH)
async def start_create(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(data={})
    first = STEPS[0]
    await state.set_state(first[0])
    await message.answer(
        "⏳ <b>Создание подписки</b>\n\n"
        f"Введи {first[2]}\n\n"
        "/skip — пропустить, /cancel — отмена.",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("Нечего отменять.", reply_markup=main_menu_kb())
        return
    await state.clear()
    await message.answer("❌ Создание отменено.", reply_markup=main_menu_kb())


@router.message(Command("skip"), StateFilter("*"))
async def cmd_skip(message: Message, state: FSMContext) -> None:
    cur = await state.get_state()
    if cur is None or cur == CreateSubscription.confirm.state:
        return
    await _advance(message, state, None)


@router.message(StateFilter(*TEXT_STATES), F.text, ~F.text.startswith("/"))
async def on_text_step(message: Message, state: FSMContext) -> None:
    txt = (message.text or "").strip()
    if not txt:
        return
    await _advance(message, state, txt)


@router.message(StateFilter(*INT_STATES), F.text, ~F.text.startswith("/"))
async def on_int_step(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(" ", "")
    if not raw.isdigit():
        await message.answer("Нужно число. Попробуй ещё раз или /skip.")
        return
    await _advance(message, state, int(raw))


@router.callback_query(F.data == CB_CONFIRM)
async def on_confirm(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.from_user is None or cb.message is None:
        return
    d = await state.get_data()
    u = cb.from_user
    user = await get_or_create_user(u.id, username=u.username, first_name=u.first_name)
    try:
        sub = await create_subscription(
            user_id=user.id,
            source="avby",
            brand=d.get("brand"),
            model=d.get("model"),
            year_from=d.get("year_from"),
            year_to=d.get("year_to"),
            price_from=d.get("price_from"),
            price_to=d.get("price_to"),
        )
    except Exception as e:
        await state.clear()
        await cb.message.answer(f"❌ Ошибка: {e}", reply_markup=main_menu_kb())
        await cb.answer()
        return
    await state.clear()
    await cb.message.edit_text(f"✅ Подписка #{sub.id} создана.")
    await cb.message.answer("Смотри в 📋 Мои подписки.", reply_markup=main_menu_kb())
    await cb.answer()


@router.callback_query(F.data == CB_CANCEL)
async def on_cancel_cb(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if cb.message is not None:
        await cb.message.edit_text("❌ Создание отменено.")
    await cb.answer()