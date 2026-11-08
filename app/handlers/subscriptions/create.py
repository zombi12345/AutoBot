from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.data.cars import BRAND_NAMES, BRANDS, PRICES, YEARS
from app.db.repositories.subscriptions import create_subscription
from app.db.repositories.users import get_or_create_user
from app.keyboards.main_menu import BTN_LONG_SEARCH, main_menu_kb
from app.states.subscription import CreateSubscription

router = Router(name="subs_create")

PER_PAGE = 8


# ---------- Рендеры ----------

def render_brands(page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    start = page * PER_PAGE
    end = start + PER_PAGE
    chunk = BRAND_NAMES[start:end]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(chunk), 2):
        rows.append([
            InlineKeyboardButton(text=name, callback_data=f"cs:b:{start + i + j}")
            for j, name in enumerate(chunk[i:i + 2])
        ])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"cs:bp:{page - 1}"))
    if end < len(BRAND_NAMES):
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"cs:bp:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cs:cancel")])
    return f"🚗 <b>Выбери марку</b> (стр. {page + 1})", InlineKeyboardMarkup(inline_keyboard=rows)


def render_models(brand_idx: int, page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    brand = BRAND_NAMES[brand_idx]
    models = BRANDS[brand]
    start = page * PER_PAGE
    end = start + PER_PAGE
    chunk = models[start:end]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(chunk), 2):
        rows.append([
            InlineKeyboardButton(text=name, callback_data=f"cs:m:{brand_idx}:{start + i + j}")
            for j, name in enumerate(chunk[i:i + 2])
        ])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"cs:mp:{brand_idx}:{page - 1}"))
    if end < len(models):
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"cs:mp:{brand_idx}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([
        InlineKeyboardButton(text="Пропустить", callback_data="cs:skip:model"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cs:cancel"),
    ])
    return f"🚗 <b>{brand}</b> — выбери модель", InlineKeyboardMarkup(inline_keyboard=rows)


def render_years(field: str, min_year: int | None = None) -> tuple[str, InlineKeyboardMarkup]:
    years = [y for y in YEARS if min_year is None or y >= min_year]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(years), 4):
        rows.append([
            InlineKeyboardButton(text=str(y), callback_data=f"cs:{field}:{y}")
            for y in years[i:i + 4]
        ])
    rows.append([
        InlineKeyboardButton(text="Пропустить", callback_data=f"cs:skip:{field}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cs:cancel"),
    ])
    title = "📅 <b>Год ОТ</b>" if field == "yf" else "📅 <b>Год ДО</b>"
    return title, InlineKeyboardMarkup(inline_keyboard=rows)


def render_prices(field: str, min_price: int | None = None) -> tuple[str, InlineKeyboardMarkup]:
    prices = [p for p in PRICES if min_price is None or p >= min_price]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(prices), 4):
        rows.append([
            InlineKeyboardButton(
                text=("$0" if p == 0 else f"${p:,}".replace(",", " ")),
                callback_data=f"cs:{field}:{p}",
            )
            for p in prices[i:i + 4]
        ])
    rows.append([
        InlineKeyboardButton(text="Пропустить", callback_data=f"cs:skip:{field}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cs:cancel"),
    ])
    title = "💰 <b>Цена ОТ, USD</b>" if field == "pf" else "💰 <b>Цена ДО, USD</b>"
    return title, InlineKeyboardMarkup(inline_keyboard=rows)


def render_preview(d: dict) -> tuple[str, InlineKeyboardMarkup]:
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
        InlineKeyboardButton(text="✅ Создать", callback_data="cs:done"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cs:cancel"),
    ]])
    return "\n".join(lines), kb


async def safe_edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    if cb.message is None:
        await cb.answer()
        return
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass
    await cb.answer()


# ---------- Entry ----------

