from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError

from ..keyboards.common import start_keyboard, menu_keyboard, subscription_keyboard
from ..services import user_service
from ..states.fitting import FittingStates
from ..utils.media import default_banner, intro_video
from bot.config import get_settings

logger = logging.getLogger(__name__)

router = Router(name="start")
_settings = get_settings()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    user = await user_service.get_user(message.from_user.id)

    if not await _has_required_subscription(message.bot, message.from_user.id):
        await _prompt_subscription(message)
        await state.set_state(FittingStates.start)
        return

    if not user:
        user, created = await user_service.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
    else:
        created = False

    await send_post_start_screen(message, user, created)
    await state.set_state(FittingStates.menu)


@router.callback_query(F.data == "subscription:check")
async def verify_subscription(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings.required_channel:
        await callback.answer("Подписка не требуется.", show_alert=True)
        return

    user = await user_service.get_user(callback.from_user.id)
    if not await _has_required_subscription(callback.bot, callback.from_user.id):
        await callback.answer("Не вижу подписку на канал 😅", show_alert=True)
        return

    user = await user_service.get_user(callback.from_user.id)
    if not user:
        user, created = await user_service.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        if callback.message:
            await send_post_start_screen(callback.message, user, created)
        await callback.answer("Спасибо! Бонус начислен 🎁", show_alert=False)
    else:
        if callback.message:
            await send_post_start_screen(callback.message, user, created=False)
        await callback.answer("Отлично! Продолжаем 🚀", show_alert=False)
    await state.set_state(FittingStates.menu)


async def _send_landing_message(message: Message, caption: str, reply_markup) -> None:
    video = intro_video()
    if video:
        await message.answer_video(video=video, caption=caption, reply_markup=reply_markup)
    else:
        await message.answer_photo(photo=default_banner(), caption=caption, reply_markup=reply_markup)


async def send_post_start_screen(message: Message, user, created: bool) -> None:
    if created and not user.is_admin:
        await _send_landing_message(
            message,
            caption=(
                "Привет! 👋 Это Hypetuning — бот, который примеряет диски на твою машину с помощью ИИ.\n"
                "Дарю 1 бесплатную генерацию, чтобы ты протестил сервис.\n\n"
                "Что есть в меню:\n"
                "• Примерка — загружаешь фото авто и дисков, бот совмещает их.\n"
                "• Магазин — докупить генерации.\n"
                "• Помощь и Поддержка — подсказки и связь с нами.\n\n"
                "Жми «Примерка» и загружай фото машины."
            ),
            reply_markup=start_keyboard(),
        )
    else:
        balance_display = "∞" if user.is_admin else str(user.balance)
        await _send_landing_message(
            message,
            caption=(
                "🏁 Главное меню Hypetuning\n"
                f"Баланс: {balance_display} генераций.\n\n"
                "• Примерка — новая генерация.\n"
                "• Магазин — пополнить баланс.\n"
                "• Помощь — инструкции.\n"
                "• Поддержка — написать нам.\n\n"
                "Нужен референс? Подписывайся на @hypetuning."
            ),
            reply_markup=menu_keyboard(),
        )


def _channel_label() -> str:
    if not _settings.required_channel:
        return ""
    channel = _settings.required_channel
    if channel.startswith("@"):
        return channel
    return f"@{channel}"


def _channel_link() -> str | None:
    if _settings.required_channel_link:
        return _settings.required_channel_link
    channel = _settings.required_channel
    if channel.startswith("@"):
        channel = channel[1:]
    if channel:
        return f"https://t.me/{channel}"
    return None


async def _prompt_subscription(message: Message) -> None:
    if not _settings.required_channel:
        return
    channel_text = _channel_label()
    if channel_text:
        text = (
            "Чтобы получить бесплатную генерацию, подпишись на наш канал "
            f"{channel_text} и нажми «Я подписался»."
        )
    else:
        text = "Чтобы получить бесплатную генерацию, подпишись на наш канал и нажми «Я подписался»."
    await message.answer(
        text,
        reply_markup=subscription_keyboard(_channel_link()),
    )


async def _has_required_subscription(bot, user_id: int) -> bool:
    if not _settings.required_channel:
        return True
    try:
        member = await bot.get_chat_member(_settings.required_channel, user_id)
    except TelegramAPIError as err:
        logger.warning("Failed to check subscription for %s: %s", user_id, err)
        return False

    status = getattr(member, "status", None)
    return status not in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
