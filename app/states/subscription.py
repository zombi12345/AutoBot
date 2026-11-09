from aiogram.fsm.state import State, StatesGroup


class CreateSubscription(StatesGroup):
    source = State()
    brand = State()
    model = State()
    year_from = State()
    year_to = State()
    price_from = State()
    price_to = State()
    confirm = State()
    manual_brand = State()
    manual_model = State()
    manual_year_from = State()
    manual_year_to = State()
    manual_price_from = State()
    manual_price_to = State()
    confirm_brand = State()
    confirm_model = State()

class AISearch(StatesGroup):
    awaiting = State()