from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from bot.config import get_settings
from ..keyboards.common import menu_keyboard, payment_link_keyboard, payment_success_keyboard
from ..services import payment_service, user_service
from ..services.yookassa_service import get_yookassa_service
from ..states.fitting import FittingStates

router = Router(name="payments")
_settings = get_settings()
logger = logging.getLogger(__name__)


def _find_package(label: str):
    for package in _settings.payment_packages:
        if package.label == label:
            return package
    return None


def _build_receipt_customer(callback: CallbackQuery) -> dict[str, str] | None:
    if not _settings.yookassa_send_receipt:
        return None
    full_name = (
        callback.from_user.full_name
        or callback.from_user.username
        or f"Telegram user {callback.from_user.id}"
    )
    email = _settings.yookassa_receipt_email
    if callback.from_user.username:
        email = f"{callback.from_user.username}@telegram.me"
    if not email:
        email = f"{callback.from_user.id}@telegram.local"
    return {
        "full_name": full_name[:256],
        "email": email,
    }


@router.callback_query(F.data.startswith("shop:"))
async def select_package(callback: CallbackQuery, state: FSMContext) -> None:
    label = callback.data.split(":", maxsplit=1)[1]
    package = _find_package(label)
    if not package:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    if _settings.use_yookassa:
        await _create_yookassa_payment(callback, state, package)
    else:
        await _create_telegram_invoice(callback, state, package)


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout: PreCheckoutQuery) -> None:
    await pre_checkout.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, state: FSMContext) -> None:
    payment = message.successful_payment
    payload = payment.invoice_payload

    try:
        _, label, credits_str = payload.split(":")
        credits = int(credits_str)
    except (ValueError, AttributeError):
        await message.answer("Не удалось обработать платёж.", reply_markup=menu_keyboard())
        await state.set_state(FittingStates.menu)
        return

    package = _find_package(label)
    if not package:
        await message.answer("Тариф не найден.", reply_markup=menu_keyboard())
        await state.set_state(FittingStates.menu)
        return

    await user_service.add_credits(message.from_user.id, credits)
    await payment_service.record_payment(
        telegram_id=message.from_user.id,
        amount=payment.total_amount,
        credits=credits,
        package_label=label,
        payment_id=payment.provider_payment_charge_id or payment.telegram_payment_charge_id,
        status="succeeded",
    )

    updated_user = await user_service.get_user(message.from_user.id)
    await _send_success_reply(message, credits, updated_user)
    await state.set_state(FittingStates.menu)


@router.callback_query(F.data.startswith("payment:check:"))
async def check_payment_status(callback: CallbackQuery, state: FSMContext) -> None:
    if not _settings.use_yookassa:
        await callback.answer("Платёж проверяется автоматически", show_alert=True)
        return

    _, _, payment_id = callback.data.partition("payment:check:")
    if not payment_id:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    await _inspect_yookassa_payment(callback, state, payment_id)


async def _create_telegram_invoice(callback: CallbackQuery, state: FSMContext, package) -> None:
    if not _settings.provider_token:
        await callback.answer("Платёжный провайдер не настроен", show_alert=True)
        return

    prices = [LabeledPrice(label=package.name, amount=package.amount)]
    payload = f"pkg:{package.label}:{package.credits}"

    if callback.message:
        await callback.message.answer_invoice(
            title=package.name,
            description="Пакет генераций для примерки дисков.",
            payload=payload,
            provider_token=_settings.provider_token,
            currency=_settings.payments_currency,
            prices=prices,
        )
    await callback.answer()
    await state.set_state(FittingStates.shop)


