from __future__ import annotations

from functools import lru_cache

from aiogram.types import BufferedInputFile

from bot.config import BASE_DIR

ASSETS_DIR = BASE_DIR / "app" / "assets"
DEFAULT_BANNER_PATH = BASE_DIR / "lenarst.jpg"
STEP1_BANNER_PATH = ASSETS_DIR / "shag1.png"
STEP2_BANNER_PATH = ASSETS_DIR / "shag2.png"


@lru_cache()
def _banner_bytes() -> bytes:
    return DEFAULT_BANNER_PATH.read_bytes()


def default_banner() -> BufferedInputFile:
    """Return the default banner image for rich messages."""
    return BufferedInputFile(_banner_bytes(), filename="lenarst.jpg")


@lru_cache()
def _step1_banner_bytes() -> bytes:
    return STEP1_BANNER_PATH.read_bytes()


def step1_banner() -> BufferedInputFile:
    """Banner for the first fitting step when requesting the car photo."""
    return BufferedInputFile(_step1_banner_bytes(), filename="step1_banner.png")


@lru_cache()
def _step2_banner_bytes() -> bytes:
    return STEP2_BANNER_PATH.read_bytes()


def step2_banner() -> BufferedInputFile:
    """Banner for the second fitting step when requesting wheel photos."""
    return BufferedInputFile(_step2_banner_bytes(), filename="step2_banner.png")
