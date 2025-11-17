from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message

from ..keyboards.common import (
    cancel_keyboard,
    car_uploaded_keyboard,
    confirm_generation_keyboard,
    menu_keyboard,
    post_result_keyboard,
    shop_keyboard,
)
from ..services import user_service
from ..services.ai_service import get_ai_service
from ..services.video_service import get_video_service
from ..states.fitting import FittingStates
from ..utils.media import default_banner, step1_banner, step2_banner
from ..utils.storage import build_upload_path, read_upload_bytes

VIDEO_CREDIT_COST = 3

router = Router(name="fitting")
logger = logging.getLogger(__name__)


async def _send_main_menu(message: Message, user_id: int) -> None:
    """Return user to the main menu with banner and balance info."""
    user = await user_service.get_user(user_id)
    balance_display = "∞" if user and user.is_admin else str(user.balance if user else 0)
    await message.answer_photo(
        photo=default_banner(),
        caption=(
            "🏁 Главное меню Hype Tuning\n"
            f"Твой баланс: {balance_display} генераций\n\n"
            "Хочешь вдохновения? Загляни в наш Telegram: @hypetuning"
        ),
        reply_markup=menu_keyboard(),
    )


@router.message(F.text == "❌ Отмена")
async def global_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено. Возвращаю тебя в меню.")
    await _send_main_menu(message, message.from_user.id)
    await state.set_state(FittingStates.menu)


