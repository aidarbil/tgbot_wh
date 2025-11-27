# Hypetuning Telegram Bot

Telegram-бот для примерки автомобильных дисков с использованием нейросети, оплатой через ЮKassa и учётом генераций.

## Возможности
- Регистрация пользователя с бонусной генерацией.
- Главное меню с балансом и переходами в примерку, магазин, помощь и поддержку.
- FSM из 8 состояний для примерки, магазина и вспомогательных экранов.
- Загрузка фото авто и дисков, обращение к AI API для комбинирования изображений.
- Учёт баланса генераций и бесконечный доступ для админов.
- Оплата пакетов генераций через Telegram Payments (ЮKassa).
- Админ-команды `/stats`, `/users`, `/addcredits`, `/broadcast`.

## Быстрый старт
1. **Python**: убедитесь, что установлена версия 3.10+.
2. **Установите зависимости**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Настройте переменные окружения**:
   ```bash
   cp .env.example .env
   ```
   Заполните значения: токен бота, provider_token ЮKassa (выдаёт @BotFather), API-ключ AI и т.д.
4. **Запустите бота вручную** (long polling):
   ```bash
   python bot/manage_bot.py start
   ```
   Проверить статус либо остановить, когда нужно:
   ```bash
   python bot/manage_bot.py status
   python bot/manage_bot.py stop
   ```
5. **Хостинг**: для production используйте VPS c Ubuntu 22+, настройте systemd или Supervisor и при необходимости webhook с HTTPS.

## Управление процессом
- `python bot/manage_bot.py start` — запустить бота и записать PID в `bot/bot.pid`.
- `python bot/manage_bot.py stop` — остановить текущий процесс (при необходимости с `--force`).
- `python bot/manage_bot.py status` — проверить, запущен ли бот.
- `python bot/manage_bot.py restart` — перезапустить бота одной командой.

## Конфигурация
- `BOT_TOKEN` — токен из @BotFather.
- `PAYMENT_PROVIDER_TOKEN` — токен ЮKassa, подключенный в BotFather.
- `DATABASE_URL` — строка подключения SQLAlchemy. Пример для PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/dbname`.
- `AI_PROVIDER` — `gemini`, `chatgpt` или `nanobanana`. При отсутствии ключа возвращается заглушка (оригинальное фото авто).
- `FAL_API_KEY` — API-ключ платформы fal.ai для моделей семейства Nano Banana.
- `ADMIN_IDS` — список Telegram ID через запятую. Админам доступен бесконечный баланс и команды.
- `SUPPORT_CONTACT` — контакт поддержки, отображается пользователям.
- `FREE_CREDITS` — количество генераций при регистрации.
- `REQUIRED_CHANNEL` / `REQUIRED_CHANNEL_LINK` — канал, на который пользователь обязан подписаться, и ссылка на него; без подписки приветственный бонус не выдаётся.

## Архитектура
```
bot/
├── main.py              # Точка входа
├── config.py            # Загрузка настроек
├── app/
│   ├── database.py      # Async SQLAlchemy engine + session
│   ├── models/          # User, Payment
│   ├── handlers/        # Start, меню, примерка, оплаты, админ
│   ├── keyboards/       # Reply/inline клавиатуры
│   ├── services/        # Пользователи, платежи, интеграция с AI
│   └── states/          # FSM состояния
├── requirements.txt
└── README.md
```

## Интеграция AI
Файл `app/services/ai_service.py` содержит обёртку для Gemini и OpenAI. Для production замените заглушку на реальную загрузку ключей и обработку ответов API. При ошибке генерации пользователю возвращается генерация на баланс.

## Платежи
- Inline-кнопки магазина вызывают `sendInvoice` с нужным тарифом.
- `PreCheckoutQuery` подтверждается автоматически (при необходимости можно добавить проверки).
- `SuccessfulPayment` увеличивает баланс, лог записывается в таблицу `payments`.

## Администрирование
- `/stats` — общая статистика пользователей и оплат.
- `/users` — последние пользователи с балансами.
- `/addcredits <telegram_id> <n>` — ручное изменение баланса.
- `/broadcast <текст>` — рассылка сообщения всем пользователям (без учёта ошибок блокировки).

## TODO / улучшения
- Добавить миграции (alembic) для продакшена.
- Реализовать кеширование изображений в S3/Cloud Storage.
- Расширить обработку ошибок AI и платежей.
- Настроить хранение логов в отдельном файле (`bot.log`).
