from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_SEARCH = "🔍 Разовый поиск"
BTN_LONG_SEARCH = "⏳ Долгий поиск"
BTN_AI = "🤖 Умный поиск"
BTN_MY_SUBS = "📋 Мои подписки"
BTN_HELP = "ℹ️ Помощь"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SEARCH), KeyboardButton(text=BTN_LONG_SEARCH)],
            [KeyboardButton(text=BTN_AI), KeyboardButton(text=BTN_MY_SUBS)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие или напиши запрос",
    )