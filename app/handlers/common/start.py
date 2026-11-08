from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.db.repositories.users import get_or_create_user
from app.keyboards.main_menu import BTN_HELP, BTN_SEARCH, main_menu_kb

router = Router(name="common_start")

HELP_TEXT = (
    "📖 <b>Как пользоваться</b>\n\n"
    "• 🔍 <b>Разовый поиск</b> — задать критерии и получить ссылки сейчас\n"
    "• ⏳ <b>Долгий поиск</b> — подписка: пришлю новые объявления\n"
    "• 📋 <b>Мои подписки</b> — список и управление\n\n"
    "Команды: /start /help /menu"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    u = message.from_user
    if u is None:
        return
    await get_or_create_user(u.id, username=u.username, first_name=u.first_name)
    name = u.first_name or "друг"
    await message.answer(
        f"👋 Привет, {name}!\n\n"
        "Помогу найти авто на av.by и других площадках.\n"
        "Выбери действие:",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb())


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer("Меню:", reply_markup=main_menu_kb())


@router.message(F.text == BTN_HELP)
async def btn_help(message: Message) -> None:
    await cmd_help(message)


@router.message(F.text == BTN_SEARCH)
async def btn_search(message: Message) -> None:
    await message.answer("🔍 Разовый поиск — в разработке (D-6).")