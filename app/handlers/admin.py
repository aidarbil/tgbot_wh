from __future__ import annotations

from typing import Optional

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..services import user_service

router = Router(name="admin")


async def _is_admin(user_id: int) -> bool:
    user = await user_service.get_user(user_id)
    return bool(user and user.is_admin)


@router.message(Command("stats"))
async def admin_stats(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        return

    stats = await user_service.get_stats()
    await message.answer(
        "📊 Статистика\n"
        f"Пользователей: {stats['users']}\n"
        f"Успешных оплат: {stats['payments']}\n"
        f"Выдано генераций (оплаченных): {stats['credited_generations']}",
    )


@router.message(Command("users"))
async def admin_users(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        return

    users = await user_service.list_users(limit=20)
    if not users:
        await message.answer("Пользователей нет.")
        return

    lines = [
        "👥 Пользователи:" ,
    ]
    for user in users:
        username = f"@{user.username}" if user.username else "(нет username)"
        balance = "∞" if user.is_admin else str(user.balance)
        lines.append(f"• {username} — id {user.telegram_id}, баланс {balance}")

    await message.answer("\n".join(lines))


@router.message(Command("addcredits"))
async def admin_addcredits(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /addcredits <telegram_id> <количество>")
        return

    try:
        target_id = int(parts[1])
        credits = int(parts[2])
    except ValueError:
        await message.answer("ID и количество должны быть числами.")
        return

    user = await user_service.add_credits(target_id, credits)
    if not user:
        await message.answer("Пользователь не найден.")
        return

    balance = "∞" if user.is_admin else str(user.balance)
    await message.answer(f"Баланс пользователя {target_id} теперь {balance}.")


@router.message(Command("broadcast"))
async def admin_broadcast(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        return

    text = message.text.split(maxsplit=1)
    if len(text) != 2:
        await message.answer("Использование: /broadcast <сообщение>")
        return

    broadcast_text = text[1]
    users = await user_service.list_users(limit=1000)
    sent = 0
    failed = 0
    for user in users:
        try:
            await message.bot.send_message(user.telegram_id, broadcast_text)
            sent += 1
        except Exception:  # pragma: no cover - network errors
            failed += 1

    await message.answer(f"Рассылка завершена. Успешно: {sent}, ошибок: {failed}.")
