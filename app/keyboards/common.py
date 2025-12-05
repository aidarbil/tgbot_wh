from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def start_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚗 Использовать бесплатную примерку")
    builder.button(text="💳 Купить генерации")
    builder.button(text="ℹ️ Помощь")
    builder.button(text="🛟 Поддержка")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚗 Примерка")
    builder.button(text="💳 Купить генерации")
    builder.button(text="ℹ️ Помощь")
    builder.button(text="🛟 Поддержка")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def car_uploaded_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="↩️ Изменить фото авто")
    builder.button(text="❌ Отмена")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def confirm_generation_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="✅ Запустить")
    builder.button(text="🔁 Заменить фото авто")
    builder.button(text="🔁 Заменить фото дисков")
    builder.button(text="❌ Отмена")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def post_result_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🎬 Видео-пролёт")
    builder.button(text="🔁 Новая примерка")
    builder.button(text="💳 Купить генерации")
    builder.button(text="🏠 В меню")
    builder.adjust(1, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def shop_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="1 генерация — 199₽", callback_data="shop:one")
    builder.button(text="3 генерации 💎 — 299₽", callback_data="shop:three")
    builder.button(text="5 генераций — 399₽", callback_data="shop:five")
    builder.button(text="10 генераций — 499₽", callback_data="shop:ten")
    builder.button(text="🏠 В меню", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


def payment_success_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚗 Примерка")
    builder.button(text="🏠 В меню")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def payment_link_keyboard(payment_url: str, payment_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить", url=payment_url)
    builder.button(text="✅ Проверить оплату", callback_data=f"payment:check:{payment_id}")
    builder.button(text="🏠 В меню", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


def subscription_keyboard(channel_url: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if channel_url:
        builder.button(text="🔥 Подписаться", url=channel_url)
    builder.button(text="✅ Я подписался", callback_data="subscription:check")
    builder.adjust(1)
    return builder.as_markup()
