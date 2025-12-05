from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict

from yookassa import Configuration, Payment

from bot.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


def _format_amount(amount_in_minor_units: int) -> str:
    value = (Decimal(amount_in_minor_units) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{value:.2f}"


@dataclass(slots=True)
class CreatedPayment:
    payment_id: str
    confirmation_url: str
    status: str
    idempotence_key: str
    metadata: Dict[str, Any]


class YooKassaService:
    def __init__(self) -> None:
        if not _settings.yookassa_shop_id or not _settings.yookassa_secret_key:
            raise RuntimeError("YooKassa credentials are not configured")
        Configuration.account_id = _settings.yookassa_shop_id
        Configuration.secret_key = _settings.yookassa_secret_key

    def _build_receipt(
        self,
        *,
        amount_minor: int,
        description: str,
        customer: dict[str, str] | None,
    ) -> dict[str, Any]:
        if not customer:
            raise RuntimeError("YOOKASSA_RECEIPT_EMAIL is not configured")
        email = customer.get("email")
        if not email:
            raise RuntimeError("YOOKASSA_RECEIPT_EMAIL is not configured")
        item = {
            "description": description[:128],
            "quantity": "1.00",
            "amount": {
                "value": _format_amount(amount_minor),
                "currency": _settings.payments_currency,
            },
            "vat_code": _settings.yookassa_receipt_vat_code,
            "payment_mode": "full_payment",
            "payment_subject": "service",
        }
        receipt: dict[str, Any] = {
            "customer": {
                "full_name": customer.get("full_name", "")[:256],
                "email": email,
            },
            "items": [item],
        }
        if _settings.yookassa_tax_system_code:
            receipt["tax_system_code"] = _settings.yookassa_tax_system_code
        return receipt

    async def create_payment(
        self,
        *,
        amount: int,
        description: str,
        metadata: Dict[str, Any],
        receipt_customer: dict[str, str] | None = None,
    ) -> CreatedPayment:
        if not _settings.yookassa_return_url:
            raise RuntimeError("YOOKASSA_RETURN_URL is not configured")
        payload = {
            "amount": {
                "value": _format_amount(amount),
                "currency": _settings.payments_currency,
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": _settings.yookassa_return_url,
            },
            "description": description,
            "metadata": metadata,
        }
        if _settings.yookassa_send_receipt:
            payload["receipt"] = self._build_receipt(
                amount_minor=amount,
                description=description,
                customer=receipt_customer,
            )
        idempotence_key = str(uuid.uuid4())

        payment = await asyncio.to_thread(Payment.create, payload, idempotency_key=idempotence_key)
        confirmation_url = getattr(getattr(payment, "confirmation", None), "confirmation_url", None)
        if not confirmation_url:
            raise RuntimeError("YooKassa did not return a confirmation URL")

        return CreatedPayment(
            payment_id=payment.id,
            confirmation_url=confirmation_url,
            status=payment.status,
            idempotence_key=idempotence_key,
            metadata=metadata,
        )

    async def get_payment(self, payment_id: str):  # pragma: no cover - depends on YooKassa SDK
        return await asyncio.to_thread(Payment.find_one, payment_id)


_service: YooKassaService | None = None


def get_yookassa_service() -> YooKassaService:
    global _service
    if _service is None:
        _service = YooKassaService()
    return _service
