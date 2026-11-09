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

from app.data.cars_full import BRAND_NAMES, BRANDS
from app.db.repositories.subscriptions import create_subscription, update_subscription
from app.db.repositories.users import get_or_create_user
from app.keyboards.main_menu import BTN_LONG_SEARCH, BTN_SEARCH, main_menu_kb
from app.states.subscription import CreateSubscription
from app.utils.fuzzy import find_brand, find_model

router = Router(name="subs_create")

BRANDS_PER_PAGE = 8


def _manual_btn(field: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"cs:manual:{field}")


def _cancel_btn() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="❌ Отмена", callback_data="cs:cancel")


def render_brands(page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    start = page * BRANDS_PER_PAGE
    end = start + BRANDS_PER_PAGE
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
    rows.append([_manual_btn("brand")])
    rows.append([_cancel_btn()])
    total_pages = (len(BRAND_NAMES) + BRANDS_PER_PAGE - 1) // BRANDS_PER_PAGE
    return f"🚗 <b>Выбери марку</b> (стр. {page + 1}/{total_pages})", InlineKeyboardMarkup(inline_keyboard=rows)


def render_models(brand_idx: int) -> tuple[str, InlineKeyboardMarkup]:
    brand = BRAND_NAMES[brand_idx]
    models = BRANDS[brand]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(models), 2):
        rows.append([
            InlineKeyboardButton(text=name, callback_data=f"cs:m:{brand_idx}:{i + j}")
            for j, name in enumerate(models[i:i + 2])
        ])
    rows.append([
        InlineKeyboardButton(text="Пропустить", callback_data="cs:skip:model"),
        _manual_btn("model"),
    ])
    rows.append([_cancel_btn()])
    return f"🚗 <b>{brand}</b> — выбери модель (всего {len(models)})", InlineKeyboardMarkup(inline_keyboard=rows)


def render_years(field: str, min_year: int | None = None) -> tuple[str, InlineKeyboardMarkup]:
    years = [y for y in range(2026, 1989, -1) if min_year is None or y >= min_year]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(years), 4):
        rows.append([
            InlineKeyboardButton(text=str(y), callback_data=f"cs:{field}:{y}")
            for y in years[i:i + 4]
        ])
    rows.append([
        InlineKeyboardButton(text="Пропустить", callback_data=f"cs:skip:{field}"),
        _manual_btn(field),
    ])
    rows.append([_cancel_btn()])
    title = "📅 <b>Год ОТ</b>" if field == "yf" else "📅 <b>Год ДО</b>"
    return title, InlineKeyboardMarkup(inline_keyboard=rows)


def render_prices(field: str, min_price: int | None = None) -> tuple[str, InlineKeyboardMarkup]:
    base = [0, 1000, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 12000, 15000, 18000,
            20000, 25000, 30000, 40000, 50000, 70000, 100000, 150000, 200000]
    prices = [p for p in base if min_price is None or p >= min_price]
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
        _manual_btn(field),
    ])
    rows.append([_cancel_btn()])
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
    is_once = d.get("mode") == "once"
    if is_once:
        lines += ["", "Запустить поиск?"]
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔍 Искать", callback_data="cs:search_once"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cs:cancel"),
        ]])
    else:
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


async def _try_save_edit(cb: CallbackQuery, state: FSMContext, field: str, value) -> bool:
    """Если в режиме редактирования — сохраняет в БД, возвращает в карточку, True.
    Иначе False (продолжаем обычный каскад)."""
    d = await state.get_data()
    edit_id = d.get("edit_sub_id")
    if not edit_id:
        return False
    await update_subscription(int(edit_id), **{field: value})
    await state.clear()
    from app.handlers.subscriptions.detail import show_detail
    await show_detail(cb, int(edit_id))
    return True


# ---------- Entry ----------