@router.message(F.text == BTN_LONG_SEARCH)
async def start_create(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(brand=None, brand_idx=None, model=None,
                            year_from=None, year_to=None,
                            price_from=None, price_to=None)
    await state.set_state(CreateSubscription.brand)
    text, kb = render_brands(0)
    await message.answer(text, reply_markup=kb)


# ---------- Бренд ----------

@router.callback_query(F.data.startswith("cs:bp:"))
async def on_brand_page(cb: CallbackQuery) -> None:
    page = int(cb.data.split(":")[2])
    text, kb = render_brands(page)
    await safe_edit(cb, text, kb)


@router.callback_query(F.data.startswith("cs:b:"))
async def on_brand_pick(cb: CallbackQuery, state: FSMContext) -> None:
    idx = int(cb.data.split(":")[2])
    brand = BRAND_NAMES[idx]
    await state.update_data(brand=brand, brand_idx=idx)
    await state.set_state(CreateSubscription.model)
    text, kb = render_models(idx, 0)
    await safe_edit(cb, text, kb)


# ---------- Модель ----------

@router.callback_query(F.data.startswith("cs:mp:"))
async def on_model_page(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    brand_idx, page = int(parts[2]), int(parts[3])
    text, kb = render_models(brand_idx, page)
    await safe_edit(cb, text, kb)


@router.callback_query(F.data.startswith("cs:m:"))
async def on_model_pick(cb: CallbackQuery, state: FSMContext) -> None:
    parts = cb.data.split(":")
    brand_idx, model_idx = int(parts[2]), int(parts[3])
    brand = BRAND_NAMES[brand_idx]
    model = BRANDS[brand][model_idx]
    await state.update_data(model=model)
    await state.set_state(CreateSubscription.year_from)
    text, kb = render_years("yf")
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:skip:model")
async def on_skip_model(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(model=None)
    await state.set_state(CreateSubscription.year_from)
    text, kb = render_years("yf")
    await safe_edit(cb, text, kb)


# ---------- Год от ----------

@router.callback_query(F.data.startswith("cs:yf:"))
async def on_year_from(cb: CallbackQuery, state: FSMContext) -> None:
    year = int(cb.data.split(":")[2])
    await state.update_data(year_from=year)
    await state.set_state(CreateSubscription.year_to)
    text, kb = render_years("yd", min_year=year)
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:skip:yf")
async def on_skip_yf(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(year_from=None)
    await state.set_state(CreateSubscription.year_to)
    text, kb = render_years("yd")
    await safe_edit(cb, text, kb)


# ---------- Год до ----------

@router.callback_query(F.data.startswith("cs:yd:"))
async def on_year_to(cb: CallbackQuery, state: FSMContext) -> None:
    year = int(cb.data.split(":")[2])
    await state.update_data(year_to=year)
    await state.set_state(CreateSubscription.price_from)
    text, kb = render_prices("pf")
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:skip:yd")
async def on_skip_yd(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(year_to=None)
    await state.set_state(CreateSubscription.price_from)
    text, kb = render_prices("pf")
    await safe_edit(cb, text, kb)


# ---------- Цена от ----------

@router.callback_query(F.data.startswith("cs:pf:"))
async def on_price_from(cb: CallbackQuery, state: FSMContext) -> None:
    price = int(cb.data.split(":")[2])
    await state.update_data(price_from=price if price > 0 else None)
    await state.set_state(CreateSubscription.price_to)
    text, kb = render_prices("pd", min_price=price)
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:skip:pf")
async def on_skip_pf(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(price_from=None)
    await state.set_state(CreateSubscription.price_to)
    text, kb = render_prices("pd")
    await safe_edit(cb, text, kb)


# ---------- Цена до ----------

@router.callback_query(F.data.startswith("cs:pd:"))
async def on_price_to(cb: CallbackQuery, state: FSMContext) -> None:
    price = int(cb.data.split(":")[2])
    await state.update_data(price_to=price if price > 0 else None)
    await state.set_state(CreateSubscription.confirm)
    d = await state.get_data()
    text, kb = render_preview(d)
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:skip:pd")
async def on_skip_pd(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(price_to=None)
    await state.set_state(CreateSubscription.confirm)
    d = await state.get_data()
    text, kb = render_preview(d)
    await safe_edit(cb, text, kb)


# ---------- Создать / Отмена ----------

@router.callback_query(F.data == "cs:done")
async def on_done(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.from_user is None or cb.message is None:
        await cb.answer()
        return
    d = await state.get_data()
    u = cb.from_user
    user = await get_or_create_user(u.id, username=u.username, first_name=u.first_name)
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
    await state.clear()
    await cb.message.edit_text(f"✅ Подписка #{sub.id} создана.")
    await cb.message.answer("Смотри в 📋 Мои подписки.", reply_markup=main_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "cs:cancel")
async def on_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if cb.message is not None:
        try:
            await cb.message.edit_text("❌ Создание отменено.")
        except TelegramBadRequest:
            pass
    await cb.answer()