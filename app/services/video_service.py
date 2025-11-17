from __future__ import annotations

import base64
import logging
from typing import Optional

import aiohttp

from bot.config import get_settings

logger = logging.getLogger(__name__)

_SETTINGS = get_settings()

DEFAULT_VIDEO_PROMPT = (
    "###Instruction###\nYou are a photorealistic image-to-video model.\n\n###Input Reference###\n- The provided image shows the same custom car in two halves divided by a thin neon-green horizontal line.\n- The top half is a 3/4 front view, the bottom half is a side profile.\n- Both halves share the same body color, lighting and custom wheels — treat them as one real vehicle.\n\n###Task###\n- Reconstruct the full 3D car based on both views.\n- Produce a cinematic drone fly-around that lasts roughly five seconds.\n- Start near the front 3/4 view, orbit smoothly around the car at door height, and finish near the starting angle.\n- Keep the car centered, maintain realistic lighting, reflections, wheel design and motion blur.\n- The background should stay coherent with the lighting seen in the reference image, but avoid duplicating the split layout.\n\n###Output###\nDeliver a single 5-second MP4 that looks like a stabilized drone performing a 360° orbit of the car."
)


class VideoService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        resolution: str = "720p",
        duration: str = "5",
    ) -> None:
        self.api_key = api_key or _SETTINGS.fal_api_key
        self.endpoint = "https://fal.run/fal-ai/wan-25-preview/image-to-video"
        self.resolution = resolution
        self.duration = duration

    async def generate(self, image_bytes: bytes, prompt: Optional[str] = None) -> bytes:
        if not self.api_key:
            logger.error("FAL API key not configured; aborting video generation")
            raise RuntimeError("FAL API key not configured")

        payload = {
            "prompt": prompt or DEFAULT_VIDEO_PROMPT,
            "image_url": self._to_data_uri(image_bytes),
            "resolution": self.resolution,
            "duration": self.duration,
            "enable_safety_checker": True,
            "enable_prompt_expansion": True,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Key {self.api_key}",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.endpoint, json=payload, headers=headers, timeout=600) as response:
                response.raise_for_status()
                data = await response.json()

            try:
                video_url = data["video"]["url"]
            except (KeyError, TypeError) as exc:
                logger.error("Unexpected Wan Pro response: %s", data)
                raise RuntimeError("Failed to parse Wan Pro response") from exc

            async with session.get(video_url, timeout=600) as video_response:
                video_response.raise_for_status()
                return await video_response.read()

    @staticmethod
    def _to_data_uri(image: bytes) -> str:
        encoded = base64.b64encode(image).decode()
        mime = "image/png" if image.startswith(b"\x89PNG") else "image/jpeg"
        return f"data:{mime};base64,{encoded}"


def get_video_service() -> VideoService:
    return VideoService()
