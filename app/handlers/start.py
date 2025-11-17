from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..keyboards.common import start_keyboard, menu_keyboard
from ..services import user_service
from ..states.fitting import FittingStates
from ..utils.media import default_banner

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    user, created = await user_service.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )

    if created and not user.is_admin:
        await message.answer_photo(
            photo=default_banner(),
            caption=(
                "Привет! 👋 Я бот Hype Tuning и помогу примерить диски на твоё авто.\n"
                "На старте дарю 1 бесплатную примерку 🎁\n"
                "Готов начать? Жми кнопку ниже."
            ),
            reply_markup=start_keyboard(),
        )
    else:
        balance_display = "∞" if user.is_admin else str(user.balance)
        await message.answer_photo(
            photo=default_banner(),
            caption=(
                "🏁 Главное меню Hype Tuning\n"
                f"Твой баланс: {balance_display} генераций\n\n"
                "Хочешь вдохновения? Загляни в наш Telegram: @hypetuning"
            ),
            reply_markup=menu_keyboard(),
        )

    await state.set_state(FittingStates.menu)
