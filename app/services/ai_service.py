from __future__ import annotations

import asyncio
import base64
import logging
from typing import Optional

import aiohttp

from bot.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

GENERATION_REQUEST_TIMEOUT = 240
GENERATION_DOWNLOAD_TIMEOUT = 240
NANOBANANA_RETRIES = 2  # additional attempts after the first try
NANOBANANA_BACKOFF_BASE = 2
GPT_IMAGE15_RETRIES = 2  # additional attempts after the first try
GPT_IMAGE15_BACKOFF_BASE = 2


GENERATION_PROMPT = """Task: Photorealistic rim swap from two photos; новые диски должны быть 1:1 как на фото B, одинаково точные в обеих панелях.
Inputs:
- A: фото авто. Машина, фон, свет, краска, стекла не меняются.
- B: фронтальное фото нового диска. Использовать ровно этот диск без изменений; только металл диска (игнорировать шину/тормоз в B).

Do:
1) Вырезать лицевую часть диска из B; сохранить 1:1: точное число спиц, форма/толщина/изгиб спиц, болтовой круг, центр/лого, финиш/текстура, профиль обода.
2) В A маскировать только металл диска (передний и задний колёса). Не маскировать боковину/протектор шины и кузов.
3) Жёстко удалить старый диск внутри маски (без бленда/инпейнта). Шины и тормоза не трогать.
4) Вставить новый диск из B на каждое колесо; подогнать эллипс/перспективу; совместить центр ступицы, диаметр, вылет, развал, поворот. Исправить дисторсию при необходимости.
5) Окклюзия: ротор/суппорт строго за спицами; без двойных/призрачных спиц, без просвечиваний.
6) Свет: матч освещение/тон из A, сохраняя финиш B; лёгкие тени спиц на ротор; без ореолов у борта/ступицы.

Layout (новые диски с точным числом спиц в обеих панелях):
- 2-panel коллаж, холст 4:3, горизонтальный сплит 50/50, тонкий тёмный разделитель.
- Top: плотный боковой кадр (level side-view) переднего колеса + переднего крыла; колесо ~50–70% кадра; новый диск чётко виден, число спиц и центр точно как в B.
- Bottom: полный уровеньный боковой профиль того же авто; оба колеса с тем же новым диском и тем же числом спиц; старых дисков нет нигде.
- Добавить лаконичную реалистичную вывеску «hypetuning.ru» на здании/фоне за машиной; читабельно, без лишних эффектов.

Must NOT:
- Менять кузов/краску/клиренс/развал/шины/тормоза/фон.
- Придумывать дизайн или менять число/форму/толщину спиц, болтовой круг, центр/лого, финиш.
- Добавлять текст/водяные знаки кроме одной вывески «hypetuning.ru»; без глоу, блюра, фильтров, цветокора.

Negative prompt: low quality, blur, noise, compression artifacts, aliasing, ghost/double spokes, residual old rim, wrong spoke/lug count, wrong spoke shape/thickness, wrong center cap/logo, perspective mismatch, halos at bead/hub, unrealistic reflections, over/underexposure, color cast, CGI look, plastic textures, любые пиксели старого диска в любой панели."""


