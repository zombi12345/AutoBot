from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.data.cars_full import BRAND_NAMES, BRANDS, BRAND_IDS, MODEL_IDS
from app.services.ai.parser import parse_query
from app.states.subscription import AISearch
from app.utils.fuzzy import find_brand, find_model

router = Router(name="search_ai")

BTN_AI = "🤖 Умный поиск"

LABELS = [("brand","Марка"),("model","Модель"),("year_from","Год от"),("year_to","Год до"),
          ("price_from","Цена от"),("price_to","Цена до"),("fuel_type","Топливо"),
          ("transmission","КПП"),("body_type","Кузов"),("mileage_to","Пробег до"),
          ("engine_cc_from","Объём от"),("engine_cc_to","Объём до")]

FUEL_RU = {"gasoline":"бензин","diesel":"дизель","hybrid":"гибрид","electric":"электро","gas":"газ"}
TRANS_RU = {"automatic":"автомат","manual":"механика","variator":"вариатор","robot":"робот"}


# Индекс модели → объём (L): glk350 → 3.5, c200 → 2.0, e220 → 2.2 и т.п.
# Работает для тех, где цифры = объём (Mercedes, Audi, BMW редко).
_MODEL_ENGINE_HINT = {
    "180": 1.8, "200": 2.0, "220": 2.2, "230": 2.3, "250": 2.5,
    "280": 2.8, "300": 3.0, "320": 3.2, "350": 3.5, "400": 4.0,
    "420": 4.2, "450": 4.5, "500": 5.0, "550": 5.5, "600": 6.0,
    "320": 3.2, "280": 2.8, "200": 2.0, "180": 1.8,
}


def _extract_engine_from_model(model_raw: str) -> tuple[str, int | None, int | None]:
    """'glk350' -> ('glk', 3400, 3600); 'c200' -> ('c', 1900, 2100);
    'e220' -> ('e', 2100, 2300); 'x5' -> ('x5', None, None) (не объём).
    """
    if not model_raw:
        return model_raw, None, None
    import re as _re
    s = str(model_raw).strip().lower().replace(" ", "")
    m = _re.match(r"^([a-zа-я]+)(\d{2,3})$", s)
    if not m:
        return model_raw, None, None
    base, digits = m.group(1), m.group(2)
    # digits должны быть из словаря объёмов
    engine_l = _MODEL_ENGINE_HINT.get(digits)
    if engine_l is None:
        return model_raw, None, None
    cc = int(engine_l * 1000)
    return base, cc - 100, cc + 100


def _normalize_parsed(parsed: dict) -> dict:
    """Мерседес -> Mercedes-Benz, glk350 -> GLK + engine_cc 3400-3600."""
    out = dict(parsed)

    # 1. brand
    brand_raw = out.get("brand")
    if brand_raw:
        canon, _ = find_brand(brand_raw, BRAND_NAMES)
        if canon:
            out["brand"] = canon

    # 2. model: вытащить engine_cc из цифр в конце (glk350)
    model_raw = out.get("model")
    if model_raw:
        base, cc_from, cc_to = _extract_engine_from_model(model_raw)
        if cc_from is not None and cc_to is not None:
            # объём найден — сохраняем если ещё нет
            if not out.get("engine_cc_from"):
                out["engine_cc_from"] = cc_from
            if not out.get("engine_cc_to"):
                out["engine_cc_to"] = cc_to
            # модель — базовое имя (glk, c, e) → fuzzy ниже
            model_raw = base

    # 3. fuzzy по модели (с приоритетом точного/класс-матча)
    brand = out.get("brand")
    if model_raw and brand and brand in BRANDS:
        models_list = BRANDS[brand]
        base_l = str(model_raw).strip().lower()
        chosen = None

        # 3a. если вытащили объём — base="c"/"e"/"s"/"glk" — ищем "X-Класс" или точное
        if out.get("engine_cc_from"):
            # точное совпадение: GLK == glk
            for m in models_list:
                if m.lower() == base_l:
                    chosen = m
                    break
            # base + "-класс" (C-Класс)
            if chosen is None:
                for m in models_list:
                    if m.lower().startswith(base_l + "-"):
                        chosen = m
                        break
            # base + " класс" (без дефиса)
            if chosen is None:
                for m in models_list:
                    if m.lower().startswith(base_l + " "):
                        chosen = m
                        break

        # 3b. обычный fuzzy
        if chosen is None:
            canon_m, _ = find_model(model_raw, models_list)
            chosen = canon_m

        out["model"] = chosen if chosen else model_raw
    return out


def _format_labels(parsed: dict) -> list[str]:
    lines = []
    for k, lbl in LABELS:
        v = parsed.get(k)
        if v is None:
            disp = "—"
        elif k == "fuel_type":
            disp = FUEL_RU.get(v, v)
        elif k == "transmission":
            disp = TRANS_RU.get(v, v)
        elif k in ("price_from","price_to"):
            disp = f"${v}"
        elif k == "mileage_to":
            disp = f"{v:,} км".replace(",", " ")
        elif k in ("engine_cc_from","engine_cc_to"):
            disp = f"{v} см³"
        else:
            disp = str(v)
        lines.append(f"• {lbl}: <b>{disp}</b>")
    return lines


