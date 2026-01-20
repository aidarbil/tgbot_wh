from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.app.database import create_db_and_tables
from bot.app.handlers import admin, fitting, menu, payments, start
from bot.app.webhooks.server import start_webhook_server
from bot.utils.loop import PipeEventLoopPolicy

logger = logging.getLogger(__name__)


async def main() -> None:
    logs_dir = Path(__file__).resolve().parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "bot.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    logger.info("Bot startup initiated")
    settings = get_settings()

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not configured")

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(fitting.router)
    dp.include_router(payments.router)
    dp.include_router(admin.router)

    logger.info("Creating database and tables if needed")
    await create_db_and_tables()

    logger.info("Launching webhook server (YooKassa) if enabled")
    webhook_runner = await start_webhook_server()
    try:
        logger.info("Starting polling")
        await dp.start_polling(bot)
    finally:
        if webhook_runner:
            logger.info("Stopping webhook server")
            await webhook_runner.cleanup()


if __name__ == "__main__":
    asyncio.set_event_loop_policy(PipeEventLoopPolicy())
    asyncio.run(main())
