from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from aiohttp import web

from bot.config import get_settings
from bot.app.services import payment_service, user_service

logger = logging.getLogger(__name__)
_settings = get_settings()

RETURN_PAGE = """<!doctype html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\">
  <title>Hypetuning — YooKassa</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f0f; color: #fff; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
    .card { background: #1c1c1c; padding: 32px; border-radius: 16px; max-width: 420px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.35); }
    .card h1 { margin-top: 0; }
    .card a { color: #4ac1ff; text-decoration: none; }
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>Спасибо!</h1>
    <p>Если оплата прошла, вернись в Telegram и нажми «✅ Проверить оплату» в боте Hypetuning.</p>
    <p>Если окно не закрылось автоматически, просто вернись в приложение Telegram вручную.</p>
  </div>
</body>
</html>"""


def register_yookassa_routes(app: web.Application) -> None:
    app.router.add_post("/yookassa/webhook", handle_webhook)
    app.router.add_get("/yookassa/return", handle_return)


async def handle_return(_: web.Request) -> web.Response:
    return web.Response(text=RETURN_PAGE, content_type="text/html")


async def handle_webhook(request: web.Request) -> web.StreamResponse:
    if not _settings.yookassa_webhook_secret:
        raise web.HTTPForbidden(text="Webhook secret is not configured")

    auth_header = request.headers.get("Authorization", "")
    if not _is_authorized(auth_header):
        raise web.HTTPUnauthorized()

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise web.HTTPBadRequest(text="Invalid JSON")

    event = payload.get("event")
    payment_object = payload.get("object") or {}

    if event in {"payment.succeeded", "payment.waiting_for_capture", "payment.canceled"}:
        await _process_payment_object(payment_object)
    else:
        logger.debug("Ignoring YooKassa event %s", event)

    return web.json_response({"status": "ok"})


def _is_authorized(header: str) -> bool:
    if not header.startswith("Basic "):
        return False
    token = header.split(" ", maxsplit=1)[1]
    expected = base64.b64encode(f"{_settings.yookassa_shop_id}:{_settings.yookassa_webhook_secret}".encode()).decode()
    return token == expected


async def _process_payment_object(obj: dict[str, Any]) -> None:
    payment_id = obj.get("id")
    status = obj.get("status", "pending")
    metadata = obj.get("metadata") or {}
    if not payment_id or "telegram_id" not in metadata:
        logger.warning("Webhook without metadata: %s", obj)
        return

    telegram_id = int(metadata.get("telegram_id"))
    credits = int(metadata.get("credits", 0))
    package_label = metadata.get("package_label", "")
    amount_minor = _amount_to_minor(obj.get("amount"))
    paid_at = _parse_iso_datetime(obj.get("paid_at") or obj.get("captured_at"))

    payment_record = await payment_service.get_payment(payment_id)
    previous_status = payment_record.status if payment_record else None

    await user_service.get_or_create_user(telegram_id, None)
    await payment_service.record_payment(
        telegram_id=telegram_id,
        amount=amount_minor,
        credits=credits,
        package_label=package_label or (payment_record.package if payment_record else "unknown"),
        payment_id=payment_id,
        status=status,
        provider="yookassa",
        payment_link=payment_record.payment_link if payment_record else None,
        idempotence_key=payment_record.idempotence_key if payment_record else None,
        metadata=metadata,
        paid_at=paid_at,
    )

    if status == "succeeded" and previous_status != "succeeded" and credits > 0:
        await user_service.add_credits(telegram_id, credits)
        logger.info("YooKassa payment %s succeeded; %s credits added to %s", payment_id, credits, telegram_id)


def _amount_to_minor(amount: Any) -> int:
    if not amount:
        return 0
    value = None
    if isinstance(amount, dict):
        value = amount.get("value")
    else:
        value = getattr(amount, "value", None)
    return _decimal_to_minor(value)


def _decimal_to_minor(value) -> int:
    if value is None:
        return 0
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return 0
    return int((decimal_value * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
