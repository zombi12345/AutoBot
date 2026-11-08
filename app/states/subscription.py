from aiogram.fsm.state import State, StatesGroup


class CreateSubscription(StatesGroup):
    brand = State()
    model = State()
    year_from = State()
    year_to = State()
    price_from = State()
    price_to = State()
    confirm = State()