@router.message(F.text.in_([BTN_LONG_SEARCH, BTN_SEARCH]))
async def start_create(message: Message, state: FSMContext) -> None:
    mode = "once" if (message.text or "") == BTN_SEARCH else "sub"
    await state.clear()
    await state.update_data(
        mode=mode,
        brand=None, brand_idx=None, model=None,
        year_from=None, year_to=None,
        price_from=None, price_to=None,
    )
    await state.set_state(CreateSubscription.brand)
    text, kb = render_brands(0)
    hint = "🔍 Разовый поиск — в конце покажу объявления." if mode == "once" else "⏳ Новая подписка."
    await message.answer(f"{hint}\n\n{text}", reply_markup=kb)


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
    if await _try_save_edit(cb, state, "brand", brand):
        return
    await state.update_data(brand=brand, brand_idx=idx)
    await state.set_state(CreateSubscription.model)
    text, kb = render_models(idx)
    await safe_edit(cb, text, kb)


# ---------- Модель ----------

@router.callback_query(F.data.startswith("cs:m:"))
async def on_model_pick(cb: CallbackQuery, state: FSMContext) -> None:
    parts = cb.data.split(":")
    brand_idx, model_idx = int(parts[2]), int(parts[3])
    brand = BRAND_NAMES[brand_idx]
    model = BRANDS[brand][model_idx]
    if await _try_save_edit(cb, state, "model", model):
        return
    await state.update_data(model=model)
    await state.set_state(CreateSubscription.year_from)
    text, kb = render_years("yf")
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:skip:model")
async def on_skip_model(cb: CallbackQuery, state: FSMContext) -> None:
    if await _try_save_edit(cb, state, "model", None):
        return
    await state.update_data(model=None)
    await state.set_state(CreateSubscription.year_from)
    text, kb = render_years("yf")
    await safe_edit(cb, text, kb)


# ---------- Год от / до ----------

@router.callback_query(F.data.startswith("cs:yf:"))
async def on_year_from(cb: CallbackQuery, state: FSMContext) -> None:
    year = int(cb.data.split(":")[2])
    if await _try_save_edit(cb, state, "year_from", year):
        return
    await state.update_data(year_from=year)
    await state.set_state(CreateSubscription.year_to)
    text, kb = render_years("yd", min_year=year)
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:skip:yf")
async def on_skip_yf(cb: CallbackQuery, state: FSMContext) -> None:
    if await _try_save_edit(cb, state, "year_from", None):
        return
    await state.update_data(year_from=None)
    await state.set_state(CreateSubscription.year_to)
    text, kb = render_years("yd")
    await safe_edit(cb, text, kb)


@router.callback_query(F.data.startswith("cs:yd:"))
async def on_year_to(cb: CallbackQuery, state: FSMContext) -> None:
    year = int(cb.data.split(":")[2])
    if await _try_save_edit(cb, state, "year_to", year):
        return
    await state.update_data(year_to=year)
    await state.set_state(CreateSubscription.price_from)
    text, kb = render_prices("pf")
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:skip:yd")
async def on_skip_yd(cb: CallbackQuery, state: FSMContext) -> None:
    if await _try_save_edit(cb, state, "year_to", None):
        return
    await state.update_data(year_to=None)
    await state.set_state(CreateSubscription.price_from)
    text, kb = render_prices("pf")
    await safe_edit(cb, text, kb)


# ---------- Цена от / до ----------

@router.callback_query(F.data.startswith("cs:pf:"))
async def on_price_from(cb: CallbackQuery, state: FSMContext) -> None:
    price = int(cb.data.split(":")[2])
    value = price if price > 0 else None
    if await _try_save_edit(cb, state, "price_from", value):
        return
    await state.update_data(price_from=value)
    await state.set_state(CreateSubscription.price_to)
    text, kb = render_prices("pd", min_price=price)
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:skip:pf")
async def on_skip_pf(cb: CallbackQuery, state: FSMContext) -> None:
    if await _try_save_edit(cb, state, "price_from", None):
        return
    await state.update_data(price_from=None)
    await state.set_state(CreateSubscription.price_to)
    text, kb = render_prices("pd")
    await safe_edit(cb, text, kb)