class AIService:
    """Wrapper for image generation providers.

    The default implementation returns the original car photo if the provider
    is not configured. Replace provider-specific stubs with real API calls
    before production use.
    """

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None) -> None:
        self.api_key = api_key or _settings.fal_api_key
        self.provider = (provider or _settings.ai_provider).lower()

    async def generate(self, car_photo: bytes, wheel_photo: bytes) -> bytes:
        if not self.api_key:
            logger.error("FAL API key not configured; aborting generation")
            raise RuntimeError("FAL API key not configured")

        if self.provider == "gemini":
            return await self._call_gemini(car_photo, wheel_photo)
        if self.provider in {"chatgpt", "openai"}:
            return await self._call_openai(car_photo, wheel_photo)
        if self.provider in {"gpt_image15", "gpt-image-1.5", "gptimage15", "gpt_image_15"}:
            return await self._call_gpt_image15(car_photo, wheel_photo)
        if self.provider in {"nanobanana", "nano-banana", "fal_nanobanana"}:
            return await self._call_nanobanana(car_photo, wheel_photo)

        logger.error("Unknown AI provider '%s'", self.provider)
        raise RuntimeError(f"Unknown AI provider '{self.provider}'")

    async def _call_gemini(self, car_photo: bytes, wheel_photo: bytes) -> bytes:
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": GENERATION_PROMPT},
                        {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(car_photo).decode()}},
                        {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(wheel_photo).decode()}},
                    ]
                }
            ]
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=payload, headers=headers, timeout=60) as response:
                response.raise_for_status()
                data = await response.json()

        try:
            image_data = data["candidates"][0]["content"]["parts"][0]["inline_data"]["data"]
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected Gemini response: %s", data)
            raise RuntimeError("Failed to parse Gemini response") from exc
        return base64.b64decode(image_data)

    async def _call_openai(self, car_photo: bytes, wheel_photo: bytes) -> bytes:
        endpoint = "https://api.openai.com/v1/images/edits"
        form_data = aiohttp.FormData()
        form_data.add_field("prompt", GENERATION_PROMPT)
        form_data.add_field("model", "gpt-image-1")
        form_data.add_field("image[], car", car_photo, filename="car.jpg", content_type="image/jpeg")
        form_data.add_field("mask", wheel_photo, filename="wheels.png", content_type="image/png")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, data=form_data, headers=headers, timeout=60) as response:
                response.raise_for_status()
                data = await response.json()

        try:
            image_data = data["data"][0]["b64_json"]
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected OpenAI response: %s", data)
            raise RuntimeError("Failed to parse OpenAI response") from exc
        return base64.b64decode(image_data)

    async def _call_nanobanana(self, car_photo: bytes, wheel_photo: bytes) -> bytes:
        endpoint = "https://fal.run/fal-ai/nano-banana-pro/edit"

        def _detect_mime(image: bytes) -> str:
            if image.startswith(b"\x89PNG"):
                return "image/png"
            if image.startswith(b"\xff\xd8"):
                return "image/jpeg"
            return "image/jpeg"

        def _to_data_uri(image: bytes) -> str:
            encoded = base64.b64encode(image).decode()
            mime = _detect_mime(image)
            return f"data:{mime};base64,{encoded}"

        payload = {
            "prompt": GENERATION_PROMPT,
            "image_urls": [_to_data_uri(car_photo), _to_data_uri(wheel_photo)],
            "num_images": 1,
            "output_format": "png",
            "aspect_ratio": "4:3",
            "resolution": "1K",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Key {self.api_key}",
        }

        async with aiohttp.ClientSession() as session:
            attempts = NANOBANANA_RETRIES + 1
            for attempt in range(1, attempts + 1):
                try:
                    async with session.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=GENERATION_REQUEST_TIMEOUT,
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()

                    try:
                        image_url = data["images"][0]["url"]
                    except (KeyError, IndexError) as exc:
                        logger.error("Unexpected Nano Banana response: %s", data)
                        raise RuntimeError("Failed to parse Nano Banana response") from exc

                    async with session.get(image_url, timeout=GENERATION_DOWNLOAD_TIMEOUT) as image_response:
                        image_response.raise_for_status()
                        return await image_response.read()
                except asyncio.TimeoutError:
                    if attempt >= attempts:
                        logger.error("Nano Banana request timed out after %s attempts", attempts)
                        raise
                    sleep_for = NANOBANANA_BACKOFF_BASE ** attempt
                    logger.warning(
                        "Nano Banana request timeout (attempt %s/%s). Retrying in %ss",
                        attempt,
                        attempts,
                        sleep_for,
                    )
                    await asyncio.sleep(sleep_for)

    async def _call_gpt_image15(self, car_photo: bytes, wheel_photo: bytes) -> bytes:
        endpoint = "https://fal.run/fal-ai/gpt-image-1.5/edit"

        def _detect_mime(image: bytes) -> str:
            if image.startswith(b"\x89PNG"):
                return "image/png"
            if image.startswith(b"\xff\xd8"):
                return "image/jpeg"
            return "image/jpeg"

        def _to_data_uri(image: bytes) -> str:
            encoded = base64.b64encode(image).decode()
            mime = _detect_mime(image)
            return f"data:{mime};base64,{encoded}"

        payload = {
            "prompt": GENERATION_PROMPT,
            "image_urls": [_to_data_uri(car_photo), _to_data_uri(wheel_photo)],
            "image_size": "auto",
            "background": "auto",
            "quality": "high",
            "input_fidelity": "high",
            "num_images": 1,
            "output_format": "png",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Key {self.api_key}",
        }

        async with aiohttp.ClientSession() as session:
            attempts = GPT_IMAGE15_RETRIES + 1
            for attempt in range(1, attempts + 1):
                try:
                    async with session.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=GENERATION_REQUEST_TIMEOUT,
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()

                    try:
                        image_url = data["images"][0]["url"]
                    except (KeyError, IndexError) as exc:
                        logger.error("Unexpected GPT Image 1.5 response: %s", data)
                        raise RuntimeError("Failed to parse GPT Image 1.5 response") from exc

                    async with session.get(image_url, timeout=GENERATION_DOWNLOAD_TIMEOUT) as image_response:
                        image_response.raise_for_status()
                        return await image_response.read()
                except asyncio.TimeoutError:
                    if attempt >= attempts:
                        logger.error("GPT Image 1.5 request timed out after %s attempts", attempts)
                        raise
                    sleep_for = GPT_IMAGE15_BACKOFF_BASE ** attempt
                    logger.warning(
                        "GPT Image 1.5 request timeout (attempt %s/%s). Retrying in %ss",
                        attempt,
                        attempts,
                        sleep_for,
                    )
                    await asyncio.sleep(sleep_for)


def get_ai_service() -> AIService:
    return AIService()
