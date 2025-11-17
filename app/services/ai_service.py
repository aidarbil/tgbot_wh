from __future__ import annotations

import base64
import logging
from typing import Optional

import aiohttp

from bot.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

GENERATION_REQUEST_TIMEOUT = 180
GENERATION_DOWNLOAD_TIMEOUT = 240


GENERATION_PROMPT = """You receive exactly two inline images for editing.
Image A (inline image 1): the full car with the OLD rims installed.
Image B (inline image 2): the NEW rim design that must replace every rim on the car.

OVERALL GOAL:
Render a single photorealistic image that shows two copies of my car:
- Left copy: 3/4 front perspective.
- Right copy: pure side/profile perspective.
Both copies must feature only the NEW rim from Image B. There can be no trace of the old rims anywhere in the output.

RIM REPLACEMENT WORKFLOW:
1. Locate every wheel in Image A, including rims and tire sidewalls.
2. Remove 100 percent of each old rim and the surrounding tire details. Any leftover pixel from the old wheel counts as a failure.
3. Use Image B as the exact blueprint for the NEW rim. Apply it to every wheel:
   - Match spoke structure, center cap, material, and color precisely.
   - Adjust perspective for each viewpoint (3/4 and side) so the rim sits naturally.
   - Reconstruct the tire around the new rim so proportions remain realistic.
4. Blend seamlessly. No doubling, ghost edges, or partial remnants of the previous rim are allowed. If old rim details persist, redo the replacement.
5. Ensure every visible wheel uses the NEW rim. The final composition must never mix old and new designs.

SCENE AND COMPOSITION:
- Place both cars together on a realistic ground plane with soft daylight reflections.
- Use the Moscow City skyline in neutral daylight as the background.
- Keep both cars identical aside from their viewing angle.
- Cast consistent, natural shadows and reflections that match a single light direction.

LICENSE PLATE SPECIFICATION:
- Display the text "HypeTuning.ru" on both cars' plates.
- Plates must appear physically mounted and respect bumper curvature and lighting.

LIGHTING AND MATERIAL CONTINUITY:
- Match exposure, color tone, and paint reflections to Image A.
- Do not alter paint color, body shape, or ride height.
- Ensure the new rims share the same lighting conditions and reflective qualities as the rest of the car.

STRICT PROHIBITIONS:
- Never keep, partially show, or blend old rim details.
- Do not modify the bodywork, color, or suspension of the car.
- Do not change the environment beyond the described Moscow City scene.
- Do not apply filters, stylization, or duplicate the same camera angle twice.

EXPECTED RESULT:
Deliver one high-quality photorealistic composite where:
- Left car = 3/4 front view equipped with the new rims.
- Right car = side view equipped with the new rims.
- Lighting, reflections, and materials match across both cars.
- There is absolutely zero evidence of the old rims anywhere in the image."""


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
        endpoint = "https://fal.run/fal-ai/nano-banana/edit"

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
            "output_format": "jpeg",
            "aspect_ratio": "16:9",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Key {self.api_key}",
        }

        async with aiohttp.ClientSession() as session:
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


def get_ai_service() -> AIService:
    return AIService()
