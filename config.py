from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
import os


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


@dataclass
class PaymentPackage:
    name: str
    amount: int  # amount in the smallest currency unit (kopeks)
    credits: int
    label: str


@dataclass
class Settings:
    bot_token: str
    provider_token: str
    payments_provider: str
    database_url: str
    ai_provider: str
    fal_api_key: str
    admin_ids: List[int]
    support_contact: str
    free_credits: int = 1
    payments_currency: str = "RUB"
    required_channel: str = ""
    required_channel_link: str = ""
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    yookassa_return_url: str = ""
    yookassa_webhook_secret: str = ""
    yookassa_send_receipt: bool = False
    yookassa_tax_system_code: int | None = None
    yookassa_receipt_vat_code: int = 1
    yookassa_receipt_email: str = ""
    webhook_host: str = "127.0.0.1"
    webhook_port: int = 8080

    @property
    def payment_packages(self) -> List[PaymentPackage]:
        return [
            PaymentPackage(name="1 генерация", amount=19900, credits=1, label="one"),
            PaymentPackage(name="3 генерации 💎", amount=29900, credits=3, label="three"),
            PaymentPackage(name="5 генераций", amount=39900, credits=5, label="five"),
            PaymentPackage(name="10 генераций", amount=49900, credits=10, label="ten"),
        ]

    @property
    def use_yookassa(self) -> bool:
        return self.payments_provider == "yookassa"


@lru_cache()
def get_settings() -> Settings:
    raw_admins = os.getenv("ADMIN_IDS", "")
    admin_ids = [int(admin.strip()) for admin in raw_admins.split(",") if admin.strip()]

    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        provider_token=os.getenv("PAYMENT_PROVIDER_TOKEN", ""),
        payments_provider=os.getenv("PAYMENTS_PROVIDER", "telegram").lower(),
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db"),
        ai_provider=os.getenv("AI_PROVIDER", "gemini"),
        fal_api_key=os.getenv("FAL_API_KEY", os.getenv("AI_API_KEY", "")),
        admin_ids=admin_ids,
        support_contact=os.getenv("SUPPORT_CONTACT", "@username"),
        free_credits=int(os.getenv("FREE_CREDITS", "1")),
        required_channel=os.getenv("REQUIRED_CHANNEL", ""),
        required_channel_link=os.getenv("REQUIRED_CHANNEL_LINK", ""),
        yookassa_shop_id=os.getenv("YOOKASSA_SHOP_ID", ""),
        yookassa_secret_key=os.getenv("YOOKASSA_SECRET_KEY", ""),
        yookassa_return_url=os.getenv("YOOKASSA_RETURN_URL", ""),
        yookassa_webhook_secret=os.getenv("YOOKASSA_WEBHOOK_SECRET", ""),
        yookassa_send_receipt=os.getenv("YOOKASSA_SEND_RECEIPT", "false").lower() in {"1", "true", "yes"},
        yookassa_tax_system_code=int(os.getenv("YOOKASSA_TAX_SYSTEM_CODE")) if os.getenv("YOOKASSA_TAX_SYSTEM_CODE") else None,
        yookassa_receipt_vat_code=int(os.getenv("YOOKASSA_RECEIPT_VAT_CODE", "1")),
        yookassa_receipt_email=os.getenv("YOOKASSA_RECEIPT_EMAIL", ""),
        webhook_host=os.getenv("WEBHOOK_HOST", "127.0.0.1"),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "8080")),
    )