@router.callback_query(F.data.startswith("cs:pd:"))
async def on_price_to(cb: CallbackQuery, state: FSMContext) -> None:
    price = int(cb.data.split(":")[2])
    value = price if price > 0 else None
    if await _try_save_edit(cb, state, "price_to", value):
        return
    await state.update_data(price_to=value)
    await state.set_state(CreateSubscription.confirm)
    d = await state.get_data()
    text, kb = render_preview(d)
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:skip:pd")
async def on_skip_pd(cb: CallbackQuery, state: FSMContext) -> None:
    if await _try_save_edit(cb, state, "price_to", None):
        return
    await state.update_data(price_to=None)
    await state.set_state(CreateSubscription.confirm)
    d = await state.get_data()
    text, kb = render_preview(d)
    await safe_edit(cb, text, kb)


# ---------- Ручной ввод (только для создания) ----------

@router.callback_query(F.data.startswith("cs:manual:"))
async def on_manual(cb: CallbackQuery, state: FSMContext) -> None:
    field = cb.data.split(":")[2]
    mapping = {
        "brand": CreateSubscription.manual_brand,
        "model": CreateSubscription.manual_model,
        "yf": CreateSubscription.manual_year_from,
        "yd": CreateSubscription.manual_year_to,
        "pf": CreateSubscription.manual_price_from,
        "pd": CreateSubscription.manual_price_to,
    }
    st = mapping.get(field)
    if st is None:
        await cb.answer()
        return
    await state.set_state(st)
    prompts = {
        "brand": "Введи марку (BMW, Geely, Лада, ВАЗ…)",
        "model": "Введи модель (X5, Coolray, Веста…)",
        "yf": "Введи год ОТ (например: 2015)",
        "yd": "Введи год ДО (например: 2023)",
        "pf": "Введи цену ОТ в USD (например: 10000)",
        "pd": "Введи цену ДО в USD (например: 30000)",
    }
    if cb.message is not None:
        try:
            await cb.message.edit_text(prompts[field])
        except TelegramBadRequest:
            pass
    await cb.answer()


@router.message(CreateSubscription.manual_brand, F.text)
async def on_manual_brand(message: Message, state: FSMContext) -> None:
    txt = (message.text or "").strip()
    if not txt:
        return
    canonical, mtype = find_brand(txt, BRAND_NAMES)
    if mtype == "exact" and canonical:
        idx = BRAND_NAMES.index(canonical)
        await state.update_data(brand=canonical, brand_idx=idx)
        await state.set_state(CreateSubscription.model)
        text, kb = render_models(idx)
        await message.answer(text, reply_markup=kb)
        return
    if mtype == "fuzzy" and canonical:
        idx = BRAND_NAMES.index(canonical)
        await state.update_data(pending_brand=canonical, pending_brand_idx=idx, raw_brand=txt)
        await state.set_state(CreateSubscription.confirm_brand)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ {canonical}", callback_data="cs:fb:Y")],
            [InlineKeyboardButton(text=f"✏️ Оставить «{txt}»", callback_data="cs:fb:N")],
        ])
        await message.answer(f"Возможно, ты имел в виду <b>{canonical}</b>?", reply_markup=kb)
        return
    await state.update_data(brand=txt, brand_idx=None)
    await state.set_state(CreateSubscription.year_from)
    text, kb = render_years("yf")
    await message.answer(f"Марка «{txt}» не в справочнике — сохраню как есть, модели пропущу.\n\n{text}", reply_markup=kb)


