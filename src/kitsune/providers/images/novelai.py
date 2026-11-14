"""NovelAI image generation (via the maintained ``novelai-sdk`` package)."""

from __future__ import annotations

import io
import random
from typing import Any, List, Optional

from ...errors import ImageError

DEFAULT_NEGATIVE = (
    "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, cropped, "
    "worst quality, jpeg artifacts, signature, watermark"
)


class NovelAIImages:
    def __init__(
        self, token: str, *, model: str = "nai-diffusion-4-5-full", size: str = "portrait", client: Any = None
    ) -> None:
        if not token and client is None:
            raise ImageError("a NovelAI token is required for images")
        self.token = token
        self.model = model
        self.size = size
        self._client = client

    def _sdk(self) -> Any:
        if self._client is None:
            from novelai import AsyncNovelAI

            self._client = AsyncNovelAI(api_key=self.token)
        return self._client

    def params(self, prompt: str, *, negative: str = "", seed: Optional[int] = None) -> Any:
        from novelai.types import GenerateImageParams

        return GenerateImageParams(
            prompt=prompt,
            model=self.model,
            size=self.size,
            negative_prompt=negative or DEFAULT_NEGATIVE,
            seed=seed if seed is not None else random.randint(0, 2**32 - 1),
        )

    async def generate(self, prompt: str, *, negative: str = "", seed: Optional[int] = None) -> List[bytes]:
        try:
            images = await self._sdk().image.generate(self.params(prompt, negative=negative, seed=seed))
        except Exception as e:  # the SDK raises its own exception types
            raise ImageError(str(e) or e.__class__.__name__) from e
        out = []
        for im in images:
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            out.append(buf.getvalue())
        return out

    async def aclose(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if close is not None:
                res = close()
                if hasattr(res, "__await__"):
                    await res
