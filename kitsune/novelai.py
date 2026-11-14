"""NovelAI: text-to-speech and image generation."""

from __future__ import annotations

import asyncio
import io
import random
from typing import List, Optional

import httpx

API = "https://api.novelai.net"


class NovelAIError(RuntimeError):
    pass


class NovelAI:
    def __init__(self, token: str, *, voice_seed: str = "Aini", image_model: str = "nai-diffusion-4-5-full",
                 image_size: str = "portrait", timeout: float = 120.0) -> None:
        if not token:
            raise NovelAIError("NOVELAI_TOKEN is not set (get a persistent API token in NovelAI's account settings)")
        self.token = token
        self.voice_seed = voice_seed
        self.image_model = image_model
        self.image_size = image_size
        self.http = httpx.AsyncClient(timeout=timeout, headers={"Authorization": f"Bearer {token}"})
        self._images = None

    # -- text to speech ---------------------------------------------------------------------------------
    async def tts(self, text: str, *, seed: Optional[str] = None) -> bytes:
        """Speak ``text`` with TTS v2; returns MP3 bytes. NovelAI cuts text at 1000 characters."""
        body = {"text": text[:1000], "seed": seed or self.voice_seed, "voice": -1, "opus": False, "version": "v2"}
        r = await self.http.post(f"{API}/ai/generate-voice", json=body)
        if r.status_code >= 400:
            raise NovelAIError(f"TTS failed ({r.status_code}): {r.text[:200]}")
        return r.content

    # -- images -------------------------------------------------------------------------------------------
    def _client(self):
        if self._images is None:
            from novelai import AsyncNovelAI

            self._images = AsyncNovelAI(api_key=self.token)
        return self._images

    async def image(self, prompt: str, *, negative: str = "", size: Optional[str] = None,
                    seed: Optional[int] = None) -> List[bytes]:
        """Generate an anime image from Danbooru-style tags; returns PNG bytes."""
        from novelai.types import GenerateImageParams

        params = GenerateImageParams(prompt=prompt, model=self.image_model, size=size or self.image_size,
                                     negative_prompt=negative or None,
                                     seed=seed if seed is not None else random.randint(0, 2**32 - 1))
        try:
            images = await self._client().image.generate(params)
        except Exception as e:
            raise NovelAIError(f"image generation failed: {e}") from e
        out = []
        for im in images:
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            out.append(buf.getvalue())
        return out

    async def close(self) -> None:
        await self.http.aclose()
        if self._images is not None:
            close = getattr(self._images, "close", None) or getattr(self._images, "aclose", None)
            if close:
                res = close()
                if asyncio.iscoroutine(res):
                    await res
