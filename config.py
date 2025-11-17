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
    database_url: str
    ai_provider: str
    fal_api_key: str
    admin_ids: List[int]
    support_contact: str
    free_credits: int = 1
    payments_currency: str = "RUB"

    @property
    def payment_packages(self) -> List[PaymentPackage]:
        return [
            PaymentPackage(name="1 генерация", amount=19900, credits=1, label="one"),
            PaymentPackage(name="3 генерации 💎", amount=29900, credits=3, label="three"),
            PaymentPackage(name="5 генераций", amount=39900, credits=5, label="five"),
            PaymentPackage(name="10 генераций", amount=49900, credits=10, label="ten"),
        ]


@lru_cache()
def get_settings() -> Settings:
    raw_admins = os.getenv("ADMIN_IDS", "")
    admin_ids = [int(admin.strip()) for admin in raw_admins.split(",") if admin.strip()]

    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        provider_token=os.getenv("PAYMENT_PROVIDER_TOKEN", ""),
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db"),
        ai_provider=os.getenv("AI_PROVIDER", "gemini"),
        fal_api_key=os.getenv("FAL_API_KEY", os.getenv("AI_API_KEY", "")),
        admin_ids=admin_ids,
        support_contact=os.getenv("SUPPORT_CONTACT", "@username"),
        free_credits=int(os.getenv("FREE_CREDITS", "1")),
    )
