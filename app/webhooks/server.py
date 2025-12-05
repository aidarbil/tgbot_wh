from __future__ import annotations

import logging
from typing import Optional

from aiohttp import web

from bot.config import get_settings
from .yookassa import register_yookassa_routes

logger = logging.getLogger(__name__)


async def start_webhook_server() -> Optional[web.AppRunner]:
    settings = get_settings()
    if not settings.use_yookassa:
        return None
    if not settings.yookassa_webhook_secret or not settings.yookassa_shop_id:
        logger.warning("YooKassa webhook credentials are missing; webhook server disabled.")
        return None

    app = web.Application()
    register_yookassa_routes(app)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port)
    await site.start()
    logger.info("Webhook server started on %s:%s", settings.webhook_host, settings.webhook_port)
    return runner
