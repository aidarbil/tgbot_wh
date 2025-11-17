from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import func, select

from bot.config import get_settings
from ..database import session_factory
from ..models.payment import Payment
from ..models.user import User

_settings = get_settings()


async def get_or_create_user(telegram_id: int, username: Optional[str]) -> Tuple[User, bool]:
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            if username and user.username != username:
                user.username = username
            return user, False

        is_admin = telegram_id in _settings.admin_ids
        starting_balance = 10_000_000 if is_admin else _settings.free_credits
        user = User(
            telegram_id=telegram_id,
            username=username,
            balance=starting_balance,
            is_admin=is_admin,
        )
        session.add(user)
        await session.flush()
        return user, True


async def get_user(telegram_id: int) -> Optional[User]:
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def add_credits(telegram_id: int, credits: int) -> Optional[User]:
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return None
        user.balance += credits
        await session.flush()
        return user


async def deduct_credit(telegram_id: int, amount: int = 1) -> bool:
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return False
        if user.is_admin:
            return True
        if amount <= 0:
            return True
        if user.balance < amount:
            return False
        user.balance -= amount
        await session.flush()
        return True


async def set_balance(telegram_id: int, amount: int) -> Optional[User]:
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return None
        user.balance = amount
        await session.flush()
        return user


async def list_users(limit: int = 50) -> list[User]:
    async with session_factory() as session:
        result = await session.execute(select(User).order_by(User.created_at.desc()).limit(limit))
        return list(result.scalars().all())


async def get_stats() -> dict[str, int]:
    async with session_factory() as session:
        total_users = await session.scalar(select(func.count(User.id))) or 0
        total_payments = await session.scalar(select(func.count(Payment.id))) or 0
        credited_generations = await session.scalar(
            select(func.coalesce(func.sum(Payment.credits), 0)).where(Payment.status == "succeeded")
        ) or 0

    return {
        "users": int(total_users),
        "payments": int(total_payments),
        "credited_generations": int(credited_generations),
    }