@router.message(CreateSubscription.manual_model, F.text)
async def on_manual_model(message: Message, state: FSMContext) -> None:
    txt = (message.text or "").strip()
    if not txt:
        return
    d = await state.get_data()
    brand_idx = d.get("brand_idx")
    canonical = None
    mtype = "none"
    if brand_idx is not None and brand_idx < len(BRAND_NAMES):
        brand = BRAND_NAMES[brand_idx]
        canonical, mtype = find_model(txt, BRANDS[brand])
    if mtype == "exact" and canonical:
        await state.update_data(model=canonical)
        await state.set_state(CreateSubscription.year_from)
        text, kb = render_years("yf")
        await message.answer(text, reply_markup=kb)
        return
    if mtype == "fuzzy" and canonical:
        await state.update_data(pending_model=canonical, raw_model=txt)
        await state.set_state(CreateSubscription.confirm_model)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ {canonical}", callback_data="cs:fm:Y")],
            [InlineKeyboardButton(text=f"✏️ Оставить «{txt}»", callback_data="cs:fm:N")],
        ])
        await message.answer(f"Возможно, ты имел в виду <b>{canonical}</b>?", reply_markup=kb)
        return
    await state.update_data(model=txt)
    await state.set_state(CreateSubscription.year_from)
    text, kb = render_years("yf")
    await message.answer(text, reply_markup=kb)


