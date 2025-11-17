from aiogram.fsm.state import State, StatesGroup


class FittingStates(StatesGroup):
    start = State()
    menu = State()
    wait_car_photo = State()
    wait_wheel_photo = State()
    confirm_generation = State()
    generating = State()
    video_generating = State()
    shop = State()
    help = State()
    support = State()
