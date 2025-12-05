from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from ..keyboards.common import cancel_keyboard, menu_keyboard, shop_keyboard
from ..services import user_service
from ..states.fitting import FittingStates
from ..utils.media import default_banner, step1_banner

router = Router(name="menu")
_settings = get_settings()


@router.callback_query(F.data == "menu:back")
async def callback_back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    user = await user_service.get_user(callback.from_user.id)
    balance_display = "∞" if user and user.is_admin else str(user.balance if user else 0)
    if callback.message:
        await callback.message.answer_photo(
            photo=default_banner(),
            caption=(
                "🏁 Главное меню Hypetuning\n"
                f"Твой баланс: {balance_display} генераций\n\n"
                "Хочешь вдохновения? Загляни в наш Telegram: @hypetuning"
            ),
            reply_markup=menu_keyboard(),
        )
    await callback.answer()
    await state.set_state(FittingStates.menu)


@router.message(F.text == "🏠 В меню")
async def back_to_menu(message: Message, state: FSMContext) -> None:
    user = await user_service.get_user(message.from_user.id)
    balance_display = "∞" if user and user.is_admin else str(user.balance if user else 0)
    await message.answer_photo(
        photo=default_banner(),
        caption=(
            "🏁 Главное меню Hypetuning\n"
            f"Твой баланс: {balance_display} генераций\n\n"
            "Хочешь вдохновения? Загляни в наш Telegram: @hypetuning"
        ),
        reply_markup=menu_keyboard(),
    )
    await state.set_state(FittingStates.menu)


@router.message(F.text == "🚗 Использовать бесплатную примерку")
async def start_free_trial(message: Message, state: FSMContext) -> None:
    await start_fitting_flow(message, state)


@router.message(F.text == "🔁 Новая примерка")
async def repeat_fitting(message: Message, state: FSMContext) -> None:
    await start_fitting_flow(message, state)


@router.message(F.text == "🚗 Примерка")
async def start_fitting_flow(message: Message, state: FSMContext) -> None:
    user = await user_service.get_user(message.from_user.id)
    if not user:
        user, _ = await user_service.get_or_create_user(message.from_user.id, message.from_user.username)

    if not user.is_admin and user.balance <= 0:
        await message.answer(
            "У тебя закончились генерации 😔\nЧтобы продолжить, выбери пакет:",
            reply_markup=shop_keyboard(),
        )
        await state.set_state(FittingStates.shop)
        return

    await message.answer_photo(
        photo=step1_banner(),
        caption=(
            "📸 Шаг 1 из 2\nПришли фото своего авто (лучше боковой ракурс, без бликов).\n"
            "ℹ️ Результат создаёт нейросеть — возможны небольшие отличия от оригинала."
        ),
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(FittingStates.wait_car_photo)


@router.message(F.text == "💳 Купить генерации")
async def show_shop(message: Message, state: FSMContext) -> None:
    await message.answer("Выбери подходящий пакет:", reply_markup=shop_keyboard())
    await state.set_state(FittingStates.shop)


@router.message(F.text == "ℹ️ Помощь")
async def show_help(message: Message, state: FSMContext) -> None:
    await message.answer(
        "ℹ️ Как работает Hypetuning\n"
        "1. Пополни баланс генераций.\n"
        "2. Пришли фото авто и дисков.\n"
        "3. Забери результат примерки за ~15 секунд.\n"
        "🎬 Видео-пролёт списывает 3 генерации.\n"
        "Советы: авто ¾ сбоку, диски фронтально, без бликов.",
    )
    await state.set_state(FittingStates.help)


@router.message(F.text == "🛟 Поддержка")
async def show_support(message: Message, state: FSMContext) -> None:
    await message.answer_photo(
        photo=default_banner(),
        caption=(
            "🛟 Если что-то пошло не так — напиши админу:\n"
            f"👉 {_settings.support_contact}"
        ),
    )
    await state.set_state(FittingStates.support)