@router.message(F.text == "🎬 Видео-пролёт")
async def generate_video_flyby(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    image_bytes = read_upload_bytes(user_id, "result")

    if not image_bytes:
        await message.answer(
            "Пока нет свежей примерки. Сначала сгенерируй изображение с новыми дисками."
        )
        return

    user = await user_service.get_user(user_id)
    if not user:
        user, _ = await user_service.get_or_create_user(user_id, message.from_user.username)

    if not user.is_admin:
        if user.balance < VIDEO_CREDIT_COST:
            await message.answer(
                f"Для видео-пролёта нужно {VIDEO_CREDIT_COST} генерации. Пополни баланс и попробуй снова.",
                reply_markup=shop_keyboard(),
            )
            await state.set_state(FittingStates.shop)
            return

        deducted = await user_service.deduct_credit(user_id, amount=VIDEO_CREDIT_COST)
        if not deducted:
            await message.answer(
                "Не удалось списать генерации для видео. Пополни баланс и попробуй снова.",
                reply_markup=shop_keyboard(),
            )
            await state.set_state(FittingStates.shop)
            return

    await message.answer(
        f"🎬 Запускаю видео-пролёт — списываю {VIDEO_CREDIT_COST} генерации. Дай мне ~20 секунд."
    )
    await state.set_state(FittingStates.video_generating)

    video_service = get_video_service()

    try:
        video_bytes = await video_service.generate(image_bytes)
    except Exception as exc:  # pragma: no cover - external API errors
        logger.exception("Video generation failed: %s", exc)
        if not user.is_admin:
            await user_service.add_credits(user_id, VIDEO_CREDIT_COST)
        await message.answer(
            "Не удалось сделать видео. Попробуй позже или обнови результат примерки — списанные генерации уже вернул."
        )
        await state.set_state(FittingStates.menu)
        return

    video_path = build_upload_path(user_id, "video")
    video_path.write_bytes(video_bytes)

    output_video = BufferedInputFile(video_bytes, filename="hype_tuning_flyby.mp4")
    await message.answer_video(output_video, caption="Видео-пролёт готов! 🎬")

    updated_user = await user_service.get_user(user_id)
    balance_display = "∞" if updated_user and updated_user.is_admin else str(updated_user.balance if updated_user else 0)

    await message.answer(
        f"Осталось: {balance_display} генераций. Делись видео с друзьями или запускай новую примерку.",
        reply_markup=post_result_keyboard(),
    )
    await state.set_state(FittingStates.menu)


@router.message(FittingStates.wait_car_photo, F.photo)
async def handle_car_photo(message: Message, state: FSMContext) -> None:
    file_id = message.photo[-1].file_id
    upload_path = build_upload_path(message.from_user.id, "car")
    await message.bot.download(file=file_id, destination=str(upload_path))
    await state.update_data(
        car_photo_file_id=file_id,
        car_photo_path=str(upload_path),
    )
    await message.answer_photo(
        photo=step2_banner(),
        caption=(
            "🛞 Шаг 2 из 2\nПришли фото дисков фронтально, при хорошем свете."
        ),
        reply_markup=car_uploaded_keyboard(),
    )
    await state.set_state(FittingStates.wait_wheel_photo)


@router.message(FittingStates.wait_car_photo)
async def handle_invalid_car(message: Message) -> None:
    await message.answer("Пришли, пожалуйста, фотографию в формате изображения.", reply_markup=cancel_keyboard())


@router.message(FittingStates.wait_wheel_photo, F.photo)
async def handle_wheel_photo(message: Message, state: FSMContext) -> None:
    file_id = message.photo[-1].file_id
    upload_path = build_upload_path(message.from_user.id, "wheel")
    await message.bot.download(file=file_id, destination=str(upload_path))
    await state.update_data(
        wheel_photo_file_id=file_id,
        wheel_photo_path=str(upload_path),
    )
    await message.answer(
        "Всё готово ✅\nСписываем 1 генерацию и запускаем примерку?",
        reply_markup=confirm_generation_keyboard(),
    )
    await state.set_state(FittingStates.confirm_generation)


@router.message(FittingStates.wait_wheel_photo, F.text == "↩️ Изменить фото авто")
async def change_car_photo(message: Message, state: FSMContext) -> None:
    await state.set_state(FittingStates.wait_car_photo)
    await message.answer_photo(
        photo=step1_banner(),
        caption=(
            "📸 Шаг 1 из 2\nПришли фото своего авто (лучше боковой ракурс, без бликов)."
        ),
        reply_markup=cancel_keyboard(),
    )


@router.message(FittingStates.wait_wheel_photo)
async def handle_invalid_wheel(message: Message) -> None:
    await message.answer("Пришли, пожалуйста, фото дисков или воспользуйся кнопками ниже.")


@router.message(FittingStates.confirm_generation, F.text == "🔁 Заменить фото авто")
async def confirm_change_car(message: Message, state: FSMContext) -> None:
    await state.set_state(FittingStates.wait_car_photo)
    await message.answer_photo(
        photo=step1_banner(),
        caption=(
            "📸 Шаг 1 из 2\nПришли фото своего авто (лучше боковой ракурс, без бликов)."
        ),
        reply_markup=cancel_keyboard(),
    )


@router.message(FittingStates.confirm_generation, F.text == "🔁 Заменить фото дисков")
async def confirm_change_wheels(message: Message, state: FSMContext) -> None:
    await state.set_state(FittingStates.wait_wheel_photo)
    await message.answer_photo(
        photo=step2_banner(),
        caption=(
            "🛞 Шаг 2 из 2\nПришли фото дисков фронтально, при хорошем свете."
        ),
        reply_markup=car_uploaded_keyboard(),
    )


@router.message(FittingStates.confirm_generation, F.text == "✅ Запустить")
async def launch_generation(message: Message, state: FSMContext) -> None:
    user = await user_service.get_user(message.from_user.id)
    if not user:
        user, _ = await user_service.get_or_create_user(message.from_user.id, message.from_user.username)

    if not user.is_admin and user.balance <= 0:
        await message.answer(
            "Недостаточно генераций. Пополни баланс через магазин.",
            reply_markup=shop_keyboard(),
        )
        await state.set_state(FittingStates.shop)
        return

    success = await user_service.deduct_credit(message.from_user.id)
    if not success:
        await message.answer("Не удалось списать генерацию. Попробуй позже или пополни баланс.")
        await _send_main_menu(message, message.from_user.id)
        await state.set_state(FittingStates.menu)
        return

    data = await state.get_data()
    car_id = data.get("car_photo_file_id")
    wheel_id = data.get("wheel_photo_file_id")

    if not car_id or not wheel_id:
        await message.answer("Фото не нашёл. Начни примерку заново.")
        await _send_main_menu(message, message.from_user.id)
        await state.set_state(FittingStates.menu)
        return

    await message.answer("🎨 Генерирую результат... Дай мне ~15 секунд.")
    await state.set_state(FittingStates.generating)

    async def _load_photo_bytes(kind: str, file_id: str, path_key: str) -> bytes | None:
        path_value = data.get(path_key)
        if path_value:
            path = Path(path_value)
            if path.exists():
                return path.read_bytes()

        cached_bytes = read_upload_bytes(message.from_user.id, kind)  # noqa: FBT003
        if cached_bytes is not None:
            return cached_bytes

        buffer = BytesIO()
        await message.bot.download(file=file_id, destination=buffer)
        photo_bytes = buffer.getvalue()
        upload_path = build_upload_path(message.from_user.id, kind)
        upload_path.write_bytes(photo_bytes)
        await state.update_data(**{path_key: str(upload_path)})
        return photo_bytes

    car_bytes = await _load_photo_bytes("car", car_id, "car_photo_path")
    wheel_bytes = await _load_photo_bytes("wheel", wheel_id, "wheel_photo_path")

    if not car_bytes or not wheel_bytes:
        await message.answer("Не удалось обработать фото. Пришли их ещё раз, пожалуйста.")
        await _send_main_menu(message, message.from_user.id)
        await state.set_state(FittingStates.menu)
        return

    ai_service = get_ai_service()
    try:
        result_bytes = await ai_service.generate(
            car_photo=car_bytes,
            wheel_photo=wheel_bytes,
        )
    except Exception as exc:  # pragma: no cover - network/AI failure handling
        logger.exception("AI generation failed: %s", exc)
        await message.answer(
            "К сожалению, не удалось получить результат. Я верну генерацию в ближайшее время."
        )
        await _send_main_menu(message, message.from_user.id)
        await user_service.add_credits(message.from_user.id, 1)
        await state.set_state(FittingStates.menu)
        return

    result_path = build_upload_path(message.from_user.id, "result")
    result_path.write_bytes(result_bytes)
    await state.update_data(result_photo_path=str(result_path))

    video_path = build_upload_path(message.from_user.id, "video")
    if video_path.exists():
        video_path.unlink(missing_ok=True)

    output_file = BufferedInputFile(result_bytes, filename="hype_tuning_result.jpg")
    await message.answer_photo(output_file)

    user = await user_service.get_user(message.from_user.id)
    balance_display = "∞" if user and user.is_admin else str(user.balance if user else 0)
    await message.answer(
        "Готово! Вот примерка с новыми дисками 🚘\n"
        f"Осталось: {balance_display} генераций.\n"
        "Сохрани результат, покажи друзьям — пусть оценят!\n"
        f"Нужно видео? Жми «🎬 Видео-пролёт» — списывает {VIDEO_CREDIT_COST} генерации за кинематографичный облет.",
        reply_markup=post_result_keyboard(),
    )

    await state.set_state(FittingStates.menu)