async def _create_yookassa_payment(callback: CallbackQuery, state: FSMContext, package) -> None:
    try:
        service = get_yookassa_service()
    except RuntimeError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    metadata = {
        "telegram_id": callback.from_user.id,
        "package_label": package.label,
        "credits": package.credits,
    }

    receipt_customer = _build_receipt_customer(callback)
    if _settings.yookassa_send_receipt and not receipt_customer:
        await callback.answer("Не настроен email для чеков YooKassa. Обратись в поддержку.", show_alert=True)
        return

    try:
        created_payment = await service.create_payment(
            amount=package.amount,
            description=f"Пакет генераций Hypetuning: {package.name}",
            metadata=metadata,
            receipt_customer=receipt_customer,
        )
    except Exception as exc:  # pragma: no cover - network interaction
        logger.exception("YooKassa create_payment failed: %s", exc)
        await callback.answer("Не удалось создать платёж. Попробуй позже.", show_alert=True)
        return

    user = await user_service.get_user(callback.from_user.id)
    if not user:
        await user_service.get_or_create_user(callback.from_user.id, callback.from_user.username)

    await payment_service.record_payment(
        telegram_id=callback.from_user.id,
        amount=package.amount,
        credits=package.credits,
        package_label=package.label,
        payment_id=created_payment.payment_id,
        status=created_payment.status,
        provider="yookassa",
        payment_link=created_payment.confirmation_url,
        idempotence_key=created_payment.idempotence_key,
        metadata=metadata,
    )

    if callback.message:
        await callback.message.answer(
            "Ссылка на оплату готова. Перейди по кнопке, а после оплаты нажми «✅ Проверить оплату».",
            reply_markup=payment_link_keyboard(created_payment.confirmation_url, created_payment.payment_id),
        )
    await callback.answer()
    await state.set_state(FittingStates.shop)


async def _inspect_yookassa_payment(callback: CallbackQuery, state: FSMContext, payment_id: str) -> None:
    payment_record = await payment_service.get_payment(payment_id)
    if not payment_record:
        await callback.answer("Платёж не найден. Попробуй создать его заново.", show_alert=True)
        return

    if payment_record.status == "succeeded":
        if callback.message:
            updated_user = await user_service.get_user(callback.from_user.id)
            await _send_success_reply(callback.message, payment_record.credits, updated_user)
        await state.set_state(FittingStates.menu)
        await callback.answer("Оплата уже зачислена.")
        return

    try:
        service = get_yookassa_service()
        payment = await service.get_payment(payment_id)
    except Exception as exc:  # pragma: no cover - network interaction
        logger.exception("YooKassa payment fetch failed: %s", exc)
        await callback.answer("Не удалось проверить статус. Попробуй позже.", show_alert=True)
        return

    status = getattr(payment, "status", "pending")
    metadata = getattr(payment, "metadata", None) or {}
    amount_minor = _amount_to_minor_units(getattr(payment, "amount", None)) or payment_record.amount
    paid_at = _parse_iso_datetime(getattr(payment, "paid_at", None)) or _parse_iso_datetime(getattr(payment, "captured_at", None))

    previous_status = payment_record.status
    await payment_service.record_payment(
        telegram_id=callback.from_user.id,
        amount=amount_minor,
        credits=int(metadata.get("credits", payment_record.credits)),
        package_label=metadata.get("package_label", payment_record.package),
        payment_id=payment_id,
        status=status,
        provider="yookassa",
        payment_link=payment_record.payment_link,
        idempotence_key=payment_record.idempotence_key,
        metadata=metadata,
        paid_at=paid_at,
    )

    if status == "succeeded" and previous_status != "succeeded":
        credits = int(metadata.get("credits", payment_record.credits))
        await user_service.add_credits(callback.from_user.id, credits)
        updated_user = await user_service.get_user(callback.from_user.id)
        if callback.message:
            await _send_success_reply(callback.message, credits, updated_user)
        await state.set_state(FittingStates.menu)
        await callback.answer("Оплата подтверждена!", show_alert=False)
    elif status in {"pending", "waiting_for_capture"}:
        await callback.answer("Платёж ещё обрабатывается в YooKassa. Попробуй чуть позже.", show_alert=True)
    else:
        await callback.answer(f"Текущий статус платежа: {status}", show_alert=True)


async def _send_success_reply(message: Message, credits: int, user) -> None:
    balance_display = "∞" if user and getattr(user, "is_admin", False) else str(user.balance if user else 0)
    await message.answer(
        "✅ Оплата прошла!\n"
        f"Баланс пополнен на {credits} генераций.\n"
        f"Твой текущий баланс: {balance_display}.",
        reply_markup=payment_success_keyboard(),
    )


def _amount_to_minor_units(amount) -> int:
    if not amount:
        return 0
    value = getattr(amount, "value", None)
    if value is None and isinstance(amount, dict):
        value = amount.get("value")
    return _decimal_to_minor(value)


def _decimal_to_minor(value) -> int:
    if value is None:
        return 0
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return 0
    minor_units = (decimal_value * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(minor_units)


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
