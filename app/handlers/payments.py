from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from bot.config import get_settings
from ..keyboards.common import menu_keyboard, payment_success_keyboard
from ..services import payment_service, user_service
from ..states.fitting import FittingStates

router = Router(name="payments")
_settings = get_settings()


def _find_package(label: str):
    for package in _settings.payment_packages:
        if package.label == label:
            return package
    return None


@router.callback_query(F.data.startswith("shop:"))
async def select_package(callback: CallbackQuery, state: FSMContext) -> None:
    label = callback.data.split(":", maxsplit=1)[1]
    package = _find_package(label)
    if not package:
        await callback.answer("Тариф не найден", show_alert=True)
        return

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
    balance_display = "∞" if updated_user and updated_user.is_admin else str(updated_user.balance if updated_user else 0)

    await message.answer(
        "✅ Оплата прошла!\n"
        f"Баланс пополнен на {credits} генераций.\n"
        f"Твой текущий баланс: {balance_display}.",
        reply_markup=payment_success_keyboard(),
    )
    await state.set_state(FittingStates.menu)
