from aiogram import F, Router
from aiogram.types import Message

from app.db.repositories.subscriptions import list_user_subscriptions
from app.db.repositories.users import get_or_create_user
from app.keyboards.main_menu import BTN_MY_SUBS

router = Router(name="subs_list")


@router.message(F.text == BTN_MY_SUBS)
async def show_my_subs(message: Message) -> None:
    u = message.from_user
    if u is None:
        return
    user = await get_or_create_user(u.id, username=u.username, first_name=u.first_name)
    subs = await list_user_subscriptions(user.id)
    if not subs:
        await message.answer("📋 Подписок пока нет. Нажми ⏳ Долгий поиск, чтобы создать.")
        return
    lines = [f"📋 <b>Твои подписки ({len(subs)}):</b>", ""]
    for s in subs:
        parts: list[str] = []
        if s.brand:
            parts.append(s.brand)
        if s.model:
            parts.append(s.model)
        if s.year_from or s.year_to:
            parts.append(f"{s.year_from or '...'}–{s.year_to or '...'}")
        if s.price_from or s.price_to:
            parts.append(f"${s.price_from or '...'}–${s.price_to or '...'}")
        label = " ".join(parts) if parts else "без критериев"
        lines.append(f"#{s.id} • {label} • <i>{s.status}</i>")
    lines += ["", "Управление (pause/delete) — в D-5."]
    await message.answer("\n".join(lines))