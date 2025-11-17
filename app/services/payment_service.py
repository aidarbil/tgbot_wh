from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from ..database import session_factory
from ..models.payment import Payment
from ..models.user import User


async def record_payment(
    *,
    telegram_id: int,
    amount: int,
    credits: int,
    package_label: str,
    payment_id: str,
    status: str,
) -> Payment:
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one()

        result = await session.execute(select(Payment).where(Payment.payment_id == payment_id))
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = status
            payment.amount = amount
            payment.credits = credits
            payment.package = package_label
            return payment

        payment = Payment(
            user_id=user.id,
            amount=amount,
            credits=credits,
            package=package_label,
            payment_id=payment_id,
            status=status,
        )
        session.add(payment)
        await session.flush()
        return payment


async def update_payment_status(payment_id: str, status: str) -> Optional[Payment]:
    async with session_factory() as session:
        result = await session.execute(select(Payment).where(Payment.payment_id == payment_id))
        payment = result.scalar_one_or_none()
        if not payment:
            return None
        payment.status = status
        await session.flush()
        return payment