@router.message(CreateSubscription.manual_year_from, F.text)
async def on_manual_year_from(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (1980 <= int(raw) <= 2026):
        await message.answer("Нужен год от 1980 до 2026. Попробуй ещё раз.")
        return
    year = int(raw)
    await state.update_data(year_from=year)
    await state.set_state(CreateSubscription.year_to)
    text, kb = render_years("yd", min_year=year)
    await message.answer(text, reply_markup=kb)


@router.message(CreateSubscription.manual_year_to, F.text)
async def on_manual_year_to(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (1980 <= int(raw) <= 2026):
        await message.answer("Нужен год от 1980 до 2026. Попробуй ещё раз.")
        return
    year = int(raw)
    await state.update_data(year_to=year)
    await state.set_state(CreateSubscription.price_from)
    text, kb = render_prices("pf")
    await message.answer(text, reply_markup=kb)


@router.message(CreateSubscription.manual_price_from, F.text)
async def on_manual_price_from(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(" ", "")
    if not raw.isdigit():
        await message.answer("Нужно число (USD). Попробуй ещё раз.")
        return
    price = int(raw)
    await state.update_data(price_from=price if price > 0 else None)
    await state.set_state(CreateSubscription.price_to)
    text, kb = render_prices("pd", min_price=price)
    await message.answer(text, reply_markup=kb)


@router.message(CreateSubscription.manual_price_to, F.text)
async def on_manual_price_to(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(" ", "")
    if not raw.isdigit():
        await message.answer("Нужно число (USD). Попробуй ещё раз.")
        return
    price = int(raw)
    await state.update_data(price_to=price if price > 0 else None)
    await state.set_state(CreateSubscription.confirm)
    d = await state.get_data()
    text, kb = render_preview(d)
    await message.answer(text, reply_markup=kb)


# ---------- Fuzzy: бренд ----------

@router.callback_query(F.data == "cs:fb:Y")
async def on_confirm_brand_yes(cb: CallbackQuery, state: FSMContext) -> None:
    d = await state.get_data()
    idx = d.get("pending_brand_idx")
    if idx is None or idx >= len(BRAND_NAMES):
        await cb.answer()
        return
    canonical = BRAND_NAMES[idx]
    await state.update_data(brand=canonical, brand_idx=idx,
                            pending_brand=None, pending_brand_idx=None, raw_brand=None)
    await state.set_state(CreateSubscription.model)
    text, kb = render_models(idx)
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:fb:N")
async def on_confirm_brand_no(cb: CallbackQuery, state: FSMContext) -> None:
    d = await state.get_data()
    raw = d.get("raw_brand") or "—"
    await state.update_data(brand=raw, brand_idx=None,
                            pending_brand=None, pending_brand_idx=None, raw_brand=None)
    await state.set_state(CreateSubscription.year_from)
    text, kb = render_years("yf")
    await safe_edit(cb, f"Ок, сохраняю «{raw}» как есть.\n\n{text}", kb)


# ---------- Fuzzy: модель ----------

@router.callback_query(F.data == "cs:fm:Y")
async def on_confirm_model_yes(cb: CallbackQuery, state: FSMContext) -> None:
    d = await state.get_data()
    canonical = d.get("pending_model")
    if not canonical:
        await cb.answer()
        return
    await state.update_data(model=canonical, pending_model=None, raw_model=None)
    await state.set_state(CreateSubscription.year_from)
    text, kb = render_years("yf")
    await safe_edit(cb, text, kb)


@router.callback_query(F.data == "cs:fm:N")
async def on_confirm_model_no(cb: CallbackQuery, state: FSMContext) -> None:
    d = await state.get_data()
    raw = d.get("raw_model") or "—"
    await state.update_data(model=raw, pending_model=None, raw_model=None)
    await state.set_state(CreateSubscription.year_from)
    text, kb = render_years("yf")
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

    # pre-seed seen: сразу запомним существующие объявления, чтобы не спамить старыми
    try:
        from app.data.cars_full import BRAND_IDS, MODEL_IDS
        from app.services.parsers.avby import search
        from app.db.repositories.subscriptions import update_subscription

        brand_id = BRAND_IDS.get(sub.brand) if sub.brand else None
        model_id = None
        if brand_id and sub.model:
            model_id = (MODEL_IDS.get(sub.brand) or {}).get(sub.model)
        crit = {
            "brand_id": brand_id,
            "model_id": model_id,
            "year_from": sub.year_from,
            "year_to": sub.year_to,
            "price_from": sub.price_from,
            "price_to": sub.price_to,
            "query": None if brand_id else (f"{sub.brand or ''} {sub.model or ''}".strip() or None),
        }
        seed = await search(crit, limit=100)
        if seed:
            await update_subscription(sub.id, seen_listing_ids=[r["id"] for r in seed])
    except Exception:
        pass

    await cb.message.edit_text(f"✅ Подписка #{sub.id} создана.")
    await cb.message.answer("Смотри в 📋 Мои подписки.", reply_markup=main_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "cs:cancel")
async def on_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    d = await state.get_data()
    edit_id = d.get("edit_sub_id")
    await state.clear()
    if edit_id:
        from app.handlers.subscriptions.detail import show_detail
        await show_detail(cb, int(edit_id))
        return
    if cb.message is not None:
        try:
            await cb.message.edit_text("❌ Создание отменено.")
        except TelegramBadRequest:
            pass
    await cb.answer()

@router.callback_query(F.data == "cs:search_once")
async def on_search_once(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.from_user is None or cb.message is None:
        await cb.answer()
        return
    d = await state.get_data()
    u = cb.from_user
    await get_or_create_user(u.id, username=u.username, first_name=u.first_name)

    from app.data.cars_full import BRAND_IDS, MODEL_IDS
    from app.services.parsers.avby import search as avby_search

    brand = d.get("brand")
    model = d.get("model")
    brand_id = BRAND_IDS.get(brand) if brand else None
    model_id = None
    if brand_id and model:
        model_id = (MODEL_IDS.get(brand) or {}).get(model)

    criteria = {
        "brand_id": brand_id,
        "model_id": model_id,
        "year_from": d.get("year_from"),
        "year_to": d.get("year_to"),
        "price_from": d.get("price_from"),
        "price_to": d.get("price_to"),
        "query": None if brand_id else (f"{brand or ''} {model or ''}".strip() or None),
    }
    await state.clear()
    await cb.message.edit_text("🔍 Ищу на av.by…")
    try:
        results = await avby_search(criteria, limit=100)
    except Exception as e:
        await cb.message.edit_text(f"❌ Ошибка поиска: {e}")
        await cb.answer()
        return
    if not results:
        await cb.message.edit_text("😔 Ничего не найдено. Попробуй смягчить критерии.")
        await cb.answer()
        return

    from app.handlers.subscriptions import find as find_mod
    await find_mod._render_search_results(cb, results, d)
    await cb.answer()