def _criteria_from_parsed(parsed: dict) -> dict:
    brand = parsed.get("brand")
    model = parsed.get("model")
    brand_id = BRAND_IDS.get(brand) if brand else None
    model_id = None
    if brand_id and model:
        model_id = (MODEL_IDS.get(brand) or {}).get(model)
    return {
        "brand_id": brand_id,
        "model_id": model_id,
        "brand": brand,
        "model": model,
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


@router.message(F.text == BTN_AI)
async def start_ai(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AISearch.awaiting)
    await message.answer(
        "🤖 <b>Умный поиск</b>\n\n"
        "Опиши машину своими словами.\n"
        "Пример: <i>BMW X5 2019-2023 дизель автомат до 40000, пробег до 120к</i>\n\n"
        "/cancel — отмена"
    )


@router.message(StateFilter(AISearch.awaiting), F.text)
async def on_ai_query(message: Message, state: FSMContext) -> None:
    txt = (message.text or "").strip()
    if not txt or txt.startswith("/"):
        return
    if len(txt) < 3:
        await message.answer("Опиши подробнее.")
        return

    await message.answer("🤖 Разбираю…")
    parsed = await parse_query(txt)
    if not any(parsed.values()):
        await message.answer("⚠️ Не смог разобрать. Опиши подробнее: марка, модель, год, цена.")
        return

    # fuzzy-нормализация
    parsed = _normalize_parsed(parsed)

    lines = ["📋 <b>Вот что я понял:</b>", ""] + _format_labels(parsed) + ["", "Всё верно?"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Искать / Сохранить", callback_data="ai:ok")],
        [InlineKeyboardButton(text="✏️ Заново", callback_data="ai:retry")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="ai:cancel")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)
    sort_mil = ("пробег" in txt.lower() and ("наимень" in txt.lower() or "меньш" in txt.lower() or "min" in txt.lower()))
    await state.update_data(ai_parsed=parsed, ai_raw=txt, sort_by_mileage=sort_mil)


@router.message(StateFilter(AISearch.awaiting), F.text.startswith("/cancel"))
async def ai_cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Отменено")


@router.callback_query(F.data == "ai:cancel")
async def ai_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if cb.message:
        await cb.message.edit_text("❌ Отменено")
    await cb.answer()


@router.callback_query(F.data == "ai:retry")
async def ai_retry(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AISearch.awaiting)
    await state.update_data(ai_parsed=None)
    if cb.message:
        await cb.message.edit_text("✏️ Напиши запрос заново.")
    await cb.answer()


@router.callback_query(F.data == "ai:ok")
async def ai_ok(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.message is None or cb.from_user is None:
        await cb.answer()
        return
    d = await state.get_data()
    parsed = d.get("ai_parsed") or {}
    if not any(parsed.values()):
        await cb.message.edit_text("⚠️ Не разобрал. Опиши подробнее.")
        await cb.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇧🇾 Av.by — искать", callback_data="ai:search:avby"),
         InlineKeyboardButton(text="🇧🇾 Kufar — искать", callback_data="ai:search:kufar")],
        [InlineKeyboardButton(text="⏳ Av.by — подписка", callback_data="ai:save:avby"),
         InlineKeyboardButton(text="⏳ Kufar — подписка", callback_data="ai:save:kufar")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="ai:cancel")],
    ])
    await cb.message.edit_text("Что сделать с критериями?", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("ai:search"))
async def ai_search(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.message is None or cb.from_user is None:
        await cb.answer()
        return
    src = cb.data.split(":")[2] if len(cb.data.split(":")) >= 3 else "avby"
    d = await state.get_data()
    parsed = d.get("ai_parsed") or {}
    await state.clear()

    from app.services.parsers import search as source_search
    from app.handlers.subscriptions import find as find_mod

    criteria = _criteria_from_parsed(parsed)
    await cb.message.edit_text("🔍 Ищу на av.by…")
    try:
        results = await source_search(src, criteria, limit=100)
    except Exception as e:
        await cb.message.edit_text(f"❌ Ошибка поиска: {e}")
        await cb.answer()
        return
    if not results:
        await cb.message.edit_text(
            "😔 Ничего не найдено по этим критериям.\n\n"
            "Попробуй смягчить: убрать цену, расширить годы."
        )
        await cb.answer()
        return
    sort_by_mileage = d.get("sort_by_mileage", False)
    await find_mod._render_search_results(cb, results, parsed, sort_by_mileage=sort_by_mileage)
    await cb.answer()


@router.callback_query(F.data.startswith("ai:save"))
async def ai_save(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.message is None or cb.from_user is None:
        await cb.answer()
        return
    src = cb.data.split(":")[2] if len(cb.data.split(":")) >= 3 else "avby"
    d = await state.get_data()
    parsed = d.get("ai_parsed") or {}
    raw = d.get("ai_raw") or ""
    await state.clear()

    if not any(parsed.get(k) for k in ("brand", "model", "year_from", "year_to", "price_to")):
        await cb.message.edit_text("⚠️ Не понял критериев. Опиши подробнее.")
        await cb.answer()
        return

    from app.db.repositories.subscriptions import create_subscription
    from app.db.repositories.users import get_or_create_user
    from app.keyboards.main_menu import main_menu_kb

    u = cb.from_user
    user = await get_or_create_user(u.id, username=u.username, first_name=u.first_name)
    sub = await create_subscription(
        user_id=user.id,
        source=src,
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
    parts = []
    if parsed.get("brand"):
        parts.append(parsed["brand"])
    if parsed.get("model"):
        parts.append(parsed["model"])
    label = " ".join(parts) or f"#{sub.id}"
    await cb.message.edit_text(f"✅ Подписка #{sub.id} создана: <b>{label}</b>")
    await cb.message.answer("Смотри в 📋 Мои подписки.", reply_markup=main_menu_kb())
    await cb.answer()